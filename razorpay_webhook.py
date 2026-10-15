
import os
import hmac
import hashlib
import json
import logging
import requests
import psycopg2
from flask import Flask, request, jsonify

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("minibot_webhook")

DATABASE_URL = os.environ.get("DATABASE_URL")
WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET")
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")
SYNC_TOKEN = os.environ.get("MINIBOT_SYNC_TOKEN")

ACTIVE_EVENTS = {
    "subscription.activated",
    "subscription.charged",
    "subscription.resumed",
}

INACTIVE_EVENTS = {
    "subscription.cancelled",
    "subscription.halted",
    "subscription.paused",
    "subscription.completed",
}


def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured.")

    return psycopg2.connect(
        DATABASE_URL,
        connect_timeout=10,
        sslmode="require",
    )


def update_user_subscription(subscription_id, status):
    premium = status == "active"

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE minibot_users
                SET premium = %s,
                    razorpay_status = %s,
                    updated_at = NOW()
                WHERE razorpay_subscription_id = %s
                """,
                (premium, status, subscription_id),
            )
            updated_rows = cursor.rowcount

        connection.commit()
        return updated_rows
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@app.route("/", methods=["GET"])
def health_check():
    return jsonify({
        "service": "MiniBot Razorpay Webhook",
        "status": "running",
    }), 200


@app.route("/razorpay/webhook", methods=["POST"])
def razorpay_webhook():
    if not WEBHOOK_SECRET or not DATABASE_URL:
        return jsonify({"error": "Webhook configuration missing."}), 503

    signature = request.headers.get("X-Razorpay-Signature", "")
    raw_body = request.get_data(cache=True)

    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not signature or not hmac.compare_digest(
        expected_signature, signature
    ):
        return jsonify({"error": "Invalid signature."}), 400

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return jsonify({"error": "Invalid JSON."}), 400

    event = payload.get("event", "")
    if event not in ACTIVE_EVENTS and event not in INACTIVE_EVENTS:
        return jsonify({"status": "ignored", "event": event}), 200

    subscription = (
        payload.get("payload", {})
        .get("subscription", {})
        .get("entity", {})
    )

    subscription_id = subscription.get("id")
    status = subscription.get("status")

    if not subscription_id or not status:
        return jsonify({"error": "Subscription details missing."}), 400

    # Only an active subscription grants Premium.
    if event in INACTIVE_EVENTS:
        status = "inactive"

    try:
        rows = update_user_subscription(subscription_id, status)

        if rows == 0:
            logger.warning("No database user matched subscription %s",
                           subscription_id)
            return jsonify({
                "status": "received",
                "matched_user": False,
            }), 200

        logger.info("Updated subscription %s to %s",
                    subscription_id, status)

        return jsonify({
            "status": "updated",
            "premium": status == "active",
        }), 200

    except Exception:
        logger.exception("Database update failed.")
        return jsonify({"error": "Database update failed."}), 500


# Temporary endpoint for synchronizing an existing subscription.
# Remove this endpoint after completing the one-time sync.
@app.route(
    "/admin/sync/<sync_token>/<subscription_id>",
    methods=["GET"],
)
def sync_existing_subscription(sync_token, subscription_id):
    if not SYNC_TOKEN or not hmac.compare_digest(
        sync_token, SYNC_TOKEN
    ):
        return jsonify({"error": "Unauthorized."}), 401

    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        return jsonify({"error": "Razorpay API credentials missing."}), 503

    try:
        response = requests.get(
            "https://api.razorpay.com/v1/subscriptions/"
            + subscription_id,
            auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET),
            timeout=20,
        )

        if response.status_code != 200:
            logger.warning("Razorpay subscription lookup failed: %s",
                           response.status_code)
            return jsonify({
                "error": "Razorpay could not verify the subscription.",
                "http_status": response.status_code,
            }), 502

        data = response.json()
        verified_id = data.get("id")
        status = data.get("status")

        if verified_id != subscription_id:
            return jsonify({"error": "Subscription ID mismatch."}), 400

        if status not in {
            "created", "authenticated", "active",
            "pending", "halted", "cancelled", "completed",
        }:
            return jsonify({
                "error": "Unexpected subscription status.",
                "status": status,
            }), 400

        rows = update_user_subscription(subscription_id, status)

        if rows == 0:
            return jsonify({
                "status": status,
                "matched_user": False,
                "message": (
                    "Razorpay verified the subscription, but no database "
                    "user has this subscription ID. Premium was not granted."
                ),
            }), 200

        return jsonify({
            "status": status,
            "matched_user": True,
            "premium": status == "active",
        }), 200

    except Exception:
        logger.exception("Subscription synchronization failed.")
        return jsonify({"error": "Synchronization failed."}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
