# maincog.py
import asyncio
import colorsys
import discord
from discord.ext.commands.context import Context
from dotenv import load_dotenv
from discord.errors import InvalidData
from discord.ext import commands, tasks
from io import BytesIO, StringIO
import numpy
import os
from PIL import Image
import requests
import time
import traceback
from typing import Callable, Dict, List, Tuple, Union

from modules.strafes import Game, Style, User, UserState, Map, Record, Rank, DEFAULT_GAMES, DEFAULT_STYLES, open_json
from modules import utils
from modules.utils import Incrementer, StringBuilder
from modules.strafes_wrapper import Client

class ArgumentChecker:
    def __init__(self):
        self.game:Game = None
        self.style:Style = None
        self.user_data:User = None
        self.map:Map = None
        self.valid = False
    def __bool__(self):
        return self.valid

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

# TODO: why do i have one cog for everything
class MainCog(commands.Cog):
    def __init__(self, bot):
        self.bot:commands.Bot = bot
        self.bot.remove_command("help")
        load_dotenv()
        self.strafes = Client(os.getenv("API_KEY"))
        self.globals_started = False
        self.global_announcements.start()
        print("maincog loaded")
    
    def cog_unload(self):
        print("unloading maincog")
        self.global_announcements.cancel()
        self.strafes.close()

    async def try_except(self, coroutine):
        try:
            await coroutine
        except:
            pass

    async def create_global_embed(self, record):
        return (record.game, record.style, await self.make_global_embed(record))

    @tasks.loop(minutes=1)
    async def global_announcements(self):
        # this is wrapped in a try-except because if this raises
        # an error the entire task stops and we don't want that :)
        # yeah this is a bad practice but idk what else to do
        try:
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
                start = time.time()
                embed_tasks = []
                for record in records:
                    print(f"New global:\n{record}")
                    embed_tasks.append(self.create_global_embed(record))
                all_embeds = await asyncio.gather(*embed_tasks)
                end = time.time()
                print(f"embeds created: {end-start}s")
                start = time.time()
                bhop_auto = []
                bhop_style = []
                surf_auto = []
                surf_style = []
                for game, style, embed in all_embeds:
                    if game == Game.BHOP and style == Style.AUTOHOP:
                        bhop_auto.append(embed)
                    elif game == Game.BHOP and style != Style.AUTOHOP:
                        bhop_style.append(embed)
                    elif game == Game.SURF and style == Style.AUTOHOP:
                        surf_auto.append(embed)
                    elif game == Game.SURF and style != Style.AUTOHOP:
                        surf_style.append(embed)
                tasks = []
                for guild in self.bot.guilds:
                    for ch in guild.text_channels:
                        if ch.name == "globals":
                            for _,_,embed in all_embeds:
                                tasks.append(self.try_except(ch.send(embed=embed)))
                        elif ch.name == "bhop-auto-globals":
                            for embed in bhop_auto:
                                tasks.append(self.try_except(ch.send(embed=embed)))
                        elif ch.name == "bhop-styles-globals":
                            for embed in bhop_style:
                                tasks.append(self.try_except(ch.send(embed=embed)))
                        elif ch.name == "surf-auto-globals":
                            for embed in surf_auto:
                                tasks.append(self.try_except(ch.send(embed=embed)))
                        elif ch.name == "surf-styles-globals":
                            for embed in surf_style:
                                tasks.append(self.try_except(ch.send(embed=embed)))
                await asyncio.gather(*tasks)
                end = time.time()
                print(f"embeds posted: {end-start}s")
        except Exception as error:
            try:
                tb_channel = self.bot.get_channel(812768023920115742)
                tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
                for msg in utils.page_messages(f"Error in globals!\n{type(error).__name__}: {error}\n" + tb):
                    await tb_channel.send(f"```\n{msg}\n```")
            except:
                pass
            
    @global_announcements.before_loop
    async def before_global_announcements(self):
        print("waiting for ready")
        #we have to wait for the bot to on_ready() or we won't be able to find channels/guilds
        await self.bot.wait_until_ready()

    @commands.command(name="recentwrs")
    async def get_recent_wrs(self, ctx:Context, game, style="autohop"):
        arguments = await self.argument_checker(ctx, game=game, style=style)
        if not arguments:
            return
        msg = MessageBuilder(title=f"10 Recent WRs [game: {arguments.game}, style: {arguments.style}]", 
            cols=[MessageCol.USERNAME, MessageCol.MAP_NAME, MessageCol.TIME, MessageCol.DATE], 
            items= await self.strafes.get_recent_wrs(arguments.game, arguments.style)
        ).build()
        await ctx.send(self.format_markdown_code(msg))

    @commands.command(name="record")
    async def get_user_record(self, ctx:Context, user, game, style, *, map_name):
        arguments = await self.argument_checker(ctx, user=user, game=game, style=style, map_name=map_name)
        if not arguments:
            return
        record = await self.strafes.get_user_record(arguments.user_data, arguments.game, arguments.style, arguments.map)
        if record is None:
            await ctx.send(self.format_markdown_code(f"No record by {arguments.user_data.username} found on map: {arguments.map.displayname} [game: {arguments.game}, style: {arguments.style}]"))
        else:
            placement, total_completions = await self.strafes.get_record_placement(record)
            msg = MessageBuilder(title=f"{arguments.user_data.username}'s record on {record.map.displayname} [game: {arguments.game}, style: {arguments.style}]",
                cols=[MessageCol.TIME, MessageCol.DATE, MessageCol.Col("Placement", 20, lambda _: f"{placement}{self.get_ordinal(placement)} / {total_completions}")],
                items=[record]
            ).build()
            await ctx.send(self.format_markdown_code(msg))

    @commands.command(name="wrmap")
    async def get_wrmap(self, ctx:Context, game, style, *args):
        if len(args) == 0:
            await ctx.send(self.format_markdown_code("Missing map name."))
            return
        elif len(args) > 1 and args[-1].isnumeric():
            page = int(args[-1])
            map_name = " ".join(args[:-1])
        else:
            page = 1
            map_name = " ".join(args)
        if not map_name:
            await ctx.send(self.format_markdown_code("Missing map name."))
            return
        if page < 1:
            await ctx.send(self.format_markdown_code("Page number cannot be less than 1."))
            return
        arguments = await self.argument_checker(ctx, game=game, style=style, map_name=map_name)
        if not arguments:
            return
        records, page_count = await self.strafes.get_map_times(arguments.style, arguments.map, page)
        if page_count == 0:
            await ctx.send(self.format_markdown_code(f"{arguments.map.displayname} has not yet been completed in {arguments.style}."))
            return
        else:
            if page > page_count:
                page = page_count
            incrementer = Incrementer(((page - 1) * 25) + 1)
            msg = MessageBuilder(title=f"Record list for map: {arguments.map.displayname} [game: {arguments.game}, style: {arguments.style}, page: {page}/{page_count}]", 
                cols=[MessageCol.Col("Placement", 11, lambda _ : incrementer.increment()), MessageCol.USERNAME, MessageCol.TIME, MessageCol.DATE], 
                items=records
            ).build()
            await ctx.send(self.format_markdown_code(msg))

    @commands.cooldown(4, 60, commands.cooldowns.BucketType.guild)
    @commands.command(name="wrlist")
    async def wr_list(self, ctx:Context, user, *args):
        valid_sorts = ["", "date", "time", "name"]
        sort = ""
        page = 1
        game = None
        style = None
        args = args[:4] if len(args) >= 4 else args
        for i in args:
            i = i.lower()
            if i in valid_sorts:
                sort = i
            elif i.isnumeric():
                page = int(i)
            elif i == "txt":
                page = -1
            elif i == "both":
                game = "both"
            elif i == "all":
                if game:
                    style = "all"
                else:
                    game = "all"
            elif Game.contains(i) and not game:
                game = i
            elif Style.contains(i) and not style:
                style = i

        #loop through all games or all styles if not specified (or if "both" or "all")
        arguments = await self.argument_checker(ctx, user=user, game=None if game in [None, "both", "all"] else game, style=None if style in [None, "all"] else style)
        if not arguments:
            return
        if game in [None, "both", "all"]:
            g = DEFAULT_GAMES
        else:
            g = [arguments.game]
        if style in [None, "all"]:
            s = DEFAULT_STYLES
        else:
            s = [arguments.style]

        tasks = []
        for _game in g:
            for _style in s:
                if not (_game == Game.SURF and _style == Style.SCROLL):
                    tasks.append(self.strafes.get_user_wrs(arguments.user_data, _game, _style))  
        results = await asyncio.gather(*tasks)
        
        wrs:List[Record] = []
        count = 0
        for result in results:
            wrs += result
            count += len(result)
        if count == 0:
            await ctx.send(self.format_markdown_code(f"{arguments.user_data.username} has no WRs in the specified game and style."))
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
        else:
            game = arguments.game
        if s is DEFAULT_STYLES:
            style = "all"
            cols.append(MessageCol.STYLE)
        else:
            style = arguments.style
        if sort == "":
            sort = "default"
        if page != -1:
            total_pages = ((count - 1) // 25) + 1
            if page > total_pages:
                page = total_pages
            msg = MessageBuilder(cols=cols, items=wrs[(page-1)*25:page*25]).build()
            the_messages = utils.page_messages(f"WR list for {arguments.user_data.username} [game: {game}, style: {style}, sort: {sort}, page: {page}/{total_pages}] (Records: {count})\n{msg}")
            for m in the_messages:
                await ctx.send(self.format_markdown_code(m))
        else:
            with StringIO() as f:
                msg = MessageBuilder(cols=cols, items=wrs).build()
                f.write(f"WR list for {arguments.user_data.username} [game: {game}, style: {style}, sort: {sort}] (Records: {count})\n{msg}")
                f.seek(0)
                await ctx.send(file=discord.File(f, filename=f"wrs_{arguments.user_data.username}_{game}_{style}.txt"))

    @commands.command(name="map")
    async def map_info(self, ctx:Context, *args):
        if len(args) == 0:
            await ctx.send(self.format_markdown_code("Missing arguments."))
            return
        elif not Game.contains(args[-1]):
            game = None
            map_name = " ".join(args)
        else:
            game = Game(args[-1])
            map_name = " ".join(args[:-1])
        if map_name == "":
            await ctx.send(self.format_markdown_code("No map specified."))
            return
        the_map = await self.strafes.map_from_name(map_name, game)
        if the_map is None:
            if map_name.isnumeric():
                the_map = await self.strafes.map_from_id(int(map_name))
            if the_map is None or the_map.id == -1:
                await ctx.send(self.format_markdown_code(f"\"{map_name}\" is not a valid map."))
                return
        
        embed = discord.Embed(color=0x7c17ff)
        url = await self.strafes.get_asset_thumbnail(the_map.id)
        if url:
            embed.set_thumbnail(url=url)
        embed.set_footer(text="Map Info")
        embed.title = f"\U0001F5FA  {the_map.displayname} ({the_map.game})"
        embed.add_field(name="Creator", value=the_map.creator)
        embed.add_field(name="Map ID", value=the_map.id)
        embed.add_field(name="Server Load Count", value=the_map.playcount)
        await ctx.send(embed=embed)

    @commands.cooldown(4, 60, commands.cooldowns.BucketType.guild)
    @commands.command(name="wrcount")
    async def wr_count(self, ctx:Context, user):
        arguments = await self.argument_checker(ctx, user=user)
        if not arguments:
            return
        count = 0
        the_dict = {
            Game.BHOP: [],
            Game.SURF: []
        }
        async def the_order(game, style):
            return (game, style, await self.strafes.total_wrs(arguments.user_data, game, style))
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
        url = await self.strafes.get_user_headshot_url(arguments.user_data.id)
        if url:
            embed.set_thumbnail(url=url)
        embed.set_footer(text="WR Count")
        if arguments.user_data.username != arguments.user_data.displayname:
            name = f"{arguments.user_data.displayname} ({arguments.user_data.username})"
        else:
            name = arguments.user_data.username
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

    @commands.command(name="fastecheck")
    async def faste_check(self, ctx:Context, user, game, style):
        arguments = await self.argument_checker(ctx, user=user, game=game, style=style)
        if not arguments:
            return
        if arguments.style == Style.SCROLL:
            await ctx.send(self.format_markdown_code("Scroll is not eligible for faste."))
            return
        wrs = await self.strafes.total_wrs(arguments.user_data, arguments.game, arguments.style)
        if (arguments.style == Style.AUTOHOP and wrs >= 10) or wrs >= 50:
            await ctx.send(self.format_markdown_code(f"WRs: {wrs}\n{arguments.user_data.username} is eligible for faste in {arguments.game} in the style {arguments.style}."))
        else:
            await ctx.send(self.format_markdown_code(f"WRs: {wrs}\n{arguments.user_data.username} is NOT eligible for faste in {arguments.game} in the style {arguments.style}."))

    @commands.command(name="profile")
    async def user_rank(self, ctx:Context, user, game, style):
        arguments = await self.argument_checker(ctx, user=user, game=game, style=style)
        if not arguments:
            return
        tasks = [
            self.strafes.get_user_rank(arguments.user_data, arguments.game, arguments.style),
            self.strafes.get_user_completion(arguments.user_data, arguments.game, arguments.style),
            self.strafes.total_wrs(arguments.user_data, arguments.game, arguments.style)
        ]
        results = await asyncio.gather(*tasks)
        rank_data:Rank = results[0]
        if not rank_data or rank_data.placement < 1:
            await ctx.send(self.format_markdown_code(f"No data available for {arguments.user_data.username} [game: {arguments.game}, style: {arguments.style}]"))
            return
        else:
            completions, total_maps = results[1]
            wrs = results[2]
            await ctx.send(embed= await self.make_user_embed(arguments.user_data, rank_data, arguments.game, arguments.style, completions, total_maps, wrs))

    @commands.command(name="ranks")
    async def ranks(self, ctx:Context, game, style, page=1):
        page = int(page)
        if page < 1:
            await ctx.send(self.format_markdown_code("Page number cannot be less than 1."))
            return
        arguments = await self.argument_checker(ctx,game=game, style=style)
        if not arguments:
            return
        ranks, page_count = await self.strafes.get_ranks(arguments.game, arguments.style, page)
        if page_count == 0:
            await ctx.send(self.format_markdown_code(f"No ranks found [game: {arguments.game}, style: {arguments.style}] (???)."))
            return
        elif page > page_count:
            page = page_count
        msg = MessageBuilder(title=f"Ranks [game: {arguments.game}, style: {arguments.style}, page: {page}/{page_count}]",
            cols=[MessageCol.PLACEMENT, MessageCol.USERNAME, MessageCol.RANK, MessageCol.SKILL],
            items=ranks
        ).build()
        await ctx.send(self.format_markdown_code(msg))
    
    @commands.command(name="times")
    async def times(self, ctx:Context, user, *args):
        if len(args) == 0:
            game = None
            style = None
            page = 1
        elif len(args) == 1:
            style = None
            if args[0].isnumeric() or args[0] == "txt":
                game = None
                page = args[0]
            elif args[0] == "all":
                await ctx.send(self.format_markdown_code("To create a .txt use 'txt' instead of 'all'"))
                return
            else:
                game = args[0]
                page = 1
        elif len(args) == 2:
            game = args[0]
            if args[1].isnumeric() or args[1] == "txt":
                style = None
                page = args[1]
            elif args[1] == "all":
                await ctx.send(self.format_markdown_code("To create a .txt use 'txt' instead of 'all'"))
                return
            else:
                style = args[1]
                page = 1
        else:
            game = args[0]
            style = args[1]
            if args[2].isnumeric() or args[2] == "txt":
                page = args[2]
            elif args[2] == "all":
                await ctx.send(self.format_markdown_code("To create a .txt use 'txt' instead of 'all'"))
                return
            else:
                page = 1
        if page != "txt":
            page = int(page)
            if page < 1:
                await ctx.send(self.format_markdown_code("Page number cannot be less than 1."))
                return
        else:
            page = -1
        if game in ["all", "both"]:
            game = None
        if style == "all":
            style = None
        arguments = await self.argument_checker(ctx, user=user, game=game, style=style)
        if not arguments:
            return
        if style:
            style = arguments.style
        if game:
            game = arguments.game
        record_list, page_count = await self.strafes.get_user_times(arguments.user_data, game, style, page)
        if page_count == 0:
            if not style:
                style = "all"
            if not game:
                game = "both"
            await ctx.send(self.format_markdown_code(f"No times found for {arguments.user_data.username} [game: {game}, style: {style}]"))
            return
        elif page > page_count:
            page = page_count
        cols = [MessageCol.MAP_NAME, MessageCol.TIME, MessageCol.DATE]
        if game is None:
            game = "both"
            cols.append(MessageCol.GAME)
        if style is None:
            style = "all"
            cols.append(MessageCol.STYLE)
        if page == -1:
            msg = MessageBuilder(title=f"Recent times for {arguments.user_data.username} [game: {game}, style: {style}] (total: {len(record_list)})", 
                cols=cols, 
                items=record_list
            ).build()
            with StringIO() as f:
                f.write(msg)
                f.seek(0)
                await ctx.send(file=discord.File(f, filename=f"times_{arguments.user_data.username}_{game}_{style}.txt"))
                return
        msg = MessageBuilder(title=f"Recent times for {arguments.user_data.username} [game: {game}, style: {style}, page: {page}/{page_count}]", 
            cols=cols, 
            items=record_list
        ).build()
        for message in utils.page_messages(msg):
            await ctx.send(self.format_markdown_code(message))
    
    @commands.command(name="mapcount")
    async def map_count(self, ctx:Context):
        embed = discord.Embed(title=f"\N{CLIPBOARD}  Map Count", color=0xfc9c00)
        embed.add_field(name="Bhop Maps", value=str(await self.strafes.get_map_count(Game.BHOP)))
        embed.add_field(name="Surf Maps", value=str(await self.strafes.get_map_count(Game.SURF)))
        embed.add_field(name="More info", value="https://wiki.strafes.net/maps")
        await ctx.send(embed=embed)

    @commands.command(name="compare")
    async def compare(self, ctx:Context, *args):
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
                arguments = await self.argument_checker(ctx, arg)
                if not arguments:
                    return
                else:
                    if len(users) > 7:
                        await ctx.send(self.format_markdown_code("You can only compare up to 8 users at a time."))
                        return
                    else:
                        users.append(arguments.user_data)
        if len(users) == 1 and len(styles) > 1:
            user = users[0]
            users = [user for _ in range(len(styles))]
        if game is None:
            await ctx.send(self.format_markdown_code("No game specified."))
            return
        elif len(users) < 2:
            await ctx.send(self.format_markdown_code("Not enough users specified."))
            return
        elif len(styles) != 1 and len(styles) != len(users):
            await ctx.send(self.format_markdown_code("No style specified or the number of styles does not match the number of users."))
            return

        comparables : Dict[ComparableUserStyle, int] = {}
        comparables_list : List[ComparableUserStyle] = []
        for i, user in enumerate(users):
            style = styles[i] if len(styles) > 1 else styles[0]
            comparable = ComparableUserStyle(user, style)
            if comparable in comparables:
                await ctx.send(self.format_markdown_code(f"You cannot compare users to themselves with the same style (user: {user}, style: {style})"))
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
            tasks = [self.strafes.get_user_headshot_url(users[0].id), self.strafes.get_user_headshot_url(users[1].id)]
            urls = await asyncio.gather(*tasks)
            url1 = urls[0]
            url2 = urls[1]
            file = None
            if url1 is not None and url2 is not None:
                try:
                    # https://stackoverflow.com/questions/7391945/how-do-i-read-image-data-from-a-url-in-python
                    img1 = Image.open(requests.get(url1, stream=True).raw)
                    img2 = Image.open(requests.get(url2, stream=True).raw)
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
    async def map_status(self, ctx:Context, user, game, style):
        args = await self.argument_checker(ctx, user, game, style)
        if not args:
            return
        records = await self.strafes.get_user_times(args.user_data, args.game, args.style, -1)
        completed_maps = set(i.map.id for i in records[0])
        incompleted_maps = []
        map_count = await self.strafes.get_map_count(args.game)
        for id, map in Map.map_lookup.items():
            if map.game == args.game and id not in completed_maps:
                # TODO: binary search insert
                incompleted_maps.append(map)
        incompleted_maps.sort(key=lambda i: i.displayname)
        msg = MessageBuilder(title=f"Incomplete maps for {args.user_data.username} [game: {args.game}, style: {args.style}] (total: {len(incompleted_maps)} / {map_count})",
            cols=[MessageCol.Col("Map name", 30, lambda i: i.displayname)],
            items=incompleted_maps
            ).build()
        with StringIO() as f:
            f.write(msg)
            f.seek(0)
            await ctx.send(file=discord.File(f, filename=f"incomplete_maps_{args.user_data.username}_{args.game}_{args.style}.txt"))

    @commands.command(name="maps")
    async def maps(self, ctx:Context, *args):
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
            await ctx.send(self.format_markdown_code(f"No maps found by '{creator}'."))
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
                await ctx.send(self.format_markdown_code(msg))
            else:
                msg = MessageBuilder(title=f"List of all maps [page: {page} / {total_pages}]",
                    cols=cols,
                    items=the_maps
                ).build()
                await ctx.send(self.format_markdown_code(msg))
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
    async def user_info(self, ctx:Context, user:str):
        if user == "me":
            roblox_user = await self.strafes.get_roblox_user_from_discord(ctx.author.id)
            if not roblox_user:
                await ctx.send(self.format_markdown_code("Invalid username. No Roblox username associated with your Discord account."))
                return
            else:
                the_user = roblox_user
        elif user.isnumeric():
            the_user = int(user)
        else:
            discord_user_id = self.get_discord_user_id(user)
            if discord_user_id:
                roblox_user = await self.strafes.get_roblox_user_from_discord(discord_user_id)
                if not roblox_user:
                    try:
                        u  = await self.bot.fetch_user(int(discord_user_id))
                        if u:
                            await ctx.send(self.format_markdown_code(f"Invalid username ('{u.name}' does not have a Roblox account associated with their Discord account.)"))
                        else:
                            # I think this is redundant but I'm not sure
                            await ctx.send(self.format_markdown_code(f"Invalid username (no user associated with that Discord account.)"))
                    except:
                        await ctx.send(self.format_markdown_code(f"Invalid discord user ID."))
                    return
                else:
                    the_user = roblox_user
            else:
                the_user = user
        try:
            user_data = await self.strafes.get_user_data(the_user)
            embed = discord.Embed(color=0xfcba03)
            url = await self.strafes.get_user_headshot_url(user_data.id)
            if url:
                embed.set_thumbnail(url=url)
            embed.add_field(name="Username", value=user_data.username, inline=True)
            embed.add_field(name="ID", value=user_data.id, inline=True)
            embed.add_field(name="Display name", value=user_data.displayname, inline=True)
            embed.set_footer(text="User Info")
            await ctx.send(embed=embed)
        except InvalidData:
            if user.isnumeric():
                await ctx.send(self.format_markdown_code(f"Invalid user ID (user ID '{user}' does not exist on Roblox)."))
                return
            else:
                await ctx.send(self.format_markdown_code(f"Invalid username (username '{user}' does not exist on Roblox)."))
                return
        except TimeoutError:
            await ctx.send(self.format_markdown_code(f"Error: User data request timed out."))
            return

    @commands.command(name="help")
    async def help(self, ctx:Context, cmd : str = ""):
        cmd = cmd.lower()
        embed = discord.Embed(title="\U00002753  Help", color=0xe32f22) #\U00002753: red question mark
        embed.set_thumbnail(url="https://i.imgur.com/ief5VmF.png")
        commands_json = open_json("files/help.json")
        if cmd:
            if cmd in commands_json:
                command = commands_json[cmd]
                embed.add_field(name=f"{self.bot.command_prefix}{cmd} {command['args']}", value=command['blurb'], inline=False)
            else:
                await ctx.send(self.format_markdown_code(f"Command '{cmd}' not recognized! Use !help with no command to get a list of valid commands."))
                return
        else:
            embed.add_field(name="How to use", value="Do !help {command} to get info on how to use a command.", inline=False)
            cmds = [c for c in commands_json.keys()]
            cmds.sort()
            embed.add_field(name="All Commands", value=", ".join(cmds), inline=False)

        await ctx.send(embed=embed)
    
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
            await ctx.send(self.format_markdown_code(m))

    @commands.command(name="updatemaps")
    @commands.is_owner()
    async def update_maps(self, ctx:Context):
        await self.strafes.update_maps()
        await ctx.send(self.format_markdown_code("Maps updated."))
    
    def get_discord_user_id(self, s):
        if s[:3] == "<@!" and s[-1] == ">":
            return s[3:-1]
        elif s[:2] == "<@" and s[-1] == ">":
            return s[2:-1]
        else:
            return None
    
    #checks if user, game, style, and map_name are valid arguments
    #passing None as argument to any of these fields will pass the check for that field
    #returns an ArgumentChecker object with the properly converted arguments
    #is falsy if the check failed, truthy if it passed
    async def argument_checker(self, ctx:Context, user:str=None, game:str=None, style:str=None, map_name:str=None) -> ArgumentChecker:
        arguments = ArgumentChecker()
        if game:
            try:
                arguments.game = Game(game.lower())
            except KeyError:
                await ctx.send(self.format_markdown_code(f"'{game}' is not a valid game. 'bhop' and 'surf' are valid."))
                return arguments
        if style:
            try:
                arguments.style = Style(style.lower())
            except KeyError:
                await ctx.send(self.format_markdown_code(f"'{style}' is not a valid style. 'autohop', 'auto', 'aonly', 'hsw' are valid examples."))
                return arguments
        if arguments.game == Game.SURF and arguments.style == Style.SCROLL:
            await ctx.send(self.format_markdown_code("Surf and scroll cannot be combined."))
            return arguments
        if user:
            if user == "me":
                roblox_user = await self.strafes.get_roblox_user_from_discord(ctx.author.id)
                if not roblox_user:
                    await ctx.send(self.format_markdown_code("Invalid username (no Roblox username associated with your Discord account. Visit https://verify.eryn.io/)"))
                    return arguments
                else:
                    user = roblox_user
            else:
                discord_user_id = self.get_discord_user_id(user)
                if discord_user_id:
                    roblox_user = await self.strafes.get_roblox_user_from_discord(discord_user_id)
                    if not roblox_user:
                        try:
                            u = await self.bot.fetch_user(int(discord_user_id))
                            if u:
                                await ctx.send(self.format_markdown_code(f"Invalid username ('{u.name}' does not have a Roblox account associated with their Discord account.)"))
                            else:
                                await ctx.send(self.format_markdown_code(f"Invalid username (no user associated with that Discord account.)"))
                        except:
                            await ctx.send(self.format_markdown_code(f"Invalid discord user ID."))
                        return arguments
                    else:
                        user = roblox_user
            try:
                arguments.user_data = await self.strafes.get_user_data(user)
            except InvalidData:
                await ctx.send(self.format_markdown_code(f"Invalid username (username '{user}' does not exist on Roblox)."))
                return arguments
            except TimeoutError:
                await ctx.send(self.format_markdown_code(f"Error: User data request timed out."))
                return arguments
            if not await self.check_user_status(ctx, arguments.user_data):
                return arguments
        if map_name:
            arguments.map = await self.strafes.map_from_name(map_name, arguments.game)
            if not arguments.map:
                await ctx.send(self.format_markdown_code(f"\"{map_name}\" is not a valid {arguments.game} map."))
                return arguments
        arguments.valid = True
        return arguments
    
    #set the user_id and username of the argument_checker before passing it to this
    async def check_user_status(self, ctx:Context, user_data:User):
        state = await self.strafes.get_user_state(user_data)
        if not state:
            await ctx.send(self.format_markdown_code(f"'{user_data.username}' has not played bhop/surf."))
            return False
        else:
            user_data.state = state
            if user_data.state == UserState.BLACKLISTED:
                await ctx.send(self.format_markdown_code(f"{user_data.username} is blacklisted."))
                return False
            elif user_data.state == UserState.PENDING:
                await ctx.send(self.format_markdown_code(f"{user_data.username} is pending moderation."))
                return False
        return True

    def format_markdown_code(self, s : str):
        s = s.replace("`", "") # don't allow the ` character to prevent escaping code blocks
        return f"```\n{s}```"

    def get_ordinal(self, num:int) -> str:
        ordinal = "th"
        if num % 100 > 13 or num % 100 < 11:
            n = num % 10
            if n == 1:
                ordinal = "st"
            elif n == 2:
                ordinal = "nd"
            elif n == 3:
                ordinal = "rd"
        return ordinal
    
    async def make_global_embed(self, record:Record):
        embed = discord.Embed(title=f"\N{CROWN}  {record.map.displayname}", color=0x80ff80)
        embed.set_author(name="New WR", icon_url="https://i.imgur.com/PtLyW2j.png")
        url = await self.strafes.get_user_headshot_url(record.user.id)
        if url:
            embed.set_thumbnail(url=url)
        embed.add_field(name="Player", value=record.user.username, inline=True)
        if not record.previous_record:
            embed.add_field(name="Time", value=f"{record.time} (-n/a s)", inline=True)
            embed.add_field(name="Info", value=f"**Game:** {record.game}\n**Style:** {record.style}\n**Date:** {record.date}\n**Previous WR:** n/a", inline=False)
        else:
            embed.add_field(name="Time", value=f"{record.time} ({record.diff:+.3f} s)", inline=True)
            embed.add_field(name="Info", value=f"**Game:** {record.game}\n**Style:** {record.style}\n**Date:** {record.date}\n**Previous WR:** {record.previous_record.time} ({record.previous_record.user.username})", inline=False)
        embed.set_footer(text="World Record")
        return embed
    
    async def make_user_embed(self, user:User, rank_data:Rank, game:Game, style:Style, completions, total_maps, wrs):
        ordinal = self.get_ordinal(rank_data.placement)
        if user.username != user.displayname:
            name = f"{user.displayname} ({user.username})"
        else:
            name = user.username
        embed = discord.Embed(title=f"\N{NEWSPAPER}  {name}", color=0x1dbde0)
        url = await self.strafes.get_user_headshot_url(user.id)
        if url:
            embed.set_thumbnail(url=url)
        embed.add_field(name="Rank", value=f"{rank_data} ({rank_data.rank})", inline=True)
        embed.add_field(name="Skill", value=f"{rank_data.skill:.3f}%", inline=True)
        embed.add_field(name="Placement", value=f"{rank_data.placement}{ordinal}") if rank_data.placement > 0 else embed.add_field(name="Placement", value="n/a")
        embed.add_field(name="Info", value=f"**Game:** {game}\n**Style:** {style}\n**WRs:** {wrs}\n**Completion:** {100 * completions / total_maps:.2f}% ({completions}/{total_maps})\n**Moderation status:** {user.state}")
        embed.set_footer(text="User Profile")
        return embed

def setup(bot):
    print("loading maincog")
    bot.add_cog(MainCog(bot))