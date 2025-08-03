import os
import re
import smtplib
import ssl
import gspread
import json
import base64
import io
import textwrap
import markdown2

from google.oauth2 import service_account
from email.message import EmailMessage
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


# --- Gspread Helper Function ---
def add_email_to_sheet(email):
    """Adds a timestamp and email to the Google Sheet."""
    if not GOOGLE_CREDENTIALS_B64:
        print("Error: GOOGLE_CREDENTIALS_B64 not set.")
        return "error"
    
    try:
        # Decode the Base64 string back to bytes
        creds_bytes = base64.b64decode(GOOGLE_CREDENTIALS_B64)
        
        # Load credentials from the decoded bytes in memory
        creds_dict = json.load(io.BytesIO(creds_bytes))
        
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)

        sheet = client.open_by_key(GOOGLE_SHEET_ID).sheet1 # Use .sheet1 for the first sheet

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
    

def generate_welcome_email():
    email_content = f"""
    # Welcome to Genesis Engine! 🚀

    Hey there,

    Thanks for signing up for the Genesis Engine Weekly Coding Group! We're thrilled to have you join our community.

    The idea behind this group is to create a vibrant space for builders, developers, and creatives to come together and do something amazing: **build in public, learn from each other, and spark new ideas.**

    We believe that sharing your work, no matter what stage it's in, is one of the best ways to grow. Here, you'll be able to:

    * **Showcase what you're working on**, getting feedback and support from a community of your peers.

    * **Learn new skills** and technologies by seeing how others are tackling their projects.

    * **Find inspiration** for your next big idea by engaging with a diverse group of creators.

    Our weekly sessions will be a chance to connect, collaborate, and push our projects forward.

    We're also exploring the possibility of holding **monthly sessions with speakers and experts in the field**. These sessions would provide an opportunity to dive deep into specific topics and learn from leaders in the industry.

    We're gauging the level of interest in this group and would love to hear your thoughts. If you have any suggestions or ideas, please reply to this email and let us know!

    In the meantime, feel free to introduce yourself! We can't wait to see what you'll create.

    Best,
    The Genesis Engine Team
    """
    # Using textwrap.dedent to remove the leading indentation from the multiline string.
    return textwrap.dedent(email_content).strip()


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
    try:
        plain_text_content = generate_welcome_email()
        html_content = markdown2.markdown(plain_text_content)
        
        msg = EmailMessage()
        msg["Subject"] = "Welcome to Genesis Engine! Let's Build Together 🚀"
        msg["From"] = GMAIL_USER
        msg["To"] = recipient_email
        msg.set_content(plain_text_content)
        msg.add_alternative(html_content, subtype="html")

    # --- Send the Email ---
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