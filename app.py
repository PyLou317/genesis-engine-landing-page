import os
import re
import smtplib
import ssl
from email.message import EmailMessage

from flask import Flask, render_template, request, flash, redirect, url_for
from decouple import config
from flask_wtf.csrf import CSRFProtect

# File to store collected emails
EMAIL_FILE = "emails.txt"

# Regular expression for basic email validation
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

# --- Flask App Initialization ---
app = Flask(__name__)
app.secret_key = config("FLASK_SECRET_KEY")
csrf = CSRFProtect(app)

# --- GMAIL SMTP Configuration from .env file ---
GMAIL_USER = config("GMAIL_USER", default=None)
GMAIL_APP_PASSWORD = config("GMAIL_APP_PASSWORD", default=None)

def send_confirmation_email(recipient_email):
    """
    Sends a confirmation email to the user using Gmail's SMTP server.

    Args:
        recipient_email (str): The email address to send the confirmation to.

    Returns:
        bool: True if the email was sent successfully, False otherwise.
    """
    # Use credentials loaded by decouple at the start of the app
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("Error: GMAIL_USER and GMAIL_APP_PASSWORD not set in .env file.")
        # In a real app, you might want to log this error more formally
        return False

    # --- Create the Email ---
    msg = EmailMessage()
    msg["Subject"] = "Welcome to The Genesis Engine Meetup!"
    msg["From"] = GMAIL_USER
    msg["To"] = recipient_email
    msg.set_content(
        "Thank you for your interest in The Genesis Engine!\n\n"
        "We've received your registration and will keep you updated with news about our first meetup.\n\n"
        "Best regards,\nThe Genesis Engine Team"
    )

    # --- Send the Email ---
    try:
        # Create a secure SSL context
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        return True
    except smtplib.SMTPAuthenticationError:
        print("Error: SMTP authentication failed. Check your GMAIL_USER and GMAIL_APP_PASSWORD in the .env file.")
    except Exception as e:
        # Log the actual error for debugging
        print(f"An error occurred while sending the email: {e}")
    return False


@app.route("/", methods=["GET", "POST"])
def index():
    """Handles the landing page and form submission."""
    if request.method == "POST":
        email = request.form.get("email", "").strip()

        # --- Validation ---
        if not email:
            flash("Email address cannot be empty.", "danger")
            return redirect(url_for("index"))

        if not EMAIL_REGEX.match(email):
            flash("Please enter a valid email address.", "danger")
            return redirect(url_for("index"))

        # --- Save Email to File ---
        try:
            existing_emails = set()
            if os.path.exists(EMAIL_FILE):
                with open(EMAIL_FILE, "r") as f:
                    existing_emails = [line.strip() for line in f if line.strip()]
                    
            if email.strip() in existing_emails:
                flash("You're already registered for updates!", "warning")
                return redirect(url_for("index"))
                
            # If not a duplicate, append the new email
            with open(EMAIL_FILE, "a") as f:
                f.write(email.strip() + "\n")
                
        except IOError as e:
            print(f"Error writing to file: {e}")
            flash("A server error occurred. Please try again later.", "danger")
            return redirect(url_for("index"))

        # --- Send Confirmation Email ---
        if send_confirmation_email(email):
            flash("Success! You're signed up for weekly updates. Check your inbox for a confirmation!", "success")
        else:
            # This message is shown if env vars are missing or SMTP fails
            flash("Your email was saved, but we couldn't send a confirmation. We'll be in touch!", "warning")

        return redirect(url_for("index"))

    return render_template("index.html")


if __name__ == "__main__":
    # Note: `debug=True` is for development only.
    app.run(debug=True)