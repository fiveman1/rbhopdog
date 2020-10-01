# main.py
import discord
import os
import requests
import sys

sys.path.insert(1, os.path.join(sys.path[0], '../modules'))

import rbhop_api as rbhop
import files

from discord.ext import commands, tasks

class MainCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.commands_text = ""
        with open(rbhop.fix_path("files/commands.txt")) as file:
            data = file.read()
            self.commands_text = data

        self.games = ["bhop", "surf"]
        self.styles = ["a-only", "autohop", "backwards", "half-sideways", "scroll", "sideways", "w-only"]

        #guild_ids = [759491070374969404, 728022833254629517] #0, my testing server, 1: sev's server
        self.global_announcements.start()
        print("maincog loaded")
    
    def cog_unload(self):
        print("unloading maincog")
        self.global_announcements.cancel()

    @tasks.loop(minutes=1)
    async def global_announcements(self):
        print("doing globals")
        records = rbhop.get_new_wrs()
        if len(records) > 0:
            for guild in self.bot.guilds:
                for ch in guild.channels:
                    if ch.name == "globals":
                        for record in records:
                            await ch.send(embed=self.make_global_embed(record))
    
    @global_announcements.before_loop
    async def before_global_announcements(self):
        print("waiting for read")
        await self.bot.wait_until_ready()

    @commands.command(name="recentwrs")
    async def get_recent_wrs(self, ctx, game, style="autohop"):
        game = game.lower()
        style = style.lower()
        await ctx.send(self.format_markdown_code(rbhop.bot_get_recent_wrs(game, style)))

    @commands.command(name="userrecord")
    async def get_user_record(self, ctx, game, style, mapname, user=None):
        game = game.lower()
        style = style.lower()
        if user == None:
            user = self.get_roblox_username(ctx.author.id)
        record = rbhop.bot_get_user_record(user, game, style, mapname)
        if record == None:
            await ctx.send(self.format_markdown_code("No time found on this map."))
        else:
            await ctx.send(self.format_markdown_code(record))

    @commands.command(name="wrlist")
    async def wr_list(self, ctx, user=None, game=None, style=None):
        g = []
        s = []
        if user == None:
            user = self.get_roblox_username(ctx.author.id)
        if game == None:
            g = self.games
        else:
            g.append(game.lower())
        if style == None:
            s = self.styles
        else:
            s.append(style.lower())
        wrs = []
        count = 0
        for game in g:
            for style in s:
                if not(game == "surf" and style == "scroll"):
                    record_list = rbhop.get_user_wrs(user, game, style)
                    if record_list != None:
                        count += len(record_list)
                        wrs.append(record_list)
        convert_ls = []
        for record_ls in wrs:
            record_ls_sort = sorted(record_ls, key = lambda i: i.map_name)
            for record in record_ls_sort:
                convert_ls.append(record)
        messages = rbhop.page_records(convert_ls, sort="")
        for message in messages:
            await ctx.send(self.format_markdown_code(message))

    @commands.command(name="wrcount")
    async def wr_count(self, ctx, user=None):
        if user == None:
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
            msg = f"Total WRs: {count}\n" + msg
        else:
            msg = "Total WRs: 0"
        await ctx.send(self.format_markdown_code(msg))

    @commands.command(name="fastecheck")
    async def faste_check(self, ctx, game, style, user=None):
        game = game.lower()
        style = style.lower()
        if style == "scroll":
            await ctx.send(self.format_markdown_code("Scroll is not eligible for faste"))
            return
        if user == None:
            user = self.get_roblox_username(ctx.author.id)
        wrs = rbhop.total_wrs(user, game, style)
        if (style in ["autohop", "auto"] and wrs >= 10) or wrs >= 50:
            await ctx.send(self.format_markdown_code(f"WRs: {wrs}\n{user} is eligible for faste in {game} in the style {style}."))
        else:
            await ctx.send(self.format_markdown_code(f"WRs: {wrs}\n{user} is NOT eligible for faste in {game} in the style {style}."))

    @commands.command(name="userrank")
    async def user_rank(self, ctx, game, style, user=None):
        if user == None:
            user = self.get_roblox_username(ctx.author.id)
        await ctx.send(self.format_markdown_code(rbhop.get_user_rank(user, game, style)))

    @commands.command(name="commands")
    async def list_commands(self, ctx):
        await ctx.send(self.format_markdown_code(self.commands_text))

    def get_roblox_username(self, user_id):
        res = requests.get(f"https://verify.eryn.io/api/user/{user_id}")
        if res:
            return res.json()["robloxUsername"]
        else:
            raise Exception("No username found")

    def format_markdown_code(self, s):
        return f"```{s}```"
    
    def make_global_embed(self, record):
        embed = discord.Embed(title=f"\N{CROWN}  {record.map_name}", color=0x80ff80)
        embed.set_thumbnail(url="https://i.imgur.com/PtLyW2j.png")
        embed.add_field(name="Player", value=record.username, inline=True)
        embed.add_field(name="Time", value=f"{record.time_string} (-{record.diff:.3f} s)", inline=True)
        embed.add_field(name="\u200B", value="\u200B", inline=True)
        embed.add_field(name="Info", value=f"**Game:** {record.game_string}\n**Style:** {record.style_string}\n**Date:** {record.date_string}", inline=True)
        embed.set_footer(text="World Record")
        return embed

def setup(bot):
    print("loading maincog")
    bot.add_cog(MainCog(bot))