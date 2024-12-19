import json

def get_user_responses():
    """
    Prompt the user for responses to populate the payload items.

    Returns:
        dict: A dictionary containing user inputs for the payload.
    """
    payload = {
        "Address": input("Enter Address (default: null): ") or "Kanata, ON",
        "Make": input("Enter Make (default: null): ") or None,
        "Model": input("Enter Model (default: null): ") or None,
        "PriceMin": input("Enter Minimum Price (default: null): ") or None,
        "PriceMax": input("Enter Maximum Price (default: null): ") or None,
        "Skip": 0,
        "Top": 15,
        "IsNew": "True",
        "IsUsed": "True",
        "WithPhotos": "True",
        "YearMax": input("Enter Maximum Year (default: null): ") or None,
        "YearMin": input("Enter Minimum Year (default: null): ") or None,
        "micrositeType": 1,  # This field is fixed
    }

    # Convert numerical inputs or booleans
    for key in ["PriceMin", "PriceMax", "Skip", "Top", "YearMax", "YearMin"]:
        if payload[key] is not None:
            try:
                payload[key] = int(payload[key])
            except ValueError:
                payload[key] = None

    for key in ["IsNew", "IsUsed", "WithPhotos"]:
        if payload[key] is not None:
            payload[key] = payload[key].strip().lower() == "true"

    return payload

def save_payload_to_file(payload):
    """
    Save the payload to a file in JSON format.

    Args:
        payload (dict): The payload to save.
    """
    filename = input("Enter the name of the file to save (with .txt extension): ")
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=4)
    print(f"Payload saved to {filename}")

def read_payload_from_file(filename = "ff2019.txt"):
    """
    Read a payload from a file in JSON format.

    Returns:
        dict: The payload read from the file.
    """
    #filename = input("Enter the name of the file to read (with .txt extension): ")
    print("TEST PAYLOAD: FORD FUSION 2017-19")
    try:
        with open(filename, "r", encoding="utf-8") as file:
            payload = json.load(file)
            print(f"Payload successfully loaded from {filename}")
            return payload
    except FileNotFoundError:
        print(f"File {filename} not found.")
        return None