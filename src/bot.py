# bot.py
import asyncio
import discord
from discord.ext import commands
from discord.ext.commands.context import Context
from dotenv import load_dotenv
import os
import time
import traceback
import sys

from modules import utils
from modules.strafes import APIError, StrafesClient

class StrafesBot(commands.Bot):

    async def on_ready(self):
        print(f"{self.user} has connected to Discord!")
        await self.change_presence(status=discord.Status.online, activity=discord.Game(name=f"{self.command_prefix}help"))

    async def on_command_error(self, ctx : Context, error : Exception):
        ignored = (discord.Forbidden, commands.CommandNotFound)
        if isinstance(error, ignored):
            return
        if isinstance(error, commands.BadArgument):
            await ctx.send(utils.fmt_md_code("Error: Bad argument"))
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(utils.fmt_md_code(f'This command is on cooldown. Please wait {error.retry_after:.2f}s.'))
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(utils.fmt_md_code(f"Error: Missing argument(s): {error.param}"))
        elif isinstance(error, commands.CommandInvokeError):
            if isinstance(error.original, ignored):
                return
            elif isinstance(error.original, APIError):
                print(error.original.create_debug_message())
                await ctx.send(utils.fmt_md_code(str(error.original)))
            else:
                await ctx.send(utils.fmt_md_code(f"Command invokation error: {error.original}."))
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
            await self.send_traceback(ctx, error)
        else:
            print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

async def main():

    load_dotenv()
    TOKEN = os.getenv("DISCORD_TOKEN")
    COMMAND = os.getenv("COMMAND")

    intents = discord.Intents.default()
    intents.message_content = True
    bot = StrafesBot(command_prefix=COMMAND, intents=intents)
    
    async with bot:
        await bot.load_extension("cogs.maincog")
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())