import requests
import json

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

query = """
[out:json][timeout:180];
area["ISO3166-1"="IR"]->.iran;
(
  node["tourism"~"hotel|hostel|guest_house"](area.iran);
  way["tourism"~"hotel|hostel|guest_house"](area.iran);
);
out center tags;

"""

response = requests.post(OVERPASS_URL, data=query)
response.raise_for_status()

data = response.json()

with open("hotels_raw.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("✅ hotels_raw.json created")
