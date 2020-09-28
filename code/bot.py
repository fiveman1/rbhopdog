# bot.py
import datetime
import json
import os
import requests
import traceback
import sys
from dotenv import load_dotenv

import rbhop_api as rbhop

from discord.ext import commands

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

commands_text = ""
with open("..\\files\\commands.txt") as file:
    data = file.read()
    commands_text = data

games = ["bhop", "surf"]
styles = ["autohop", "scroll", "sideways", "half-sideways", "w-only", "a-only", "backwards"]

bot = commands.Bot(command_prefix="!")

@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")

@bot.command(name="recentwrs")
async def get_recent_wrs(ctx, game, style="autohop"):
    game = game.lower()
    style = style.lower()
    await ctx.send(format_markdown_code(rbhop.bot_get_recent_wrs(game, style)))

@bot.command(name="userrecord")
async def get_user_record(ctx, game, style, mapname, user=None):
    game = game.lower()
    style = style.lower()
    if user == None:
        user = get_roblox_username(ctx.author.id)
    record = rbhop.bot_get_user_record(user, game, style, mapname)
    if record == None:
        await ctx.send(format_markdown_code("No time found on this map."))
    else:
        await ctx.send(format_markdown_code(record))

@bot.command(name="wrlist")
async def wr_list(ctx, user=None, game=None, style=None):
    g = []
    s = []
    if user == None:
        user = get_roblox_username(ctx.author.id)
    if game == None:
        g = games
    else:
        g.append(game.lower())
    if style == None:
        s = styles
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
    for record_ls in wrs:
        messages = rbhop.page_records(record_ls)
        for message in messages:
            await ctx.send(format_markdown_code(message))

@bot.command(name="wrcount")
async def wr_count(ctx, user=None):
    msg = ""
    count = 0
    for game in games:
        msg += f"{game}:\n"
        for style in styles:
            if not(game == "surf" and style == "scroll"):
                wrs = rbhop.total_wrs(user, game, style)
                if wrs > 0:
                    count += wrs
                    msg += f"    {style}: {wrs}\n"
    if count > 0:
        msg = f"Total WRs: {count}\n" + msg
    else:
        msg = "Total WRs: 0"
    await ctx.send(format_markdown_code(msg))

@bot.command(name="fastecheck")
async def faste_check(ctx, game, style, user=None):
    game = game.lower()
    style = style.lower()
    if style == "scroll":
        await ctx.send(format_markdown_code("Scroll is not eligible for faste"))
        return
    if user == None:
        user = get_roblox_username(ctx.author.id)
    wrs = rbhop.total_wrs(user, game, style)
    if (style in ["autohop", "auto"] and wrs >= 10) or wrs >= 50:
        await ctx.send(format_markdown_code(f"WRs: {wrs}\n{user} is eligible for faste in {game} in the style {style}."))
    else:
        await ctx.send(format_markdown_code(f"WRs: {wrs}\n{user} is NOT eligible for faste in {game} in the style {style}."))

@bot.command(name="commands")
async def list_commands(ctx):
    await ctx.send(format_markdown_code(commands_text))

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("```Invalid command```")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("```Error: Bad argument```")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"```Error: Missing argument(s): {error.param}```")
    #elif isinstance(error, commands.CommandInvokeError):
        #await ctx.send(f"```Error: Error in argument: {error.original}. Check that your arguments are spelled correctly.```")
    else:
        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

def get_roblox_username(user_id):
    res = requests.get(f"https://verify.eryn.io/api/user/{user_id}")
    if res:
        return res.json()["robloxUsername"]
    else:
        raise Exception("No username found")

def format_markdown_code(s):
    return f"```{s}```"

bot.run(TOKEN)