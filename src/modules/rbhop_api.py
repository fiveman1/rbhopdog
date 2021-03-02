# rbhop_api.py
import asyncio
import aiohttp
import datetime
from discord.errors import InvalidData
from dotenv import load_dotenv
from enum import Enum
import json
import os
import requests
from requests.models import Response
from typing import Dict, List, Optional, Tuple, Union

from modules.utils import Incrementer

load_dotenv()
API_KEY = os.getenv("API_KEY")

URL = "https://api.strafes.net/v1/"

headers = {
    "api-key":API_KEY,
}

def fix_path(path):
    return os.path.abspath(os.path.expanduser(path))

def open_json(path):
    with open(fix_path(path)) as file:
        data = file.read()
        return json.loads(data)

async def get_strafes(session:aiohttp.ClientSession, end_of_url, params={}) -> aiohttp.ClientResponse:
    return await session.get(f"https://api.strafes.net/v1/{end_of_url}", headers=headers, params=params)

def get(end_of_url, params) -> Response:
    return requests.get(URL + end_of_url, headers=headers, params=params)

class Time:
    def __init__(self, millis:int):
        self.millis = millis
        self._time_str = Time.format_time(millis)

    def __str__(self):
        return self._time_str

    @staticmethod
    def format_time(time):
        if time > 86400000:
            return ">1 day"
        millis = Time.format_helper(time % 1000, 3)
        seconds = Time.format_helper((time // 1000) % 60, 2)
        minutes = Time.format_helper((time // (1000 * 60)) % 60, 2)
        hours = Time.format_helper((time // (1000 * 60 * 60)) % 24, 2)
        if hours == "00":
            return minutes + ":" + seconds + "." + millis
        else:
            return hours + ":" + minutes + ":" + seconds

    @staticmethod
    def format_helper(time, digits):
        time = str(time)
        while len(time) < digits:
            time = "0" + time
        return time

class Date:
    def __init__(self, timestamp):
        self.timestamp:int = timestamp
        self._date_str = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

    def __str__(self):
        return self._date_str

def create_str_to_val(dict):
    str_to_val = {}
    for key, values in dict.items():
        for value in values:
            str_to_val[value] = key
    return str_to_val

_GAMES = {
    0: ["maptest"],
    1: ["bhop"],
    2: ["surf"]
}
_STR_TO_GAME = create_str_to_val(_GAMES)

class Game(Enum):
    MAPTEST = 0
    BHOP = 1
    SURF = 2

    @property
    def name(self):
        return _GAMES[self.value][0]

    def __str__(self):
        return self.name

    @staticmethod
    def contains(obj):
        return obj in Game._value2member_map_ if isinstance(obj, int) else obj in _STR_TO_GAME

setattr(Game, "__new__", lambda cls, value: super(Game, cls).__new__(cls, _STR_TO_GAME[value] if isinstance(value, str) else value))
DEFAULT_GAMES:List[Game] = [Game.BHOP, Game.SURF]

_STYLES = {
    1: ["autohop", "auto", "a"],
    2: ["scroll", "s"],
    3: ["sideways", "sw"],
    4: ["half-sideways", "hsw", "half"],
    5: ["w-only", "wonly", "wo", "w"],
    6: ["a-only", "aonly", "ao"],
    7: ["backwards", "bw"],
    8: ["faste"]
}
_STR_TO_STYLE = create_str_to_val(_STYLES)

class Style(Enum):
    AUTOHOP = 1
    SCROLL = 2
    SIDEWAYS = 3
    HSW = 4
    WONLY = 5
    AONLY = 6
    BACKWARDS = 7
    FASTE = 8

    @property
    def name(self):
        return _STYLES[self.value][0]
        
    def __str__(self):
        return self.name

    @staticmethod
    def contains(obj):
        return obj in Style._value2member_map_ if isinstance(obj, int) else obj in _STR_TO_STYLE

# This allows us to get an enum via the value, name, or name alias (ex. Style(1), Style("autohop"), Style("auto"))
setattr(Style, "__new__", lambda cls, value: super(Style, cls).__new__(cls, _STR_TO_STYLE[value] if isinstance(value, str) else value))
DEFAULT_STYLES:List[Style] = [style for style in Style if style != Style.FASTE]

class Map:
    bhop_map_pairs:List[Tuple[str, "Map"]] = []
    surf_map_pairs:List[Tuple[str, "Map"]] = []
    bhop_map_count:int = 0
    surf_map_count:int = 0
    # hash table for id -> displayname because each id is unique
    map_lookup:Dict[int, "Map"] = {}

    def __init__(self, id, displayname, creator, game, date, playcount):
        self.id:int = id
        self.displayname:str = displayname
        self.creator:str = creator
        self.game:Game = game
        self.date:Date = date
        self.playcount:int = playcount

    def __str__(self):
        return self.displayname

    @staticmethod
    def from_dict(d) -> "Map":
        return Map(
            d["ID"],
            d["DisplayName"],
            d["Creator"],
            Game(d["Game"]),
            Date(d["Date"]),
            d["PlayCount"]
        )

    @staticmethod
    async def write_maps():
        async with aiohttp.ClientSession() as session:
            first_bhop = get_strafes(session, "map", {
                "game":Game.BHOP.value,
                "page":1
            })
            first_surf = get_strafes(session, "map", {
                "game":Game.SURF.value,
                "page":1
            })
            tasks = [first_bhop, first_surf]
            responses = await asyncio.gather(*tasks)
            bhop_data = await responses[0].json()
            surf_data = await responses[1].json()
            bhop_pages = int(responses[0].headers["Pagination-Count"])
            surf_pages = int(responses[1].headers["Pagination-Count"])
            async def mapper(game, page):
                res = get_strafes(session, "map", {
                    "game":game.value,
                    "page":page
                })
                return game, await res
            page = Incrementer(1)
            tasks = []
            while page.increment() < bhop_pages:
                tasks.append(mapper(Game.BHOP, page.get()))
            page = Incrementer(1)
            while page.increment() < surf_pages:
                tasks.append(mapper(Game.SURF, page.get()))
            responses = await asyncio.gather(*tasks)
            for game, res in responses:
                if game == Game.BHOP:
                    bhop_data += await res.json()
                elif game == Game.SURF:
                    surf_data += await res.json()
            with open(fix_path("files/bhop_maps.json"), "w") as file:
                json.dump(bhop_data, file)
            with open(fix_path("files/surf_maps.json"), "w") as file:
                json.dump(surf_data, file)

    @staticmethod
    async def setup_maps():
        try:
            bhop_maps = open_json("files/bhop_maps.json")
            surf_maps = open_json("files/surf_maps.json")
        except:
            await Map.write_maps()
            bhop_maps = open_json("files/bhop_maps.json")
            surf_maps = open_json("files/surf_maps.json")

        Map.bhop_map_count = len(bhop_maps)
        Map.surf_map_count = len(surf_maps)

        Map.bhop_map_pairs.clear()
        Map.surf_map_pairs.clear()
        Map.map_lookup.clear()

        for m in bhop_maps:
            map = Map.from_dict(m)
            Map.bhop_map_pairs.append((map.displayname.lower(), map))
            Map.map_lookup[map.id] = map
        Map.bhop_map_pairs.sort(key=lambda i: i[0])

        for m in surf_maps:
            map = Map.from_dict(m)
            Map.surf_map_pairs.append((map.displayname.lower(), map))
            Map.map_lookup[map.id] = map
        Map.surf_map_pairs.sort(key=lambda i: i[0])

    @staticmethod
    async def update_maps():
        await Map.write_maps()
        await Map.setup_maps()

    # ls should be sorted
    # performs an iterative binary search
    # returns the first index where the item was found according to the compare function
    @staticmethod
    def _find_item(ls, compare):
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
    def _compare_maps(name, map_name):
        if map_name.startswith(name):
            return 0
        elif map_name < name:
            return -1
        else:
            return 1

    @staticmethod
    def _from_name(name, ls):
        name = name.lower()
        idx = Map._find_item(ls, lambda m : Map._compare_maps(name, m[0]))
        if idx != -1:
            while idx > 0:
                if ls[idx-1][0].startswith(name):
                    idx -= 1
                else:
                    break
            return ls[idx][1]
        else:
            return None

    @staticmethod
    def from_name(map_name:str, game:Game) -> Optional["Map"]:
        if game == Game.BHOP:
            return Map._from_name(map_name, Map.bhop_map_pairs)
        elif game == Game.SURF:
            return Map._from_name(map_name, Map.surf_map_pairs)
        return None

    @staticmethod
    def from_id(map_id:int) -> "Map":
        try:
            return Map.map_lookup[map_id]
        except KeyError:
            return Map(-1, "Missing map", "", Game.BHOP, -1, -1)

asyncio.get_event_loop().run_until_complete(Map.setup_maps())

class Rank:
    __ranks__ = ("New","Newb","Bad","Okay","Not Bad","Decent","Getting There","Advanced","Good","Great","Superb","Amazing","Sick","Master","Insane","Majestic","Baby Jesus","Jesus","Half God","God")

    def __init__(self, rank, skill, placement, user):
        self.rank:int = rank
        self.skill:float = skill
        self.placement:int = placement
        self.user:User = user
        self._rank_string = Rank.__ranks__[self.rank - 1]

    def __str__(self):
        return self._rank_string

    @staticmethod
    def from_dict(data, user:"User"):
        return Rank(
            1 + int(float(data["Rank"]) * 19),
            round(float(data["Skill"]) * 100.0, 3),
            data["Placement"],
            user
        )

class Record:
    def __init__(self, id, time, user, map, date, style, mode, game):
        self.id:int = id
        self.time:Time = time
        self.user:User = user
        self.map:Map = map
        self.date:Date = date
        self.style:Style = style
        self.mode:int = mode
        self.game:Game = game
        self.diff:float = -1.0
        self.previous_record:Record = None

    def __str__(self):
        return f"Time: {self.time}\nMap: {self.map}\nUser: {self.user}\nGame: {self.game}, style: {self.style}"

    #include user or map if they are known already
    @staticmethod
    def from_dict(d, user:"User"=None, map:Map=None) -> "Record":
        if not user:
            user = User.get_user_data(d["User"])
        if not map:
            map = Map.from_id(d["Map"])
        return Record(
            d["ID"],
            Time(d["Time"]),
            user,
            map,
            Date(d["Date"]),
            Style(d["Style"]),
            d["Mode"],
            Game(d["Game"])
        )

    #include user or map if they are known already
    @staticmethod
    def make_record_list(records:List, user:"User"=None, map:Map=None) -> List["Record"]:
        ls = []
        id_to_user = None
        if not user:
            user_ids = set()
            for record in records:
                user_ids.add(record["User"])
            id_to_user = User.get_user_data_from_list(list(user_ids))
        for record in records:
            if not user:
                ls.append(Record.from_dict(record, user=id_to_user[record["User"]], map=map))
            else:
                ls.append(Record.from_dict(record, user=user, map=map))
        return ls

class User:
    def __init__(self):
        self.id = -1
        self.username = ""
        self.displayname = ""
        self.state = UserState.DEFAULT

    def __str__(self):
        return self.username

    @staticmethod
    def from_dict(d) -> "User":
        user = User()
        user.id = d["id"]
        user.username = d["name"]
        user.displayname = d["displayName"]
        return user

    @staticmethod
    def get_user_data(user : Union[str, int]) -> "User":
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

    @staticmethod
    def get_user_data_from_list(users:List[int]) -> Dict[int, "User"]:
        res = requests.post("https://users.roblox.com/v1/users", data={"userIds":users})
        if res:
            user_lookup = {}
            for user_dict in res.json()["data"]:
                user = User.from_dict(user_dict)
                user_lookup[user_dict["id"]] = user
            return user_lookup
        else:
            raise TimeoutError("Error getting user data")

class UserState(Enum):
    DEFAULT = 0
    WHITELISTED = 1
    BLACKLISTED = 2
    PENDING = 3

    @property
    def name(self):
        return super().name.lower()
        
    def __str__(self):
        return self.name

def get_recent_wrs(game:Game, style:Style) -> List[Record]:
    res = get("time/recent/wr", {
        "game":game.value,
        "style":style.value,
        "whitelist":"true"
    })
    data = res.json()
    return Record.make_record_list(data)

async def get_user_wrs(user_data:User, game:Game, style:Style) -> List[Record]:
    async with aiohttp.ClientSession() as session:
        res = await get_strafes(session, f"time/user/{user_data.id}/wr", {
            "game":game.value,
            "style":style.value
        })
        data = await res.json()
        if data:
            return Record.make_record_list(data, user=user_data)
        else:
            return []

#returns a record object of a user's time on a given map
def get_user_record(user_data:User, game:Game, style:Style, map:Map) -> Optional[Record]:
    res = get(f"time/user/{user_data.id}", {
        "game":game.value,
        "style":style.value,
        "map":map.id
    })
    data = res.json()
    if len(data) == 0:
        return None
    else:
        return Record.from_dict(data[0], user=user_data)

async def total_wrs(user_data:User, game:Game, style:Style) -> int:
    async with aiohttp.ClientSession() as session:
        res = await get_strafes(session, f"time/user/{user_data.id}/wr", {
            "game":game.value,
            "style":style.value
        })
        data = await res.json()
        if data:
            return len(data)
        else:
            return 0

async def get_user_rank(user_data:User, game:Game, style:Style) -> Optional[Rank]:
    async with aiohttp.ClientSession() as session:
        res = await get_strafes(session, f"rank/{user_data.id}", {
            "game":game.value,
            "style":style.value
        })
        data = await res.json()
        if data:
            return Rank.from_dict(data, user_data)
        else:
            return None

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
def get_ranks(game:Game, style:Style, page:int) -> Tuple[List[Rank], int]:
    params = {
        "game":game.value,
        "style":style.value,
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
            params["page"] = page_count
            data = get("rank", params).json()
            page = converted_page_count
    ls = []
    if page % 2 == 1:
        data = data[:25]
    elif page % 2 == 0:
        data = data[25:]
    users = []
    for i in data:
        users.append(i["User"])
    user_lookup = User.get_user_data_from_list(users)
    for i in data:
        ls.append(Rank.from_dict(i, user_lookup[i["User"]]))
    return ls, converted_page_count

def find_max_page(last_page, page_count, real_page_length, custom_page_length) -> int:
    return int(((page_count - 1) * (real_page_length / custom_page_length)) + ((len(last_page) - 1) // custom_page_length) + 1)

async def get_user_times(user_data:User, game:Optional[Game], style:Optional[Style], page:int) -> Tuple[List[Record], int]:
    async with aiohttp.ClientSession() as session:
        url = f"time/user/{user_data.id}"
        params = {"page":1}
        if game is not None:
            params["game"] = game.value
        if style is not None:
            params["style"] = style.value
        first_page_res = await get_strafes(session, url, params)
        first_page_data = await first_page_res.json()
        if len(first_page_data) == 0:
            return [], 0
        pagination_count = int(first_page_res.headers["Pagination-Count"])
        if page == -1:
            tasks = []
            the_page = Incrementer(1)
            while the_page.increment() < pagination_count:
                params_copy = params.copy()
                params_copy["page"] = the_page.get()
                tasks.append(get_strafes(session, url, params_copy))
            responses = await asyncio.gather(*tasks)
            results = first_page_data
            for response in responses:
                results += await response.json()
            return Record.make_record_list(results, user=user_data), -1
        else:
            page_length = 25
            the_real_page, start = divmod((int(page) - 1) * page_length, 200)
            the_real_page += 1
            end = start + page_length
            the_page_data = None
            last_page_data = None
            if pagination_count == 1:
                the_page_data = first_page_data
                last_page_data = first_page_data
            elif the_real_page == 1:
                the_page_data = first_page_data
                params["page"] = pagination_count
                the_res = await get_strafes(session, url, params)
                last_page_data = await the_res.json()
            elif the_real_page >= pagination_count:
                params["page"] = pagination_count
                the_res = await get_strafes(session, url, params)
                last_page_data = await the_res.json()
                the_page_data = last_page_data
            else:
                tasks = []
                params_copy = params.copy()
                params_copy["page"] = the_real_page
                tasks.append(get_strafes(session, url, params_copy))
                params_copy = params.copy()
                params_copy["page"] = pagination_count
                tasks.append(get_strafes(session, url, params_copy))
                responses = await asyncio.gather(*tasks)
                the_page_data = await responses[0].json()
                last_page_data = await responses[1].json()           
            max_page = find_max_page(last_page_data, pagination_count, 200, page_length)
            if page > max_page:
                start = ((int(max_page) - 1) * page_length) % 200
                end = start + page_length
            return Record.make_record_list(the_page_data[start:end], user=user_data), max_page

async def get_user_completion(user_data:User, game:Game, style:Style) -> Tuple[int, int]:
    records, _ = await get_user_times(user_data, game, style, -1)
    completions = len(records)
    if game == Game.BHOP:
        return completions, Map.bhop_map_count
    elif game == Game.SURF:
        return completions, Map.surf_map_count
    else:
        return completions, 1

#records is a list of records from a given map
def sort_map(records:List):
    records.sort(key=lambda i: (i["Time"], i["Date"]))

#changes a WR's diff and previous_record in place by comparing first and second place
#times on the given map
async def calculate_wr_diff(session, record:Record):
    res = await get_strafes(session, f"time/map/{record.map.id}", {
        "style":record.style.value,
    })
    data = await res.json()
    data = data[:20]
    if len(data) > 1:
        sort_map(data)
        record.previous_record = Record.from_dict(data[1])
        record.diff = round((record.time.millis - record.previous_record.time.millis) / 1000.0, 3)

# returns a list of lists of wrs, each list is a unique game/style combination
async def get_wrs():
    async with aiohttp.ClientSession() as session:
        tasks = []
        for game in DEFAULT_GAMES:
            for style in DEFAULT_STYLES:
                if not (game == Game.SURF and style == Style.SCROLL):
                    tasks.append(get_strafes(session, "time/recent/wr", {
                            "game":game.value,
                            "style":style.value,
                            "whitelist":"true"
                        }))
        wrs = []
        responses = await asyncio.gather(*tasks)
        for res in responses:
            wrs.append(await res.json())
        return wrs

async def write_wrs():
    with open(fix_path("files/recent_wrs.json"), "w") as file:
        json.dump(await get_wrs(), file)

def search(ls, record):
    for i in ls:
        if record["ID"] == i["ID"]:
            return i
    return None

async def get_new_wrs() -> List[Record]:
    try:
        old_wrs = open_json("files/recent_wrs.json")
    except FileNotFoundError:
        await write_wrs()
        return []
    new_wrs = await get_wrs()
    globals:List[Record] = []
    for i in range(len(new_wrs)):
        for record in new_wrs[i]:
            match = search(old_wrs[i], record)
            if match:
                #records by the same person on the same map have the same id even if they beat it
                if record["Time"] != match["Time"]:
                    r = Record.from_dict(record)
                    r.diff = round((int(record["Time"]) - int(match["Time"])) / 1000.0, 3)
                    r.previous_record = Record.from_dict(match)
                    globals.append(r)
                #we can break here because the lists are sorted in the same fashion
                else:
                    break
            else:
                globals.append(Record.from_dict(record))
    async with aiohttp.ClientSession() as session:
        tasks = []
        for wr in globals:
            if not wr.previous_record:
                tasks.append(calculate_wr_diff(session, wr))
        await asyncio.gather(*tasks)

    #overwrite recent_wrs.json with new wrs if they exist
    if len(globals) > 0:
        with open(fix_path("files/recent_wrs.json"), "w") as file:
            json.dump(new_wrs, file)
    globals.sort(key = lambda i: i.date.timestamp)
    return globals

# TODO: optimize this to reduce unnecessary api calls
def get_map_times(style:Style, map:Map, page:int) -> Tuple[List[Record], int]:
    page_length = 25
    page_num, start = divmod((int(page) - 1) * page_length, 200)
    params = {
        "style":style.value,
        "page":page_num + 1
    }
    res = get(f"time/map/{map.id}", params)
    data = res.json()
    if len(data) > 0:
        page_count = int(res.headers["Pagination-Count"])
        params["page"] = page_count
        converted_page_count = find_max_pages(f"time/map/{map.id}", params, page_count, 200, page_length)
    else:
        params["page"] = 1
        first_page_res = get(f"time/map/{map.id}", params)
        if len(first_page_res.json()) == 0:
            return [], 0
        else:
            page_count = int(first_page_res.headers["Pagination-Count"])
            params["page"] = page_count
            converted_page_count = find_max_pages(f"time/map/{map.id}", params, page_count, 200, page_length)
            data = get(f"time/map/{map.id}", params).json()
    #add the previous and next page so that we can sort the times across pages properly
    res2data = []
    if page_num > 0:
        params["page"] = page_num
        res2 = get(f"time/map/{map.id}", params)
        res2data = res2.json()
        data = res2data + data
    if page_num + 2 <= converted_page_count:
        params["page"] = page_num + 2
        res3 = get(f"time/map/{map.id}", params)
        data += res3.json()
    sort_map(data)
    if page > converted_page_count:
        start = ((int(converted_page_count) - 1) * page_length) % 200
    start += len(res2data)
    end = start + page_length
    return Record.make_record_list(data[start:end], map=map), converted_page_count

async def get_user_state(user_data:User) -> Tuple[aiohttp.ClientResponse, Dict]:
    async with aiohttp.ClientSession() as session:
        res = await get_strafes(session, f"user/{user_data.id}", {})
        return res, await res.json()

def get_record_placement(record:Record) -> Tuple[int, int]:
    params = {
        "style":record.style.value,
        "page":1
    }
    first_page_res = get(f"time/map/{record.map.id}", params)
    page_count = int(first_page_res.headers["Pagination-Count"])
    completions = 0
    if page_count == 1:
        completions = len(first_page_res.json())
    else:
        params["page"] = page_count
        last_page_res = get(f"time/map/{record.map.id}", params)
        completions = len(last_page_res.json()) + (page_count - 1) * 200
    return get(f"time/{record.id}/rank", {}).json()["Rank"], completions