import json
import os
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import database

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "email_config.json")


def send_notification(member, direction, timestamp):
    threading.Thread(
        target=_send, args=(member, direction, timestamp), daemon=True
    ).start()


def _send(member, direction, timestamp):
    try:
        with open(_CONFIG_PATH) as f:
            config = json.load(f)

        if not config.get("enabled", True):
            return

        caregiver = database.get_caregiver(member["id"])
        if not caregiver or not caregiver.get("email"):
            return

        notify_on = caregiver.get("notify_on") or "BOTH"
        if notify_on == "NONE":
            return
        if notify_on == "IN" and direction != "IN":
            return
        if notify_on == "OUT" and direction != "OUT":
            return

        sender = config["sender_email"]
        password = config["app_password"]
        recipient = caregiver["email"]

        first = member["first_name"]
        last = member["last_name"]
        label = "IN" if direction == "IN" else "OUT"
        time_str = timestamp.strftime("%I:%M %p")
        date_str = timestamp.strftime("%A %d %B %Y")

        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = recipient
        msg["Subject"] = f"Sign-{label} Notification — {first} {last}"
        msg.attach(MIMEText(
            f"Hi,\n\n"
            f"{first} {last} has been signed {label} at {time_str} on {date_str}.\n\n"
            f"— Kiosk Sign-In System",
            "plain",
        ))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)

    except Exception:
        pass
