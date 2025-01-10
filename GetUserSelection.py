
from AutoScraperUtil import cleaned_input, get_makes_input, get_models_input,transform_strings, get_models_for_make

def get_keywords_from_user(kw_type = "exclude"):
    """
    Allows the user to input keywords and manage them through a menu system.
    Inputs: kw_type (default: exclude) exclude or include
    Returns a list of keywords.
    """
    keywords = []

    print(f"Enter keywords to {kw_type} one by one. Press -1 to stop entering keywords.")
    while True:
        keyword = input(f"Enter a keyword to {kw_type}: ").strip()
        if keyword == '-1':
            break
        if keyword:
            keywords.append(keyword)

    while True:
        print(f"\nCurrent {kw_type} keywords:", ", ".join(keywords) if keywords else "None")
        print("Menu:")
        print(f"1. Add a keyword to {kw_type} ")
        print(f"2. Remove an {kw_type}  keyword")
        print("3. Finish")

        choice = input("Choose an option (1, 2, or 3): ").strip()
        if choice == '1':
            new_keyword = input(f"Enter a new keyword to {kw_type}: ").strip()
            if new_keyword:
                keywords.append(new_keyword)
        elif choice == '2':
            keyword_to_remove = input(f"Enter an {kw_type} keyword to remove: ").strip()
            if keyword_to_remove in keywords:
                keywords.remove(keyword_to_remove)
            else:
                print("Keyword not found.")
        elif choice == '3':
            break
        else:
            print("Invalid choice. Please try again.")

    return transform_strings(keywords)

def get_user_responses():
    """
    Prompt the user for responses to populate the payload items and validate logical consistency.

    Returns:
        dict: A dictionary containing user inputs for the payload.
    """
    #all_makes = get_all_makes()
    payload = {
        "Make": get_makes_input(),
        "Model": None,
        "Proximity": -1,
        "Address": None,
        "YearMin": None,
        "YearMax": None,
        "PriceMin": None,
        "PriceMax": None,
        "OdometerMax":None,
        "OdometerMin":None,
        "Skip": 0,
        "Top": 15,
        "IsNew": True,
        "IsUsed": True,
        "WithPhotos": True,
        "Exclusions": [],
        "Inclusion": "",
        "micrositeType": 1,  # This field is fixed
    }

    if payload["Make"]:
        models_for_make = get_models_for_make(payload["Make"])
        if models_for_make:
            payload["Model"] = get_models_input(models_for_make)

    payload["Address"] = cleaned_input("Address", "Kanata, ON", str)
    payload["Proximity"] = cleaned_input("Distance",-1,int)

    payload["YearMin"] = cleaned_input("Minimum Year", None, int)
    payload["YearMax"] = cleaned_input("Maximum Year", None, int)

    payload["PriceMin"] = cleaned_input("Minimum Price", None, int)
    payload["PriceMax"] = cleaned_input("Maximum Price", None, int)

    payload["OdometerMax"] = cleaned_input("Maximum KMs", None,int)
    payload["OdometerMin"] = cleaned_input("Minimum KMs",None, int)

    # Validate logical consistency of inputs
    if payload["PriceMin"] is not None and payload["PriceMax"] is not None:
        if payload["PriceMin"] > payload["PriceMax"]:
            print("Error: Minimum Price cannot be greater than Maximum Price. Please re-enter.")
            payload["PriceMin"] = cleaned_input("Minimum Price", None, int)
            payload["PriceMax"] = cleaned_input("Maximum Price", None, int)

    if payload["OdometerMin"] is not None and payload["OdometerMax"] is not None:
        if payload["OdometerMin"] > payload["OdometerMax"]:
            print("Error: Minimum KMs cannot be greater than Maximum KMs. Please re-enter.")
            payload["OdometerMin"] = cleaned_input("Minimum KMs", None, int)
            payload["OdometerMax"] = cleaned_input("Maximum Price", None, int)

    if payload["YearMin"] is not None and payload["YearMax"] is not None:
        if payload["YearMin"] > payload["YearMax"]:
            print("Error: Minimum Year cannot be greater than Maximum Year. Please re-enter.")
            payload["YearMin"] = cleaned_input("Minimum Year", None, int)
            payload["YearMax"] = cleaned_input("Maximum Year", None, int)

    payload["Exclusions"] = get_keywords_from_user()
    payload["Inclusion"] = cleaned_input("String To Be Always Included", None, str)
    print(payload)
    return payload


if __name__ == "__main__":
    get_user_responses()

