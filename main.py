from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash
from dotenv import load_dotenv
import os
from reservation_functions import save_slots, load_slots, occupied_status_check, compare_motion_times, hour_range_for_slot
from auth import auth_bp
from collections import defaultdict
import requests
import json
import time
from datetime import datetime, timedelta
user_reservations = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

app = Flask(__name__)
app.secret_key = 'your_secret_key'

load_dotenv()
authorized_users = os.getenv("AUTHORIZED_USERS", "").split(",")
SLOTS_FILE = "slots.pkl"
slots = load_slots(SLOTS_FILE)
app.register_blueprint(auth_bp)

MAX_RESERVATIONS_PER_DATE_OBJECT = 2  # Maximum number of reservations a user can make


@app.route("/reserve-slot", methods=["POST"])
def reserve_slot_route():
    slot_number = int(request.form.get("slot_number"))
    reservation_date = request.form.get("reservation_date")
    object_name = request.form.get("object_name")
    hour_range = request.form.get("hour_range")
    username = session.get("username")
    email_address = session.get("email_address")

    date_slots = slots.setdefault(reservation_date, {})
    slot_info_list = date_slots.setdefault(object_name, [])

    if session.get("role") == "user":
        user_reserved_slots = [slot_info for slot_info in slot_info_list if slot_info.get("player_name") == username]
        if len(user_reserved_slots) >= 1:
            flash("You can only reserve up to one hour range for the selected object and date.", "error")
            return redirect(url_for("get_available_slots"))
        if user_reservations[username][reservation_date][object_name] >= 2:
            flash(f"You have reached the maximum number of reservations (2) for {reservation_date} on {object_name}.", "error")
            return redirect(url_for("get_available_slots"))

    for slot_info in slot_info_list:
        if slot_info.get("slot_number") == slot_number:
            slot_info["player_name"] = username
            slot_info["email_address"] = email_address
            slot_info["hour_range"] = hour_range
            break
    else:
        slot_info = {"slot_number": slot_number, "player_name": username, "email_address": email_address,
                     "hour_range": hour_range}
        slot_info_list.append(slot_info)

    user_reservations[username][reservation_date][object_name] += 1
    flash_message = f"Slot {hour_range} for {reservation_date} has been reserved by {username} on {object_name}."
    flash(flash_message, "success")
    session["flash_message"] = flash_message
    save_slots(slots, SLOTS_FILE)
    return redirect(url_for("get_available_slots"))


@app.route("/available-slots", methods=["GET", "POST"])
def get_available_slots():
    if "username" not in session:
        return redirect(url_for("home"))
    if request.method == "POST":
        reservation_date = request.form.get("reservation_date")
        object_name = request.form.get("object_name")
        session["reservation_date"] = reservation_date
        session["object_name"] = object_name
        return redirect(url_for("get_available_slots"))

    # Handle GET request
    reservation_date = session.get("reservation_date")
    object_name = session.get("object_name")

    # Get the slots for the specified date and object
    date_slots = slots.get(reservation_date, {})
    slot_info_list = date_slots.get(object_name, [])

    # Prepare the slot data  for rendering the template
    slots_data = []
    hour_range_start = 10
    hour_interval = 1.5
    hour_range_end = hour_range_start + hour_interval
    total_slots = 8  # Replace with the desired number of slots

    for slot_number in range(1, total_slots + 1):
        slot_info = next((slot for slot in slot_info_list if slot.get("slot_number") == slot_number), None)
        hour_range = hour_range_for_slot(hour_range_start, hour_range_end)
        slot_data = {
            "reservation_date": reservation_date,
            "object_name": object_name,
            "slot_number": slot_number,
            "hour_range": hour_range,
            "player_name": slot_info.get("player_name") if slot_info else None,
            "email_address": slot_info.get("email_address") if slot_info else None
        }
        slots_data.append(slot_data)

        # Update the hour range for the next slot
        hour_range_start = hour_range_end
        hour_range_end += hour_interval

    motion_result, comparison_times, count = compare_motion_times()
    status_message, status_data = occupied_status_check()

    return render_template(
        "slots.html",
        slots=slots_data,
        show_email_address=session.get("role") == "user",
        status_data=status_data,
        motion_result=motion_result,
        comparison_times=comparison_times,
        count=count,
        status_message=status_message
    )


@app.route("/cancel-reservation", methods=["POST"])
def cancel_reservation_route():
    reservation_date = request.form.get("reservation_date")
    object_name = request.form.get("object_name")
    hour_range = request.form.get("hour_range")
    cancel_all = request.form.get("cancel_all")  # New parameter to determine if all reservations should be canceled
    username = session.get("username")  # Retrieve the logged-in user's username from the session
    role = session.get("role")  # Retrieve the user's role from the session

    date_slots = slots.get(reservation_date, {})
    slot_info_list = date_slots.get(object_name, [])

    # Find the slot(s) to cancel the reservation based on the hour range and username
    canceled_count = 0  # Track the number of canceled reservations

    for slot_info in slot_info_list:
        if slot_info.get("hour_range") == hour_range:
            if role == "admin" or (role == "user" and slot_info.get("player_name") == username):
                slot_info_list.remove(slot_info)
                canceled_count += 1

    if cancel_all == "true":
        canceled_count = len(slot_info_list)
        slot_info_list.clear()

    if canceled_count > 0:
        flash(f"{canceled_count} reservation(s) canceled for {reservation_date} on {object_name}.", "success")
        save_slots(slots, SLOTS_FILE)
    else:
        flash(f"No reservations found on {reservation_date} in {object_name}.", "error")

    return redirect(url_for("get_available_slots"))


@app.route("/delete-reservation", methods=["POST"])
def delete_reservations_route():
    reservation_date = request.form.get("reservation_date")

    if reservation_date in slots:
        slots.pop(reservation_date)
        save_slots(slots, SLOTS_FILE)
        flash(f"All reservations for {reservation_date} have been deleted.")
        return redirect(url_for("index"))
    else:
        slots.pop(reservation_date)
        flash(f"No reservations found for {reservation_date}.")
        return redirect(url_for("index"))


@app.route("/cancel-object", methods=["POST"])
def cancel_object_route():
    object_name = request.form.get("object_name")

    canceled_count = 0  # Track the number of canceled reservations
    for reservation_date, date_slots in slots.items():
        slot_info_list = date_slots.get(object_name, [])
        for slot_info in slot_info_list[:]:
            slot_info_list.remove(slot_info)
            canceled_count += 1
    if canceled_count > 0:
        save_slots(slots, SLOTS_FILE)
        flash(f"{canceled_count} reservation(s) canceled on {object_name}.", "success")
    else:
        flash(f"No reservations found for on {object_name} .", "error")
    return redirect(url_for("index"))


@app.route("/")
def home():
    # Render the desired template
    return render_template("home.html")


@app.route("/index")
def index():
    # Render the desired template
    return render_template("index.html")


@app.errorhandler(404)
def page_not_found(error):
    return "404 Not Found", 404


if __name__ == "__main__":
    app.run(debug=True)
