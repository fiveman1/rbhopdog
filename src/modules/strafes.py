# strafes.py
from aiocache import cached
import aiohttp
from aiorwlock import RWLock
import asyncio
import datetime
import json
import random
from typing import Any, Dict, List, Optional, Tuple, Union

from modules.strafes_base import *
from modules.utils import Incrementer, fix_path, open_json

class APIError(Exception):

    def __init__(self, url, headers, params, status, body, api_name, msg=""):
        if not msg:
            msg = f"An error occurred attempting to use the {api_name} API."
        super().__init__(msg)
        self.url = url
        self.headers = headers
        self.params = params
        self.status = status
        self.body = body
    
    def create_debug_message(self):
        s = ["API error debug:", str(self.__class__), f"URL: {self.url}", f"Headers: {self.headers}", f"Params: {self.params}", f"Status: {self.status}", f"Body: {self.body}"]
        return "\n".join(s)

class TimeoutError(APIError):
    def __init__(self, timeout, url, headers, params, api_name):
        super().__init__(url, headers, params, "n/a", "n/a", api_name, f"A timeout occurred attempting to use the {api_name} API after {timeout} seconds.")

class NotFoundError(Exception):

    def __init__(self):
        super().__init__("404 Not Found")

class MapsNotLoadedError(Exception):

    def __init__(self):
        super().__init__("Tried to access maps before loading them! Call await client.load_maps() first!")

class SessionHandler:

    def __init__(self, timeout, id):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout))
        self.lock = asyncio.Lock()
        self.active_count : int = 0
        self.needs_closing : bool = False
        self.id = id

    def close(self):
        if not self.session:
            return
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.session.close())
            else:
                loop.run_until_complete(self.session.close())
        except Exception:
            pass

    def __del__(self):
        self.close()

    async def try_close(self):
        async with self.lock:
            # print(f"[ID: {self.id}] In try close")
            self.needs_closing = True
            if self.active_count == 0:
                # print(f"[ID: {self.id}] try_close closing")
                await self.session.close()
            else:
                pass
                # print(f"[ID: {self.id}] Not closing (active: {self.active_count})")

    async def __aenter__(self) -> "SessionHandler":
        async with self.lock:
            self.active_count += 1
            # print(f"[ID: {self.id}] In aenter (active: {self.active_count})")
            return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        async with self.lock:
            self.active_count -= 1
            # print(f"[ID: {self.id}] In aexit (active: {self.active_count})")
            if self.needs_closing and self.active_count == 0:
                # print(f"[ID: {self.id}] aexit closing")
                await self.session.close()

class JSONRes:
    def __init__(self, res:aiohttp.ClientResponse, json):
        self.res = res
        self.json = json

class StrafesClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.last_session_created : datetime.datetime = None
        self._handler : SessionHandler = None
        self.lock = asyncio.Lock()
        self.bhop_map_pairs : List[Tuple[str, Map]] = []
        self.surf_map_pairs : List[Tuple[str, Map]] = []
        self.bhop_map_count : int = 0
        self.surf_map_count : int = 0
        # hash table for id -> displayname because each id is unique
        self.map_lookup : Dict[int, Map] = {}
        self.maps_loaded : bool = False
        self.map_lock = RWLock()

    def close(self):
        if self._handler:
            self._handler.close()

    def __del__(self):
        self.close()

    @property
    async def handler(self) -> SessionHandler:
        async with self.lock:
            if self.last_session_created:
                time = datetime.datetime.now()
                if (time - self.last_session_created).total_seconds() > 59:
                    await self._handler.try_close()
                    self._handler = SessionHandler(20, self._handler.id + 1)
                    self.last_session_created = time
            else:
                self._handler = SessionHandler(20, 1)
                self.last_session_created = datetime.datetime.now()
            return self._handler

    async def get_request(self, url, api_name, params={}, headers={}) -> JSONRes:
        async with await self.handler as handler:
            session = handler.session
            try:
                async with session.get(url, headers=headers, params=params) as res:
                    if res.status == 404:
                        raise NotFoundError()
                    elif res.status < 200 or res.status >= 300:
                        try:
                            body = await res.text()
                        except:
                            body = "n/a"
                        raise APIError(url, headers, params, res.status, body, api_name)
                    try:
                        json = await res.json()
                        return JSONRes(res, json)
                    except aiohttp.ContentTypeError:
                        raise APIError(url, headers, params, res.status, await res.text(), api_name)
            except asyncio.TimeoutError:
                raise TimeoutError(session.timeout.total, url, headers, params, api_name)

    async def post_request(self, url, api_name, data={}, headers={}) -> JSONRes:
        async with await self.handler as handler:
            session = handler.session
            try:
                async with session.post(url, headers=headers, data=data) as res:
                    if res.status == 404:
                        raise NotFoundError()
                    elif res.status < 200 or res.status >= 300:
                        try:
                            body = await res.text()
                        except:
                            body = "n/a"
                        raise APIError(url, headers, data, res.status, body, api_name)
                    try:
                        json = await res.json()
                        return JSONRes(res, json)
                    except aiohttp.ContentTypeError:
                        raise APIError(url, headers, data, res.status, await res.text(), api_name)
            except asyncio.TimeoutError:
                raise TimeoutError(session.timeout.total, url, headers, data, api_name)

    async def get_strafes(self, end_of_url, params={}) -> JSONRes:
        return await self.get_request(f"https://api.strafes.net/v1/{end_of_url}", "strafes.net", params, {"api-key":self.api_key})

    async def _map_mapper(self, game : Game, page : int):
        res = self.get_strafes("map", {
            "game":game.value,
            "page":page
        })
        return game, await res

    async def load_maps(self):
        first_bhop = self.get_strafes("map", {
            "game":Game.BHOP.value,
            "page":1
        })
        first_surf = self.get_strafes("map", {
            "game":Game.SURF.value,
            "page":1
        })
        tasks = [first_bhop, first_surf]
        data : List[JSONRes] = await asyncio.gather(*tasks)
        bhop_maps = data[0].json
        surf_maps = data[1].json
        bhop_pages = int(data[0].res.headers["Pagination-Count"])
        surf_pages = int(data[1].res.headers["Pagination-Count"])

        tasks = []
        page = Incrementer(1)
        while page.increment() < bhop_pages:
            tasks.append(self._map_mapper(Game.BHOP, page.get()))
        page = Incrementer(1)
        while page.increment() < surf_pages:
            tasks.append(self._map_mapper(Game.SURF, page.get()))
        responses : List[Tuple[Game, JSONRes]] = await asyncio.gather(*tasks)
        for game, res in responses:
            if game == Game.BHOP:
                bhop_maps += res.json
            elif game == Game.SURF:
                surf_maps += res.json
        
        async with self.map_lock.writer_lock:
            self.bhop_map_count = len(bhop_maps)
            self.surf_map_count = len(surf_maps)

            self.bhop_map_pairs.clear()
            self.surf_map_pairs.clear()
            self.map_lookup.clear()

            for m in bhop_maps:
                map = Map.from_dict(m)
                self.bhop_map_pairs.append((map.displayname.lower(), map))
                self.map_lookup[map.id] = map
            self.bhop_map_pairs.sort(key=lambda i: i[0])

            for m in surf_maps:
                map = Map.from_dict(m)
                self.surf_map_pairs.append((map.displayname.lower(), map))
                self.map_lookup[map.id] = map
            self.surf_map_pairs.sort(key=lambda i: i[0])
            self.maps_loaded = True

    # ls should be sorted
    # performs an iterative binary search
    # returns the first index where the item was found according to the compare function
    @staticmethod
    def _find_item(ls, compare) -> int:
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
    def _compare_maps(name : str, map_name : str) -> int:
        if map_name.startswith(name):
            return 0
        elif map_name < name:
            return -1
        else:
            return 1

    @staticmethod
    def _map_from_name(name : str, ls : List[Tuple[str, Map]]) -> Optional[Map]:
        name = name.lower()
        idx = StrafesClient._find_item(ls, lambda m : StrafesClient._compare_maps(name, m[0]))
        if idx != -1:
            while idx > 0:
                if ls[idx-1][0].startswith(name):
                    idx -= 1
                else:
                    break
            return ls[idx][1]
        else:
            the_map = None
            shortest_name = None
            for map_name, m in ls:
                if name in map_name and (shortest_name is None or len(map_name) < len(shortest_name)):
                    shortest_name = map_name
                    the_map = m
            return the_map

    async def map_from_name(self, map_name : str, game : Optional[Game]) -> Optional[Map]:
        async with self.map_lock.reader_lock:
            if not self.maps_loaded:
                raise MapsNotLoadedError()
            if game == Game.BHOP:
                return self._map_from_name(map_name, self.bhop_map_pairs)
            elif game == Game.SURF:
                return self._map_from_name(map_name, self.surf_map_pairs)
            elif game is None:
                res = self._map_from_name(map_name, self.bhop_map_pairs)
                if res is None:
                    res = self._map_from_name(map_name, self.surf_map_pairs)
                return res
            return None

    async def map_from_id(self, map_id:int) -> Map:
        async with self.map_lock.reader_lock:
            if not self.maps_loaded:
                raise MapsNotLoadedError()
            try:
                return self.map_lookup[map_id]
            except KeyError:
                return Map(-1, "Missing map", "", Game.BHOP, -1, -1)

    async def get_map_count(self, game : Game) -> int:
        async with self.map_lock.reader_lock:
            if not self.maps_loaded:
                raise MapsNotLoadedError()
            if game == Game.BHOP:
                return self.bhop_map_count
            elif game == Game.SURF:
                return self.surf_map_count
            else:
                return 1

    async def get_maps_by_creator(self, creator : Optional[str]) -> List[Map]:
        async with self.map_lock.reader_lock:
            if not self.maps_loaded:
                raise MapsNotLoadedError()
            if not creator:
                return list(self.map_lookup.values())
            creator = creator.lower()
            matches = []
            for map in self.map_lookup.values():
                if creator in map.creator.lower():
                    matches.append(map)
            return matches

    async def get_all_maps(self) -> List[Map]:
         async with self.map_lock.reader_lock:
            if not self.maps_loaded:
                raise MapsNotLoadedError()
            return list(self.map_lookup.values())

    @cached(ttl=60*60)
    async def get_user_data(self, user : Union[str, int]) -> User:
        if type(user) == int:
            res = await self.get_request(f"https://users.roblox.com/v1/users/{user}", "Roblox Users")
            return User.from_dict(res.json)
        else:
            res = await self.post_request("https://users.roblox.com/v1/usernames/users", "Roblox Users", {"usernames":[user]})
            data = res.json["data"]
            if len(data) > 0:
                return User.from_dict(data[0])
            else:
                raise NotFoundError()

    async def get_user_data_from_list(self, users : List[int]) -> Dict[int, User]:
        res = await self.post_request("https://users.roblox.com/v1/users", "Roblox Users", {"userIds":users})
        user_lookup = {}
        for user_dict in res.json["data"]:
            user = User.from_dict(user_dict)
            user_lookup[user_dict["id"]] = user
        return user_lookup

    #include user or map if they are known already
    async def record_from_dict(self, d, user : User = None, map : Map = None) -> Record:
        if not user:
            user = await self.get_user_data(d["User"])
        if not map:
            map = await self.map_from_id(d["Map"])
        return Record.from_dict(d, user, map)

    #include user or map if they are known already
    async def make_record_list(self, records : List, user : User = None, map : Map = None) -> List[Record]:
        ls = []
        id_to_user = None
        if not user:
            user_ids = set()
            for record in records:
                user_ids.add(record["User"])
            id_to_user = await self.get_user_data_from_list(list(user_ids))
        for record in records:
            if not user:
                ls.append(await self.record_from_dict(record, user=id_to_user[record["User"]], map=map))
            else:
                ls.append(await self.record_from_dict(record, user=user, map=map))
        return ls

    async def get_recent_wrs(self, game:Game, style:Style) -> List[Record]:
        res = await self.get_strafes("time/recent/wr", {
            "game":game.value,
            "style":style.value,
            "whitelist":"true"
        })
        return await self.make_record_list(res.json)

    async def get_user_wrs(self, user_data:User, game:Game, style:Style) -> List[Record]:
        res = await self.get_strafes(f"time/user/{user_data.id}/wr", {
            "game":game.value,
            "style":style.value
        })
        if res.json:
            return await self.make_record_list(res.json, user=user_data)
        else:
            return []

    #returns a record object of a user's time on a given map
    async def get_user_record(self, user_data:User, game:Game, style:Style, map:Map) -> Optional[Record]:
        res = await self.get_strafes(f"time/user/{user_data.id}", {
            "game":game.value,
            "style":style.value,
            "map":map.id
        })
        if len(res.json) == 0:
            return None
        else:
            return await self.record_from_dict(res.json[0], user=user_data)

    async def total_wrs(self, user_data:User, game:Game, style:Style) -> int:
        res = await self.get_strafes(f"time/user/{user_data.id}/wr", {
            "game":game.value,
            "style":style.value
        })
        if res.json:
            return len(res.json)
        else:
            return 0

    async def get_user_rank(self, user_data:User, game:Game, style:Style) -> Optional[Rank]:
        res = await self.get_strafes(f"rank/{user_data.id}", {
            "game":game.value,
            "style":style.value
        })
        if res.json:
            return Rank.from_dict(res.json, user_data)
        else:
            return None

    async def find_max_pages(self, url, params, page_count, page_length, custom_page_length) -> int:
        params["page"] = page_count
        res = await self.get_strafes(url, params)
        data = res.json
        if len(data) > 0:
            converted_page_count = int(((page_count - 1) * (page_length / custom_page_length)) + ((len(data) - 1) // custom_page_length) + 1)
            return converted_page_count
        else:
            return 0

    #returns 25 ranks at a given page number, page 1: top 25, page 2: 26-50, etc.
    async def get_ranks(self, game:Game, style:Style, page:int) -> Tuple[List[Rank], int]:
        params = {
            "game":game.value,
            "style":style.value,
            "page":(int((page - 1) / 2)) + 1
        }
        page_length = 25
        res = await self.get_strafes("rank", params)
        data = res.json
        if len(data) > 0:
            page_count = int(res.res.headers["Pagination-Count"])
            converted_page_count = await self.find_max_pages("rank", params, page_count, 50, page_length)
        else:
            params["page"] = 1
            first_page_res = await self.get_strafes("rank", params)
            if len(first_page_res.json) == 0:
                return [], 0
            else:
                page_count = int(first_page_res.res.headers["Pagination-Count"])
                converted_page_count = await self.find_max_pages("rank", params, page_count, 50, page_length)
                params["page"] = page_count
                the_res = await self.get_strafes("rank", params)
                data = the_res.json
                page = converted_page_count
        ls = []
        if page % 2 == 1:
            data = data[:25]
        elif page % 2 == 0:
            data = data[25:]
        users = []
        for i in data:
            users.append(i["User"])
        user_lookup = await self.get_user_data_from_list(users)
        for i in data:
            ls.append(Rank.from_dict(i, user_lookup[i["User"]]))
        return ls, converted_page_count

    @staticmethod
    def find_max_page(last_page, page_count, real_page_length, custom_page_length) -> int:
        return int(((page_count - 1) * (real_page_length / custom_page_length)) + ((len(last_page) - 1) // custom_page_length) + 1)

    async def get_user_times(self, user_data:User, game:Optional[Game], style:Optional[Style], page:int) -> Tuple[List[Record], int]:
        url = f"time/user/{user_data.id}"
        params = {"page":1}
        if game is not None:
            params["game"] = game.value
        if style is not None:
            params["style"] = style.value
        first_page_res = await self.get_strafes(url, params)
        first_page_data = first_page_res.json
        if len(first_page_data) == 0:
            return [], 0
        pagination_count = int(first_page_res.res.headers["Pagination-Count"])
        if page == -1:
            tasks = []
            the_page = Incrementer(1)
            while the_page.increment() < pagination_count:
                params_copy = params.copy()
                params_copy["page"] = the_page.get()
                tasks.append(self.get_strafes(url, params_copy))
            responses = await asyncio.gather(*tasks)
            results = first_page_data
            for response in responses:
                results += response.json
            return await self.make_record_list(results, user=user_data), -1
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
                the_res = await self.get_strafes(url, params)
                last_page_data = the_res.json
            elif the_real_page >= pagination_count:
                params["page"] = pagination_count
                the_res = await self.get_strafes(url, params)
                last_page_data = the_res.json
                the_page_data = last_page_data
            else:
                tasks = []
                params_copy = params.copy()
                params_copy["page"] = the_real_page
                tasks.append(self.get_strafes(url, params_copy))
                params_copy = params.copy()
                params_copy["page"] = pagination_count
                tasks.append(self.get_strafes(url, params_copy))
                responses = await asyncio.gather(*tasks)
                the_page_data = responses[0].json
                last_page_data = responses[1].json
            max_page = self.find_max_page(last_page_data, pagination_count, 200, page_length)
            if page > max_page:
                start = ((int(max_page) - 1) * page_length) % 200
                end = start + page_length
            return await self.make_record_list(the_page_data[start:end], user=user_data), max_page

    async def get_user_completion(self, user_data:User, game:Game, style:Style) -> Tuple[int, int]:
        records, _ = await self.get_user_times(user_data, game, style, -1)
        return len(records), await self.get_map_count(game)

    #records is a list of records from a given map
    @staticmethod
    def sort_map(records:List[Dict[str, Any]]):
        records.sort(key=lambda i: (i["Time"], i["Date"]))

    #changes a WR's diff and previous_record in place by comparing first and second place
    #times on the given map
    async def calculate_wr_diff(self, record : Record) -> bool:
        if record.previous_record is not None:
            return True
        res = await self.get_strafes(f"time/map/{record.map.id}", {
            "style":record.style.value,
        })
        data = res.json
        data = data[:20]
        if len(data) > 1:
            self.sort_map(data)
            if data[0]["ID"] != record.id:
                return False
            record.previous_record = await self.record_from_dict(data[1])
            record.diff = round((record.time.millis - record.previous_record.time.millis) / 1000.0, 3)
        return True

    # returns a list of lists of wrs, each list is a unique game/style combination
    async def get_wrs(self):
        tasks = []
        for game in DEFAULT_GAMES:
            for style in DEFAULT_STYLES:
                if not (game == Game.SURF and style == Style.SCROLL):
                    tasks.append(self.get_strafes("time/recent/wr", {
                            "game":game.value,
                            "style":style.value,
                            "whitelist":"true"
                        }))
        wrs = []
        responses = await asyncio.gather(*tasks)
        for res in responses:
            wrs.append(res.json)
        return wrs

    async def write_wrs(self):
        with open(fix_path("files/recent_wrs.json"), "w") as file:
            json.dump(await self.get_wrs(), file)

    @staticmethod
    def search(ls, record):
        for i in ls:
            if record["ID"] == i["ID"]:
                return i
        return None

    async def get_new_wrs(self) -> List[Record]:
        try:
            old_wrs = open_json("files/recent_wrs.json")
        except FileNotFoundError:
            await self.write_wrs()
            return []
        new_wrs = await self.get_wrs()
        globals:List[Record] = []
        for i in range(len(new_wrs)):
            for record in new_wrs[i]:
                match = self.search(old_wrs[i], record)
                if match:
                    #records by the same person on the same map have the same id even if they beat it
                    if record["Time"] != match["Time"]:
                        r = await self.record_from_dict(record)
                        r.diff = round((int(record["Time"]) - int(match["Time"])) / 1000.0, 3)
                        r.previous_record = await self.record_from_dict(match)
                        globals.append(r)
                    #we can break here because the lists are sorted in the same fashion
                    else:
                        break
                else:
                    globals.append(await self.record_from_dict(record))

        #overwrite recent_wrs.json with new wrs if they exist
        if len(globals) > 0:
            with open(fix_path("files/recent_wrs.json"), "w") as file:
                json.dump(new_wrs, file)
        
        tasks = []
        for wr in globals:
            tasks.append(self.calculate_wr_diff(wr))
        rets = await asyncio.gather(*tasks)

        checked_globals = []
        for i, wr in enumerate(globals):
            if rets[i]:
                checked_globals.append(wr)
        
        checked_globals.sort(key = lambda i: i.date.timestamp)
        return checked_globals

    async def get_map_times(self, style:Style, map:Map, page:int) -> Tuple[List[Record], int]:
        page_length = 25
        page_num, start = divmod((int(page) - 1) * page_length, 200)
        page_num += 1
        params = {
            "style":style.value,
            "page":page_num
        }
        res = await self.get_strafes(f"time/map/{map.id}", params)
        data = res.json
        if len(data) > 0:
            page_count = int(res.res.headers["Pagination-Count"])
            params["page"] = page_count
            converted_page_count = await self.find_max_pages(f"time/map/{map.id}", params, page_count, 200, page_length)
        else:
            params["page"] = 1
            first_page_res = await self.get_strafes(f"time/map/{map.id}", params)
            if len(first_page_res.json) == 0:
                return [], 0
            else:
                page_count = int(first_page_res.res.headers["Pagination-Count"])
                params["page"] = page_count
                tasks = [self.find_max_pages(f"time/map/{map.id}", params, page_count, 200, page_length), self.get_strafes(f"time/map/{map.id}", params)]
                results = await asyncio.gather(*tasks)
                converted_page_count = results[0]
                page_num = converted_page_count
                the_res = results[1]
                data = the_res.json

        #add the previous and next page so that we can sort the times across pages properly
        before_len = 0
        add_before = page_num > 1
        add_after = page_num + 1 <= converted_page_count
        tasks = []

        if add_before:
            copy = params.copy()
            copy["page"] = page_num - 1
            tasks.append(self.get_strafes(f"time/map/{map.id}", copy))
        if add_after:
            copy = params.copy()
            copy["page"] = page_num + 1
            tasks.append(self.get_strafes(f"time/map/{map.id}", copy))
        
        if add_before or add_after:
            results : List[JSONRes] = await asyncio.gather(*tasks)
            if add_before:
                before_len = len(results[0].json)
                data = results[0].json + data
            if add_after:
                data += results[-1].json

        self.sort_map(data)
        if page > converted_page_count:
            start = ((int(converted_page_count) - 1) * page_length) % 200
        start += before_len
        end = start + page_length
        return await self.make_record_list(data[start:end], map=map), converted_page_count

    async def get_user_state(self, user_data:User) -> Optional[UserState]:
        try:
            res = await self.get_strafes(f"user/{user_data.id}", {})
            return UserState(res.json["State"])
        except NotFoundError:
            return None

    async def get_record_placement(self, record:Record) -> Tuple[int, int]:
        params = {
            "style":record.style.value,
            "page":1
        }
        first_page_res = await self.get_strafes(f"time/map/{record.map.id}", params)
        page_count = int(first_page_res.res.headers["Pagination-Count"])
        completions = 0
        tasks = [self.get_strafes(f"time/{record.id}/rank", {})]
        if page_count == 1:
            completions = len(first_page_res.json)
            res = await asyncio.gather(*tasks)
            rank = res[0].json["Rank"]
        else:
            params["page"] = page_count
            tasks.append(self.get_strafes(f"time/map/{record.map.id}", params))
            res = await asyncio.gather(*tasks)
            rank = res[0].json["Rank"]
            completions = len(res[1].json) + (page_count - 1) * 200
        return rank, completions

    # this doesn't cache values that return None
    @cached(ttl=24*60*60)
    async def get_roblox_user_from_discord(self, discord_user_id:int) -> int:
        res = await self.get_request(f"https://verify.eryn.io/api/user/{discord_user_id}", "eryn.io")
        return res.json["robloxId"]

    @cached(ttl=60*60)
    async def get_user_headshot_url(self, user_id:int) -> str:
        res = await self.get_request(f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=180x180&format=Png&isCircular=false", "Roblox Avatar")
        data = res.json
        if data and data['data'][0]['imageUrl']:
            return f"{data['data'][0]['imageUrl']}?{random.randint(0, 100000)}"
        else:
            return None

    @cached()
    async def get_asset_thumbnail(self, asset_id:int) -> str:
        res = await self.get_request(f"https://thumbnails.roblox.com/v1/assets?assetIds={asset_id}&size=250x250&format=Png&isCircular=false", "Roblox Asset")
        data = res.json
        if data and data["data"][0]["imageUrl"]:
            return data["data"][0]["imageUrl"]
        else:
            return None