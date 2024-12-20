import json


def cleaned_input(itemTitle, defaultval, expectedtype):
    """
    Prompts the user for input, validates it, and ensures it matches the expected type.

    :param itemTitle: str, title of the item being requested
    :param defaultval: default value to use if input is empty
    :param expectedtype: type, the expected type of the input
    :return: value of the correct type
    """
    while True:
        try:
            user_input = input(f"Enter {itemTitle} (default: {defaultval}): ")
            if not user_input.strip():
                return defaultval
            value = expectedtype(user_input)
            return value
        except ValueError:
            print(f"Invalid input. Please enter a value of type {expectedtype.__name__}.")

def get_user_responses():
    """
    Prompt the user for responses to populate the payload items and validate logical consistency.

    Returns:
        dict: A dictionary containing user inputs for the payload.
    """
    exclusions = []
    payload = {
        "Address": cleaned_input("Address", "Kanata, ON", str),
        "Make": cleaned_input("Make", None, str),
        "Model": cleaned_input("Model", None, str),
        "PriceMin": cleaned_input("Minimum Price", None, int),
        "PriceMax": cleaned_input("Maximum Price", None, int),
        "Skip": cleaned_input("Skip", 0, int),
        "Top": cleaned_input("Top", 15, int),
        "IsNew": cleaned_input("Is the car new? (True/False)", True, bool),
        "IsUsed": cleaned_input("Is the car used? (True/False)", True, bool),
        "WithPhotos": cleaned_input("With photos only? (True/False)", True, bool),
        "YearMax": cleaned_input("Maximum Year", None, int),
        "YearMin": cleaned_input("Minimum Year", None, int),
        "micrositeType": 1,  # This field is fixed
    }

    # Validate logical consistency of inputs
    if payload["PriceMin"] is not None and payload["PriceMax"] is not None:
        if payload["PriceMin"] > payload["PriceMax"]:
            print("Error: Minimum Price cannot be greater than Maximum Price. Please re-enter.")
            payload["PriceMin"] = cleaned_input("Minimum Price", None, int)
            payload["PriceMax"] = cleaned_input("Maximum Price", None, int)

    if payload["YearMin"] is not None and payload["YearMax"] is not None:
        if payload["YearMin"] > payload["YearMax"]:
            print("Error: Minimum Year cannot be greater than Maximum Year. Please re-enter.")
            payload["YearMin"] = cleaned_input("Minimum Year", None, int)
            payload["YearMax"] = cleaned_input("Maximum Year", None, int)

    return payload, exclusions

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