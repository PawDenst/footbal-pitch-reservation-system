import json
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, current_app
from flask_mail import Mail, Message
import smtplib
from dotenv import load_dotenv

load_dotenv()


auth_bp = Blueprint("auth", __name__)

USER_FILE = os.getenv("USER_FILE")
MAIL_SERVER = os.getenv("MAIL_SERVER")
MAIL_PORT = int(os.getenv("MAIL_PORT"))
MAIL_USE_TLS = os.getenv("MAIL_USE_TLS") == 'True'
MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")

mail = Mail()


def send_confirmation_email_address(email_address, username):
    # Set up the email_address configuration
    mail.init_app(current_app)
    current_app.config['MAIL_SERVER'] = MAIL_SERVER
    current_app.config['MAIL_PORT'] = MAIL_PORT
    current_app.config['MAIL_USE_TLS'] = MAIL_USE_TLS
    current_app.config['MAIL_USERNAME'] = MAIL_USERNAME
    current_app.config['MAIL_PASSWORD'] = MAIL_PASSWORD

    # Generate the link for the user to click on
    confirm_link = url_for('auth.confirm_registration', email_address=email_address, _external=True)

    # Compose the email_address message
    msg = Message(
        subject="Registration Confirmation",
        sender="pawelqq1@gmail.com",  # Replace with your email address
        recipients=[email_address],
        body=f"Hello {username},\n\nThank you for registering. Please click on the following link to complete your registration:\n{confirm_link}"
    )

    # Send the email_address
    with current_app.app_context():
        mail.init_app(current_app)
        mail.send(msg)


@auth_bp.route("/confirm-registration/<string:email_address>")
def confirm_registration(email_address):
    users = load_users()

    # Find the user with the provided email
    for user in users:
        if user.get("email_address") == email_address:
            user["registered"] = True
            save_users(users)
            session["username"] = user["username"]
            session["email_address"] = user.get("email_address")
            session["role"] = "user"  # Or any other default role for registered users
            flash("Registration confirmed! You can now log in.")
            return redirect(url_for("index"))

    flash("Invalid registration confirmation link.", "error")
    return redirect(url_for("home"))


def load_users():
    try:
        with open(USER_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return []


def save_users(users):
    with open(USER_FILE, "w") as file:
        json.dump(users, file)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        email_address = request.form.get("email_address")  # New field for the user's email_address

        if username and password and email_address:  # Check if all required fields are provided
            users = load_users()

            if any(user["username"] == username for user in users):
                flash("Username already taken.", "error")
                return redirect(url_for("home"))

            # Store the user information
            user = {"username": username, "password": password, "email_address": email_address, "registered": False}
            users.append(user)
            save_users(users)

            # Send the registration confirmation email_address
            send_confirmation_email_address(email_address, username)  # Pass the application object to the function

            flash(f"Registration successful! Please check your email: {email_address} to complete the registration.")
            return redirect(url_for("home"))



@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        users = load_users()

        # Check if the username and password match and the user is registered
        for user in users:
            if user["username"] == username and user["password"] == password and user["registered"]:
                # Set the user in the session
                session["username"] = username
                session["email_address"] = user.get("email_address")
                if username == "admin" and password == "adminpassword":
                    session["role"] = "admin"
                else:
                    session["role"] = "user"
                return redirect(url_for("index"))
        flash("Cant login! Please check if your username and password are valid or go to email_address to complete the registration.")
        return redirect(url_for("home"))

    # If the user is already logged in, redirect to home
    if "username" in session:
        return redirect(url_for("index"))

    return render_template("index.html")


@auth_bp.route("/logout", methods=["POST"])
def logout():
    # Clear the session
    session.clear()
    return redirect(url_for("home"))
