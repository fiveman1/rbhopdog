# bot.py
import asyncio
import discord
from discord.ext import commands
from discord.ext.commands.context import Context
from discord.ext.commands.errors import CheckFailure
import json
import traceback
import sys

from modules import utils
from modules.strafes import APIError

class StrafesBot(commands.Bot):

    def __init__(self, strafes_key : str, bloxlink_key : str, db_user : str, db_pass : str, **kwargs):
        super().__init__(**kwargs)
        self.strafes_key = strafes_key
        self.bloxlink_key = bloxlink_key
        self.db_user = db_user
        self.db_pass = db_pass

    async def on_ready(self):
        print(f"{self.user} has connected to Discord!")
        await self.change_presence(status=discord.Status.online, activity=discord.Game(name=f"{self.command_prefix}help"))

    async def on_command_error(self, ctx : Context, error : Exception):
        ignored = (discord.Forbidden, commands.CommandNotFound, CheckFailure)
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
                print(error.original.create_debug_message(), file=sys.stderr)
                await ctx.send(utils.fmt_md_code(str(error.original)))
            else:
                await ctx.send(utils.fmt_md_code(f"Command invokation error: {error.original}."))
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
            await self.send_traceback(ctx, error)
        else:
            print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
    
    #formatting taken from https://github.com/drumman22/Bhop-Bot/blob/bhop-bot-v3/cogs/error_handler.py
    async def send_traceback(self, ctx : Context, error : commands.CommandInvokeError):
        tb_channel = self.get_channel(utils.TRACEBACK_CHANNEL)
        if isinstance(error.original, APIError):
            for msg in utils.page_messages(error.original.create_debug_message()):
                try:
                    await tb_channel.send(utils.fmt_md_code(msg))
                except discord.errors.HTTPException:
                    pass
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        args = " ".join([str(arg) for arg in ctx.args[2:]])
        command = f"{ctx.bot.command_prefix}{ctx.invoked_with}"
        if args:
            command += f" {args}"
        author = ctx.author
        name = f"{author.name}#{author.discriminator}"
        await tb_channel.send(
                f"An error occured while executing `{command}` command by "
                f"{name}@{ctx.guild.name} in {ctx.channel.mention}."
                f"\n> {ctx.message.jump_url}\n"
            )

        try:
            embed = discord.Embed(color=discord.Colour.from_rgb(48, 97, 230))
            embed.set_author(name=name, icon_url=author.avatar.url)
            embed.description = ctx.message.content
            date = ctx.message.created_at.strftime("%B %d, %Y %-I:%M %p")
            embed.set_footer(text=f"#{ctx.message.channel.name} ({ctx.guild.name}) | {date}")
            await tb_channel.send(embed=embed)
        except:
            pass

        for msg in utils.page_messages(f"{type(error).__name__}: {error}\n" + tb):
            await tb_channel.send(utils.fmt_md_code(msg))

async def main():

    with open("config.json") as file:
        config = json.load(file)
    TOKEN = config["DISCORD_TOKEN"]
    COMMAND = config["COMMAND"]
    STRAFES = config["STRAFES_KEY"]
    BLOXLINK = config["BLOXLINK_KEY"]
    SQL_USER = config["SQL_USER"]
    SQL_PASS = config["SQL_PASS"]

    intents = discord.Intents.default()
    intents.message_content = True
    bot = StrafesBot(STRAFES, BLOXLINK, SQL_USER, SQL_PASS, command_prefix=COMMAND, intents=intents)

    #shamelessly adapted from here
    #https://stackoverflow.com/questions/40667445/how-would-i-make-a-reload-command-in-python-for-a-discord-bot
    @bot.command(name="load", hidden=True)
    @commands.is_owner()
    async def load(ctx : Context, *, module : str):
        """Loads a module."""
        module = "cogs." + module
        try:
            await ctx.bot.load_extension(module)
        except Exception as e:
            await ctx.send('\N{PISTOL}')
            await ctx.send('{}: {}'.format(type(e).__name__, e))
        else:
            await ctx.send('\N{OK HAND SIGN}')

    @bot.command(name="unload", hidden=True)
    @commands.is_owner()
    async def unload(ctx : Context, *, module : str):
        """Unloads a module."""
        module = "cogs." + module
        try:
            await ctx.bot.unload_extension(module)
        except Exception as e:
            await ctx.send('\N{PISTOL}')
            await ctx.send('{}: {}'.format(type(e).__name__, e))
        else:
            await ctx.send('\N{OK HAND SIGN}')

    @bot.command(name="reload", hidden=True)
    @commands.is_owner()
    async def reload(ctx : Context, *, module : str):
        """Reloads a module."""
        module = "cogs." + module
        try:
            await ctx.bot.unload_extension(module)
            await ctx.bot.load_extension(module)
        except Exception as e:
            await ctx.send('\N{PISTOL}')
            await ctx.send('{}: {}'.format(type(e).__name__, e))
        else:
            await ctx.send('\N{OK HAND SIGN}')
    
    async with bot:
        await bot.load_extension("cogs.maincog")
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())