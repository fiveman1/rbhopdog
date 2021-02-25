# rbhop_api.py
import datetime
from discord.errors import InvalidData
from dotenv import load_dotenv
from enum import Enum
import json
import os
import requests
from requests.models import Response
from typing import Dict, List, Optional, Tuple, Union

from modules import files

load_dotenv()
API_KEY = os.getenv("API_KEY")

URL = "https://api.strafes.net/v1/"

headers = {
    "api-key":API_KEY,
}

# TODO: turn these into enums or something
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

def fix_path(path):
    return os.path.abspath(os.path.expanduser(path))

def open_json(path):
    with open(fix_path(path)) as file:
        data = file.read()
        return json.loads(data)

# TODO: convert stuff that uses map_name and map_id to Map objects and also implement that :)
class Map:
    bhop_map_pairs = []
    surf_map_pairs = []
    bhop_map_count = 0
    surf_map_count = 0
    # hash table for id -> displayname because each id is unique
    map_lookup = {}

    @staticmethod
    def setup_maps():
        files.write_maps("bhop")
        files.write_maps("surf")
        bhop_maps = open_json("files/bhop_maps.json")
        surf_maps = open_json("files/surf_maps.json")

        Map.bhop_map_count = len(bhop_maps)
        Map.surf_map_count = len(surf_maps)

        Map.bhop_map_pairs.clear()
        Map.surf_map_pairs.clear()

        for map in bhop_maps:
            Map.bhop_map_pairs.append((map["DisplayName"].lower(), map["ID"]))
        Map.bhop_map_pairs.sort(key=lambda i: i[0])

        for map in surf_maps:
            Map.surf_map_pairs.append((map["DisplayName"].lower(), map["ID"]))
        Map.surf_map_pairs.sort(key=lambda i: i[0])

        Map.map_lookup.clear()
        for map in bhop_maps:
            Map.map_lookup[map["ID"]] = map

        for map in surf_maps:
            Map.map_lookup[map["ID"]] = map

    # ls should be sorted
    # performs an iterative binary search
    # returns the first index where the item was found according to the compare function
    @staticmethod
    def find_item(ls, compare):
        left = 0
        right = len(ls) - 1
        while left <= right:
            middle = (left + right) // 2
            res = compare(ls[middle])
            if res == 0:
                return middle
            elif res < 0:
                left = middle + 1
            else:
                right = middle - 1
        return -1

    @staticmethod
    def compare_maps(name, map_name):
        if map_name.startswith(name):
            return 0
        elif map_name < name:
            return -1
        else:
            return 1

    @staticmethod
    def id_from_name(name, ls):
        name = name.lower()
        idx = Map.find_item(ls, lambda m : Map.compare_maps(name, m[0]))
        if idx != -1:
            while idx > 0:
                if ls[idx-1][0].startswith(name):
                    idx -= 1
                else:
                    break
            return ls[idx][1]
        else:
            return -1

    @staticmethod
    def map_id_from_name(map_name, game):
        game = games[game]
        if game == 1:
            return Map.id_from_name(map_name, Map.bhop_map_pairs)
        elif game == 2:
            return Map.id_from_name(map_name, Map.surf_map_pairs)
        return -1

    @staticmethod
    def map_dict_from_id(map_id):
        try:
            return Map.map_lookup[map_id]
        except:
            return "Missing map"

    @staticmethod
    def map_name_from_id(map_id):
        try:
            return Map.map_lookup[map_id]["DisplayName"]
        except:
            return "Missing map"

Map.setup_maps()

class Rank:
    __ranks__ = ("New","Newb","Bad","Okay","Not Bad","Decent","Getting There","Advanced","Good","Great","Superb","Amazing","Sick","Master","Insane","Majestic","Baby Jesus","Jesus","Half God","God")

    def __init__(self, rank, skill, placement):
        self.rank = rank
        self.rank_string = Rank.__ranks__[self.rank - 1]
        self.skill = skill
        self.placement = placement
    @staticmethod
    def from_dict(data):
        return Rank(
            1 + int(float(data["Rank"]) * 19),
            round(float(data["Skill"]) * 100.0, 3),
            data["Placement"]
        )

class Record:
    def __init__(self, id, time, user_id, username, map_id, date, style, mode, game):
        self.id = id
        self.time = time
        self.user_id = user_id
        self.username = username
        self.map_id = map_id
        self.date = date
        self.style = style
        self.mode = mode
        self.game = game
        self.map_name = Map.map_name_from_id(self.map_id)
        self.date_string = convert_date(self.date)
        self.time_string = format_time(self.time)
        self.style_string = style_id_to_string[self.style]
        self.game_string = game_id_to_string[self.game]
        self.diff = -1.0
        self.previous_record = None
    @staticmethod
    def from_dict(d, username:Optional[str]=None) -> "Record":
        if not username:
            username = get_user_data(d["User"]).username
        return Record(
            d["ID"],
            d["Time"],
            d["User"],
            username,
            d["Map"],
            d["Date"],
            d["Style"],
            d["Mode"],
            d["Game"]
        )
    @staticmethod
    def make_record_list(records, username=None) -> List["Record"]:
        ls = []
        if username:
            for record in records:
                ls.append(Record.from_dict(record, username))
        else:
            user_ids = []
            for record in records:
                user_ids.append(record["User"])
            user_lookup = get_user_data_from_list(user_ids)
            for record in records:
                ls.append(Record.from_dict(record, user_lookup[record["User"]].username))
        return ls

class User:
    def __init__(self):
        self.id = -1
        self.username = ""
        self.displayname = ""
        self.state = UserState.DEFAULT
    @staticmethod
    def from_dict(d) -> "User":
        user = User()
        user.id = d["id"]
        user.username = d["name"]
        user.displayname = d["displayName"]
        return user

class UserState(Enum):
    DEFAULT = 0
    WHITELISTED = 1
    BLACKLISTED = 2
    PENDING = 3
    def __str__(self):
        return self.name.lower()

def get(end_of_url, params) -> Response:
    return requests.get(URL + end_of_url, headers=headers, params=params)

def get_user_data(user : Union[str, int]) -> User:
    if type(user) == int:
        res = requests.get(f"https://users.roblox.com/v1/users/{user}")
        if res.status_code == 404:
            raise InvalidData("Invalid user ID")
        try:
            data = res.json()
            return User.from_dict(data)
        except:
            raise TimeoutError("Error getting user data")
    else:
        res = requests.post("https://users.roblox.com/v1/usernames/users", data={"usernames":[user]})
        d = res.json()
        if not d:
            raise TimeoutError("Error getting user data")
        else:
            data = d["data"]
            if len(data) > 0:
                return User.from_dict(data[0])
            else:
                raise InvalidData("Invalid username")

def get_user_data_from_list(users) -> Dict[int, User]:
    res = requests.post("https://users.roblox.com/v1/users", data={"userIds":users})
    if res:
        user_lookup = {}
        for user_dict in res.json()["data"]:
            user = User.from_dict(user_dict)
            user_lookup[user_dict["id"]] = user
        return user_lookup
    else:
        raise TimeoutError("Error getting user data")

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

def get_recent_wrs(game, style) -> List[Record]:
    game = games[game]
    style = styles[style]
    res = get("time/recent/wr", {
        "game":game,
        "style":style
    })
    data = res.json()
    return Record.make_record_list(data)

def get_user_wrs(user_data:User, game, style) -> List[Record]:
    res = get(f"time/user/{user_data.id}/wr", {
        "game":games[game],
        "style":styles[style]
    })
    data = res.json()
    if data:
        return Record.make_record_list(data, user_data.username)
    else:
        return []

#returns a record object of a user's time on a given map
def get_user_record(user_data:User, game, style, map_name="") -> Optional[Record]:
    if map_name == "":
        return get_user_wrs(user_data, game, style)
    map_id = Map.map_id_from_name(map_name, game)
    res = get(f"time/user/{user_data.id}", {
        "game":games[game],
        "style":styles[style],
        "map":map_id
    })
    data = res.json()
    if len(data) == 0:
        return None
    else:
        return Record.from_dict(data[0], user_data.username)

def total_wrs(user_data:User, game, style) -> int:
    res = get(f"time/user/{user_data.id}/wr", {
        "game":games[game],
        "style":styles[style]
    })
    data = res.json()
    if data == None:
        return 0
    else:
        return len(data)

def get_user_rank(user_data:User, game, style) -> Optional[Rank]:
    res = get(f"rank/{user_data.id}", {
        "game":games[game],
        "style":styles[style]
    })
    data = res.json()
    if data == None:
        return None
    else:
        return Rank.from_dict(data)

def find_max_pages(url, params, page_count, page_length, custom_page_length) -> int:
    params["page"] = page_count
    res = get(url, params)
    data = res.json()
    if len(data) > 0:
        converted_page_count = int(((page_count - 1) * (page_length / custom_page_length)) + ((len(data) - 1) // custom_page_length) + 1)
        return converted_page_count
    else:
        return 0

#returns 25 ranks at a given page number, page 1: top 25, page 2: 26-50, etc.
def get_ranks(game, style, page) -> Tuple[List[Tuple[str, Rank]], int]:
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
    users = []
    for i in data:
        users.append(i["User"])
    user_lookup = get_user_data_from_list(users)
    for i in data:
        ls.append((user_lookup[i["User"]].username, Rank.from_dict(i)))
    return ls, converted_page_count

def get_user_times(user_data:User, game, style, page) -> Tuple[List[Record], int]:
    if page == -1:
        i = 1
        params = {"page":i}
        if game != None:
            params["game"] = games[game]
        if style != None:
            params["style"] = styles[style]
        times_ls = []
        while True:
            params["page"] = i
            res = get(f"time/user/{user_data.id}", params)
            data = res.json()
            if len(data) == 0:
                break
            else:
                times_ls += data
                i += 1
        return Record.make_record_list(times_ls, user_data.username), i - 1
    page_length = 25
    page_num, start = divmod((int(page) - 1) * page_length, 200)
    end = start + 25
    params = {"page":page_num + 1}
    if game != None:
        params["game"] = games[game]
    if style != None:
        params["style"] = styles[style]
    res = get(f"time/user/{user_data.id}", params) 
    data = res.json()
    if len(data) > 0:
        page_count = int(res.headers["Pagination-Count"])
        converted_page_count = find_max_pages(f"time/user/{user_data.id}", params, page_count, 200, page_length)
    else:
        params["page"] = 1
        first_page_res = get(f"time/user/{user_data.id}", params)
        if len(first_page_res.json()) == 0:
            return [], 0
        else:
            page_count = int(first_page_res.headers["Pagination-Count"])
            converted_page_count = find_max_pages(f"time/user/{user_data.id}", params, page_count, 200, page_length)
            page_num, start = divmod((int(converted_page_count) - 1) * page_length, 200)
            end = start + 25
            params["page"] = page_count
            data = get(f"time/user/{user_data.id}", params).json()
    return Record.make_record_list(data[start:end], user_data.username), converted_page_count

def get_user_completion(user_data:User, game, style) -> Tuple[int, int]:
    records, _ = get_user_times(user_data, game, style, -1)
    completions = len(records)
    if game == "bhop":
        return completions, Map.bhop_map_count
    else:
        return completions, Map.surf_map_count

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
        second = Record.from_dict(data[1])
        record.diff = round((int(second.time) - int(record.time)) / 1000.0, 3)
        record.previous_record = second

def search(ls, record):
    for i in ls:
        if record["ID"] == i["ID"]:
            return i
    return None

def get_new_wrs() -> List[Record]:
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
                    r = Record.from_dict(record)
                    r.diff = round((int(match["Time"]) - int(record["Time"])) / 1000.0, 3)
                    r.previous_record = Record.from_dict(match)
                    globals_ls.append(r)
                #we can break here because the lists are sorted in the same fashion
                else:
                    break
            else:
                r = Record.from_dict(record)
                calculate_wr_diff(r)
                globals_ls.append(r)

    #overwrite recent_wrs.json with new wrs if they exist
    if len(globals_ls) > 0:
        with open(fix_path("files/recent_wrs.json"), "w") as file:
            json.dump(new_wrs, file)
        file.close()
    return sorted(globals_ls, key = lambda i: i.date, reverse=True)

def get_map_times(game, style, map_name, page) -> Tuple[List[Record], int]:
    page_length = 25
    page_num, start = divmod((int(page) - 1) * page_length, 200)
    map_id = Map.map_id_from_name(map_name, game)
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
    return Record.make_record_list(data[start:end]), converted_page_count

def get_user_state(user_data:User) -> Response:
    return get(f"user/{user_data.id}", {})

def get_record_placement(record:Record) -> Tuple[int, int]:
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