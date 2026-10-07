import os
import hmac
import hashlib
from flask import Flask, request, jsonify

app = Flask(__name__)

WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")


@app.route("/razorpay-webhook", methods=["POST"])
def razorpay_webhook():

    signature = request.headers.get("X-Razorpay-Signature", "")
    body = request.get_data()

    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        return jsonify({"error": "Invalid signature"}), 400

    data = request.get_json()
    event = data.get("event")

    if event == "subscription.activated":
        print("PREMIUM SUBSCRIPTION ACTIVATED")

    elif event == "subscription.cancelled":
        print("PREMIUM SUBSCRIPTION CANCELLED")

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
