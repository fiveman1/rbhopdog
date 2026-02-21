# maincog.py
import asyncio
import colorsys
import discord
from discord.ext.commands.context import Context
from discord.ext import commands, tasks
from io import BytesIO, StringIO
import numpy
from PIL import Image
import time
import traceback
from typing import Callable, Coroutine, Dict, List, Tuple, Union

from bot import StrafesBot
from modules.strafes_base import *
from modules.strafes import APIError, StrafesClient, ErrorCode
from modules import utils
from modules.utils import Incrementer, StringBuilder
from modules.arguments import ArgumentValidator

# contains some commonly used Cols designed for use with MessageBuilder
class MessageCol:
    class Col:
        def __init__(self, title:str, width:int, map:Callable):
            self.title = title + ":"
            self.width = width
            self.map = map

    USERNAME = Col("Username", 20, lambda item: item.user.username)
    MAP_NAME = Col("Map name", 30, lambda record: record.map.displayname)
    TIME = Col("Time", 10, lambda record: str(record.time))
    DATE = Col("Date", 11, lambda record: str(record.date))
    GAME = Col("Game", 6, lambda record: record.game.name)
    STYLE = Col("Style", 14, lambda record: record.style.name)
    RANK = Col("Rank", 19, lambda rank: f"{rank} ({rank.rank})")
    SKILL = Col("Skill", 10, lambda rank: f"{rank.skill:.3f}%")
    PLACEMENT = Col("Placement", 11, lambda i: i.placement)

# a builder object? what is this? Java???
# title: title string, first line, will automatically have a newline placed at end
# cols: list of Cols, columns are constructed in the order they appear in the list
# col:
#   col.title: column title 
#   col.width: width in characters of column
#   col.map: function which is given an item from a given row and returns the value corresponding to the column, will always be given 1 arg
# items: list of items used to build the message
class MessageBuilder:

    def __init__(self, cols:List[MessageCol.Col], items:List, title:str=""):
        self.title = title
        self.cols = cols
        self.items = items

    def build(self) -> str:
        return MessageBuilder._message_builder(self.title, self.cols, self.items)

    # use list and a single join operation rather than concatenating strings hundreds of times to improve performance
    @staticmethod
    def _message_builder(title:str, cols:List[MessageCol.Col], items:List):
        msg = StringBuilder()
        if title:
            msg.append(f"{title}\n")
        last_col = cols[-1]
        cols = cols[:-1]
        for col in cols:
            msg.append(f"{MessageBuilder._add_spaces(col.title, col.width)}| ")
        msg.append(f"{last_col.title}\n")
        for item in items:
            for col in cols:
                msg.append(f"{MessageBuilder._add_spaces(col.map(item), col.width)}| ")
            msg.append(f"{last_col.map(item)[:last_col.width]}\n")
        return msg.build()
    
    @staticmethod
    def _add_spaces(s:Union[int, str], length:int):
        if type(s) == str:
            return f"{s:<{length}}"[:length]
        else:
            return f"{s:{length-1}} "[:length]

class ComparableUserStyle:

    def __init__(self, user : User, style : Style):
        self.user = user
        self.style = style

    def __hash__(self) -> int:
        return hash(self.user) + hash(self.style)

    def __eq__(self, o: object) -> bool:
        return self.user == o.user and self.style == o.style

class UserActiveCommandManager:

    def __init__(self):
        self.active : int = 0
        self.last_active : float = None

    def try_use_command(self, max_active=1, timeout=30.0) -> bool:
        now = time.monotonic()
        if self.active >= max_active:
            if now - self.last_active > timeout:
                self.complete_command()
                self.last_active = now
                return True
            else:
                return False
        else:
            self.active += 1
            self.last_active = now
            return True

    def complete_command(self):
        self.active -= 1
        if self.active < 0:
            self.active = 0

def before_strafes(max_allowed_per_user=1):
    async def before(ctx : Context):
        await ctx.send("https://strafes.fiveman1.net/")
        return
        cog : "MainCog" = ctx.cog
        user = ctx.author.id
        success = True
        async with cog.lock:
            if user in cog.active_commands:
                success = cog.active_commands[user].try_use_command(max_allowed_per_user)
            else:
                manager = UserActiveCommandManager()
                manager.try_use_command()
                cog.active_commands[user] = manager
        if not success:
            await ctx.send(utils.fmt_md_code("You have too many active commands! You must wait for them to finish before you can use another command."))
        ctx.reset_strafes = success
        return success
    return commands.check(before)

# TODO: why do i have one cog for everything
class MainCog(commands.Cog):

    def __init__(self, bot : StrafesBot):
        self.bot = bot
        self.bot.remove_command("help")
        self.strafes : StrafesClient = None
        self.maps_started = False
        self.globals_started = False
        self.lock = asyncio.Lock()
        self.active_commands : Dict[int, UserActiveCommandManager] = {}

    async def cog_load(self):
        print("Loading maincog")
        self.strafes = StrafesClient(self.bot.strafes_key, self.bot.verify_key)
        print("Loading maps")
        start = time.monotonic()
        #await self.strafes.load_maps()
        end = time.monotonic()
        print(f"Done loading maps ({end-start:.3f}s)")
        #self.update_maps.start()
        self.global_announcements.start()
        print("Maincog loaded")
    
    async def cog_unload(self):
        print("Unloading maincog")
        self.global_announcements.cancel()
        #self.update_maps.cancel()
        await self.strafes.close()

    async def task_wrapper(self, task : Coroutine[Any, Any, None], task_name : str):
        # this is wrapped in a try-except because if this raises
        # an error the entire task stops and we don't want that :)
        try:
            await task
        except Exception as error:
            try:
                await self.bot.wait_until_ready()
                tb_channel = self.bot.get_channel(utils.TRACEBACK_CHANNEL)
                tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
                for msg in utils.page_messages(f"Error in {task_name}!\n{tb}"):
                    await tb_channel.send(utils.fmt_md_code(msg))
            except:
                pass

    async def update_maps_task(self):
        if not self.maps_started:
            self.maps_started = True
        else:
            await self.strafes.load_maps()

    @tasks.loop(minutes=60)
    async def update_maps(self):
        await self.task_wrapper(self.update_maps_task(), "update_maps")

    async def try_except(self, coroutine):
        try:
            await coroutine
        except:
            pass

    def create_global_embed(self, record : Record):
        return (record.game, record.style, self.make_global_embed(record))
    
    @staticmethod
    async def post_globals(embeds : List[discord.Embed], channel : discord.channel.TextChannel):
        for embed in embeds:
            msg = await channel.send(embed=embed)
            await msg.publish()

    async def globals_task(self):
        # when the bot first runs, overwrite globals then stop
        if not self.globals_started:
            await self.strafes.write_wrs()
            self.globals_started = True
            return
        start = time.time()
        records = await self.strafes.get_new_wrs()
        if len(records) > 0:
            end = time.time()
            print(f"get new wrs: {end-start}s")
            all_embeds = []
            for record in records:
                all_embeds.append(self.create_global_embed(record))
                print(f"New global:\n{record}")
            start = time.time()
            bhop_auto = []
            bhop_style = []
            surf_auto = []
            surf_style = []
            all_globals = []
            for game, style, embed in all_embeds:
                all_globals.append(embed)
                if game == Game.BHOP and style == Style.AUTOHOP:
                    bhop_auto.append(embed)
                elif game == Game.BHOP and style != Style.AUTOHOP:
                    bhop_style.append(embed)
                elif game == Game.SURF and style == Style.AUTOHOP:
                    surf_auto.append(embed)
                elif game == Game.SURF and style != Style.AUTOHOP:
                    surf_style.append(embed)
            tasks = []
            bhop_auto_channel = self.bot.get_channel(self.bot.bhop_auto_globals)
            bhop_styles_channel = self.bot.get_channel(self.bot.bhop_styles_globals)
            surf_auto_channel = self.bot.get_channel(self.bot.surf_auto_globals)
            surf_styles_channel = self.bot.get_channel(self.bot.surf_styles_globals)
            all_channel = self.bot.get_channel(self.bot.globals)
            tasks.append(self.try_except(self.post_globals(all_globals, all_channel)))
            tasks.append(self.try_except(self.post_globals(bhop_auto, bhop_auto_channel)))
            tasks.append(self.try_except(self.post_globals(bhop_style, bhop_styles_channel)))
            tasks.append(self.try_except(self.post_globals(surf_auto, surf_auto_channel)))
            tasks.append(self.try_except(self.post_globals(surf_style, surf_styles_channel)))
            await asyncio.gather(*tasks)
            end = time.time()
            print(f"embeds posted: {end-start}s")

    @tasks.loop(seconds=30)
    async def global_announcements(self):
        await self.task_wrapper(self.globals_task(), "globals_announcements")
            
    @global_announcements.before_loop
    async def before_global_announcements(self):
        print("Waiting for ready")
        #we have to wait for the bot to on_ready() or we won't be able to find channels/guilds
        await self.bot.wait_until_ready()

    async def cog_after_invoke(self, ctx : Context):
        try:
            if ctx.reset_strafes:
                user = ctx.author.id
                async with self.lock:
                    self.active_commands[user].complete_command()
        except AttributeError:
            pass

    @commands.command(name="recentwrs")
    async def get_recent_wrs(self, ctx:Context, *args : str):
        arguments = ArgumentValidator(self.bot, self.strafes)
        arguments.game.make_required()
        arguments.style.make_required()
        valid, err = await arguments.evaluate(args, ctx.author.id)
        if not valid:
            await ctx.send(utils.fmt_md_code(err))
            return

        game : Game = arguments.game.value
        style : Style = arguments.style.value
        await ctx.send(f"https://strafes.fiveman1.net/globals?game={game.value}&style={style.value}")
        return

        async with ctx.typing():
            game : Game = arguments.game.value
            style : Style = arguments.style.value

            msg = MessageBuilder(title=f"10 Recent WRs [game: {game}, style: {style}]", 
                cols=[MessageCol.USERNAME, MessageCol.MAP_NAME, MessageCol.TIME, MessageCol.DATE], 
                items= await self.strafes.get_recent_wrs(game, style)
            ).build()
            await ctx.send(utils.fmt_md_code(msg))

    @commands.command(name="pb", aliases=["record"])
    async def get_user_pb(self, ctx:Context, *args : str):
        await ctx.send(f"https://strafes.fiveman1.net/users")
        return
    
        arguments = ArgumentValidator(self.bot, self.strafes)
        arguments.game.make_optional()
        arguments.style.make_required()
        arguments.user.make_required()
        arguments.map.make_required()
        valid, err = await arguments.evaluate(args, ctx.author.id)
        if not valid:
            await ctx.send(utils.fmt_md_code(err))
            return
        
        async with ctx.typing():
            game : Game = arguments.game.value
            style : Style = arguments.style.value
            user : User = arguments.user.value
            map : Map = arguments.map.value

            record = await self.strafes.get_user_record(user, game, style, map)
            if record is None:
                await ctx.send(utils.fmt_md_code(f"No record by {user.username} found on map: {map.displayname} [game: {game}, style: {style}]"))
            else:
                placement, total_completions = await self.strafes.get_record_placement(record)
                msg = MessageBuilder(title=f"{user.username}'s record on {record.map.displayname} [game: {game}, style: {style}]",
                    cols=[MessageCol.TIME, MessageCol.DATE, MessageCol.Col("Placement", 20, lambda _: f"{placement}{self.get_ordinal(placement)} / {total_completions}")],
                    items=[record]
                ).build()
                await ctx.send(utils.fmt_md_code(msg))

    @commands.command(name="wrmap")
    async def get_wrmap(self, ctx:Context, *args : str):
        await ctx.send(f"https://strafes.fiveman1.net/maps")
        return
        arguments = ArgumentValidator(self.bot, self.strafes)
        arguments.game.make_optional()
        arguments.style.make_required()
        arguments.map.make_required()
        arguments.page.make_optional(1)
        valid, err = await arguments.evaluate(args, ctx.author.id)
        if not valid:
            await ctx.send(utils.fmt_md_code(err))
            return

        async with ctx.typing():
            game : Game = arguments.game.value
            style : Style = arguments.style.value
            map : Map = arguments.map.value
            page : int = arguments.page.value
            records, page_count = await self.strafes.get_map_times(style, map, page)
            if page_count == 0:
                await ctx.send(utils.fmt_md_code(f"{map.displayname} has not yet been completed in {style}."))
                return
            else:
                if page > page_count:
                    page = page_count
                incrementer = Incrementer(((page - 1) * 25) + 1)
                msg = MessageBuilder(title=f"Record list for map: {map.displayname} [game: {game}, style: {style}, page: {page}/{page_count}]", 
                    cols=[MessageCol.Col("Placement", 11, lambda _ : incrementer.increment()), MessageCol.USERNAME, MessageCol.TIME, MessageCol.DATE], 
                    items=records
                ).build()
                await ctx.send(utils.fmt_md_code(msg))

    @commands.command(name="wrlist")
    async def wr_list(self, ctx:Context, *args : str):
        valid_sorts = ["date", "time", "name"]
        sort = ""
        args = list(args)
        for i, arg in enumerate(args):
            arg = arg.lower()
            if arg in valid_sorts:
                sort = arg
                break
        if sort:
            del args[i]
        
        arguments = ArgumentValidator(self.bot, self.strafes)
        arguments.game.make_optional()
        arguments.style.make_optional()
        arguments.user.make_required()

        page = 1
        for i, arg in enumerate(args):
            arg = arg.lower()
            if arg == "txt":
                page = -1
                break
        if page == -1:
            del args[i]
        else:
            arguments.page.make_optional(1)
        
        valid, err = await arguments.evaluate(args, ctx.author.id)
        if not valid:
            await ctx.send(utils.fmt_md_code(err))
            return
        
        game : Game = arguments.game.value
        style : Style = arguments.style.value
        user : User = arguments.user.value
        await ctx.send(f"https://strafes.fiveman1.net/users/{user.id}?game={999 if game is None else game.value}&style={999 if style is None else style.value}&wrs=true")
        return
    
        game : Game = arguments.game.value
        style : Style = arguments.style.value
        user : User = arguments.user.value
        if page != -1:
            page = arguments.page.value   

        async with ctx.typing():
            if game is None:
                g = DEFAULT_GAMES
            else:
                g = [game]
            if style is None:
                s = DEFAULT_STYLES
            else:
                s = [style]

            tasks = []
            for _game in g:
                for _style in s:
                    if not (_game == Game.SURF and _style == Style.SCROLL):
                        tasks.append(self.strafes.get_user_wrs(user, _game, _style))  
            results = await asyncio.gather(*tasks)
            
            wrs:List[Record] = []
            count = 0
            for result in results:
                wrs += result
                count += len(result)
            if count == 0:
                await ctx.send(utils.fmt_md_code(f"{user.username} has no WRs in the specified game and style."))
                return
            if not sort:
                wrs.sort(key = lambda i: (i.game.name, i.style.name, i.map.displayname))
            elif sort == "name":
                wrs.sort(key = lambda i: i.map.displayname)
            elif sort == "date":
                wrs.sort(key = lambda i: i.date.timestamp, reverse=True)
            elif sort == "time":
                wrs.sort(key = lambda i: i.time.millis)
            cols = [MessageCol.MAP_NAME, MessageCol.TIME, MessageCol.DATE]
            if g is DEFAULT_GAMES:
                game = "both"
                cols.append(MessageCol.GAME)
            if s is DEFAULT_STYLES:
                style = "all"
                cols.append(MessageCol.STYLE)
            if sort == "":
                sort = "default"
            if page != -1:
                total_pages = ((count - 1) // 25) + 1
                if page > total_pages:
                    page = total_pages
                msg = MessageBuilder(cols=cols, items=wrs[(page-1)*25:page*25]).build()
                the_messages = utils.page_messages(f"WR list for {user.username} [game: {game}, style: {style}, sort: {sort}, page: {page}/{total_pages}] (Records: {count})\n{msg}")
                for m in the_messages:
                    await ctx.send(utils.fmt_md_code(m))
            else:
                with StringIO() as f:
                    msg = MessageBuilder(cols=cols, items=wrs).build()
                    f.write(f"WR list for {user.username} [game: {game}, style: {style}, sort: {sort}] (Records: {count})\n{msg}")
                    f.seek(0)
                    await ctx.send(file=discord.File(f, filename=f"wrs_{user.username}_{game}_{style}.txt"))

    @commands.command(name="map")
    async def map_info(self, ctx:Context, *args : str):
        await ctx.send(f"https://strafes.fiveman1.net/maps")
        return
        arguments = ArgumentValidator(self.bot, self.strafes)
        arguments.game.make_optional()
        arguments.map.make_required()
        valid, err = await arguments.evaluate(args, ctx.author.id)
        if not valid:
            await ctx.send(utils.fmt_md_code(err))
            return
        map : Map = arguments.map.value
        
        embed = discord.Embed(color=0x7c17ff)
        url = await self.safe_get_asset_thumbnail(map.id)
        if url:
            embed.set_thumbnail(url=url)
        embed.set_footer(text="Map Info")
        embed.title = f"\U0001F5FA  {map.displayname} ({map.game})"
        embed.add_field(name="Creator", value=map.creator)
        embed.add_field(name="Map ID", value=map.id)
        embed.add_field(name="Server Load Count", value=map.playcount)
        await ctx.send(embed=embed)

    @commands.command(name="wrcount")
    async def wr_count(self, ctx:Context, *args : str):
        arguments = ArgumentValidator(self.bot, self.strafes)
        arguments.user.make_required()
        valid, err = await arguments.evaluate(args, ctx.author.id)
        if not valid:
            await ctx.send(utils.fmt_md_code(err))
            return
        user : User = arguments.user.value
        await ctx.send(f"https://strafes.fiveman1.net/users/{user.id}?game={999}&style={999}&wrs=true")
        return

        async with ctx.typing():
            count = 0
            the_dict = {
                Game.BHOP: [],
                Game.SURF: []
            }
            async def the_order(game, style):
                return (game, style, await self.strafes.total_wrs(user, game, style))
            tasks = []
            for game in DEFAULT_GAMES:
                for style in DEFAULT_STYLES:
                    if not (game == Game.SURF and style == Style.SCROLL): #skip surf/scroll
                        tasks.append(the_order(game, style))        
            results = await asyncio.gather(*tasks)
            for game, style, wrs in results:
                if wrs > 0:
                    the_dict[game].append((style, wrs))
                    count += wrs
            embed = discord.Embed(color=0xff94b8)
            url = await self.safe_get_user_headshot_url(user.id)
            if url:
                embed.set_thumbnail(url=url)
            embed.set_footer(text="WR Count")
            if user.username != user.displayname:
                name = f"{user.displayname} ({user.username})"
            else:
                name = user.username
            embed.title = f"\U0001F4C4  {name}"
            if count > 0:
                embed.description = f"Total WRs: {count}"
                if len(the_dict[Game.BHOP]) > 0:
                    body = ""
                    for c in the_dict[Game.BHOP]:
                        body += f"**{c[0]}:** {c[1]}\n"
                    embed.add_field(name=f"__bhop__", value=body[:-1], inline=False)
                if len(the_dict[Game.SURF]) > 0:
                    body = ""
                    for c in the_dict[Game.SURF]:
                        body += f"**{c[0]}:** {c[1]}\n"
                    embed.add_field(name=f"__surf__", value=body[:-1], inline=False)
            else:
                embed.description = f"Total WRs: 0 \N{crying face}"
            await ctx.send(embed=embed)

    @commands.command(name="profile")
    async def user_rank(self, ctx:Context, *args : str):
        arguments = ArgumentValidator(self.bot, self.strafes)
        arguments.game.make_required()
        arguments.style.make_required()
        arguments.user.make_required()
        valid, err = await arguments.evaluate(args, ctx.author.id)
        if not valid:
            await ctx.send(utils.fmt_md_code(err))
            return
        game : Game = arguments.game.value
        style : Style = arguments.style.value
        user : User = arguments.user.value
        await ctx.send(f"https://strafes.fiveman1.net/users/{user.id}?game={game.value}&style={style.value}")
        return

        async with ctx.typing():
            tasks = [
                self.strafes.get_user_rank(user, game, style),
                self.strafes.get_user_completion(user, game, style),
                self.strafes.total_wrs(user, game, style)
            ]
            results = await asyncio.gather(*tasks)
            rank_data:Rank = results[0]
            if not rank_data or rank_data.placement < 1:
                await ctx.send(utils.fmt_md_code(f"No data available for {user.username} [game: {game}, style: {style}]"))
            else:
                completions, total_maps = results[1]
                wrs = results[2]
                await ctx.send(embed= await self.make_user_embed(user, rank_data, game, style, completions, total_maps, wrs))

    @commands.command(name="ranks")
    async def ranks(self, ctx:Context, *args : str):
        arguments = ArgumentValidator(self.bot, self.strafes)
        arguments.game.make_required()
        arguments.style.make_required()
        arguments.page.make_optional(1)
        valid, err = await arguments.evaluate(args, ctx.author.id)
        if not valid:
            await ctx.send(utils.fmt_md_code(err))
            return
        game : Game = arguments.game.value
        style : Style = arguments.style.value
        page : int = arguments.page.value
        await ctx.send(f"https://strafes.fiveman1.net/ranks?game={game.value}&style={style.value}")
        return

        async with ctx.typing():
            ranks, page_count = await self.strafes.get_ranks(game, style, page)
            if page_count == 0:
                await ctx.send(utils.fmt_md_code(f"No ranks found [game: {game}, style: {style}] (???)."))
                return
            elif page > page_count:
                page = page_count
            msg = MessageBuilder(title=f"Ranks [game: {game}, style: {style}, page: {page}/{page_count}]",
                cols=[MessageCol.PLACEMENT, MessageCol.USERNAME, MessageCol.RANK, MessageCol.SKILL],
                items=ranks
            ).build()
            await ctx.send(utils.fmt_md_code(msg))
    
    @commands.command(name="times")
    async def times(self, ctx:Context, *args : str):
        valid_sorts = ["date", "time", "name"]
        sort = ""
        args = list(args)
        for i, arg in enumerate(args):
            arg = arg.lower()
            if arg in valid_sorts:
                sort = arg
                break
        if sort:
            del args[i]
        
        arguments = ArgumentValidator(self.bot, self.strafes)
        arguments.game.make_optional()
        arguments.style.make_optional()
        arguments.user.make_required()

        page = 1
        for i, arg in enumerate(args):
            arg = arg.lower()
            if arg == "txt":
                page = -1
                break
        if page == -1:
            del args[i]
        else:
            arguments.page.make_optional(1)
        
        valid, err = await arguments.evaluate(args, ctx.author.id)
        if not valid:
            await ctx.send(utils.fmt_md_code(err))
            return
        
        game : Game = arguments.game.value
        style : Style = arguments.style.value
        user : User = arguments.user.value
        await ctx.send(f"https://strafes.fiveman1.net/users/{user.id}?game={999 if game is None else game.value}&style={999 if style is None else style.value}")
        return

        async with ctx.typing():
            game : Game = arguments.game.value
            style : Style = arguments.style.value
            user : User = arguments.user.value
            if page != -1:
                page = arguments.page.value

            if sort and sort != "date":
                record_list, _ = await self.strafes.get_user_times(user, game, style, -1)
                page_count = ((len(record_list) - 1) // 25) + 1
            else:
                record_list, page_count = await self.strafes.get_user_times(user, game, style, page)
            if page_count == 0:
                if not style:
                    style = "all"
                if not game:
                    game = "both"
                await ctx.send(utils.fmt_md_code(f"No times found for {user.username} [game: {game}, style: {style}]"))
                return
            if page > page_count:
                page = page_count
            if sort and sort != "date":
                if sort == "time":
                    record_list.sort(key=lambda i : (i.time.millis, i.date.timestamp * -1))
                elif sort == "name":
                    record_list.sort(key=lambda i : (i.map.displayname, i.date.timestamp * -1))
                if page != -1:
                    end = page * 25
                    record_list = record_list[end-25:end]
            else:
                sort = "date"
            cols = [MessageCol.MAP_NAME, MessageCol.TIME, MessageCol.DATE]
            if game is None:
                game = "both"
                cols.append(MessageCol.GAME)
            if style is None:
                style = "all"
                cols.append(MessageCol.STYLE)
            if page == -1:
                msg = MessageBuilder(title=f"Recent times for {user.username} [game: {game}, style: {style}, sort: {sort}] (total: {len(record_list)})", 
                    cols=cols, 
                    items=record_list
                ).build()
                with StringIO() as f:
                    f.write(msg)
                    f.seek(0)
                    await ctx.send(file=discord.File(f, filename=f"times_{user.username}_{game}_{style}.txt"))
                    return
            msg = MessageBuilder(title=f"Recent times for {user.username} [game: {game}, style: {style}, sort: {sort}, page: {page}/{page_count}]", 
                cols=cols, 
                items=record_list
            ).build()
            for message in utils.page_messages(msg):
                await ctx.send(utils.fmt_md_code(message))
    
    @commands.command(name="mapcount")
    async def map_count(self, ctx:Context):
        await ctx.send(f"https://strafes.fiveman1.net/maps")
        return
        embed = discord.Embed(title=f"\N{CLIPBOARD}  Map Count", color=0xfc9c00)
        embed.add_field(name="Bhop Maps", value=str(await self.strafes.get_map_count(Game.BHOP)))
        embed.add_field(name="Surf Maps", value=str(await self.strafes.get_map_count(Game.SURF)))
        embed.add_field(name="More info", value="https://wiki.strafes.net/maps")
        await ctx.send(embed=embed)

    @commands.command(name="compare")
    async def compare(self, ctx:Context, *args : str):
        await ctx.send(f"https://strafes.fiveman1.net/compare")
        return
        game : Game = None
        txt : bool = False
        styles : List[Style] = []
        users : List[User] = []
        for arg in args:
            if arg == "txt":
                txt = True
            elif Game.contains(arg):
                game = Game(arg)
            elif Style.contains(arg):
                styles.append(Style(arg))
            else:
                arguments = ArgumentValidator(self.bot, self.strafes)
                arguments.user.make_required()
                valid, err = await arguments.set_user(arg, ctx.author.id)
                if not valid:
                    await ctx.send(utils.fmt_md_code(err))
                    return
                if len(users) > 7:
                    await ctx.send(utils.fmt_md_code("You can only compare up to 8 users at a time."))
                    return
                else:
                    users.append(arguments.user.value)
        if len(users) == 1 and len(styles) > 1:
            user = users[0]
            users = [user for _ in range(len(styles))]
        if game is None:
            await ctx.send(utils.fmt_md_code("No game specified."))
            return
        elif len(users) < 2:
            await ctx.send(utils.fmt_md_code("Not enough users specified."))
            return
        elif len(styles) != 1 and len(styles) != len(users):
            await ctx.send(utils.fmt_md_code("No style specified or the number of styles does not match the number of users."))
            return
        
        async with ctx.typing():
            comparables : Dict[ComparableUserStyle, int] = {}
            comparables_list : List[ComparableUserStyle] = []
            for i, user in enumerate(users):
                style = styles[i] if len(styles) > 1 else styles[0]
                comparable = ComparableUserStyle(user, style)
                if comparable in comparables:
                    await ctx.send(utils.fmt_md_code(f"You cannot compare users to themselves with the same style (user: {user}, style: {style})"))
                    return
                else:
                    comparables[comparable] = i
                    comparables_list.append(comparable)
            
            tasks = []
            for c in comparables:
                tasks.append(self.strafes.get_user_times(c.user, game, c.style, -1))
            times : List[Tuple[List[Record], int]] = await asyncio.gather(*tasks)

            wins : List[List[Record]] = [[] for _ in users]
            ties : List[Record] = []
            not_shared : List[List[Record]] = [[] for _ in users]
            combined : Dict[Map, List[Record]] = {}
            for records, _ in times:
                for record in records:
                    if record.map in combined:
                        combined[record.map].append(record)
                    else:
                        combined[record.map] = [record]
            for records in combined.values():
                if len(records) == 1:
                    not_shared[self.record_to_idx(records[0], comparables)].append(records[0])
                else:
                    best = None
                    tie = False
                    for record in records:
                        if best is None:
                            best = record
                        elif record.time.millis < best.time.millis:
                            tie = False
                            record.previous_record = best
                            best = record
                        elif record.time.millis == best.time.millis:
                            tie = True
                        elif best.previous_record is None or best.previous_record.time.millis > record.time.millis:
                            best.previous_record = record
                    if tie:
                        ties.append(best)
                    else:
                        wins[self.record_to_idx(best, comparables)].append(best)
            for ls in wins:
                ls.sort(key=lambda i : i.map.displayname)
            ties.sort(key=lambda i : i.map.displayname)
            for ls in not_shared:
                ls.sort(key=lambda i : i.map.displayname)

            if len(styles) > 1:
                title = " vs. ".join([f"{c.user} ({c.style})" for c in comparables_list])
            else:
                title = " vs. ".join([user.username for user in users])
            embed = discord.Embed(title=title, color=0x00ff7f)
            file = None

            if len(users) == 2:
                tasks = [self.safe_get_user_headshot_url(users[0].id), self.safe_get_user_headshot_url(users[1].id)]
                urls = await asyncio.gather(*tasks)
                url1 = urls[0]
                url2 = urls[1]
                file = None
                if url1 is not None and url2 is not None:
                    try:
                        tasks = [self.strafes.get_bytes(url1), self.strafes.get_bytes(url2)]
                        images = await asyncio.gather(*tasks)
                        img1 = Image.open(BytesIO(images[0]))
                        img2 = Image.open(BytesIO(images[1]))
                        pixels1 = numpy.asarray(img1)
                        pixels2 = numpy.asarray(img2)
                        # Create a new image by drawing a diagonal line between the two images and combining them
                        new_pixels = [list(range(180)) for _ in range(180)]
                        for i in range(180):
                            for j in range(180):
                                val = i + j
                                if val < 177:
                                    new_pixels[i][j] = pixels1[i][j]
                                elif val > 183:
                                    new_pixels[i][j] = pixels2[i][j]
                                else:
                                    r, g, b = colorsys.hsv_to_rgb(i / 180, 1, 1)
                                    new_pixels[i][j] = numpy.asarray([r * 255, g * 255, b * 255, 255], dtype=numpy.uint8)
                        new_image = Image.fromarray(numpy.array(new_pixels))
                        # https://stackoverflow.com/questions/63209888/send-pillow-image-on-discord-without-saving-the-image
                        with BytesIO() as image_binary:
                            new_image.save(image_binary, "PNG")
                            image_binary.seek(0)
                            file = discord.File(fp=image_binary, filename="thumb.png")
                            embed.set_thumbnail(url="attachment://thumb.png")
                    except:
                        pass

            msg = []
            if len(styles) == 1:
                name = f"Info (game: {game}, style: {styles[0]})"
                for i, ls in enumerate(wins):
                    c = comparables_list[i]
                    msg.append(f"{c.user} wins: **{len(ls)}**")
                msg.append(f"Ties: **{len(ties)}**")
                for i, ls in enumerate(not_shared):
                    c = comparables_list[i]
                    msg.append(f"Only completed by {c.user}: **{len(ls)}**")
            else:
                name = f"Info (game: {game})"
                for i, ls in enumerate(wins):
                    c = comparables_list[i]
                    msg.append(f"{c.user} ({c.style}) wins: **{len(ls)}**")
                msg.append(f"Ties: **{len(ties)}**")
                for i, ls in enumerate(not_shared):
                    c = comparables_list[i]
                    msg.append(f"Only completed by {c.user} ({c.style}): **{len(ls)}**")
            embed.add_field(name=name, value="\n".join(msg))
            if file is not None:
                await ctx.send(embed=embed, file=file)
            else:
                await ctx.send(embed=embed)

            if txt:
                msgs = [f"Game: {game}"]
                for i, ls in enumerate(wins):
                    c = comparables_list[i]
                    msgs.append(MessageBuilder(title=f"{c.user} wins (style: {c.style}):",
                        cols=[MessageCol.MAP_NAME, MessageCol.TIME, MessageCol.DATE, MessageCol.Col(title="Next best", width=30, map=self.compare_formatter)],
                        items=ls
                    ).build())
                msgs.append(MessageBuilder(title="Ties:",
                    cols=[MessageCol.MAP_NAME, MessageCol.TIME],
                    items=ties
                ).build())
                for i, ls in enumerate(not_shared):
                    c = comparables_list[i]
                    msgs.append(MessageBuilder(title=f"Only completed by {c.user} (style: {c.style}):",
                        cols=[MessageCol.MAP_NAME, MessageCol.TIME, MessageCol.DATE],
                        items=ls
                    ).build())
                with StringIO() as f:
                    f.write("\n".join(msgs))
                    f.seek(0)
                    fname = "_vs_".join([user.username for user in users]) + f"_{game}"
                    if len(styles) == 1:
                        fname += f"_{styles[0]}"
                    fname += ".txt"
                    await ctx.send(file=discord.File(f, filename=fname))
    
    def compare_formatter(self, record: Record) -> str:
        diff = (record.previous_record.time.millis - record.time.millis) / 1000.0
        return f"{record.previous_record.user.username} (+{diff:.3f}s)"

    def record_to_idx(self, record : Record, comparables) -> int:
        return comparables[ComparableUserStyle(record.user, record.style)]

    @commands.command(name="mapstatus")
    async def map_status(self, ctx:Context, *args : str):
        arguments = ArgumentValidator(self.bot, self.strafes)
        arguments.game.make_required()
        arguments.style.make_required()
        arguments.user.make_required()
        valid, err = await arguments.evaluate(args, ctx.author.id)
        if not valid:
            await ctx.send(utils.fmt_md_code(err))
            return
        game : Game = arguments.game.value
        style : Style = arguments.style.value
        user : User = arguments.user.value
        
        await ctx.send(f"https://strafes.fiveman1.net/users/{user.id}?game={game.value}&style={style.value}")
        return

        async with ctx.typing():
            records, _ = await self.strafes.get_user_times(user, game, style, -1)
            completed_maps = set(i.map for i in records)
            incompleted_maps = []
            map_count = await self.strafes.get_map_count(game)
            maps = await self.strafes.get_all_maps()
            for map in maps:
                if map.game == game and map not in completed_maps:
                    # TODO: binary search insert
                    incompleted_maps.append(map)
            incompleted_maps.sort(key=lambda i: i.displayname)
            msg = MessageBuilder(title=f"Incomplete maps for {user.username} [game: {game}, style: {style}] (total: {len(incompleted_maps)} / {map_count})",
                cols=[MessageCol.Col("Map name", 30, lambda i: i.displayname)],
                items=incompleted_maps
                ).build()
            with StringIO() as f:
                f.write(msg)
                f.seek(0)
                await ctx.send(file=discord.File(f, filename=f"incomplete_maps_{user.username}_{game}_{style}.txt"))

    @commands.command(name="maps")
    async def maps(self, ctx:Context, *args : str):
        await ctx.send(f"https://strafes.fiveman1.net/maps")
        return
        creator = None
        page = 1
        if len(args) > 1:
            creator = args[0]
            page = int(args[1]) if args[1].isnumeric() else None
        if len(args) == 1:
            if args[0].isnumeric():
                page = int(args[0])
            elif args[0] == "txt":
                page = None
            else:
                creator = args[0]
        the_maps = await self.strafes.get_maps_by_creator(creator)
        if not the_maps:
            await ctx.send(utils.fmt_md_code(f"No maps found by '{creator}'."))
            return
        the_maps.sort(key=lambda k: (k.game.name, k.displayname))
        cols = [MessageCol.Col("Map name", 30, lambda m: m.displayname),
                    MessageCol.Col("Creator", 35, lambda m: m.creator),
                    MessageCol.GAME,
                    MessageCol.Col("Server loads", 14, lambda m: str(m.playcount))]
        if page:
            total_pages = (len(the_maps) - 1) // 20 + 1
            if page > total_pages:
                page = total_pages
            the_maps = the_maps[(page-1)*20:page*20]
            if creator:
                msg = MessageBuilder(title=f"Search result for maps by '{creator}' [page: {page} / {total_pages}]",
                    cols=cols,
                    items=the_maps
                ).build()
                await ctx.send(utils.fmt_md_code(msg))
            else:
                msg = MessageBuilder(title=f"List of all maps [page: {page} / {total_pages}]",
                    cols=cols,
                    items=the_maps
                ).build()
                await ctx.send(utils.fmt_md_code(msg))
        else:
            if creator:
                msg = MessageBuilder(title=f"Search result for maps by '{creator}'",
                    cols=cols,
                    items=the_maps
                ).build()
                fname = f"maps_by_{creator}.txt"
            else:
                msg = MessageBuilder(title=f"List of all maps",
                    cols=cols,
                    items=the_maps
                ).build()
                fname = "all_maps.txt"
            with StringIO() as f:
                f.write(msg)
                f.seek(0)
                await ctx.send(file=discord.File(f, filename=fname))

    @commands.command(name="user")
    async def user_info(self, ctx:Context, *args : str):
        async with ctx.typing():
            arguments = ArgumentValidator(self.bot, self.strafes)
            arguments.user.make_required()
            arguments.user.check_status = False
            arguments.user.allow_id = True
            valid, err = await arguments.evaluate(args, ctx.author.id)
            if not valid:
                await ctx.send(utils.fmt_md_code(err))
                return
            user : User = arguments.user.value
            embed = discord.Embed(color=0xfcba03)
            url = await self.safe_get_user_headshot_url(user.id)
            if url:
                embed.set_thumbnail(url=url)
            embed.add_field(name="Username", value=user.username, inline=True)
            embed.add_field(name="ID", value=user.id, inline=True)
            embed.add_field(name="Display name", value=user.displayname, inline=True)
            embed.set_footer(text="User Info")
            await ctx.send(embed=embed)

    @commands.command(name="help")
    async def help(self, ctx:Context, cmd : str = ""):
        cmd = cmd.lower()
        embed = discord.Embed(title="\U00002753  Help", color=0xe32f22) #\U00002753: red question mark
        embed.set_thumbnail(url="https://i.imgur.com/ief5VmF.png")
        commands_json = utils.open_json("files/help.json")
        if cmd:
            if cmd in commands_json:
                command = commands_json[cmd]
                embed.add_field(name=f"{self.bot.command_prefix}{cmd} {command['args']}", value=command['blurb'], inline=False)
            else:
                await ctx.send(utils.fmt_md_code(f"Command '{cmd}' not recognized! Use !help with no command to get a list of valid commands."))
                return
        else:
            use_txt = "Do **" + self.bot.command_prefix + "help {command}** to get info on how to use a command."
            embed.add_field(name="How to use", value=use_txt, inline=False)
            cmds = [c for c in commands_json.keys()]
            cmds.sort()
            embed.add_field(name="All Commands", value=", ".join(cmds), inline=False)
            games_txt = ", ".join(sorted([str(i) for i in DEFAULT_GAMES]))
            embed.add_field(name=f"Games", value=games_txt, inline=False)
            styles_txt = ", ".join(sorted([str(i) for i in DEFAULT_STYLES]))
            embed.add_field(name=f"Styles", value=styles_txt, inline=False)

        await ctx.send(embed=embed)
    
    @staticmethod
    def format_aliases(ls):
        if not ls:
            return ""
        elif len(ls) == 1:
            return f"**{ls[0]}**"
        else:
            return f"**{ls[0]}**: " + ", ".join(ls[1:])

    @commands.command(name="aliases")
    async def aliases(self, ctx:Context):
        embed = discord.Embed(title="\U00002139  Aliases", color=0xff0055) #\U00002139: information source emoji
        embed.set_thumbnail(url="https://i.imgur.com/ief5VmF.png")
        games = [game for game in Game]
        games.sort(key=str)
        games_txt = []
        for game in games:
            games_txt.append(self.format_aliases(GAME_ENUM[game.value]))
        embed.add_field(name="__Games__", value="\n".join(games_txt), inline=False)
        styles = [style for style in Style]
        styles.sort(key=str)
        styles_txt = []
        for style in styles:
            styles_txt.append(self.format_aliases(STYLE_ENUM[style.value]))
        embed.add_field(name="__Styles__", value="\n".join(styles_txt), inline=False)
        embed.set_footer(text="Game and style aliases")
        await ctx.send(embed=embed)

    @commands.command(name="link")
    async def link(self, ctx : Context, *args : str):
        async with ctx.typing():
            if len(args) > 0:
                arguments = ArgumentValidator(self.bot, self.strafes)
                arguments.user.make_required()
                arguments.user.check_status = False
                arguments.user.allow_id = True
                arguments.user.allow_discord = False
                valid, err = await arguments.evaluate(args)
                if not valid:
                    await ctx.send(utils.fmt_md_code(err))
                    return
                user : User = arguments.user.value

                res = await self.strafes.begin_verify_user(ctx.author.id, user)
                if res:
                    phrase = res.result["phrase"]
                    embed = discord.Embed(title="\U0001F517  Link Roblox To Discord", color=discord.Colour.from_rgb(111, 141, 222)) #\U0001F517: chain link emoji
                    embed.add_field(name="__Phrase__", value=phrase, inline=False)
                    msg =   f"""
                            1. Copy the phrase above.
                            2. Paste the entire phrase into your About section on Roblox.
                            3. Do '{self.bot.command_prefix}link'.
                            4. If the phrase is in your description then you will be linked. That's it!
                            Note: the phrase expires after ***15 minutes***. You will need to use this command again to generate a new one if you wait too long.
                            """
                    embed.add_field(name="__How to link your Roblox account__", value=msg, inline=False)
                    embed.set_footer(text=f"Linking username {user.username} ({user.id})")
                    try:
                        await ctx.author.send(embed=embed)
                        await ctx.send(utils.fmt_md_code("DM sent."))
                    except discord.Forbidden:
                        await ctx.send(utils.fmt_md_code("I could not DM you instructions. Please check that you are allowing DMs (Settings -> Privacy & Saftery -> Allow direct messages from server members)."))
                elif res.error_code == ErrorCode.ALREADY_VERIFIED:
                    await ctx.send(utils.fmt_md_code(f"You already have an account linked to your Discord! Use '{self.bot.command_prefix}unlink' to unlink your account first."))
                else:
                    await ctx.send(utils.fmt_md_code("An unexpected error occurred."))
            else:
                res = await self.strafes.try_verify_user(ctx.author.id)
                if res:
                    username = res.result["robloxUsername"]
                    await ctx.send(utils.fmt_md_code(f"Successfully verified user '{username}'. Your account is now linked."))
                elif res.error_code == ErrorCode.ALREADY_VERIFIED:
                    await ctx.send(utils.fmt_md_code(f"You already have an account linked to your Discord! Use '{self.bot.command_prefix}help link' for more info."))
                elif res.error_code == ErrorCode.PHRASE_NOT_FOUND:
                    username = res.result["robloxUsername"]
                    await ctx.send(utils.fmt_md_code(f"Could not verify user '{username}'. Are you sure you pasted the phrase into your description? Is the username correct?"))
                elif res.error_code == ErrorCode.VERIFICATION_NOT_ACTIVE:
                    await ctx.send(utils.fmt_md_code(f"To link an account, do '{self.bot.command_prefix}link {{username}}'. If you already have but it has been longer than 15 minutes, you need to generate a new phrase."))
                else:
                    await ctx.send(utils.fmt_md_code("An unexpected error occurred."))

    @commands.command(name="unlink")
    async def unlink(self, ctx : Context):
        async with ctx.typing():
            user = await self.strafes.remove_discord_to_roblox(ctx.author.id)
            if user:
                await ctx.send(utils.fmt_md_code(f"Successfully unlinked user '{user.username}'."))
            else:
                await ctx.send(utils.fmt_md_code("You don't have an account linked!"))
    
    @commands.command(name="guilds")
    @commands.is_owner()
    async def guilds(self, ctx:Context):
        member_count = 0
        titles = ["Name:", "Members:", "Owner:"]
        msg = f"{titles[0]:40}| {titles[1]}\n"
        for guild in self.bot.guilds:
            name = guild.name[:40]
            members = guild.member_count
            member_count += guild.member_count
            msg += f"{name:40}| {members}\n"
        msg = f"Total guilds: {len(self.bot.guilds)}, total members: {member_count}\n" + msg
        for m in utils.page_messages(msg):
            await ctx.send(utils.fmt_md_code(m))

    @commands.command(name="updatemaps")
    @commands.is_owner()
    async def update_maps_cmd(self, ctx:Context):
        await self.strafes.load_maps()
        await ctx.send(utils.fmt_md_code("Maps updated."))

    def get_ordinal(self, num:int) -> str:
        remainder = num % 100
        if remainder > 13 or remainder < 11:
            n = remainder % 10
            if n == 1:
                return "st"
            elif n == 2:
                return "nd"
            elif n == 3:
                return "rd"
        return "th"
    
    def make_global_embed(self, record: Record):
        map_url = f"https://strafes.fiveman1.net/maps/{record.map.id}?game={record.game.value}&style={record.style.value}"
        embed = discord.Embed(title=f"\N{CROWN}  {record.map.displayname}", color=0x80ff80, url=map_url)
        embed.set_author(name="New WR", icon_url="https://i.imgur.com/PtLyW2j.png")
        url = record.user.thumbnail
        if url:
            embed.set_thumbnail(url=url)
        player_url = f"https://strafes.fiveman1.net/users/{record.user.id}?game={record.game.value}&style={record.style.value}"
        embed.add_field(name="Player", value=f"[{record.user.username}]({player_url})", inline=True)
        time = f"{record.time} "
        info = f"**Game:** {record.game}\n**Style:** {record.style}\n**Date:** <t:{record.date.timestamp}:f>\n**Previous WR:** "
        if not record.previous_record:
            time += "(-n/a s)"
            info += "n/a"
        else:
            time += f"({record.diff:+.3f} s)"
            info += f"{record.previous_record.time} ({record.previous_record.user.username})"
        embed.add_field(name="Time", value=time, inline=True)
        embed.add_field(name="Info", value=info, inline=False)
        map_thumb_url = record.map.thumbnail
        if map_thumb_url:
            embed.set_image(url=map_thumb_url)
        embed.set_footer(text="World Record")
        return embed
    
    async def make_user_embed(self, user:User, rank_data:Rank, game:Game, style:Style, completions, total_maps, wrs):
        ordinal = self.get_ordinal(rank_data.placement)
        if user.username != user.displayname:
            name = f"{user.displayname} ({user.username})"
        else:
            name = user.username
        embed = discord.Embed(title=f"\N{NEWSPAPER}  {name}", color=0x1dbde0)
        url = await self.safe_get_user_headshot_url(user.id)
        if url:
            embed.set_thumbnail(url=url)
        embed.add_field(name="Rank", value=f"{rank_data} ({rank_data.rank})", inline=True)
        embed.add_field(name="Skill", value=f"{rank_data.skill:.3f}%", inline=True)
        embed.add_field(name="Placement", value=f"{rank_data.placement}{ordinal}") if rank_data.placement > 0 else embed.add_field(name="Placement", value="n/a")
        embed.add_field(name="Info", value=f"**Game:** {game}\n**Style:** {style}\n**WRs:** {wrs}\n**Completion:** {100 * completions / total_maps:.2f}% ({completions}/{total_maps})\n**Moderation status:** {user.state}")
        embed.set_footer(text="User Profile")
        return embed

    async def safe_get_user_headshot_url(self, user_id : int) -> Optional[str]:
        try:
            return await self.strafes.get_user_headshot_url(user_id)
        except APIError:
            return None

    async def safe_get_asset_thumbnail(self, asset_id : int) -> Optional[str]:
        try:
            return await self.strafes.get_asset_thumbnail(asset_id)
        except APIError:
            return None
        
    async def safe_get_map_thumbs(self, records: List[Record]):
        try:
            return await self.strafes.get_map_thumbs(records)
        except APIError:
            return {}

async def setup(bot : commands.Bot):
    await bot.add_cog(MainCog(bot))