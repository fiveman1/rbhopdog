# rbhop_api.py
import datetime
import json
import os
import requests
from dotenv import load_dotenv

import files
from tree import MapTree

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
    "a" : 1,
    "scroll" : 2,
    "s" : 2,
    "sideways" : 3,
    "sw" : 3,
    "half-sideways" : 4,
    "hsw" : 4,
    "half" : 4,
    "w-only" : 5,
    "wonly" : 5,
    "wo" : 5,
    "w" : 5,
    "a-only" : 6,
    "aonly" : 6,
    "ao" : 6,
    "backwards" : 7,
    "bw" : 7,
    "faste" : 8,
    1 : 1,
    2 : 2,
    3 : 3,
    4 : 4,
    5 : 5,
    6 : 6,
    7 : 7,
    8 : 8
}

style_id_to_string = {
    1 : "autohop",
    2 : "scroll",
    3 : "sideways",
    4 : "half-sideways",
    5 : "w-only",
    6 : "a-only",
    7 : "backwards",
    8 : "faste"
}

games = {
    "maptest" : 0,
    "bhop" : 1,
    "surf" : 2,
    0 : 0,
    1 : 1,
    2 : 2
}

game_id_to_string = {
    0 : "maptest",
    1 : "bhop",
    2 : "surf"
}

ranks = ("New","Newb","Bad","Okay","Not Bad","Decent","Getting There","Advanced","Good","Great","Superb","Amazing","Sick","Master","Insane","Majestic","Baby Jesus","Jesus","Half God","God")

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

# hash table for id -> displayname because each id is unique
map_lookup = {}
for map in bhop_maps:
    map_lookup[map["ID"]] = map["DisplayName"]
for map in surf_maps:
    map_lookup[map["ID"]] = map["DisplayName"]

def update_maps():
    files.write_maps("bhop")
    bhop_maps = open_json("files/bhop_maps.json")
    for map in bhop_maps:
        map_lookup[map["ID"]] = map["DisplayName"]
    files.write_maps("surf")
    surf_maps = open_json("files/surf_maps.json")
    for map in surf_maps:
        map_lookup[map["ID"]] = map["DisplayName"]

def map_name_from_id(map_id, game):
    try:
        return map_lookup[map_id]
    except:
        return "Missing map"

# bst for displayname -> id so that users can enter partial names (i.e. "adven" -> "Adventure v2" -> id)
# MapTree is designed for such operations
# was this necessary over just iterating a list? ...probably not. But it's cool, right?
bhop_map_to_id = MapTree()
for map in bhop_maps:
    bhop_map_to_id.add(map["DisplayName"], map["ID"])

bhop_map_to_id.print()

surf_map_to_id = MapTree()
for map in surf_maps:
    surf_map_to_id.add(map["DisplayName"], map["ID"])

def map_id_from_name(map_name, game):
    game = games[game]
    if game == 1:
        return bhop_map_to_id.get(map_name)
    elif game == 2:
        return surf_map_to_id.get(map_name)
    return -1

def map_dict_from_id(map_id, game):
    game = games[game]
    if game == 1:
        map_data = bhop_maps
    elif game == 2:
        map_data = surf_maps
    for m in map_data:
        if m["ID"] == map_id:
            return m
    return "Map id not found"

class Record():
    def __init__(self, id, time, user_id, map_id, date, style, mode, game, user=None):
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
        self.previous_record = None
        if user == None:
            username, _ = get_user_data(user_id)
            self.username = username
        else:
            self.username = user

def get(end_of_url, params):
    res = requests.get(URL + end_of_url, headers=headers, params=params)
    if not res:
        print(res)
        print(res.text)
        raise Exception("Request failed")
    else:
        return res

def get_user_data(user):
    if type(user) == int:
        res = requests.get(f"https://api.roblox.com/users/{user}")
        try:
            data = res.json()
            return data["Username"], data["Id"]
        except KeyError:
            raise Exception("Invalid user ID")
        except:
            raise Exception("Error getting user data")
    else:
        res = requests.get(f"https://api.roblox.com/users/get-by-username?username={user}")
        try:
            data = res.json()
            return data["Username"], data["Id"]
        except KeyError:
            raise Exception("Invalid username")
        except:
            raise Exception("Error getting user data")

#takes time value as input from json in miliseconds
def format_time(time):
    if time > 86400000:
        return ">1 day"
    milis = format_helper(time % 1000, 3)
    seconds = format_helper((time // 1000) % 60, 2)
    minutes = format_helper((time // (1000 * 60)) % 60, 2)
    hours = format_helper((time // (1000 * 60 * 60)) % 24, 2)
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

def get_recent_wrs(game, style):
    game = games[game]
    style = styles[style]
    res = get("time/recent/wr", {
        "game":game,
        "style":style
    })
    data = res.json()
    return make_record_list(data)

#can input userID as int or username as string
def get_user_wrs(user, game, style):
    username, user_id = get_user_data(user)
    res = get(f"time/user/{user_id}/wr", {
        "game":games[game],
        "style":styles[style]
    })
    data = res.json()
    if data:
        return make_record_list(data, username)
    else:
        return []

#returns a record object of a user's time on a given map
def get_user_record(user, game, style, map_name=""):
    if map_name == "":
        return get_user_wrs(user, game, style)
    _, user_id = get_user_data(user)
    map_id = map_id_from_name(map_name, game)
    res = get(f"time/user/{user_id}", {
        "game":games[game],
        "style":styles[style],
        "map":map_id
    })
    data = res.json()
    if len(data) == 0:
        return None
    else:
        return convert_to_record(data[0])

def total_wrs(user, game, style):
    _, user_id = get_user_data(user)
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
    _, user_id = get_user_data(user)
    res = get(f"rank/{user_id}", {
        "game":games[game],
        "style":styles[style]
    })
    data = res.json()
    return convert_rank(data)

def find_max_pages(url, params, page_count, page_length, custom_page_length):
    params["page"] = page_count
    res = get(url, params)
    data = res.json()
    if len(data) > 0:
        converted_page_count = int(((page_count - 1) * (page_length / custom_page_length)) + ((len(data) - 1) // custom_page_length) + 1)
        return converted_page_count
    else:
        return 0

#returns 25 ranks at a given page number, page 1: top 25, page 2: 26-50, etc.
def get_ranks(game, style, page):
    params = {
        "game":games[game],
        "style":styles[style],
        "page":(int((page - 1) / 2)) + 1
    }
    page_length = 25
    res = get("rank", params)
    data = res.json()
    if len(data) > 0:
        page_count = int(res.headers["Pagination-Count"])
        converted_page_count = find_max_pages("rank", params, page_count, 50, page_length)
    else:
        params["page"] = 1
        first_page_res = get("rank", params)
        if len(first_page_res.json()) == 0:
            return [], 0
        else:
            page_count = int(first_page_res.headers["Pagination-Count"])
            converted_page_count = find_max_pages("rank", params, page_count, 50, page_length)
    ls = []
    if page % 2 == 1:
        data = data[:25]
    elif page % 2 == 0:
        data = data[25:]
    for i in data:
        user, _ = get_user_data(i["User"])
        r, rank, skill, placement, = convert_rank(i)
        ls.append({"Username": user, "R": r, "Rank": rank, "Skill": skill, "Placement": placement})
    return ls, converted_page_count

def get_user_times(user, game, style, page):
    if page == -1:
        i = 1
        params = {"page":i}
        if game != None:
            params["game"] = games[game]
        if style != None:
            params["style"] = styles[style]
        _, userid = get_user_data(user)
        times_ls = []
        while True:
            params["page"] = i
            res = get(f"time/user/{userid}", params)
            data = res.json()
            if len(data) == 0:
                break
            else:
                times_ls += data
                i += 1
        return make_record_list(times_ls, user), i - 1
    page_length = 25
    page_num, start = divmod((int(page) - 1) * page_length, 200)
    end = start + 25
    params = {"page":page_num + 1}
    if game != None:
        params["game"] = games[game]
    if style != None:
        params["style"] = styles[style]
    _, userid = get_user_data(user)
    res = get(f"time/user/{userid}", params) 
    data = res.json()
    if len(data) > 0:
        page_count = int(res.headers["Pagination-Count"])
        converted_page_count = find_max_pages(f"time/user/{userid}", params, page_count, 200, page_length)
    else:
        params["page"] = 1
        first_page_res = get(f"time/user/{userid}", params)
        if len(first_page_res.json()) == 0:
            return [], 0
        else:
            page_count = int(first_page_res.headers["Pagination-Count"])
            converted_page_count = find_max_pages(f"time/user/{userid}", params, page_count, 200, page_length)
            page_num, start = divmod((int(converted_page_count) - 1) * page_length, 200)
            end = start + 25
            params["page"] = page_count
            data = get(f"time/user/{userid}", params).json()
    return make_record_list(data[start:end], user), converted_page_count

def get_user_completion(user, game, style):
    records, _ = get_user_times(user, game, style, -1)
    completions = len(records)
    if game == "bhop":
        return completions, len(bhop_maps)
    else:
        return completions, len(surf_maps)

def convert_rank(data):
    if data == None:
        return 0,0,0,0
    else:
        r = 1 + int(float(data["Rank"]) * 19)
        rank = ranks[r - 1]
        skill = round(float(data["Skill"]) * 100.0, 3)
        return r, rank, skill, data["Placement"]

#records is a list of records from a given map
def sort_map(records):
    records.sort(key=lambda i: (i["Time"], i["Date"]))

#changes a WR's diff and previous_record in place by comparing first and second place
#times on the given map
def calculate_wr_diff(record):
    res = get(f"time/map/{record.map_id}", {
        "style":record.style,
    })
    data = res.json()
    sort_map(data)
    if len(data) > 1:
        second = convert_to_record(data[1])
        record.diff = round((int(second.time) - int(record.time)) / 1000.0, 3)
        record.previous_record = second

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
                        "style":style,
                        "whitelist":True
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
                    r.previous_record = convert_to_record(match)
                    globals_ls.append(r)
                #we can break here because the lists are sorted in the same fashion
                else:
                    break
            else:
                r = convert_to_record(record)
                calculate_wr_diff(r)
                # if r.diff != -1.0 or get(f"user/{r.user_id}", {}).json()["State"] == 1:
                globals_ls.append(r)

    #overwrite recent_wrs.json with new wrs if they exist
    if len(globals_ls) > 0:
        with open(fix_path("files/recent_wrs.json"), "w") as file:
            json.dump(new_wrs, file)
        file.close()
    return sorted(globals_ls, key = lambda i: i.date, reverse=True)

def get_map_times(game, style, map_name, page):
    page_length = 25
    page_num, start = divmod((int(page) - 1) * page_length, 200)
    map_id = map_id_from_name(map_name, game)
    params = {
        "style":styles[style],
        "page":page_num + 1
    }
    res = get(f"time/map/{map_id}", params)
    data = res.json()
    if len(data) > 0:
        page_count = int(res.headers["Pagination-Count"])
        params["page"] = page_count
        converted_page_count = find_max_pages(f"time/map/{map_id}", params, page_count, 200, page_length)
    else:
        params["page"] = 1
        first_page_res = get(f"time/map/{map_id}", params)
        if len(first_page_res.json()) == 0:
            return [], 0
        else:
            page_count = int(first_page_res.headers["Pagination-Count"])
            params["page"] = page_count
            converted_page_count = find_max_pages(f"time/map/{map_id}", params, page_count, 200, page_length)
            return [], converted_page_count
    #add the previous and next page so that we can sort the times across pages properly
    res2data = []
    if page_num > 0:
        params["page"] = page_num
        res2 = get(f"time/map/{map_id}", params)
        res2data = res2.json()
        data = res2data + data
    if page_num + 2 <= converted_page_count:
        params["page"] = page_num + 2
        res3 = get(f"time/map/{map_id}", params)
        data += res3.json()
    sort_map(data)
    start += len(res2data)
    end = start + page_length
    return make_record_list(data[start:end]), converted_page_count

def get_user(user):
    _, user_id = get_user_data(user)
    return get(f"user/{user_id}", {}).json()

def get_record_placement(record:Record):
    params = {
        "style":record.style,
        "page":1
    }
    first_page_res = get(f"time/map/{record.map_id}", params)
    page_count = int(first_page_res.headers["Pagination-Count"])
    completions = 0
    if page_count == 1:
        completions = len(first_page_res.json())
    else:
        params["page"] = page_count
        last_page_res = get(f"time/map/{record.map_id}", params)
        completions = len(last_page_res.json()) + (page_count - 1) * 200
    return get(f"time/{record.id}/rank", {}).json()["Rank"], completions