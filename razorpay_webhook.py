
import os
import hmac
import hashlib
import json
import logging

from flask import Flask, request, jsonify
import psycopg2


# ============================================================
# MINIBOT RAZORPAY WEBHOOK
# ============================================================

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("minibot_webhook")

DATABASE_URL = os.environ.get("DATABASE_URL")
WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET")

# Events that indicate an active subscription.
ACTIVE_EVENTS = {
    "subscription.activated",
    "subscription.charged",
    "subscription.resumed",
}

# Events that should remove Premium access.
INACTIVE_EVENTS = {
    "subscription.cancelled",
    "subscription.halted",
    "subscription.paused",
    "subscription.completed",
}


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured.")

    return psycopg2.connect(
        DATABASE_URL,
        connect_timeout=10,
        sslmode="require",
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({
        "service": "MiniBot Razorpay Webhook",
        "status": "running",
    }), 200


# ============================================================
# RAZORPAY WEBHOOK
# ============================================================

@app.route("/razorpay/webhook", methods=["POST"])
def razorpay_webhook():

    if not WEBHOOK_SECRET:
        logger.error("RAZORPAY_WEBHOOK_SECRET is not configured.")
        return jsonify({
            "error": "Webhook secret is not configured."
        }), 503

    if not DATABASE_URL:
        logger.error("DATABASE_URL is not configured.")
        return jsonify({
            "error": "Database is not configured."
        }), 503

    # Verify the signature against the exact raw request body.
    signature = request.headers.get(
        "X-Razorpay-Signature", ""
    )

    raw_body = request.get_data(cache=True)

    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not signature or not hmac.compare_digest(
        expected_signature, signature
    ):
        logger.warning("Invalid Razorpay webhook signature.")
        return jsonify({
            "error": "Invalid signature."
        }), 400

    # Parse the verified event.
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return jsonify({
            "error": "Invalid JSON payload."
        }), 400

    event = payload.get("event", "")

    # Ignore unrelated events.
    if event not in ACTIVE_EVENTS and event not in INACTIVE_EVENTS:
        logger.info("Ignoring event: %s", event)
        return jsonify({
            "status": "ignored",
            "event": event,
        }), 200

    subscription = (
        payload.get("payload", {})
        .get("subscription", {})
        .get("entity", {})
    )

    subscription_id = subscription.get("id")
    subscription_status = subscription.get("status")

    if not subscription_id:
        logger.warning(
            "Subscription ID missing from event %s", event
        )
        return jsonify({
            "error": "Subscription ID missing."
        }), 400

    # Only grant access for appropriate active events and statuses.
    # A charged event may arrive with an activated subscription.
    premium = (
        event in ACTIVE_EVENTS
        and subscription_status in {"active", "authenticated"}
    )

    connection = None

    try:
        connection = get_db_connection()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE minibot_users
                SET
                    premium = %s,
                    razorpay_status = %s,
                    updated_at = NOW()
                WHERE razorpay_subscription_id = %s
                """,
                (
                    premium,
                    subscription_status or event,
                    subscription_id,
                ),
            )

            updated_rows = cursor.rowcount

        connection.commit()

        if updated_rows == 0:
            logger.warning(
                "No user found for subscription ID %s",
                subscription_id,
            )

            # The event is valid, but the app's database does not
            # contain this subscription ID. Do not grant access.
            return jsonify({
                "status": "received",
                "matched_user": False,
            }), 200

        logger.info(
            "Subscription %s updated: event=%s, status=%s, premium=%s",
            subscription_id,
            event,
            subscription_status,
            premium,
        )

        return jsonify({
            "status": "updated",
            "premium": premium,
        }), 200

    except Exception:
        if connection:
            connection.rollback()

        logger.exception("Failed to update subscription in database.")

        return jsonify({
            "error": "Database update failed."
        }), 500

    finally:
        if connection:
            connection.close()


# ============================================================
# START WEBHOOK SERVER
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))

    app.run(
        host="0.0.0.0",
        port=port,
    )
