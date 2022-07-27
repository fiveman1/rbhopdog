from typing import List, Optional, Tuple
from modules.strafes_wrapper import Client
from modules.strafes import Game, Style, User, UserState
from discord.ext.commands import Bot
from discord.errors import InvalidData

def get_discord_user_id(s : str) -> Optional[str]:
    if s[:3] == "<@!" and s[-1] == ">":
        return s[3:-1]
    elif s[:2] == "<@" and s[-1] == ">":
        return s[2:-1]
    else:
        return None

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

class ArgumentValidator:

    def __init__(self, bot : Bot, strafes : Client):
        self.bot = bot
        self.strafes = strafes
        self.game = ArgumentValue()
        self.style = ArgumentValue()
        self.user = UserValue()
        self.map = ArgumentValue()
        self.page = ArgumentValue()

    async def set_user(self, user, author_id) -> Tuple[bool, str]:
        if user == "me" or not user:
            user = await self.strafes.get_roblox_user_from_discord(author_id)
            if not user:
                return False, "Invalid username (no Roblox username associated with your Discord account. Visit https://rover.link/login)"
        else:
            discord_user_id = get_discord_user_id(user)
            if discord_user_id:
                roblox_user = await self.strafes.get_roblox_user_from_discord(discord_user_id)
                if not roblox_user:
                    err = ""
                    try:
                        u = await self.bot.fetch_user(int(discord_user_id))
                        if u:
                            err = f"Invalid username ('{u.name}' does not have a Roblox account associated with their Discord account.)"
                        else:
                            err = "Invalid username (no user associated with that Discord account.)"
                    except:
                        err = "Invalid discord user ID."
                    return False, err
                else:
                    user = roblox_user
        try:
            self.user.value = await self.strafes.get_user_data(user)
        except InvalidData:
            return False, f"Invalid username (username '{user}' does not exist on Roblox)."
        except TimeoutError:
            return False, "Error: User data request timed out."
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
    
    async def evaluate(self, args : List[str], author_id : int = None) -> Tuple[bool, str]:
        args = list(args)
        if not self.game.is_not_required():
            if len(args) == 0:
                return False, "Missing game!"
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
                return False, "No valid game found (try bhop or surf)"
        if not self.style.is_not_required():
            if len(args) == 0:
                return False, "Missing style!"
            found = False
            for i, arg in enumerate(args):
                lowercase = arg.lower()
                if Style.contains(lowercase):
                    self.style.value = Style(lowercase)
                    found = True
                    break
            if found:
                del args[i]
            elif self.style.is_required():
                return False, "No valid style found (try autohop/auto/a, aonly/ao, sideways/sw, etc.)"
        if not self.page.is_not_required():
            found = False
            if len(args) > 1 and args[-1].isnumeric():
                self.page.value = int(args[-1])
                found = True
            if found:
                del args[-1]
            elif self.page.is_required():
                return False, "No valid page number found"
        user_found = False
        if self.map.is_required():
            if len(args) == 0:
                return False, "Missing map!"
            if not self.user.is_required():
                map_name = " ".join(args)
                smap = await self.strafes.map_from_name(map_name, self.game.value)
                if not smap:
                    if self.game.value is not None:
                        return False, f"\"{map_name}\" is not a {self.game.value} valid map."
                    else:
                        return False, f"\"{map_name}\" is not a valid map."
            else:
                if len(args) < 2:
                    return False, "Missing map or user!"
                username = args[0]
                map_name = " ".join(args[1:])
                smap = await self.strafes.map_from_name(map_name, self.game.value)
                if not smap:
                    smap = await self.strafes.map_from_name(" ".join(args[:-1]), self.game.value)
                    if smap:
                        username = args[-1]
                    else:
                        if self.game.value is not None:
                            return False, f"\"{map_name}\" is not a {self.game.value} valid map."
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
                return False, "Missing user!"
            username = " ".join(args)
            valid, err = await self.set_user(username, author_id)
            if not valid:
                return False, err
        return True, ""
