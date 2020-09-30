# bot.py
import os
import traceback
import sys
from dotenv import load_dotenv

sys.path.insert(1, os.path.join(sys.path[0], 'modules')) #for some reason I can't load modules in cogs without this

from discord.ext import commands

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

bot = commands.Bot(command_prefix="test!")

@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")
    bot.load_extension("cogs.maincog")

@bot.event
async def on_command_error(ctx, error):
    #if isinstance(error, commands.CommandNotFound):
        #await ctx.send("```Invalid command```")
    if isinstance(error, commands.BadArgument):
        await ctx.send("```Error: Bad argument```")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"```Error: Missing argument(s): {error.param}```")
    elif isinstance(error, commands.CommandInvokeError):
        await ctx.send(f"```Error in argument: {error.original}. Check that your arguments are spelled correctly.```")
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
    else:
        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

#shamelessly adapted from here
#https://stackoverflow.com/questions/40667445/how-would-i-make-a-reload-command-in-python-for-a-discord-bot
@bot.command(name="load", hidden=True)
@commands.is_owner()
async def load(ctx, *, module : str):
    """Loads a module."""
    module = "cogs." + module
    try:
        bot.load_extension(module)
    except Exception as e:
        await ctx.send('\N{PISTOL}')
        await ctx.send('{}: {}'.format(type(e).__name__, e))
    else:
        await ctx.send('\N{OK HAND SIGN}')

@bot.command(name="unload", hidden=True)
@commands.is_owner()
async def unload(ctx, *, module : str):
    """Unloads a module."""
    module = "cogs." + module
    try:
        bot.unload_extension(module)
    except Exception as e:
        await ctx.send('\N{PISTOL}')
        await ctx.send('{}: {}'.format(type(e).__name__, e))
    else:
        await ctx.send('\N{OK HAND SIGN}')

@bot.command(name="reload", hidden=True)
@commands.is_owner()
async def _reload(ctx, *, module : str):
    """Reloads a module."""
    module = "cogs." + module
    try:
        bot.unload_extension(module)
        bot.load_extension(module)
    except Exception as e:
        await ctx.send('\N{PISTOL}')
        await ctx.send('{}: {}'.format(type(e).__name__, e))
    else:
        await ctx.send('\N{OK HAND SIGN}')

@bot.command(name="shutdown", hidden=True)
@commands.is_owner()
async def shutdown(ctx):
    print("shutting down")
    await ctx.bot.logout()
    print("shut down succesful")

bot.run(TOKEN)