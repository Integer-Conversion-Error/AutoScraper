import requests

def get_models_for_make_via_request(make):
    """
    Fetches all models for a given car make by sending a POST request to the AutoTrader API.

    Args:
        make (str): The car make for which models are to be fetched.

    Returns:
        dict: A dictionary of models and their respective counts, or an empty dictionary if none found.
    """
    try:
        url = "https://www.autotrader.ca/Home/Refine"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-US,en;q=0.9',
            'AllowMvt': 'true'
        }
        # Using cookies from the response
        cookies = {
            'atOptUser': 'db0860a4-b562-4270-9ed0-b2d2875c873c',
            'nlbi_820541_1646237': 'Z30UdORIkUeQlTEnZpjQsQAAAACqH714EnL/JlzmRPTWgXMX'
        }
        payload = {
            "IsDealer": True,
            "IsPrivate": True,
            "InMarketType": "basicSearch",
            "Address": "Rockland",
            "Proximity": -1,
            "Make": make,
            "Model": None,
            "IsNew": True,
            "IsUsed": True,
            "IsCpo": True,
            "IsDamaged": False,
            "WithPhotos": True,
            "WithPrice": True,
            "HasDigitalRetail": False
        }

        # Sending POST request with headers and cookies
        response = requests.post(url, json=payload, headers=headers, cookies=cookies)
        response.raise_for_status()  # Raise HTTPError for bad responses

        data = response.json()

        # Extract and return models from the response
        return data.get("Models", {})
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while making the request: {e}")
        return {}
    except ValueError as e:
        print(f"Failed to parse JSON response: {e}")
        return {}

# Example usage
make = "Acura"
models = get_models_for_make_via_request(make)
if models:
    print(f"Models for {make}:", models)
else:
    print(f"No models found for make: {make}")
