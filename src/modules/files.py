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

#game better be "bhop" or "surf"
def write_maps(game):
    game_id = game
    if game == "bhop":
        game_id = 1
    else:
        game_id = 2
    page = 1
    map_data = []
    while True:
        maps = get("map", {
            "game":game_id,
            "page":page
        }).json()
        if len(maps) == 0:
            break
        else:
            map_data += maps
            page += 1
    with open(fix_path(f"files/{game}_maps.json"), "w") as file:
        json.dump(map_data, file)
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