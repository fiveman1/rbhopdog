# writemaps.py
import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY")

URL = "https://api.strafes.net/v1/"

def fix_path(path):
    return os.path.abspath(os.path.expanduser(path))

headers = {
    "api-key":API_KEY,
}

def get(end_of_url, params):
    res = requests.get(URL + end_of_url, headers=headers, params=params)
    if not res:
        print(res)
        print(res.text)
        raise Exception("Request failed")
    else:
        return res

def write_bhop_maps():
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

    with open(fix_path("files/bhop_maps.json"), "w") as file:
        json.dump(bhop_map_data, file)
    file.close()

def write_surf_maps():
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

    with open(fix_path("files/surf_maps.json"), "w") as file:
        json.dump(surf_map_data, file)
    file.close()

def write_wrs():
    wrs_data = []
    for game in range(1,3):
        for style in range(1,8):
            if not (game == 2 and style == 2): #skip surf/scroll
                wrs = get("time/recent/wr", {
                        "game":game,
                        "style":style
                    })
                wrs_data.append(wrs.json())
    # LIST OF LIST OF WRS, EACH LIST IS A GAME AND STYLE
    with open(fix_path("files/recent_wrs.json"), "w") as file:
        json.dump(wrs_data, file)
    file.close()