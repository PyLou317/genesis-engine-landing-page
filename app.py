import os
import re
import smtplib
import ssl
import gspread
import json
import base64
import io

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from email.message import EmailMessage
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

from flask import Flask, render_template, request, flash, redirect, url_for
from decouple import config
from flask_wtf.csrf import CSRFProtect
import certifi

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

# --- Google Sheet Configuration from .env ---
GOOGLE_SHEET_ID = config("GOOGLE_SHEET_ID")
GOOGLE_CREDENTIALS_B64 = config("GOOGLE_CREDENTIALS_B64")
GOOGLE_RANGE_NAME = config("GOOGLE_RANGE_NAME", default=None)
GOOGLE_CREDENTIALS_PATH = os.path.join(app.root_path, config("GOOGLE_CREDENTIALS_FILE", "credentials.json"))


# def get_gspread_client():
#     """Authenticates and returns a gspread client."""
#     try:
#         # Load the JSON string from the environment variable
#         creds_json = json.loads(config("GOOGLE_CREDENTIALS_JSON"))
        
#         # Create credentials directly from the dictionary
#         scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
#         creds = Credentials.from_service_account_info(creds_json, scopes=scope)
        
#         return gspread.authorize(creds)
#     except Exception as e:
#         print(f"Error authenticating with Google Sheets: {e}")
#         return None
    

# --- Gspread Helper Function ---
def add_email_to_sheet(email):
    """Adds a timestamp and email to the Google Sheet."""
    if not GOOGLE_CREDENTIALS_PATH:
        print("Error: GOOGLE_CREDENTIALS_JSON not set in .env file.")
        return "error"
    
    # ADD THIS LINE FOR DEBUGGING:
    print(f"DEBUG: GOOGLE_CREDENTIALS_JSON content length: {len(GOOGLE_CREDENTIALS_PATH)}")
    print(f"DEBUG: GOOGLE_CREDENTIALS_JSON content: {GOOGLE_CREDENTIALS_PATH}")
    
    try:
        # Decode the Base64 string back to bytes
        creds_bytes = base64.b64decode(GOOGLE_CREDENTIALS_B64)
        
        # Load the credentials from the decoded bytes
        creds_dict = json.load(io.BytesIO(creds_bytes))
        
        
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)

        sheet = client.open_by_key(GOOGLE_SHEET_ID).emails
        
        # Check for duplicates before appending
        emails_in_sheet = sheet.col_values(2)
        if email in emails_in_sheet:
            return "duplicate"

        row = [str(datetime.now()), email]
        sheet.append_row(row)
        return "success"

    except Exception as e:
        print(f"Error adding email to Google Sheet: {e}")
        return "error"
    

# --- Email Sending Function ---
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
    msg["Subject"] = "Welcome to the Genesis Engine Meetup!"
    msg["From"] = GMAIL_USER
    msg["To"] = recipient_email
    msg.set_content(
        "Thank you for your interest in the Genesis Engine!\n\n"
        "We've received your registration and will keep you updated with news about our first meetup.\n\n"
        "Best regards,\nthe Genesis Engine Team"
    )

    # --- Send the Email ---
    try:
        # Create a secure SSL context
        context = ssl.create_default_context(cafile=certifi.where())
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
        if not email or not EMAIL_REGEX.match(email):
            flash("Please enter a valid email address.", "danger")
            return redirect(url_for("index"))

        # --- Add Email to Google Sheet ---
        sheet_status = add_email_to_sheet(email)
        if sheet_status == "duplicate":
            flash("You're already registered for updates!", "warning")
            return redirect(url_for("index"))
        elif sheet_status == "error":
            flash("A server error occurred. Please try again later.", "danger")
            return redirect(url_for("index"))
        
        # --- Save Email to File ---
        # try:
        #     existing_emails = set()
        #     if os.path.exists(EMAIL_FILE):
        #         with open(EMAIL_FILE, "r") as f:
        #             existing_emails = [line.strip() for line in f if line.strip()]
                    
        #     if email.strip() in existing_emails:
        #         flash("You're already registered for updates!", "warning")
        #         return redirect(url_for("index"))
                
        #     # If not a duplicate, append the new email
        #     with open(EMAIL_FILE, "a") as f:
        #         f.write(email.strip() + "\n")
                
        # except IOError as e:
        #     print(f"Error writing to file: {e}")
        #     flash("A server error occurred. Please try again later.", "danger")
        #     return redirect(url_for("index"))

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