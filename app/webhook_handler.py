import os
import sys
import requests

import logging
from typing import Dict, Any, Tuple
from flask import Flask, request, jsonify

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

"""
Webhook Alert System

This script creates a webhook endpoint, processes incoming webhooks,
and sends email alerts based on the received data.

TODOs:
- Implement persistent storage for webhook data (e.g., SQLite database)
- Add configuration option to choose between Webhook.site and a custom webhook endpoint
- Implement rate limiting to prevent abuse of the webhook endpoint
- Add support for HTTPS using SSL certificates for secure webhook reception
- Implement webhook signature verification for added security
- Create a configuration file for easier setup and customization
- Add support for multiple recipient email addresses
- Implement templating for email alerts to improve readability
- Add support for different types of alerts (e.g., SMS, Slack notifications)
- Implement a simple web interface for monitoring webhook status and history
- Add unit tests and integration tests for improved code reliability
- Implement logging rotation to manage log file sizes
- Add support for environment-specific configurations (development, staging, production)
- Implement a retry mechanism for failed email sends
- Add support for parsing and handling different webhook payload formats
- Implement a cleanup mechanism to remove old webhook data periodically
"""

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

# Webhook configuration
WEBHOOK_SITE_API = "https://webhook.site/token"
webhook_url = None

# Webhook counter
webhook_count = 0
MAX_WEBHOOKS = 3

def create_webhook() -> str:
    """
    Create a new webhook using Webhook.site API.

    Returns:
        str: The URL of the created webhook.
    """
    try:
        response = requests.post(WEBHOOK_SITE_API)
        response.raise_for_status()
        data = response.json()
        return data['url']
    except requests.RequestException as e:
        logger.error(f"Failed to create webhook: {str(e)}")
        raise

def test_email_login() -> bool:
    """
    Test the email login credentials.

    Returns:
        bool: True if login is successful, False otherwise.
    """
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
        logger.info("Email login successful")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("Failed to authenticate with the SMTP server. Please check your email and password.")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"An error occurred while testing email login: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during email login test: {str(e)}")
        return False

def send_email_alert(subject: str, body: str) -> Tuple[bool, str]:
    """
    Send an email alert using the configured SMTP server.

    Args:
        subject (str): The subject of the email.
        body (str): The body content of the email.

    Returns:
        Tuple[bool, str]: A tuple containing a success flag and a message.
    """
    message = MIMEMultipart()
    message["From"] = SENDER_EMAIL
    message["To"] = SENDER_EMAIL  # Using sender email as recipient
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(message)
        logger.info("Email alert sent successfully")
        return True, "Email sent successfully"
    except smtplib.SMTPException as e:
        error_msg = f"An error occurred while sending the email: {str(e)}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"An unexpected error occurred: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

def process_webhook_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process the incoming webhook data.

    Args:
        data (Dict[str, Any]): The webhook payload.

    Returns:
        Dict[str, Any]: Processed data.
    """
    # Example processing logic (can modify as needed)
    processed_data = {
        "event_type": data.get("event_type", "Unknown"),
        "timestamp": data.get("timestamp"),
        "details": data.get("details", {}),
    }
    return processed_data

@app.route("/webhook", methods=["POST"])
def webhook_handler() -> Dict[str, Any]:
    """
    Handle incoming webhook POST requests.

    Returns:
        dict: A JSON response indicating the status of the webhook handling.
    """
    global webhook_count
    
    try:
        data = request.json
        logger.info(f"Received webhook data: {data}")

        processed_data = process_webhook_data(data)
        
        webhook_count += 1
        alert_subject = f"Webhook Alert {webhook_count}/{MAX_WEBHOOKS}: {processed_data['event_type']}"
        alert_body = f"Processed webhook data:\n{processed_data}"

        success, message = send_email_alert(alert_subject, alert_body)
        if not success:
            return jsonify({"status": "error", "message": message}), 500

        if webhook_count >= MAX_WEBHOOKS:
            final_subject = "Webhook Processing Complete"
            final_body = f"All {MAX_WEBHOOKS} webhooks have been processed. The system will now stop accepting new webhooks."
            send_email_alert(final_subject, final_body)
            logger.info("Maximum number of webhooks processed. Stopping.")
        
        return jsonify({"status": "success", "message": "Webhook processed and alert sent"}), 200
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    try:
        # Test email login before proceeding
        if not test_email_login():
            logger.error("Email login failed. Please check your credentials and try again.")
            sys.exit(1)

        webhook_url = create_webhook()
        logger.info(f"Created webhook: {webhook_url}")
        print(f"Webhook URL: {webhook_url}")
        print("Please configure your service to send webhooks to this URL.")
        app.run(debug=True, port=5000)
    except Exception as e:
        logger.error(f"Failed to start the application: {str(e)}")
        sys.exit(1)