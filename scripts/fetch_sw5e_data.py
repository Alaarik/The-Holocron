import json
import os
import urllib.request

API_BASE = "https://sw5eapi.azurewebsites.net/api/"
RES_DIR = os.path.join(os.path.dirname(__file__), "..", "res")

def fetch_data(endpoint, filename):
    print(f"Fetching {endpoint}...")
    req = urllib.request.Request(API_BASE + endpoint, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            filepath = os.path.join(RES_DIR, filename)
            with open(filepath, "w") as f:
                json.dump(data, f, indent=4)
            print(f"Saved {len(data)} records to {filename}.")
    except Exception as e:
        print(f"Failed to fetch {endpoint}: {e}")

if __name__ == "__main__":
    os.makedirs(RES_DIR, exist_ok=True)
    fetch_data("power", "spells.json")  # Mapped to spells.json for backward comp
    fetch_data("species", "races.json")
    fetch_data("class", "classes.json")
    fetch_data("archetype", "subclasses.json")
    fetch_data("feat", "feats.json")
    fetch_data("background", "backgrounds.json")
    fetch_data("monster", "monsters.json")
    fetch_data("equipment", "adventuring-gear.json")  # Might need splitting or custom logic
    fetch_data("enhancedItem", "magic-items.json")
