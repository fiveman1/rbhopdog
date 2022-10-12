# verifier.py

import random
import time
from typing import Dict, Optional, Tuple

from modules.strafes import StrafesClient
from modules.strafes_base import User

class ExpiringPhrase:

    def __init__(self, time : float, phrase : str, roblox_id : int, seconds_to_expire : float):
        self.time = time
        self.phrase = phrase
        self.roblox_id = roblox_id
        self.seconds_to_expire = seconds_to_expire

    def is_expired(self) -> bool:
        return (time.monotonic() - self.time) > self.seconds_to_expire

    def __bool__(self) -> bool:
        return not self.is_expired()

class AccountVerifier:

    def __init__(self, client : StrafesClient):
        self.client = client
        self.id_to_phrase : Dict[int, ExpiringPhrase] = {}
        with open("files/words.txt") as file:
            self.words = file.read().split(",")
        
    def generate_random_phrase(self) -> str:
        return " ".join(random.sample(self.words, 20))

    def get_expiring_phrase(self, discord_id : int) -> Optional[ExpiringPhrase]:
        return self.id_to_phrase.get(discord_id)

    def get_user_phrase(self, discord_id : int) -> Optional[str]:
        phrase = self.get_expiring_phrase(discord_id)
        if phrase:
            return phrase.phrase
        else:
            return None

    def create_user_phrase(self, discord_id : int, roblox_user : User) -> str:
        phrase = self.generate_random_phrase()
        self.id_to_phrase[discord_id] = ExpiringPhrase(time.monotonic(), phrase, roblox_user.id, 15*60)
        return phrase

    async def verify_user(self, discord_id : int) -> Tuple[bool, User]:
        phrase = self.get_expiring_phrase(discord_id)
        user = await self.client.get_user_data_no_cache(phrase.roblox_id)
        success = phrase.phrase in user.description
        if success:
            del self.id_to_phrase[discord_id]
        return success, user
    