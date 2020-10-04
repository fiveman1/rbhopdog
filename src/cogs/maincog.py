# maincog.py
import discord
import os
import requests
import sys
import traceback

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

    @tasks.loop(minutes=2)
    async def global_announcements(self):
        records = rbhop.get_new_wrs()
        if len(records) > 0:
            for record in records:
                print(f"New WR: {record.map_name}, {record.username}, {record.time_string}")
                for guild in self.bot.guilds:
                    for ch in guild.channels:
                        if ch.name == "globals":
                            try:
                                await ch.send(embed=self.make_global_embed(record))
                            except Exception as error:
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
        await ctx.send(self.format_markdown_code(rbhop.bot_get_recent_wrs(game, style)))

    @commands.command(name="record")
    async def get_user_record(self, ctx, user, game, style, *, mapname):
        game = game.lower()
        style = style.lower()
        if not await self.argument_checker(ctx, user, game, style, mapname):
            return
        if user == "me":
            user = self.get_roblox_username(ctx.author.id)
        record = rbhop.bot_get_user_record(user, game, style, mapname)
        if record == None:
            await ctx.send(self.format_markdown_code("No time found on this map."))
        else:
            await ctx.send(self.format_markdown_code(record))
    
    @commands.command(name="wrmap")
    async def get_wrmap(self, ctx, game, style, *, mapname):
        game = game.lower()
        style = style.lower()
        if not await self.argument_checker(ctx, None, game, style, mapname):
            return
        record_list = rbhop.make_record_list(rbhop.get_map_times(game, style, mapname)[:25])
        msg = f"Record list for map: '{mapname}' in style: '{style}'\n"
        titles = ["Rank:", "Username:", "Time:", "Date:"]
        msg += f"{titles[0]:6}| {titles[1]:20}| {titles[2]:10}| {titles[3]:20}\n"
        rank = 1
        for record in record_list:
            username = record.username[:15]
            time = record.time_string
            date = record.date_string[:20]
            msg += f"{rank:5} | {username:20}| {time:10}| {date:20}\n"
            rank += 1
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
            s.append(style.lower())
        if not await self.argument_checker(ctx, user, g[0], s[0]):
            return
        if sort not in ["", "date", "time", "style", "name"]:
            await ctx.send(self.format_markdown_code(f"'{sort}' is an invalid sort. Try 'name', 'date', 'time', or 'style'."))
            return
        if user == "me":
            user = self.get_roblox_username(ctx.author.id)
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
        messages = rbhop.page_records(convert_ls, sort=sort)
        counter = 0
        for message in messages:
            counter += 1
            await ctx.send(self.format_markdown_code(message))
            if counter >= 5:
                await ctx.send(self.format_markdown_code("Limiting messages, consider specifying game/style to reduce message count."))
                return

    @commands.cooldown(4, 60, commands.cooldowns.BucketType.guild)
    @commands.command(name="wrcount")
    async def wr_count(self, ctx, user):
        if not await self.argument_checker(ctx, user, None, None):
            return
        if user == "me":
            user = self.get_roblox_username(ctx.author.id)
        msg = ""
        count = 0
        for game in self.games:
            msg += f"{game}:\n"
            for style in self.styles:
                if not(game == "surf" and style == "scroll"):
                    wrs = rbhop.total_wrs(user, game, style)
                    if wrs > 0:
                        count += wrs
                        msg += f"    {style}: {wrs}\n"
        if count > 0:
            msg = f"{user}\nTotal WRs: {count}\n" + msg
        else:
            msg = f"{user}\nTotal WRs: 0"
        await ctx.send(self.format_markdown_code(msg))

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
        r, rank, skill, placement = rbhop.get_user_rank(user, game, style)
        if r == 0:
            await ctx.send(self.format_markdown_code(f"No data available for user {user} in {style} in {game}."))
            return
        await ctx.send(embed=self.make_user_embed(user, r, rank, skill, placement, game, style))

    @commands.command(name="help")
    async def help(self, ctx):
        await ctx.send(embed=self.make_help_embed())
    
    #checks if user, game, style, and mapname are valid arguments
    #passing None as argument to any of these fields will pass the check for that field
    async def argument_checker(self, ctx, user, game, style, mapname=None):
        if game and game not in self.games:
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
            try:
                rbhop.id_from_username(user)
            except:
                await ctx.send(self.format_markdown_code(f"'{user}' is not a valid username. No Roblox account associated with this username."))
                return False
            try:
                if not await self.check_user_status(ctx, user):
                    return False
            except:
                await ctx.send(self.format_markdown_code(f"'{user}' has not played bhop/surf."))
                return False
        if mapname:
            m = rbhop.map_id_from_name(mapname, game)
            if m == "Map id not found":
                await ctx.send(self.format_markdown_code(f"'{mapname}' is not a valid {game} map."))
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
    
    def make_global_embed(self, record):
        embed = discord.Embed(title=f"\N{CROWN}  {record.map_name}", color=0x80ff80)
        embed.set_author(name="New WR", icon_url="https://i.imgur.com/PtLyW2j.png")
        embed.set_thumbnail(url=f"https://www.roblox.com/headshot-thumbnail/image?userId={record.user_id}&width=420&height=420&format=png")
        embed.add_field(name="Player", value=record.username, inline=True)
        if record.diff == -1:
            embed.add_field(name="Time", value=f"{record.time_string} (-n/a s)", inline=True)
        else:
            embed.add_field(name="Time", value=f"{record.time_string} (-{record.diff:.3f} s)", inline=True)
        embed.add_field(name="\u200B", value="\u200B", inline=True)
        embed.add_field(name="Info", value=f"**Game:** {record.game_string}\n**Style:** {record.style_string}\n**Date:** {record.date_string}", inline=True)
        embed.set_footer(text="World Record")
        return embed
    
    def make_user_embed(self, user, r, rank, skill, placement, game, style):
        ordinal = "th"
        if placement % 10 == 1:
            ordinal = "st"
        elif placement % 10 == 2:
            ordinal = "nd"
        elif placement % 10 == 3:
            ordinal = "rd"
        wrs = rbhop.total_wrs(user, game, style)
        embed = discord.Embed(title=f"\N{NEWSPAPER}  {user}", color=0x1dbde0)
        embed.set_thumbnail(url=f"https://www.roblox.com/headshot-thumbnail/image?userId={rbhop.id_from_username(user)}&width=420&height=420&format=png")
        embed.add_field(name="Rank", value=f"{rank} ({r})", inline=True)
        embed.add_field(name="Skill", value=f"{skill:.3f}%", inline=True)
        embed.add_field(name="Placement", value=f"{placement}{ordinal}")
        embed.add_field(name="Info", value=f"**Game:** {game}\n**Style:** {style}\n**WRs:** {wrs}")
        embed.set_footer(text="User Profile")
        return embed
    
    def make_help_embed(self):
        embed = discord.Embed(title="\U00002753  Help", color=0xe32f22)
        embed.set_thumbnail(url="https://i.imgur.com/ief5VmF.png")
        embed.add_field(name="!fastecheck username game style", value="Determines if a player is eligible for faste in a given game and style.", inline=False)
        embed.add_field(name="!profile username game style", value="Gives a player's rank and skill% in the given game and style.", inline=False)
        embed.add_field(name="!recentwrs game style", value="Get a list of the 10 most recent WRs in a given game and style.", inline=False)
        embed.add_field(name="!wrcount username", value="Gives a count of a user's WRs in every game and style.", inline=False)
        embed.add_field(name="!wrlist username game:both style:all sort:default", value="Lists all of a player's world records. Valid sorts: 'date', 'name', 'style', 'time'.", inline=False)
        embed.add_field(name="!wrcount username", value="Gives a count of a user's WRs in every game and style.", inline=False)
        embed.add_field(name="!wrmap game style {map_name}", value="Gives the 15 best times on a given map and style.", inline=False)
        return embed

def setup(bot):
    print("loading maincog")
    bot.add_cog(MainCog(bot))