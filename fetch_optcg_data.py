import os
import json
import time
import requests
from typing import Dict, Any, List

# Configuration
BASE_URL = "https://www.optcgapi.com"
DATA_DIR = "optcg_data"

# Endpoints mapping based on API documentation
ENDPOINTS = {
    "sets": "/api/allSets/",
    "set_cards": "/api/allSetCards/",
    "decks": "/api/allDecks/",
    "starter_cards": "/api/allSTCards/",
    "promo_cards": "/api/allPromoCards/",  # Will fallback to /api/allPromos/ if needed
    "don_cards": "/api/allDonCards/"
}

def fetch_data(endpoint: str, retries: int = 3) -> Any:
    """Fetches data from a specific API endpoint with fallback and retry support (Item 10)."""
    url = f"{BASE_URL}{endpoint}"
    print(f"Fetching from {url}...")
    
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404 and endpoint == "/api/allPromoCards/":
                fallback_url = f"{BASE_URL}/api/allPromos/"
                print(f"Failed with 404. Trying fallback: {fallback_url}...")
                fallback_resp = requests.get(fallback_url, timeout=30)
                if fallback_resp.status_code == 200:
                    return fallback_resp.json()
            
            print(f"Warning: Attempt {attempt}/{retries} received status code {response.status_code} from {url}")
        except requests.exceptions.RequestException as e:
            print(f"Network error on attempt {attempt}/{retries} for {url}: {e}")
        except json.JSONDecodeError:
            print(f"JSON decode error on attempt {attempt}/{retries} for {url}")

        if attempt < retries:
            backoff = 2 ** (attempt - 1)  # 1s, 2s, 4s...
            print(f"Retrying in {backoff} seconds...")
            time.sleep(backoff)

    print(f"Error: All {retries} attempts failed for {url}")
    return None

def save_json(data: Any, filename: str):
    """Saves the retrieved data into a JSON file inside the data directory."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    filepath = os.path.join(DATA_DIR, filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"Successfully saved {len(data)} items to {filepath}")
    except Exception as e:
        print(f"Error saving file {filepath}: {e}")

def main():
    print("Starting OPTCG API Data Downloader...")
    
    for name, endpoint in ENDPOINTS.items():
        data = fetch_data(endpoint)
        if data:
            save_json(data, f"{name}.json")
        else:
            print(f"Could not retrieve data for {name}.")
        
        time.sleep(1)

    print("\nDownload process completed.")
    print(f"All downloaded data has been saved in the '{DATA_DIR}' folder.")

if __name__ == "__main__":
    main()
