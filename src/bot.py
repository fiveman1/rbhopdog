# bot.py
import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import traceback
import sys

from modules import utils

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
COMMAND = os.getenv("COMMAND")

bot = commands.Bot(command_prefix=COMMAND)
bot.load_extension("cogs.maincog")

@bot.event
async def on_ready():
    print(f"{bot.user} has connected to Discord!")
    await bot.change_presence(status=discord.Status.online, activity=discord.Game(name=f"{COMMAND}help"))

@bot.event
async def on_command_error(ctx, error):
    ignored = (discord.Forbidden, commands.CommandNotFound)
    if isinstance(error, ignored):
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send("```Error: Bad argument```")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f'```This command is on cooldown. Please wait {error.retry_after:.2f}s.```')
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"```Error: Missing argument(s): {error.param}```")
    elif isinstance(error, commands.CommandInvokeError):
        if isinstance(error.original, ignored):
            return
        await ctx.send(f"```Command invokation error: {error.original}.```")
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
        await send_traceback(ctx, error)
    else:
        print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

#formatting taken from https://github.com/drumman22/Bhop-Bot/blob/bhop-bot-v3/cogs/error_handler.py
async def send_traceback(ctx, error):
    tb_channel = bot.get_channel(812768023920115742)
    tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    await tb_channel.send(
            f"An error occured while executing `{''.join(ctx.prefix)}{ctx.command}` command by "
            f"{ctx.author.name}#{ctx.author.discriminator}@{ctx.guild.name} in {ctx.channel.mention}."
            f"\n> {ctx.message.jump_url}\n"
        )
    for msg in utils.page_messages(f"{type(error).__name__}: {error}\n" + tb):
        await tb_channel.send(f"```\n{msg}\n```")

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