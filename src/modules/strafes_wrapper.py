# strafes_wrapper.py
from aiocache import cached
from modules import strafes
from modules.strafes import Game, Style, Rank, Record, Map, User, UserState
import random
from typing import List, Optional, Tuple, Union

class Client(strafes.Client):
    async def get_recent_wrs(self, game:Game, style:Style) -> List[Record]:
        return await strafes.get_recent_wrs(self, game, style)

    async def get_user_wrs(self, user_data:User, game:Game, style:Style) -> List[Record]:
        return await strafes.get_user_wrs(self, user_data, game, style)

    async def get_user_record(self, user_data:User, game:Game, style:Style, map:Map) -> Optional[Record]:
        return await strafes.get_user_record(self, user_data, game, style, map)
    
    async def total_wrs(self, user_data:User, game:Game, style:Style) -> int:
        return await strafes.total_wrs(self, user_data, game, style)

    async def get_user_rank(self, user_data:User, game:Game, style:Style) -> Optional[Rank]:
        return await strafes.get_user_rank(self, user_data, game, style)

    async def get_ranks(self, game:Game, style:Style, page:int) -> Tuple[List[Rank], int]:
        return await strafes.get_ranks(self, game, style, page)

    async def get_user_times(self, user_data:User, game:Optional[Game], style:Optional[Style], page:int) -> Tuple[List[Record], int]:
        return await strafes.get_user_times(self, user_data, game, style, page)

    async def get_user_completion(self, user_data:User, game:Game, style:Style) -> Tuple[int, int]:
        return await strafes.get_user_completion(self, user_data, game, style)

    async def get_new_wrs(self) -> List[Record]:
        return await strafes.get_new_wrs(self)

    async def write_wrs(self):
        await strafes.write_wrs(self)

    async def get_map_times(self, style:Style, map:Map, page:int) -> Tuple[List[Record], int]:
        return await strafes.get_map_times(self, style, map, page)

    async def get_user_state(self, user_data:User) -> Optional[UserState]:
        return await strafes.get_user_state(self, user_data)

    async def get_record_placement(self, record:Record) -> Tuple[int, int]:
        return await strafes.get_record_placement(self, record)

    @cached(ttl=60*60)
    async def get_user_data(self, user : Union[str, int]) -> User:
        return await strafes.User.get_user_data(self, user)

    async def map_from_name(self, map_name:str, game:Game) -> Optional[Map]:
        return await strafes.Map.from_name(self, map_name, game)

    async def update_maps(self):
        await strafes.Map.update_maps(self)

    async def get_map_count(self, game:Game) -> int:
        return await strafes.Map.get_map_count(self, game)

    # this doesn't cache values that return None
    @cached(ttl=24*60*60)
    async def get_roblox_user_from_discord(self, discord_user_id:int) -> int:
        async with await self.session.get(f"https://verify.eryn.io/api/user/{discord_user_id}") as res:
            if res.status >= 200 and res.status < 300:
                data = await res.json()
                return data["robloxId"]
            else:
                return None

    @cached(ttl=60*60)
    async def get_user_headshot_url(self, user_id:int) -> str:
        async with await self.session.get(f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=180x180&format=Png&isCircular=false") as res:
            data = await res.json()
            if data['data'][0]['imageUrl']:
                return f"{data['data'][0]['imageUrl']}?{random.randint(0, 100000)}"
            else:
                return None

    @cached()
    async def get_asset_thumbnail(self, asset_id:int) -> str:
        async with await self.session.get(f"https://thumbnails.roblox.com/v1/assets?assetIds={asset_id}&size=250x250&format=Png&isCircular=false") as res:
            data = await res.json()
            return data["data"][0]["imageUrl"]
