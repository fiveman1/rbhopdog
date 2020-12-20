# maincog.py
import discord
import os
import requests
import sys
import traceback
from io import StringIO

sys.path.insert(1, os.path.join(sys.path[0], '../modules'))

import rbhop_api as rbhop
import files

from discord.ext import commands, tasks

class MainCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.remove_command("help")
        self.commands_text = ""
        with open(rbhop.fix_path("files/commands.txt")) as file:
            data = file.read()
            self.commands_text = data
        self.games = ["bhop", "surf"]
        self.styles = ["a-only", "autohop", "backwards", "half-sideways", "scroll", "sideways", "w-only"]
        files.write_wrs() #so that bot doesn't make a bunch of globals after downtime
        self.global_announcements.start()
        print("maincog loaded")
    
    def cog_unload(self):
        print("unloading maincog")
        self.global_announcements.cancel()

    @tasks.loop(minutes=1)
    async def global_announcements(self):
        try:
            records = rbhop.get_new_wrs()
        except:
            return
        if len(records) > 0:
            for record in records:
                print(f"New WR: {record.map_name}, {record.username}, {record.time_string}")
                for guild in self.bot.guilds:
                    for ch in guild.channels:
                        if isinstance(ch, discord.TextChannel):
                            if ch.name == "globals":
                                await self.post_global(ch, record)
                            if ch.name == "bhop-auto-globals" and record.game == 1 and record.style == 1:
                                await self.post_global(ch, record)
                            elif ch.name == "bhop-styles-globals" and record.game == 1 and record.style != 1:
                                await self.post_global(ch, record)
                            elif ch.name == "surf-auto-globals" and record.game == 2 and record.style == 1:
                                await self.post_global(ch, record)
                            elif ch.name == "surf-styles-globals" and record.game == 2 and record.style != 1:
                                await self.post_global(ch, record)
    
    async def post_global(self, ch, record):
        try:
            await ch.send(embed=self.make_global_embed(record))
        except Exception as error:
            if not isinstance(error, discord.errors.Forbidden):
                print("Couldn't post global")
                traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
    
    @global_announcements.before_loop
    async def before_global_announcements(self):
        print("waiting for ready")
        #we have to wait for the bot to on_ready() or we won't be able to find channels/guilds
        await self.bot.wait_until_ready()

    @commands.command(name="recentwrs")
    async def get_recent_wrs(self, ctx, game, style="autohop"):
        game = game.lower()
        style = style.lower()
        if not await self.argument_checker(ctx, None, game, style):
            return
        msg = self.message_builder(f"10 Recent WRs [game: {game}, style: {style}]", [("Username:", 20), ("Map name:", 30), ("Time:", 10), ("Date:", 11)], rbhop.get_recent_wrs(game, style))
        await ctx.send(self.format_markdown_code(msg))

    @commands.command(name="record")
    async def get_user_record(self, ctx, user, game, style, *, map_name):
        game = game.lower()
        style = style.lower()
        if not await self.argument_checker(ctx, user, game, style, map_name):
            return
        if user == "me":
            user = self.get_roblox_username(ctx.author.id)
        else:
            discord_user_id = self.get_discord_user_id(user)
            if discord_user_id:
                user = self.get_roblox_username(discord_user_id)
        style = self.convert_style(style)
        user, _ = rbhop.get_user_data(user)
        map_id = rbhop.map_id_from_name(map_name, game)
        map_name = rbhop.map_name_from_id(map_id, game)
        record = rbhop.get_user_record(user, game, style, map_name)
        if record == None:
            await ctx.send(self.format_markdown_code(f"No record by {user} found on map: {map_name} [game: {game}, style: {style}]"))
        else:
            msg = self.message_builder(f"{user}'s record on {record.map_name} [game: {game}, style: {style}]", [("Time:", 10), ("Date:", 11)], [record])
            await ctx.send(self.format_markdown_code(msg))

    @commands.command(name="wrmap")
    async def get_wrmap(self, ctx, game, style, *args):
        if len(args) == 0:
            await ctx.send(self.format_markdown_code("Missing map name."))
            return
        if args[-1].isnumeric():
            page = args[-1]
            map_name = " ".join(args[:-1])
        else:
            page = 1
            map_name = " ".join(args)
        page = int(page)
        if page < 1:
            await ctx.send(self.format_markdown_code("Page number cannot be less than 1."))
            return
        game = game.lower()
        style = style.lower()
        if not await self.argument_checker(ctx, None, game, style, map_name):
            return
        style = self.convert_style(style)
        map_id = rbhop.map_id_from_name(map_name, game)
        map_name = rbhop.map_name_from_id(map_id, game)
        records, page_count = rbhop.get_map_times(game, style, map_name, page)
        if page_count == 0:
            await ctx.send(self.format_markdown_code(f"{map_name} has not yet been completed in {style}."))
            return
        elif page > page_count:
            await ctx.send(self.format_markdown_code(f"Page number ({page}) too large (total pages: {page_count})"))
            return
        else:
            msg = self.message_builder(f"Record list for map: {map_name} [game: {game}, style: {style}, page: {page}/{page_count}]", [("Rank:", 6), ("Username:", 20), ("Time:", 10), ("Date:", 11)], records, ((page - 1) * 25) + 1)
            await ctx.send(self.format_markdown_code(msg))

    @commands.cooldown(4, 60, commands.cooldowns.BucketType.guild)
    @commands.command(name="wrlist")
    async def wr_list(self, ctx, user, game=None, style=None, sort=""):
        #loop through all games or all styles if not specified (or if "both" or "all")
        g = []
        s = []
        if game in [None, "both", "all"]:
            g = self.games
        else:
            g.append(game.lower())
        if style in [None, "all"]:
            s = self.styles
        else:
            s.append(self.convert_style(style.lower()))
        if not await self.argument_checker(ctx, user, g[0], s[0]):
            return
        if sort not in ["", "date", "time", "name"]:
            await ctx.send(self.format_markdown_code(f"'{sort}' is an invalid sort. Try 'name', 'date', or 'time'."))
            return
        if user == "me":
            user = self.get_roblox_username(ctx.author.id)
        else:
            discord_user_id = self.get_discord_user_id(user)
            if discord_user_id:
                user = self.get_roblox_username(discord_user_id)
        user, _ = rbhop.get_user_data(user)
        wrs = []
        count = 0
        for game in g:
            for style in s:
                if not(game == "surf" and style == "scroll"):
                    record_list = rbhop.get_user_wrs(user, game, style)
                    if record_list != None:
                        count += len(record_list)
                        wrs.append(record_list)
        if count == 0:
            await ctx.send(self.format_markdown_code(f"{user} has no WRs in the specified game and style."))
            return
        #default sort: sort by style, then within each style sort alphabetically
        convert_ls = []
        if sort == "":
            for record_ls in wrs:
                record_ls_sort = sorted(record_ls, key = lambda i: i.map_name)
                for record in record_ls_sort:
                    convert_ls.append(record)
        else:
            for record_ls in wrs:
                for record in record_ls:
                    convert_ls.append(record)
            if sort == "name":
                convert_ls = sorted(convert_ls, key = lambda i: i.map_name) #sort by map name
            elif sort == "date":
                convert_ls = sorted(convert_ls, key = lambda i: i.date, reverse=True) #sort by date (most recent)
            elif sort == "time":
                convert_ls = sorted(convert_ls, key = lambda i: i.time) #sort by time
        cols = [("Map name:", 30), ("Time:", 10), ("Date:", 11)]
        if len(g) > 1:
            game = "both"
            cols.append(("Game:", 6))
        if len(s) > 1:
            style = "all"
            cols.append(("Style:", 14))
        if sort == "":
            sort = "default"
        msg = self.message_builder(f"WR list for {user} [game: {game}, style: {style}, sort: {sort}] (Records: {count})", cols, convert_ls)
        counter = 0
        for message in self.page_messages(msg):
            counter += 1
            if counter > 5:
                await ctx.send(self.format_markdown_code("Limiting messages, consider specifying game/style to reduce message count."))
                return
            await ctx.send(self.format_markdown_code(message))

    @commands.command(name="map")
    async def map_info(self, ctx, game, *, map_name):
        if not await self.argument_checker(ctx, None, game, None, map_name):
            return
        map_id = rbhop.map_id_from_name(map_name, game)
        map_dict = rbhop.map_dict_from_id(map_id, game)
        map_name = map_dict["DisplayName"]
        play_count = map_dict["PlayCount"]
        map_creator = map_dict["Creator"]
        embed = discord.Embed(color=0x7c17ff)
        embed.set_thumbnail(url=f"https://www.roblox.com/asset-thumbnail/image?assetId={map_id}&width=420&height=420&format=png")
        embed.set_footer(text="Map Info")
        embed.title = f"\U0001F5FA  {map_name}"
        embed.add_field(name="Creator", value=map_creator)
        embed.add_field(name="Map ID", value=map_id)
        embed.add_field(name="Play Count", value=play_count)
        await ctx.send(embed=embed)

    @commands.cooldown(4, 60, commands.cooldowns.BucketType.guild)
    @commands.command(name="wrcount")
    async def wr_count(self, ctx, user):
        if not await self.argument_checker(ctx, user, None, None):
            return
        if user == "me":
            user = self.get_roblox_username(ctx.author.id)
        else:
            discord_user_id = self.get_discord_user_id(user)
            if discord_user_id:
                user = self.get_roblox_username(discord_user_id)
        user, user_id = rbhop.get_user_data(user)
        count = 0
        ls = [[],[]]
        for i in range(len(self.games)):
            game = self.games[i]
            for style in self.styles:
                if not(game == "surf" and style == "scroll"):
                    wrs = rbhop.total_wrs(user, game, style)
                    if wrs > 0:
                        ls[i].append((style, wrs))
                        count += wrs
        embed = discord.Embed(color=0xff94b8)
        embed.set_thumbnail(url=f"https://www.roblox.com/headshot-thumbnail/image?userId={user_id}&width=420&height=420&format=png")
        embed.set_footer(text="WR Count")
        embed.title = f"\U0001F4C4  {user}"
        if count > 0:
            embed.description = f"Total WRs: {count}"
            if len(ls[0]) > 0:
                body = ""
                for c in ls[0]:
                    if c[1] > 0:
                        body += f"**{c[0]}:** {c[1]}\n"
                embed.add_field(name=f"__bhop__", value=body[:-1], inline=False)
            if len(ls[1]) > 0:
                body = ""
                for c in ls[1]:
                    if c[1] > 0:
                        body += f"**{c[0]}:** {c[1]}\n"
                embed.add_field(name=f"__surf__", value=body[:-1], inline=False)
        else:
            embed.description = f"Total WRs: 0 \N{crying face}"
        await ctx.send(embed=embed)

    @commands.command(name="fastecheck")
    async def faste_check(self, ctx, user, game, style):
        game = game.lower()
        style = style.lower()
        if not await self.argument_checker(ctx, user, game, style):
            return
        if style == "scroll":
            await ctx.send(self.format_markdown_code("Scroll is not eligible for faste"))
            return
        if user == "me":
            user = self.get_roblox_username(ctx.author.id)
        else:
            discord_user_id = self.get_discord_user_id(user)
            if discord_user_id:
                user = self.get_roblox_username(discord_user_id)
        style = self.convert_style(style)
        user, _ = rbhop.get_user_data(user)
        wrs = rbhop.total_wrs(user, game, style)
        if (style in ["autohop", "auto"] and wrs >= 10) or wrs >= 50:
            await ctx.send(self.format_markdown_code(f"WRs: {wrs}\n{user} is eligible for faste in {game} in the style {style}."))
        else:
            await ctx.send(self.format_markdown_code(f"WRs: {wrs}\n{user} is NOT eligible for faste in {game} in the style {style}."))

    @commands.command(name="profile")
    async def user_rank(self, ctx, user, game, style):
        if not await self.argument_checker(ctx, user, game, style):
            return
        if user == "me":
            user = self.get_roblox_username(ctx.author.id)
        else:
            discord_user_id = self.get_discord_user_id(user)
            if discord_user_id:
                user = self.get_roblox_username(discord_user_id)
        style = self.convert_style(style)
        user, user_id = rbhop.get_user_data(user)
        r, rank, skill, placement = rbhop.get_user_rank(user, game, style)
        completions, total_maps = rbhop.get_user_completion(user, game, style)
        if r == 0:
            await ctx.send(self.format_markdown_code(f"No data available for user {user} in {style} in {game}."))
            return
        await ctx.send(embed=self.make_user_embed(user, user_id, r, rank, skill, placement, game, style, completions, total_maps))

    @commands.command(name="ranks")
    async def ranks(self, ctx, game, style, page=1):
        page = int(page)
        if page < 1:
            await ctx.send(self.format_markdown_code("Page number cannot be less than 1."))
            return
        if not await self.argument_checker(ctx, None, game, style):
            return
        style = self.convert_style(style)
        ranks, page_count = rbhop.get_ranks(game, style, page)
        if page_count == 0:
            await ctx.send(self.format_markdown_code(f"No ranks found in {game} {style} (???)."))
            return
        elif page > page_count:
            await ctx.send(self.format_markdown_code(f"Page number ({page}) too large (total pages: {page_count})"))
            return
        msg = f"Ranks [game: {game}, style: {style}, page: {page}/{page_count}]\n"
        titles = ["Placement:", "Username:", "Rank:", "Skill:"]
        msg += f"{titles[0]:11}| {titles[1]:20}| {titles[2]:19}| {titles[3]}\n"
        for rank in ranks:
            r = rank["R"]
            rank_string = rank["Rank"]
            skill = rank["Skill"]
            placement = rank["Placement"]
            username = rank["Username"]
            formatted = f"{rank_string} ({r})"
            msg += f"{placement:10} | {username:20}| {formatted:19}| {skill:.3f}%\n"
        await ctx.send(self.format_markdown_code(msg))
    
    @commands.command(name="times")
    async def times(self, ctx, user, *args):
        if len(args) == 0:
            game = None
            style = None
            page = 1
        elif len(args) == 1:
            style = None
            if args[0].isnumeric() or args[0] == "all":
                game = None
                page = args[0]
            else:
                game = args[0]
                page = 1
        elif len(args) == 2:
            game = args[0]
            if args[1].isnumeric() or args[1] == "all":
                style = None
                page = args[1]
            else:
                style = args[1]
                page = 1
        else:
            game = args[0]
            style = args[1]
            if args[2].isnumeric() or args[2] == "all":
                page = args[2]
            else:
                page = 1
        if page != "all":
            page = int(page)
            if page < 1:
                await ctx.send(self.format_markdown_code("Page number cannot be less than 1."))
                return
        if game in ["all", "both"]:
            game = None
        if style == "all":
            style = None
        if not await self.argument_checker(ctx, user, game, style):
            return
        if user == "me":
            user = self.get_roblox_username(ctx.author.id)
        else:
            discord_user_id = self.get_discord_user_id(user)
            if discord_user_id:
                user = self.get_roblox_username(discord_user_id)
        if style:
            style = self.convert_style(style)
        user, _ = rbhop.get_user_data(user)
        if page == "all":
            page = -1
        record_list, page_count = rbhop.get_user_times(user, game, style, page)
        if page_count == 0:
            if not style:
                style = "all"
            await ctx.send(self.format_markdown_code(f"No times found for {user} in game '{game}' style '{style}'."))
            return
        elif page > page_count:
            await ctx.send(self.format_markdown_code(f"Page number ({page}) too large (total pages: {page_count})"))
            return
        cols = [("Map name:", 30), ("Time:", 10), ("Date:", 11)]
        if game == None:
            game = "both"
            cols.append(("Game:", 6))
        if style == None:
            style = "all"
            cols.append(("Style:", 14))
        if page == -1:
            msg = self.message_builder(f"Recent times for {user} [game: {game}, style: {style}] (total: {len(record_list)})", cols, record_list)
            f = StringIO()
            f.write(msg)
            f.seek(0)
            await ctx.send(file=discord.File(f, filename=f"times_{user}_{game}_{style}.txt"))
            return
        msg = self.message_builder(f"Recent times for {user} [game: {game}, style: {style}, page: {page}/{page_count}]", cols, record_list)
        for message in self.page_messages(msg):
            await ctx.send(self.format_markdown_code(message))
    
    @commands.command(name="mapcount")
    async def map_count(self, ctx):
        embed = discord.Embed(title=f"\N{CLIPBOARD}  Map Count", color=0xfc9c00)
        embed.add_field(name="Bhop Maps", value=str(len(rbhop.bhop_maps)))
        embed.add_field(name="Surf Maps", value=str(len(rbhop.surf_maps)))
        embed.add_field(name="More info", value="https://wiki.strafes.net/maps")
        await ctx.send(embed=embed)

    @commands.command(name="help")
    async def help(self, ctx):
        await ctx.send(embed=self.make_help_embed())
    
    @commands.command(name="guilds")
    @commands.is_owner()
    async def guilds(self, ctx):
        msg = f"Total guilds: {len(self.bot.guilds)}\n"
        titles = ["Name:", "Members:", "Owner:"]
        msg += f"{titles[0]:40}| {titles[1]}\n"
        for guild in self.bot.guilds:
            name = guild.name[:40]
            members = guild.member_count
            msg += f"{name:40}| {members}\n"
        await ctx.send(self.format_markdown_code(msg))

    @commands.command(name="updatemaps")
    @commands.is_owner()
    async def update_maps(self, ctx):
        rbhop.update_maps()
        await ctx.send(self.format_markdown_code("Maps updated."))
    
    def get_discord_user_id(self, s):
        if s[:3] == "<@!" and s[-1] == ">":
            return s[3:-1]
        elif s[:2] == "<@" and s[-1] == ">":
            return s[2:-1]
        else:
            return None
    
    #title: first line, cols: list of tuples: (column_name, length of string), record_ls: a list of Records
    def message_builder(self, title, cols, record_ls, i=1):
        msg = f"{title}\n"
        for col_title in cols[:-1]:
            msg += self.add_spaces(col_title[0], col_title[1]) + "| "
        last_title = cols[-1]
        msg += f"{last_title[0]}\n"
        for record in record_ls:
            d = {
                    "Rank:":str(i),
                    "Username:":record.username,
                    "Map name:":record.map_name,
                    "Time:":record.time_string,
                    "Date:":record.date_string,
                    "Style:":record.style_string,
                    "Game:":record.game_string
                }
            for col_title in cols[:-1]:
                msg += self.add_spaces(d[col_title[0]], col_title[1]) + "| "
            msg += f"{d[last_title[0]][:last_title[1]]}\n"
            i += 1
        return msg
    
    def add_spaces(self, s, length):
        s = s[:length]
        while len(s) < length:
            s += " "
        return s
    
    def page_messages(self, msg):
        ls = []
        lines = msg.split("\n")
        items = len(lines)
        length = 0
        page = ""
        i = 0
        #add each line together until the total length exceeds 1900
        #then create a new string (message)
        while i < items:
            while i < items and length + len(lines[i]) + 2 < 2000:
                page += lines[i] + "\n"
                length += len(lines[i]) + 2
                i += 1
            ls.append(page)
            length = 0
            page = ""
        if ls[len(ls) - 1] == "\n":
            ls = ls[:-1]
        return ls
    
    #checks if user, game, style, and map_name are valid arguments
    #passing None as argument to any of these fields will pass the check for that field
    async def argument_checker(self, ctx, user, game, style, map_name=None):
        if game and game not in rbhop.games:
            await ctx.send(self.format_markdown_code(f"'{game}' is not a valid game. 'bhop' and 'surf' are valid."))
            return False
        if style and style not in rbhop.styles:
            await ctx.send(self.format_markdown_code(f"'{style}' is not a valid style. 'autohop', 'auto', 'aonly', 'hsw' are valid examples."))
            return False
        if game == "surf" and style == "scroll":
            await ctx.send(self.format_markdown_code("Surf and scroll cannot be combined."))
            return False
        if user == "me":
            username = self.get_roblox_username(ctx.author.id)
            if not username:
                await ctx.send(self.format_markdown_code("Invalid username. No Roblox username associated with your Discord account."))
                return False
            else:
                if not await self.check_user_status(ctx, username):
                    return False
        elif user:
            discord_user_id = self.get_discord_user_id(user)
            if discord_user_id:
                user = self.get_roblox_username(discord_user_id)
                if not user:
                    await ctx.send(self.format_markdown_code(f"Invalid username. '{self.bot.get_user(int(discord_user_id)).name}' does not have a Roblox account associated with their Discord account."))
                    return False
            try:
                rbhop.get_user_data(user)
            except:
                await ctx.send(self.format_markdown_code("Invalid username (username does not exist on Roblox)."))
                return False
            try:
                if not await self.check_user_status(ctx, user):
                    return False
            except:
                await ctx.send(self.format_markdown_code(f"'{user}' has not played bhop/surf."))
                return False
        if map_name:
            m = rbhop.map_id_from_name(map_name, game)
            if m == "Map id not found":
                await ctx.send(self.format_markdown_code(f"'{map_name}' is not a valid {game} map."))
                return False
        return True
    
    async def check_user_status(self, ctx, user):
        user_data = rbhop.get_user(user)
        if user_data["State"] == 2:
            await ctx.send(self.format_markdown_code(f"{user} is blacklisted."))
            return False
        elif user_data["State"] == 3:
            await ctx.send(self.format_markdown_code(f"{user} is pending moderation."))
            return False
        return True

    def get_roblox_username(self, user_id):
        res = requests.get(f"https://verify.eryn.io/api/user/{user_id}")
        if res:
            return res.json()["robloxUsername"]
        else:
            return None

    def format_markdown_code(self, s):
        return f"```\n{s}```"
    
    def convert_style(self, style):
        return rbhop.style_id_to_string[rbhop.styles[style]]
    
    def make_global_embed(self, record):
        embed = discord.Embed(title=f"\N{CROWN}  {record.map_name}", color=0x80ff80)
        embed.set_author(name="New WR", icon_url="https://i.imgur.com/PtLyW2j.png")
        embed.set_thumbnail(url=f"https://www.roblox.com/headshot-thumbnail/image?userId={record.user_id}&width=420&height=420&format=png")
        embed.add_field(name="Player", value=record.username, inline=True)
        if record.diff == -1:
            embed.add_field(name="Time", value=f"{record.time_string} (-n/a s)", inline=True)
            embed.add_field(name="\u200B", value="\u200B", inline=True)
            embed.add_field(name="Info", value=f"**Game:** {record.game_string}\n**Style:** {record.style_string}\n**Date:** {record.date_string}\n**Previous WR:** n/a", inline=True)
        else:
            embed.add_field(name="Time", value=f"{record.time_string} (-{record.diff:.3f} s)", inline=True)
            embed.add_field(name="\u200B", value="\u200B", inline=True)
            embed.add_field(name="Info", value=f"**Game:** {record.game_string}\n**Style:** {record.style_string}\n**Date:** {record.date_string}\n**Previous WR:** {record.previous_record.time_string} ({record.previous_record.username})", inline=True)
        embed.set_footer(text="World Record")
        return embed
    
    def make_user_embed(self, user, user_id, r, rank, skill, placement, game, style, completions, total_maps):
        ordinal = "th"
        if placement % 100 > 13 or placement % 100 < 11:
            n = placement % 10
            if n == 1:
                ordinal = "st"
            elif n == 2:
                ordinal = "nd"
            elif n == 3:
                ordinal = "rd"
        wrs = rbhop.total_wrs(user, game, style)
        embed = discord.Embed(title=f"\N{NEWSPAPER}  {user}", color=0x1dbde0)
        embed.set_thumbnail(url=f"https://www.roblox.com/headshot-thumbnail/image?userId={user_id}&width=420&height=420&format=png")
        embed.add_field(name="Rank", value=f"{rank} ({r})", inline=True)
        embed.add_field(name="Skill", value=f"{skill:.3f}%", inline=True)
        embed.add_field(name="Placement", value=f"{placement}{ordinal}")
        embed.add_field(name="Info", value=f"**Game:** {game}\n**Style:** {style}\n**WRs:** {wrs}\n**Completion:** {100 * completions / total_maps:.2f}% ({completions}/{total_maps})")
        embed.set_footer(text="User Profile")
        return embed
    
    def make_help_embed(self):
        embed = discord.Embed(title="\U00002753  Help", color=0xe32f22) #\U00002753: red question mark
        embed.set_thumbnail(url="https://i.imgur.com/ief5VmF.png")
        embed.add_field(name="!fastecheck username game style", value="Determines if a player is eligible for faste in a given game and style.", inline=False)
        embed.add_field(name="!map game {map_name}", value="Gives info about the given map such as the creator, total play count, and the map's asset ID.", inline=False)
        embed.add_field(name="!mapcount", value="Gives the total map count for bhop and surf.", inline=False)
        embed.add_field(name="!profile username game style", value="Gives a player's rank and skill% in the given game and style.", inline=False)
        embed.add_field(name="!ranks game style page:1", value="Gives 25 ranks in the given game and style at the specified page number (25 ranks per page).", inline=False)
        embed.add_field(name="!recentwrs game style", value="Get a list of the 10 most recent WRs in a given game and style.", inline=False)
        embed.add_field(name="!record user game style {map_name}", value="Get a user's time on a given map.", inline=False)
        embed.add_field(name="!times user game:both style:all page:1", value="Get a list of a user's 25 most recent times. It will try to be smart with the arguments: '!times fiveman1 bhop 2', '!times fiveman1 4', '!times fiveman1', '!times fiveman1 both hsw 7' are all valid. Numbers will be treated as the page number, but they must come after game/style. If the page is set to 'all', you will get a .txt with every time.", inline=False)
        embed.add_field(name="!wrcount username", value="Gives a count of a user's WRs in every game and style.", inline=False)
        embed.add_field(name="!wrlist username game:both style:all sort:default", value="Lists all of a player's world records. Valid sorts: 'date', 'name', and 'time'.", inline=False)
        embed.add_field(name="!wrmap game style {map_name} page:1", value="Gives the 25 best times on a given map and style. The page number defaults to 1 (25 records per page). If the map ends in a number you can enclose it in quotes ex. !wrmap bhop auto \"Emblem 2\"", inline=False)
        return embed

def setup(bot):
    print("loading maincog")
    bot.add_cog(MainCog(bot))