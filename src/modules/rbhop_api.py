# rbhop_api.py
import datetime
import json
import os
import requests
from dotenv import load_dotenv

import files

load_dotenv()
API_KEY = os.getenv("API_KEY")

def fix_path(path):
    return os.path.abspath(os.path.expanduser(path))

URL = "https://api.strafes.net/v1/"

headers = {
    "api-key":API_KEY,
}

styles = {
    "autohop" : 1,
    "auto" : 1,
    "scroll" : 2,
    "sideways" : 3,
    "sw" : 3,
    "half-sideways" : 4,
    "hsw" : 4,
    "half" : 4,
    "w-only" : 5,
    "wonly" : 5,
    "w" : 5,
    "a-only" : 6,
    "aonly" : 6,
    "a" : 6,
    "backwards" : 7,
    "bw" : 7,
    1 : 1,
    2 : 2,
    3 : 3,
    4 : 4,
    5 : 5,
    6 : 6,
    7 : 7
}

style_id_to_string = {
    1 : "autohop",
    2 : "scroll",
    3 : "sideways",
    4 : "half-sideways",
    5 : "w-only",
    6 : "a-only",
    7 : "backwards"
}

games = {
    "bhop" : 1,
    "surf" : 2,
    1 : 1,
    2 : 2
}

game_id_to_string = {
    1 : "bhop",
    2 : "surf"
}

ranks = ["New","Newb","Bad","Okay","Not Bad","Decent","Getting There","Advanced","Good","Great","Superb","Amazing","Sick","Master","Insane","Majestic","Baby Jesus","Jesus","Half God","God"]

def open_json(path):
    with open(fix_path(path)) as file:
        data = file.read()
        return json.loads(data)

bhop_maps = {}
try:
    bhop_maps = open_json("files/bhop_maps.json")
except FileNotFoundError:
    files.write_maps("bhop")
    bhop_maps = open_json("files/bhop_maps.json")

surf_maps = {}
try:
    surf_maps = open_json("files/surf_maps.json")
except FileNotFoundError:
    files.write_maps("surf")
    surf_maps = open_json("files/surf_maps.json")

#since dicts are sorta glorified hash tables we can optimize id -> displayname lookup
#by storing this data in a dict; now the operation should be O(1) instead of O(n)
bhop_map_lookup = {}
for map in bhop_maps:
    bhop_map_lookup[map["ID"]] = map["DisplayName"]

surf_map_lookup = {}
for map in surf_maps:
    surf_map_lookup[map["ID"]] = map["DisplayName"]

def map_name_from_id(map_id, game):
    game = games[game]
    if game == 1:
        return bhop_map_lookup[map_id]
    elif game == 2:
        return surf_map_lookup[map_id]
    return "Map name not found"

def map_id_from_name(map_name, game):
    game = games[game]
    if game == 1:
        map_data = bhop_maps
    elif game == 2:
        map_data = surf_maps
    for m in map_data:
        if m["DisplayName"] == map_name:
            return m["ID"]
    return "Map id not found"

class Record():
    def __init__(self, id, time, user_id, map_id, date, style, mode, game, username=None):
        self.id = id
        self.time = time
        self.user_id = user_id
        self.map_id = map_id
        self.date = date
        self.style = style
        self.mode = mode
        self.game = game
        self.map_name = map_name_from_id(self.map_id, self.game)
        self.date_string = convert_date(self.date)
        self.time_string = format_time(self.time)
        self.style_string = style_id_to_string[self.style]
        self.game_string = game_id_to_string[self.game]
        self.diff = -1.0
        if username == None:
            self.username = username_from_id(self.user_id)
        else:
            self.username = username

def get(end_of_url, params):
    res = requests.get(URL + end_of_url, headers=headers, params=params)
    if not res:
        print(res)
        print(res.text)
        raise Exception("Request failed")
    else:
        return res

def username_from_id(user_id):
    res = requests.get(f"https://api.roblox.com/users/{user_id}")
    data = res.json()
    try:
        return data["Username"]
    except KeyError:
        raise Exception("Invalid user ID")

def id_from_username(username):
    res = requests.get(f"https://api.roblox.com/users/get-by-username?username={username}")
    data = res.json()
    try:
        return data["Id"]
    except KeyError:
        raise Exception("Invalid username")

def get_user_username_id(user):
    username = ""
    user_id = 0
    if type(user) == str:
        user_id = id_from_username(user)
        username = user
    else:
        user_id = user
        username = username_from_id(user)
    return username, user_id

#takes time value as input from json in miliseconds
def format_time(time):
    milis = format_helper(int(time % 1000), 3)
    seconds = format_helper(int((time / 1000) % 60), 2)
    minutes = format_helper(int((time / (1000 * 60)) % 60), 2)
    hours = format_helper(int((time / (1000 * 60 * 60)) % 24), 2)
    if hours == "00":
        return minutes + ":" + seconds + "." + milis
    else:
        return hours + ":" + minutes + ":" + seconds

def format_helper(time, digits):
    time = str(time)
    while len(time) < digits:
        time = "0" + time
    return time

def convert_date(date):
    return datetime.datetime.fromtimestamp(date).strftime('%Y-%m-%d %H:%M:%S')

#records is a list of dicts made from json output from rbhop api
def make_record_list(records, username=None):
    if records == None:
        return None
    ls = []
    for record in records:
        ls.append(convert_to_record(record, username))
    return ls

def convert_to_record(record, username=None):
    return Record(
        record["ID"],
        record["Time"],
        record["User"],
        record["Map"],
        record["Date"],
        record["Style"],
        record["Mode"],
        record["Game"],
        username
    )

def sexy_format(record_list):
    records = len(record_list)
    s = f"Total records: {records}\n"
    titles = ["Username:", "Time:", "Date", "Map name:", "Style:", "Game:"]
    s += f"{titles[0]:15}| {titles[1]:10}| {titles[2]:20}| {titles[3]:20}| {titles[4]:14}| Game\n"
    for record in record_list:
        username = record.username[:15]
        time = record.time_string[:10]
        date = record.date_string[:20]
        map_name = record.map_name[:20]
        style = record.style_string[:14]
        game = record.game_string
        s += f"{username:15}| {time:10}| {date:20}| {map_name:20}| {style:14}| {game}\n"
    return s[:-1]

def page_records(record_list, sort="name"):
    if sort == "name":
        record_list = sorted(record_list, key = lambda i: i.map_name) #sort by map name
    elif sort == "date":
        record_list = sorted(record_list, key = lambda i: i.date, reverse=True) #sort by date (most recent)
    elif sort == "time":
        record_list = sorted(record_list, key = lambda i: i.time) #sort by time
    elif sort == "style":
        record_list = sorted(record_list, key = lambda i: i.style) #style
    s = sexy_format(record_list) #get raw string
    ls = []
    lines = s.split("\n")
    items = len(lines)
    length = 0
    page = ""
    i = 0
    #add each line together until the total length exceeds 1900
    #then create a new string (message)
    while i < items:
        while i < items and length < 1900:
            page += lines[i] + "\n"
            length += len(lines[i]) + 2
            i += 1
        ls.append(page)
        length = 0
        page = ""
    return ls

def get_recent_wrs(game, style):
    try:
        game = games[game]
    except:
        raise Exception("Invalid game")
    try:
        style = styles[style]
    except:
        raise Exception("Invalid style")
    res = get("time/recent/wr", {
        "game":game,
        "style":style
    })
    data = res.json()
    return make_record_list(data)

#can input userID as int or username as string
def get_user_wrs(user, game, style):
    username, user_id = get_user_username_id(user)
    res = get(f"time/user/{user_id}/wr", {
        "game":games[game],
        "style":styles[style]
    })
    data = res.json()
    return make_record_list(data, username)

def get_user_record(user, game, style, map_name=""):
    if map_name == "":
        return get_user_wrs(user, game, style)
    _, user_id = get_user_username_id(user)
    map_id = map_id_from_name(map_name, game)
    res = get(f"time/user/{user_id}", {
        "game":games[game],
        "style":styles[style],
        "map":map_id
    })
    data = res.json()
    return make_record_list(data)

def total_wrs(user, game, style):
    _, user_id = get_user_username_id(user)
    res = get(f"time/user/{user_id}/wr", {
        "game":games[game],
        "style":styles[style]
    })
    data = res.json()
    if data == None:
        return 0
    else:
        return len(data)

def get_user_rank(user, game, style):
    _, user_id = get_user_username_id(user)
    res = get(f"rank/{user_id}", {
        "game":games[game],
        "style":styles[style]
    })
    data = res.json()
    if data == None:
        return "User has no rank/times."
    else:
        r = int(float(data["Rank"]) * 20)
        if r == 0:
            return 0,0,0
        rank = ranks[r - 1]
        skill = round(float(data["Skill"]) * 100.0, 3)
        #return f"{username}\nRank: {rank} ({r}), Skill: {skill:.3f}%"
        return r, rank, skill

#returns the difference between 1st and 2nd place on a given map in seconds
def calculate_wr_diff(map_id, style):
    res = get(f"time/map/{map_id}", {
        "style":style,
    })
    data = res.json()
    if len(data) > 1:
        first = convert_to_record(data[0])
        second = convert_to_record(data[1])
        return round((int(second.time) - int(first.time)) / 1000.0, 3)
    #if there is only one time on the map someone is the only person to beat it
    #so there is no time to compare it to for diff
    else:
        return "n/a"

def search(ls, record):
    for i in ls:
        if record["ID"] == i["ID"]:
            return i
    return None

def get_new_wrs():
    new_wrs = []
    for game in range(1,3):
        for style in range(1,8):
            if not (game == 2 and style == 2): #skip surf/scroll
                wrs = get("time/recent/wr", {
                        "game":game,
                        "style":style
                    })
                new_wrs.append(wrs.json())
    old_wrs = []
    try:
        old_wrs = open_json("files/recent_wrs.json")
    except FileNotFoundError:
        files.write_wrs()
        return []
    globals_ls = []
    for i in range(len(new_wrs)):
        for record in new_wrs[i]:
            match = search(old_wrs[i], record)
            if match:
                #records by the same person on the same map have the same id even if they beat it
                if record["Time"] != match["Time"]:
                    r = convert_to_record(record)
                    r.diff = round((int(match["Time"]) - int(record["Time"])) / 1000.0, 3)
                    globals_ls.append(r)
                #we can break here because the lists are sorted in the same fashion
                else:
                    break
            else:
                r = convert_to_record(record)
                r.diff = calculate_wr_diff(record["Map"], record["Style"])
                globals_ls.append(r)
    #overwrite recent_wrs.json with new wrs if they exist
    if len(globals_ls) > 0:
        with open(fix_path("files/recent_wrs.json"), "w") as file:
            json.dump(new_wrs, file)
        file.close()
    return globals_ls

def get_map_times(game, style, map_name):
    map_id = map_id_from_name(map_name, game)
    return get(f"time/map/{map_id}", {
        "style":styles[style]
    }).json()

def get_user(user):
    _, user_id = get_user_username_id(user)
    return get(f"user/{user_id}", {}).json()

def bot_get_recent_wrs(game, style):
    return sexy_format(get_recent_wrs(game, style))

def bot_get_user_wrs(user, game, style):
    return page_records(get_user_wrs(user, game, style))

def bot_get_user_record(user, game, style, map_name):
    return sexy_format(get_user_record(user, game, style, map_name))