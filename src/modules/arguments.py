# arguments.py
from typing import Iterable, Optional, Tuple, Union
from modules.strafes_base import Game, Style, User, UserState
from modules.strafes import StrafesClient, NotFoundError
from discord.ext.commands import Bot
import discord

def get_discord_user_id(s : str) -> Optional[int]:
    if s[:3] == "<@!" and s[-1] == ">" and s[3:-1].isnumeric():
        return int(s[3:-1])
    elif s[:2] == "<@" and s[-1] == ">" and s[2:-1].isnumeric():
        return int(s[2:-1])
    else:
        return None

def clamp(lo, val, hi):
    if val <= lo:
        return lo
    elif val >= hi:
        return hi
    else:
        return val

class ArgumentValue:

    NOT_REQUIRED = 0
    REQUIRED = 1
    OPTIONAL = 2

    def __init__(self):
        self.status = ArgumentValue.NOT_REQUIRED
        self._value = None
        self.default = None

    @property
    def value(self):
        return self.default if self._value is None else self._value

    @value.setter
    def value(self, val):
        self._value = val

    def make_required(self):
        self.status = ArgumentValue.REQUIRED

    def make_optional(self, default=None):
        self.default = default
        self.status = ArgumentValue.OPTIONAL
    
    def make_not_required(self):
        self.status = ArgumentValue.NOT_REQUIRED

    def is_required(self) -> bool:
        return self.status == ArgumentValue.REQUIRED

    def is_optional(self) -> bool:
        return self.status == ArgumentValue.OPTIONAL
    
    def is_not_required(self) -> bool:
        return self.status == ArgumentValue.NOT_REQUIRED

class UserValue(ArgumentValue):

    def __init__(self):
        super().__init__()
        self.check_status = True
        self.allow_id = False
        self.allow_discord = True

class ArgumentValidator:

    def __init__(self, bot : Bot, strafes : StrafesClient):
        self.bot = bot
        self.strafes = strafes
        self.game = ArgumentValue()
        self.style = ArgumentValue()
        self.user = UserValue()
        self.map = ArgumentValue()
        self.page = ArgumentValue()

    async def set_user(self, user : Union[str, int], author_id : int) -> Tuple[bool, str]:
        if self.user.allow_discord:
            if user == "me" or not user:
                user = await self.strafes.get_roblox_user_from_discord(author_id)
                if not user:
                    return False, f"Invalid username (no Roblox account associated with your Discord account). Linking accounts has changed, use {self.bot.command_prefix}link {{username}} to link your account."
            elif isinstance(user, str):
                discord_user_id = get_discord_user_id(user)
                if discord_user_id:
                    roblox_user = await self.strafes.get_roblox_user_from_discord(discord_user_id)
                    if not roblox_user:
                        err = ""
                        try:
                            u = await self.bot.fetch_user(int(discord_user_id))
                            if u:
                                err = f"Invalid username ('{u.name}' does not have a Roblox account associated with their Discord account.) Linking accounts has changed, use {self.bot.command_prefix}help link for more info."
                            else:
                                err = "Invalid username (no user associated with that Discord account.)"
                        except discord.errors.NotFound:
                            err = "Invalid discord user ID."
                        return False, err
                    user = roblox_user
        try:
            if isinstance(user, str) and len(user) > 64:
                return False, "Username is too long!"
            self.user.value = await self.strafes.get_user_data(user)
        except NotFoundError:
            return False, f"Invalid username (username '{user}' does not exist on Roblox)."
        if self.user.check_status:
            valid, err = await self.check_user_status(self.user.value)
            if not valid:
                return False, err
        return True, ""

    async def check_user_status(self, user : User) -> Tuple[bool, str]:
        state = await self.strafes.get_user_state(user)
        if not state:
            return False, f"'{user.username}' has not played bhop/surf."
        else:
            user.state = state
            if user.state == UserState.BLACKLISTED:
                return False, f"{user.username} is blacklisted."
            elif user.state == UserState.PENDING:
                return False, f"{user.username} is pending moderation."
        return True, ""
    
    async def evaluate(self, args : Iterable[str], author_id : int = None) -> Tuple[bool, str]:
        args = list(args)
        if not self.game.is_not_required():
            if len(args) == 0 and self.game.is_required():
                return False, "Missing game."
            found = False
            for i, arg in enumerate(args):
                lowercase = arg.lower()
                if Game.contains(lowercase):
                    self.game.value = Game(lowercase)
                    found = True
                    break
            if found:
                del args[i]
            elif self.game.is_required():
                return False, f"No valid game found. Use {self.bot.command_prefix}aliases for a list of all games."
        if not self.style.is_not_required():
            if len(args) == 0 and self.style.is_required():
                return False, "Missing style."
            found = False
            for i, arg in enumerate(args):
                lowercase = arg.lower()
                if Style.contains(lowercase):
                    self.style.value = Style(lowercase)
                    found = True
                    break
            if found:
                del args[i]
                if self.style.value == Style.SCROLL:
                    if self.game.value == Game.SURF:
                        return False, "Scroll and surf cannot be combined."
                    else:
                        self.game.value = Game.BHOP
            elif self.style.is_required():
                return False, f"No valid style found. Use {self.bot.command_prefix}aliases for a list of all styles."
        if not self.page.is_not_required():
            found = False
            len_required = 1 if self.map.is_required() else 0
            if len(args) > len_required and args[-1].isnumeric():
                self.page.value = clamp(1, int(args[-1]), 999999)
                found = True
            if found:
                del args[-1]
            elif self.page.is_required():
                return False, "No valid page number found."
        user_found = False
        if self.map.is_required():
            if len(args) == 0:
                return False, "Missing map."
            if not self.user.is_required():
                map_name = " ".join(args)
                if len(map_name) > 128:
                    return False, "Map name is too long!"
                smap = await self.strafes.map_from_name(map_name, self.game.value)
                if not smap:
                    if self.game.value is not None:
                        return False, f"\"{map_name}\" is not a valid {self.game.value} map."
                    else:
                        return False, f"\"{map_name}\" is not a valid map."
            else:
                smap = await self.strafes.map_from_name(" ".join(args), self.game.value)
                if smap:
                    args.clear()
                elif len(args) < 2:
                    return False, "Missing map or user."
                else:
                    username = args[0]
                    map_name = " ".join(args[1:])
                    if len(map_name) > 128:
                        return False, "Map name is too long!"
                    smap = await self.strafes.map_from_name(map_name, self.game.value)
                    if not smap:
                        smap = await self.strafes.map_from_name(" ".join(args[:-1]), self.game.value)
                        if smap:
                            username = args[-1]
                        else:
                            if self.game.value is not None:
                                return False, f"\"{map_name}\" is not a valid {self.game.value} map."
                            else:
                                return False, f"\"{map_name}\" is not a valid map."
                    valid, err = await self.set_user(username, author_id)
                    if not valid:
                        return False, err
                    user_found = True
            self.game.value = smap.game
            self.map.value = smap
        if not user_found and self.user.is_required():
            if len(args) < 1:
                valid, err = await self.set_user(None, author_id)
                if not valid:
                    return False, err
            else:
                username = " ".join(args)
                if self.user.allow_id and username.isnumeric():
                    username = int(username)
                valid, err = await self.set_user(username, author_id)
                if not valid:
                    return False, err
        return True, ""
