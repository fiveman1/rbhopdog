# strafes_wrapper.py
import aiohttp
from modules import strafes
from modules.strafes import Game, Style, Rank, Record, Map, User, UserState
import random
from typing import List, Optional, Tuple, Union

class Client:
    def __init__(self):
        self.session = aiohttp.ClientSession()

    def close(self):
        self.session.loop.create_task(self.session.close())

    async def get_recent_wrs(self, game:Game, style:Style) -> List[Record]:
        return await strafes.get_recent_wrs(self.session, game, style)

    async def get_user_wrs(self, user_data:User, game:Game, style:Style) -> List[Record]:
        return await strafes.get_user_wrs(self.session, user_data, game, style)

    async def get_user_record(self, user_data:User, game:Game, style:Style, map:Map) -> Optional[Record]:
        return await strafes.get_user_record(self.session, user_data, game, style, map)
    
    async def total_wrs(self, user_data:User, game:Game, style:Style) -> int:
        return await strafes.total_wrs(self.session, user_data, game, style)

    async def get_user_rank(self, user_data:User, game:Game, style:Style) -> Optional[Rank]:
        return await strafes.get_user_rank(self.session, user_data, game, style)

    async def get_ranks(self, game:Game, style:Style, page:int) -> Tuple[List[Rank], int]:
        return await strafes.get_ranks(self.session, game, style, page)

    async def get_user_times(self, user_data:User, game:Optional[Game], style:Optional[Style], page:int) -> Tuple[List[Record], int]:
        return await strafes.get_user_times(self.session, user_data, game, style, page)

    async def get_user_completion(self, user_data:User, game:Game, style:Style) -> Tuple[int, int]:
        return await strafes.get_user_completion(self.session, user_data, game, style)

    async def get_new_wrs(self) -> List[Record]:
        return await strafes.get_new_wrs(self.session)

    async def write_wrs(self):
        await strafes.write_wrs(self.session)

    async def get_map_times(self, style:Style, map:Map, page:int) -> Tuple[List[Record], int]:
        return await strafes.get_map_times(self.session, style, map, page)

    async def get_user_state(self, user_data:User) -> Optional[UserState]:
        return await strafes.get_user_state(self.session, user_data)

    async def get_record_placement(self, record:Record) -> Tuple[int, int]:
        return await strafes.get_record_placement(self.session, record)

    async def get_user_data(self, user : Union[str, int]) -> User:
        return await strafes.User.get_user_data(self.session, user)

    async def map_from_name(self, map_name:str, game:Game) -> Optional[Map]:
        return await strafes.Map.from_name(self.session, map_name, game)

    async def update_maps(self):
        await strafes.Map.update_maps(self.session)

    async def get_map_count(self, game:Game) -> int:
        return await strafes.Map.get_map_count(self.session, game)

    async def get_roblox_user_from_discord(self, discord_user_id:int):
        async with await self.session.get(f"https://verify.eryn.io/api/user/{discord_user_id}") as res:
            return await res.json() if res else None

    async def get_user_headshot_url(self, user_id:int) -> str:
        async with await self.session.get(f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=180x180&format=Png&isCircular=false") as res:
            data = await res.json()
            return f"{data['data'][0]['imageUrl']}?{random.randint(0, 100000)}"

    async def get_asset_thumbnail(self, asset_id:int) -> str:
        async with await self.session.get(f"https://thumbnails.roblox.com/v1/assets?assetIds={asset_id}&size=250x250&format=Png&isCircular=false") as res:
            data = await res.json()
            return data["data"][0]["imageUrl"]
