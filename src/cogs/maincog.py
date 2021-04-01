# maincog.py
import asyncio
import discord
from discord.ext.commands.context import Context
from dotenv import load_dotenv
from discord.errors import InvalidData
from discord.ext import commands, tasks
from io import StringIO
import os
import traceback
from typing import Callable, List, Union

import time

from modules.strafes import Game, Style, User, UserState, Map, Record, Rank, DEFAULT_GAMES, DEFAULT_STYLES
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
                globals = await asyncio.gather(*embed_tasks)
                all_embeds = []
                sus = []
                for game, style, embed in globals:
                    if style == Style.SUSTAIN:
                        sus.append(embed)
                    else:
                        all_embeds.append((game, style, embed))
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
                        elif ch.name == "sustain-globals":
                            for embed in sus:
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
        if args[-1].isnumeric():
            page = args[-1]
            map_name = " ".join(args[:-1])
        else:
            page = 1
            map_name = " ".join(args)
        if not map_name:
            await ctx.send(self.format_markdown_code("Missing map name."))
            return
        page = int(page)
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
            f = StringIO()
            msg = MessageBuilder(cols=cols, items=wrs).build()
            f.write(f"WR list for {arguments.user_data.username} [game: {game}, style: {style}, sort: {sort}] (Records: {count})\n{msg}")
            f.seek(0)
            await ctx.send(file=discord.File(f, filename=f"wrs_{arguments.user_data.username}_{game}_{style}.txt"))

    @commands.command(name="map")
    async def map_info(self, ctx:Context, game, *, map_name):
        arguments = await self.argument_checker(ctx, game=game, map_name=map_name)
        if not arguments:
            return
        embed = discord.Embed(color=0x7c17ff)
        url = await self.strafes.get_asset_thumbnail(arguments.map.id)
        if url:
            embed.set_thumbnail(url=url)
        embed.set_footer(text="Map Info")
        embed.title = f"\U0001F5FA  {arguments.map.displayname}"
        embed.add_field(name="Creator", value=arguments.map.creator)
        embed.add_field(name="Map ID", value=arguments.map.id)
        embed.add_field(name="Server Load Count", value=arguments.map.playcount)
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
            f = StringIO()
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
            f = StringIO()
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
    async def help(self, ctx:Context):
        await ctx.send(embed=self.make_help_embed())
    
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

    def format_markdown_code(self, s):
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
    
    # TODO: this should be improved. make a help.txt that's easier to edit maybe?
    def make_help_embed(self):
        embed = discord.Embed(title="\U00002753  Help", color=0xe32f22) #\U00002753: red question mark
        embed.set_thumbnail(url="https://i.imgur.com/ief5VmF.png")
        embed.add_field(name="!fastecheck username game style", value="Determines if a player is eligible for faste in a given game and style.", inline=False)
        embed.add_field(name="!map game {map_name}", value="Gives info about the given map such as the creator, total play count, and the map's asset ID.", inline=False)
        embed.add_field(name="!mapcount", value="Gives the total map count for bhop and surf.", inline=False)
        embed.add_field(name="!maps {creator} {page}", value="Gives a list of maps containing {creator} in the creator name. Use 'txt' for the page to get a .txt file with every map.", inline=False)
        embed.add_field(name="!profile username game style", value="Gives a player's rank and skill% in the given game and style.", inline=False)
        embed.add_field(name="!ranks game style page:1", value="Gives 25 ranks in the given game and style at the specified page number (25 ranks per page).", inline=False)
        embed.add_field(name="!recentwrs game style", value="Get a list of the 10 most recent WRs in a given game and style.", inline=False)
        embed.add_field(name="!record user game style {map_name}", value="Get a user's time on a given map and their placement (ex. 31st / 5690).", inline=False)
        embed.add_field(name="!times user game:both style:all page:1", value="Get a list of a user's 25 most recent times. It will try to be smart with the arguments: '!times fiveman1 bhop 2', '!times fiveman1 4', '!times fiveman1', '!times fiveman1 both hsw 7' are all valid. Numbers will be treated as the page number, but they must come after game/style. If the page is set to 'txt', you will get a .txt with every time.", inline=False)
        embed.add_field(name="!user user", value="Gets the username, user ID, and profile picture of a given user. Can be used with discord accounts that have been verified via the RoVer API.", inline=False)
        embed.add_field(name="!wrcount username", value="Gives a count of a user's WRs in every game and style.", inline=False)
        embed.add_field(name="!wrlist username game:both style:all sort:default page:1", value="Lists all of a player's world records. Valid sorts: 'date', 'name', and 'time'. Use 'txt' as an argument to get a .txt file with all WRs ex. !wrlist bhop auto M1nerss txt", inline=False)
        embed.add_field(name="!wrmap game style {map_name} page:1", value="Gives the 25 best times on a given map and style. The page number defaults to 1 (25 records per page). If the map ends in a number you can enclose it in quotes ex. !wrmap bhop auto \"Emblem 2\"", inline=False)
        return embed

def setup(bot):
    print("loading maincog")
    bot.add_cog(MainCog(bot))