# writemaps.py
import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY")

URL = "https://api.strafes.net/v1/"

headers = {
    "api-key":API_KEY,
}

def get(end_of_url, params):
    res = requests.get(URL + end_of_url, headers=headers, params=params)
    if not res:
        print(res)
        print(res.text)
        raise Exception("request failed")
    else:
        return res

bhop_maps = get("map", {
    "game":"1",
    "page":"1"
})
total_pages = int(bhop_maps.headers["Pagination-Count"])
bhop_map_data = bhop_maps.json()
for i in range(2, total_pages + 1):
    m = get("map", {
        "game":"1",
        "page":str(i)
    })
    bhop_map_data = bhop_map_data + m.json()

with open("..\\files\\bhop_maps.json", "w") as file:
    json.dump(bhop_map_data, file)
file.close()

surf_maps = get("map", {
    "game":"2",
    "page":"1"
})
total_pages = int(surf_maps.headers["Pagination-Count"])
surf_map_data = surf_maps.json()
for i in range(2, total_pages + 1):
    m = get("map", {
        "game":"2",
        "page":str(i)
    })
    surf_map_data = surf_map_data + m.json()

with open("..\\files\\surf_maps.json", "w") as file:
    json.dump(surf_map_data, file)
file.close()
