import datetime
import pickle
import requests
import json
from datetime import datetime, timedelta
SLOTS_FILE = "slots.pkl"


def display_available_slots(slots):
    print("Available slots on the field:")
    for reservation_date, date_slots in slots.items():
        print(f"Date: {reservation_date}")
        for slot_number, slot in date_slots.items():
            if slot is None:
                print(f"Slot {slot_number}: Available")
            else:
                player_name = slot["player_name"]
                print(f"Slot {slot_number}: Occupied by {player_name}")


def reserve_slot(slots, slot_number, player_name, reservation_date):
    if slot_number is None or reservation_date is None:
        return "Slot number and reservation date are required.", 400

    try:
        slot_number = int(slot_number)
    except ValueError:
        return "Invalid slot number.", 400

    date_slots = slots.setdefault(reservation_date, {})
    if slot_number in date_slots and date_slots[slot_number] is not None:
        return f"Slot {slot_number} for {reservation_date} is already occupied.", 400
    else:
        date_slots[slot_number] = {"player_name": player_name}
        save_slots(slots, SLOTS_FILE)
        return f"Slot {slot_number} for {reservation_date} has been reserved by {player_name}."


def cancel_reservation(date_slots, slot_number):
    if slot_number in date_slots and date_slots[slot_number] is not None:
        player_name = date_slots[slot_number]["player_name"]
        del date_slots[slot_number]
        print(f"Reservation for slot {slot_number} has been canceled for {player_name}.")
    else:
        print(f"Slot {slot_number} is not currently reserved.")


def save_slots(slots, filename):
    with open(filename, "wb") as file:
        pickle.dump(slots, file)


def load_slots(filename):
    try:
        with open(filename, "rb") as file:
            slots = pickle.load(file)
    except FileNotFoundError:
        slots = {}
    return slots


def hour_range_for_slot(hour_range_start,hour_range_end):
    start_hour = "{:02d}:{:02d}".format(int(hour_range_start) % 24,
                                            int((hour_range_start - int(hour_range_start)) * 60))
    end_hour = "{:02d}:{:02d}".format(int(hour_range_end) % 24, int((hour_range_end - int(hour_range_end)) * 60))
    hour_range = f"{start_hour} - {end_hour}"
    return hour_range


def occupied_status_check():
    occupied_url = 'https://eu1.cloud.thethings.network/api/v3/as/applications/czujnik-wibracji-netvox/devices/eui-00137a100001bcab/packages/storage/uplink_normalized'
    occupied_headers = {
        'content-type': 'application/json',
        'authorization': 'Bearer NNSXS.FEDQCYQM7TPD6SIJF4SZRFHK3VLJPXILVSMIENQ.BVAQNVQZOIZFMULPSSEEOUNBTCFLO44TYPVC7HJPFYA7K4YN6BBA'
    }
    status_data = []
    response = requests.get(occupied_url, headers=occupied_headers)

    if response.status_code == 200:
        try:
            lines = response.text.strip().split('\n')
            for line in lines:
                try:
                    data = json.loads(line)
                    status = data['result']['uplink_message']['decoded_payload']['status']
                    timestamp = data['result']['uplink_message']['rx_metadata'][0]['time'][:19]
                    datetime_obj = datetime.fromisoformat(timestamp)
                    datetime_obj -= timedelta(hours=-2)
                    formatted_time = datetime_obj.strftime('%Y-%m-%d %H:%M')
                    status_data.append({'time': formatted_time, 'status': status})
                except KeyError:
                    print("Status key not found in the data dictionary.")
        except json.JSONDecodeError:
            print("Failed to parse JSON response in status check.")
    else:
        print(f'Request failed with status code {response.status_code}')

    if len(status_data) > 0:
        last_entry = status_data[-1]
        last_status = last_entry['status']
        if last_status == 0:
            status_message = "Not occupied"
        elif last_status == 1:
            status_message = "Occupied"
        else:
            status_message = "Invalid status value"
    else:
        status_message = "No statuses found"

    return status_message, status_data


def parse_response_text(response):
    # Split the response text by newline characters and parse each JSON separately
    json_list = []
    for line in response.text.strip().split('\n'):
        try:
            json_list.append(json.loads(line))
        except json.JSONDecodeError:
            print("Failed to parse JSON response.")
    return json_list


def compare_motion_times():
    url_entry = 'https://eu1.cloud.thethings.network/api/v3/as/applications/czujnik-ruchu-wejscie/devices/eui-a81758fffe084b76/packages/storage/uplink_normalized'
    headers_entry = {
        'content-type': 'application/json',
        'authorization': 'Bearer NNSXS.JF3TTVZIYD44H2UWVV2IJXJZZIEDB3OBELHUP2Y.FAH4FBVPG7SW7SPQYTZOXZDQXJTZBNGITLAPWJEOURI2I35G53XQ'
    }
    url_exit = 'https://eu1.cloud.thethings.network/api/v3/as/applications/czujnik-ruchu-wyjscie-2/devices/eui-a81758fffe084b77/packages/storage/uplink_normalized'
    headers_exit = {
        'content-type': 'application/json',
        'authorization': 'Bearer NNSXS.M3W5XU6PP2XKIBUIGYLWNMBT2BPQUYZTF2HTWGY.7H4JFSS3RMUBR6SDJW35XWJNERUOFRNLOTXDDNTZY73VIQ3GDEFA'
    }

    response1 = requests.get(url_entry, headers=headers_entry)
    response2 = requests.get(url_exit, headers=headers_exit)

    json_list1 = parse_response_text(response1)
    json_list2 = parse_response_text(response2)
    print(len(json_list1))
    print(len(json_list2))
    if len(json_list1) > len(json_list2):
        start1 = len(json_list1) - len(json_list2)
        start2 = 0
    elif len(json_list1) < len(json_list2):
        start2 = len(json_list2) - len(json_list1)
        start1 = 0
    elif len(json_list1) == len(json_list2):
        start1, start2 = 0
    count = 0
    comparison_times = []
    results = []

    for json1, json2 in zip(json_list1[start1:], json_list2[start2:]):
        if 'motion' in json1['result']['uplink_message']['decoded_payload'] and 'motion' in json2['result']['uplink_message']['decoded_payload']:
            motion1 = json1['result']['uplink_message']['decoded_payload']['motion']
            motion2 = json2['result']['uplink_message']['decoded_payload']['motion']
            if motion1 == 1 and motion2 == 1:
                time1 = json1['result']['received_at']
                time2 = json2['result']['received_at']
                datetime_obj1 = datetime.fromisoformat(time1)
                datetime_obj2 = datetime.fromisoformat(time2)
                # Adjust for -2 timezone offset
                datetime_obj1 -= timedelta(hours=-2)
                datetime_obj2 -= timedelta(hours=-2)
                # Format datetime as string
                formatted_time1 = datetime_obj1.strftime('%H:%M:%S')
                formatted_time2 = datetime_obj2.strftime('%H:%M:%S')
                print(f"czas1: {formatted_time1}")
                print(f"czas2: {formatted_time2}")

                if formatted_time1 < formatted_time2:
                    count += 1
                elif formatted_time1 > formatted_time2:
                    count -= 1
                comparison_times.append(formatted_time1)
                results.append(count)
                if count < 0:
                    count = 0
    return count, comparison_times, results


