import discord
import redbot
import logging
import typing
import datetime
import asyncio
import contextlib
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.utils.predicates import MessagePredicate, ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.data_manager import cog_data_path
from redbot.core.utils.chat_formatting import *
import traceback
import math
from rich.table import Table
from rich.console import Console
from io import StringIO
import string
from random import choice
from pathlib import Path
from time import monotonic
import os
import sys
from redbot.cogs.downloader.repo_manager import Repo

def _(untranslated: str):
    return untranslated

def no_colour_rich_markup(*objects: typing.Any, lang: str = "") -> str:
    """
    Slimmed down version of rich_markup which ensure no colours (/ANSI) can exist
    https://github.com/Cog-Creators/Red-DiscordBot/pull/5538/files (Kowlin)
    """
    temp_console = Console(  # Prevent messing with STDOUT's console
        color_system=None,
        file=StringIO(),
        force_terminal=True,
        width=80,
    )
    temp_console.print(*objects)
    return box(temp_console.file.getvalue(), lang=lang)  # type: ignore

__all__ = ["CogsUtils", "Loop", "Captcha"]
TimestampFormat = typing.Literal["f", "F", "d", "D", "t", "T", "R"]

class CogsUtils(commands.Cog):
    """Tools for AAA3A-cogs!"""

    def __init__(self, cog: typing.Optional[commands.Cog]=None, bot: typing.Optional[Red]=None):
        if cog is not None:
            if isinstance(cog, str):
                cog = bot.get_cog(cog)
            self.cog: commands.Cog = cog
            self.bot: Red = self.cog.bot
            self.DataPath: Path = cog_data_path(raw_name=self.cog.__class__.__name__.lower())
        elif bot is not None:
            self.cog: commands.Cog = None
            self.bot: Red = bot
        else:
            self.cog: commands.Cog = None
            self.bot: Red = None
        self.__authors__ = ["AAA3A"]
        self.__version__ = 1.0
        self.interactions = {"slash": {}, "buttons": {}, "dropdowns": {}, "added": False, "removed": False}
        if self.cog is not None:
            if hasattr(self.cog, '__authors__'):
                if isinstance(self.cog.__authors__, typing.List):
                    self.__authors__ = self.cog.__authors__
                else:
                    self.__authors__ = [self.cog.__authors__]
            elif hasattr(self.cog, '__author__'):
                if isinstance(self.cog.__author__, typing.List):
                    self.__authors__ = self.cog.__author__
                else:
                    self.__authors__ = [self.cog.__author__]
            if hasattr(self.cog, '__version__'):
                if isinstance(self.cog.__version__, typing.List):
                    self.__version__ = self.cog.__version__
            if hasattr(self.cog, '__func_red__'):
                if not isinstance(self.cog.__func_red__, typing.List):
                    self.cog.__func_red__ = []
            else:
                self.cog.__func_red__ = []
            if hasattr(self.cog, 'interactions'):
                if isinstance(self.cog.interactions, typing.Dict):
                    self.interactions = self.cog.interactions
        self.loops: typing.Dict = {}
        self.repo_name: str = "AAA3A-cogs"
        self.all_cogs: typing.List = [
                                        "AntiNuke",
                                        "AutoTraceback",
                                        "Calculator",
                                        "ClearChannel",
                                        "CmdChannel",
                                        "CtxVar",
                                        "EditFile",
                                        "Ip",
                                        "MemberPrefix",
                                        "ReactToCommand",
                                        "RolesButtons",
                                        "SimpleSanction",
                                        "Sudo",
                                        "TicketTool",
                                        "TransferChannel"
                                    ]
        self.all_cogs_dpy2: typing.List = [
                                        "AntiNuke",
                                        "AutoTraceback",
                                        "Calculator",
                                        "ClearChannel",
                                        "CmdChannel",
                                        "CtxVar",
                                        "EditFile",
                                        "Ip",
                                        "MemberPrefix",
                                        "ReactToCommand",
                                        "Sudo",
                                        "TransferChannel"
                                    ]
        if self.cog is not None:
            if not self.cog.__class__.__name__ in self.all_cogs_dpy2:
                if self.is_dpy2 or redbot.version_info >= redbot.VersionInfo.from_str("3.5.0"):
                    raise RuntimeError(f"{self.cog.__class__.__name__} needs to be updated to run on dpy2/Red 3.5.0. It's best to use `[p]cog update` with no arguments to update all your cogs, which may be using new dpy2-specific methods.")

    @property
    def is_dpy2(self) -> bool:
        """
        Returns True if the current redbot instance is running under dpy2.
        """
        return discord.version_info.major >= 2

    def format_help_for_context(self, ctx):
        """Thanks Simbad!"""
        context = super(type(self.cog), self.cog).format_help_for_context(ctx)
        s = "s" if len(self.__authors__) > 1 else ""
        return f"{context}\n\n**Author{s}**: {humanize_list(self.__authors__)}\n**Version**: {self.__version__}"

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete"""
        return

    async def red_get_data_for_user(self, *args, **kwargs) -> typing.Dict[typing.Any, typing.Any]:
        return {}
    
    def cog_unload(self):
        self._end()

    def _setup(self):
        self.cog.cogsutils = self
        self.cog.log = logging.getLogger(f"red.{self.repo_name}.{self.cog.__class__.__name__}")
        if not "format_help_for_context" in self.cog.__func_red__:
            setattr(self.cog, 'format_help_for_context', self.format_help_for_context)
        if not "red_delete_data_for_user" in self.cog.__func_red__:
            setattr(self.cog, 'red_delete_data_for_user', self.red_delete_data_for_user)
        if not "red_get_data_for_user" in self.cog.__func_red__:
            setattr(self.cog, 'red_get_data_for_user', self.red_get_data_for_user)
        if not "cog_unload" in self.cog.__func_red__:
            setattr(self.cog, 'cog_unload', self.cog_unload)
        asyncio.create_task(self._await_setup())
        # self.bot.remove_command("getallerrorsfor")
        # self.bot.add_command(self.getallerrorsfor)
    
    async def _await_setup(self):
        await self.bot.wait_until_red_ready()
        self.add_dev_env_value()
        if self.is_dpy2:
            if not hasattr(self.bot, "tree"):
                self.bot.tree = discord.app_commands.CommandTree(self.bot)
            if not self.interactions == {}:
                if "added" in self.interactions:
                    if not self.interactions["added"]:
                        if "slash" in self.interactions:
                            for slash in self.interactions["slash"]:
                                try:
                                    self.bot.tree.add_command(slash, guild=None)
                                except Exception as e:
                                    if hasattr(self.cog, 'log'):
                                        self.cog.log.error(f"The slash command `{slash.name}` could not be added correctly.", exc_info=e)
                        if "button" in self.interactions:
                            for button in self.interactions["button"]:
                                try:
                                    self.bot.add_view(button, guild=None)
                                except Exception:
                                    pass
                        self.interactions["removed"] = False
                        self.interactions["added"] = True
            await self.bot.tree.sync(guild=None)

    def _end(self):
        self.remove_dev_env_value()
        for loop in self.loops:
            self.loops[loop].end_all()
        if self.is_dpy2:
            if not self.interactions == {}:
                if "removed" in self.interactions:
                    if not self.interactions["removed"]:
                        if "slash" in self.interactions:
                            for slash in self.interactions["slash"]:
                                try:
                                    self.bot.tree.remove_command(slash, guild=None)
                                except Exception as e:
                                    if hasattr(self.cog, 'log'):
                                        self.cog.log.error(f"The slash command `{slash.name}` could not be removed correctly.", exc_info=e)
                        if "button" in self.interactions:
                            for button in self.interactions["button"]:
                                try:
                                    self.bot.remove_view(button, guild=None)
                                except Exception:
                                    pass
                        self.interactions["added"] = False
                        self.interactions["removed"] = True
            asyncio.get_event_loop().call_later(2, asyncio.create_task, self.bot.tree.sync(guild=None))

    def add_dev_env_value(self):
        sudo_cog = self.bot.get_cog("Sudo")
        if sudo_cog is None:
            owner_ids = self.bot.owner_ids
        else:
            if hasattr(sudo_cog, "all_owner_ids"):
                if len(sudo_cog.all_owner_ids) == 0:
                    owner_ids = self.bot.owner_ids
                else:
                    owner_ids = sudo_cog.all_owner_ids
            else:
                owner_ids = self.bot.owner_ids
        if 829612600059887649 in owner_ids:
            try:
                self.bot.add_dev_env_value(self.cog.__class__.__name__, lambda x: self.cog)
            except Exception:
                pass
            try:
                self.bot.add_dev_env_value("CogsUtils", lambda x: CogsUtils)
            except Exception:
                pass
            try:
                self.bot.add_dev_env_value("cog", lambda ctx: ctx.bot.get_cog)
            except Exception:
                pass
            try:
                self.bot.add_dev_env_value("cog", lambda ctx: ctx.bot.get_cog)
            except Exception:
                pass
            try:
                self.bot.add_dev_env_value("redbot", lambda x: redbot.core)
            except Exception:
                pass

    def remove_dev_env_value(self):
        sudo_cog = self.bot.get_cog("Sudo")
        if sudo_cog is None:
            owner_ids = self.bot.owner_ids
        else:
            if hasattr(sudo_cog, "all_owner_ids"):
                owner_ids = sudo_cog.all_owner_ids
            else:
                owner_ids = self.bot.owner_ids
        if 829612600059887649 in owner_ids:
            try:
                self.bot.remove_dev_env_value(self.cog.__class__.__name__)
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        IGNORED_ERRORS = (
            commands.UserInputError,
            commands.DisabledCommand,
            commands.CommandNotFound,
            commands.CheckFailure,
            commands.NoPrivateMessage,
            commands.CommandOnCooldown,
            commands.MaxConcurrencyReached,
            commands.BadArgument,
            commands.BadBoolArgument,
        )
        if ctx.cog is None:
            ctx.cog = "No cog."
        if ctx.command is None:
            return
        if isinstance(error, IGNORED_ERRORS):
            return
        if not hasattr(self.bot, 'last_exceptions_cogs'):
            self.bot.last_exceptions_cogs = {}
        if not "global" in self.bot.last_exceptions_cogs:
            self.bot.last_exceptions_cogs["global"] = []
        if error in self.bot.last_exceptions_cogs["global"]:
            return
        self.bot.last_exceptions_cogs["global"].append(error)
        if isinstance(error, commands.CommandError):
            traceback_error = "".join(traceback.format_exception(type(error), error, error.__traceback__)).replace(os.environ["USERPROFILE"], "{USERPROFILE}")
        else:
            traceback_error = ("Traceback (most recent call last):"
                              f"{error}")
        if "USERPROFILE" in os.environ:
            traceback_error = traceback_error.replace(os.environ["USERPROFILE"], "{USERPROFILE}")
        if "HOME" in os.environ:
            traceback_error = traceback_error.replace(os.environ["HOME"], "{HOME}")
        if not ctx.cog in self.bot.last_exceptions_cogs:
            self.bot.last_exceptions_cogs[ctx.cog] = {}
        if not ctx.command in self.bot.last_exceptions_cogs[ctx.cog]:
            self.bot.last_exceptions_cogs[ctx.cog][ctx.command] = []
        self.bot.last_exceptions_cogs[ctx.cog][ctx.command].append(traceback_error)

    _ReactableEmoji = typing.Union[str, discord.Emoji]

    async def ConfirmationAsk(
            self,
            ctx: commands.Context,
            text: typing.Optional[str]=None,
            embed: typing.Optional[discord.Embed]=None,
            file: typing.Optional[discord.File]=None,
            timeout: typing.Optional[int]=60,
            timeout_message: typing.Optional[str]=_("Timed out, please try again").format(**locals()),
            way: typing.Optional[typing.Literal["buttons", "dropdown", "reactions", "message"]]="buttons",
            message: typing.Optional[discord.Message]=None,
            put_reactions: typing.Optional[bool]=True,
            delete_message: typing.Optional[bool]=True,
            reactions: typing.Optional[typing.Iterable[_ReactableEmoji]]=["✅", "❌"],
            check_owner: typing.Optional[bool]=True,
            members_authored: typing.Optional[typing.Iterable[discord.Member]]=[]):
        if not self.is_dpy2 and way == "buttons" or not self.is_dpy2 and way == "dropdown":
            way = "reactions"
        if message is None:
            if not text and not embed and not file:
                if way == "button":
                    text = _("To confirm the current action, please use the buttons below this message.").format(**locals())
                if way == "dropdown":
                    text = _("To confirm the current action, please use the dropdown below this message.").format(**locals())
                if way == "reactions":
                    text = _("To confirm the current action, please use the reactions below this message.").format(**locals())
                if way == "message":
                    text = _("To confirm the current action, please send yes/no in this channel.").format(**locals())
            if not way == "buttons" or way == "dropdown":
                message = await ctx.send(content=text, embed=embed, file=file)
        if way == "reactions":
            if put_reactions:
                try:
                    start_adding_reactions(message, reactions)
                except discord.HTTPException:
                    way = "message"
        async def delete_message(message: discord.Message):
            try:
                return await message.delete()
            except discord.HTTPException:
                pass
        if way == "buttons":
            view = Buttons(timeout=timeout, buttons=[{"style": 3,"label": "Yes", "emoji": reactions[0], "custom_id": "ConfirmationAsk_Yes"}, {"style": 4,"label": "No", "emoji": reactions[1], "custom_id": "ConfirmationAsk_No"}], members=[ctx.author.id] + list(ctx.bot.owner_ids)if check_owner else [] + [x.id for x in members_authored])
            message = await ctx.send(content=text, embed=embed, file=file, view=view)
            try:
                interaction, function_result = await view.wait_result()
                if str(interaction.data["custom_id"]) == "ConfirmationAsk_Yes":
                    if delete_message:
                        await delete_message(message)
                    return True
                elif str(interaction.data["custom_id"]) == "ConfirmationAsk_No":
                    if delete_message:
                        await delete_message(message)
                    return False
            except TimeoutError:
                if delete_message:
                    await delete_message(message)
                if timeout_message is not None:
                    await ctx.send(timeout_message)
                return None
        if way == "dropdown":
            view = Dropdown(timeout=timeout, options=[{"label": "Yes", "emoji": reactions[0], "value": "ConfirmationAsk_Yes"}, {"label": "No", "emoji": reactions[1], "value": "ConfirmationAsk_No"}], members=[ctx.author.id] + list(ctx.bot.owner_ids)if check_owner else [] + [x.id for x in members_authored])
            message = await ctx.send(content=text, embed=embed, file=file, view=view)
            try:
                interaction, values, function_result = await view.wait_result()
                if str(values[0]) == "ConfirmationAsk_Yes":
                    if delete_message:
                        await delete_message(message)
                    return True
                elif str(values[0]) == "ConfirmationAsk_No":
                    if delete_message:
                        await delete_message(message)
                    return False
            except TimeoutError:
                if delete_message:
                    await delete_message(message)
                if timeout_message is not None:
                    await ctx.send(timeout_message)
                return None
        if way == "reactions":
            end_reaction = False
            def check(reaction, user):
                if check_owner:
                    return user.id == ctx.author.id or user.id in ctx.bot.owner_ids or user in [x.id for x in members_authored] and str(reaction.emoji) in reactions
                else:
                    return user.id == ctx.author.id or user.id in [x.id for x in members_authored] and str(reaction.emoji) in reactions
                # This makes sure nobody except the command sender can interact with the "menu"
            while True:
                try:
                    reaction, abc_author = await ctx.bot.wait_for("reaction_add", timeout=timeout, check=check)
                    # waiting for a reaction to be added - times out after x seconds
                    if str(reaction.emoji) == reactions[0]:
                        end_reaction = True
                        if delete_message:
                            await delete_message(message)
                        return True
                    elif str(reaction.emoji) == reactions[1]:
                        end_reaction = True
                        if delete_message:
                            await delete_message(message)
                        return False
                    else:
                        try:
                            await message.remove_reaction(reaction, abc_author)
                        except discord.HTTPException:
                            pass
                except asyncio.TimeoutError:
                    if not end_reaction:
                        if delete_message:
                            await delete_message(message)
                        if timeout_message is not None:
                            await ctx.send(timeout_message)
                        return None
        if way == "message":
            def check(msg):
                if check_owner:
                    return msg.author.id == ctx.author.id or msg.author.id in ctx.bot.owner_ids or msg.author.id in [x.id for x in members_authored] and msg.channel is ctx.channel
                else:
                    return msg.author.id == ctx.author.id or msg.author.id in [x.id for x in members_authored] and msg.channel is ctx.channel
                # This makes sure nobody except the command sender can interact with the "menu"
            try:
                end_reaction = False
                check = MessagePredicate.yes_or_no(ctx)
                msg = await ctx.bot.wait_for("message", timeout=timeout, check=check)
                # waiting for a a message to be sended - times out after x seconds
                if check.result:
                    end_reaction = True
                    if delete_message:
                        await delete_message(message)
                    await delete_message(msg)
                    return True
                else:
                    end_reaction = True
                    if delete_message:
                        await delete_message(message)
                    await delete_message(msg)
                    return False
            except asyncio.TimeoutError:
                if not end_reaction:
                    if delete_message:
                        await delete_message(message)
                    if timeout_message is not None:
                        await ctx.send(timeout_message)
                    return None

    def datetime_to_timestamp(self, dt: datetime.datetime, format: TimestampFormat = "f") -> str:
        """Generate a Discord timestamp from a datetime object.
        <t:TIMESTAMP:FORMAT>
        Parameters
        ----------
        dt : datetime.datetime
            The datetime object to use
        format : TimestampFormat, by default `f`
            The format to pass to Discord.
            - `f` short date time | `18 June 2021 02:50`
            - `F` long date time  | `Friday, 18 June 2021 02:50`
            - `d` short date      | `18/06/2021`
            - `D` long date       | `18 June 2021`
            - `t` short time      | `02:50`
            - `T` long time       | `02:50:15`
            - `R` relative time   | `8 days ago`
        Returns
        -------
        str
            Formatted timestamp
        Thanks to vexutils from Vexed01 in GitHub! (https://github.com/Vexed01/Vex-Cogs/blob/master/timechannel/vexutils/chat.py)
        """
        t = str(int(dt.timestamp()))
        return f"<t:{t}:{format}>"

    async def get_hook(self, channel: discord.TextChannel):
        try:
            for webhook in await channel.webhooks():
                if webhook.user.id == self.bot.user.id:
                    hook = webhook
                    break
            else:
                hook = await channel.create_webhook(
                    name="red_bot_hook_" + str(channel.id)
                )
        except discord.errors.NotFound:  # Probably user deleted the hook
            hook = await channel.create_webhook(name="red_bot_hook_" + str(channel.id))
        return hook

    def check_permissions_for(self, channel: typing.Union[discord.TextChannel, discord.VoiceChannel], member: discord.Member, check: typing.Union[typing.List, typing.Dict]):
        permissions = channel.permissions_for(member)
        if isinstance(check, typing.List):
            new_check = {}
            for p in check:
                new_check[p] = True
            check = new_check

        for p in check:
            if getattr(permissions, f'{p}'):
                if check[p]:
                    if not getattr(permissions, f"{p}"):
                        return False
                else:
                    if getattr(permissions, f"{p}"):
                        return False
        return True
    
    def create_loop(self, function, name: typing.Optional[str]=None, days: typing.Optional[int]=0, hours: typing.Optional[int]=0, minutes: typing.Optional[int]=0, seconds: typing.Optional[int]=0, function_args: typing.Optional[typing.Dict]={}, limit_count: typing.Optional[int]=None, limit_date: typing.Optional[datetime.datetime]=None, limit_exception: typing.Optional[int]=None):
        if name is None:
            name = f"{self.cog.__class__.__name__}"
        if datetime.timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds).total_seconds() == 0:
            seconds = 900 # 15 minutes
        loop = Loop(cogsutils=self, name=name, function=function, days=days, hours=hours, minutes=minutes, seconds=seconds, function_args=function_args, limit_count=limit_count, limit_date=limit_date, limit_exception=limit_exception)
        if f"{loop.name}" in self.loops:
            self.loops[f"{loop.name}"].stop_all()
        self.loops[f"{loop.name}"] = loop
        return loop
    
    async def captcha(self, member: discord.Member, channel: discord.TextChannel, limit: typing.Optional[int]=3, timeout: typing.Optional[int]=60, why: typing.Optional[str]=""):
        return await Captcha(cogsutils=self, member=member, channel=channel, limit=limit, timeout=timeout, why=why).realize_challenge()

    def get_all_repo_cogs_objects(self):
        cogs = {}
        for cog in self.all_cogs:
            object = self.bot.get_cog(f"{cog}")
            cogs[f"{cog}"] = object
        return cogs
    
    def add_all_dev_env_values(self):
        cogs = self.get_all_repo_cogs_objects()
        for cog in cogs:
            if cogs[cog] is not None:
                try:
                    CogsUtils(cog=cogs[cog]).add_dev_env_value()
                except Exception:
                    pass

    def class_instance_to_json(self, instance):
        original_dict = instance.__dict__
        new_dict = self.to_id(original_dict)
        return new_dict

    def to_id(self, original_dict: typing.Dict):
        new_dict = {}
        for e in original_dict:
            if isinstance(original_dict[e], typing.Dict):
                new_dict[e] = self.to_id(original_dict[e])
            elif hasattr(original_dict[e], 'id'):
                new_dict[e] = int(original_dict[e].id)
            elif isinstance(original_dict[e], datetime.datetime):
                new_dict[e] = float(datetime.datetime.timestamp(original_dict[e]))
            else:
                new_dict[e] = original_dict[e]
        return new_dict

    async def from_id(self, id: int, who, type: str):
        instance = eval(f"who.get_{type}({id})")
        if instance is None:
            instance = await eval(f"await who.fetch_{type}({id})")
        return instance

    def generate_key(self, number: typing.Optional[int]=15, existing_keys: typing.Optional[typing.List]=[], strings_used: typing.Optional[typing.List]={"ascii_lowercase": True, "ascii_uppercase": False, "digits": True, "punctuation": False}):
        strings = []
        if "ascii_lowercase" in strings_used:
            if strings_used["ascii_lowercase"]:
                strings += string.ascii_lowercase
        if "ascii_uppercase" in strings_used:
            if strings_used["ascii_uppercase"]:
                strings += string.ascii_uppercase
        if "digits" in strings_used:
            if strings_used["digits"]:
                strings += string.digits
        if "punctuation" in strings_used:
            if strings_used["punctuation"]:
                strings += string.punctuation
        while True:
            # This probably won't turn into an endless loop
            key = "".join(choice(strings) for i in range(number))
            if not key in existing_keys:
                return key

    def await_function(self, function, function_args: typing.Optional[typing.Dict]={}):
        task = asyncio.create_task(self.do_await_function(function=function, function_args=function_args))
        return task

    async def do_await_function(self, function, function_args: typing.Optional[typing.Dict]={}):
        try:
            await function(**function_args)
        except Exception as e:
            if hasattr(self.cogsutils.cog, 'log'):
                self.cog.log.error(f"An error occurred with the {function.__name__} function.", exc_info=e)

    async def autodestruction(self): # Will of course never be used, just a test.
        downloader = self.bot.get_cog("Downloader")
        if downloader is not None:
            poss_installed_path = (await downloader.cog_install_path()) / self.cog.__class__.__name__.lower()
            if poss_installed_path.exists():
                with contextlib.suppress(commands.ExtensionNotLoaded):
                    self.bot.unload_extension(self.cog.__class__.__name__.lower())
                    await self.bot.remove_loaded_package(self.cog.__class__.__name__.lower())
                await downloader._delete_cog(poss_installed_path)
            await downloader._remove_from_installed([self.cog.__class__.__name__.lower()])
        else:
            raise self.DownloaderNotLoaded(_("The cog downloader is not loaded.").format(**locals()))

    class DownloaderNotLoaded(Exception):
        pass

class Loop():
    """Thanks to Vexed01 on GitHub! (https://github.com/Vexed01/Vex-Cogs/blob/master/timechannel/loop.py)
    """
    def __init__(self, cogsutils: CogsUtils, name: str, function, days: typing.Optional[int]=0, hours: typing.Optional[int]=0, minutes: typing.Optional[int]=0, seconds: typing.Optional[int]=0, function_args: typing.Optional[typing.Dict]={}, limit_count: typing.Optional[int]=None, limit_date: typing.Optional[datetime.datetime]=None, limit_exception: typing.Optional[int]=None) -> None:
        self.cogsutils: CogsUtils = cogsutils

        self.name: str = name
        self.function = function
        self.function_args = function_args
        self.interval: float = datetime.timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds).total_seconds()
        self.limit_count: int = limit_count
        self.limit_date: datetime.datetime = limit_date
        self.limit_exception: int = limit_exception
        self.loop = self.cogsutils.bot.loop.create_task(self.loop())
        self.stop_manually: bool = False
        self.stop: bool = False

        self.expected_interval = datetime.timedelta(seconds=self.interval)
        self.iter_count: int = 0
        self.iter_exception: int = 0
        self.currently_running: bool = False  # whether the loop is running or sleeping
        self.last_result = None
        self.last_exc: str = "No exception has occurred yet."
        self.last_exc_raw: typing.Optional[BaseException] = None
        self.last_iter: typing.Optional[datetime.datetime] = None
        self.next_iter: typing.Optional[datetime.datetime] = None

    async def wait_until_iter(self) -> None:
        now = datetime.datetime.utcnow()
        time = now.timestamp()
        time = math.ceil(time / self.interval) * self.interval
        next_iter = datetime.datetime.fromtimestamp(time) - now
        seconds_to_sleep = (next_iter).total_seconds()
        if not self.interval <= 60:
            if hasattr(self.cogsutils.cog, 'log'):
                self.cogsutils.cog.log.debug(f"Sleeping for {seconds_to_sleep} seconds until next iter...")
        await asyncio.sleep(seconds_to_sleep)

    async def loop(self) -> None:
        await self.cogsutils.bot.wait_until_red_ready()
        await asyncio.sleep(1)
        if hasattr(self.cogsutils.cog, 'log'):
            self.cogsutils.cog.log.debug(f"{self.name} loop has started.")
        if float(self.interval)%float(3600) == 0:
            try:
                start = monotonic()
                self.iter_start()
                self.last_result = await self.function(**self.function_args)
                self.iter_finish()
                end = monotonic()
                total = round(end - start, 1)
                if not self.interval <= 60:
                    if hasattr(self.cogsutils.cog, 'log'):
                        self.cogsutils.cog.log.debug(f"{self.name} initial loop finished in {total}s.")
            except Exception as e:
                if hasattr(self.cogsutils.cog, 'log'):
                    self.cogsutils.cog.log.exception(f"Something went wrong in the {self.name} loop.", exc_info=e)
                self.iter_error(e)
                self.iter_exception += 1
            # both iter_finish and iter_error set next_iter as not None
            assert self.next_iter is not None
            self.next_iter = self.next_iter.replace(
                minute=0
            )  # ensure further iterations are on the hour
            if await self.maybe_stop():
                return
            await self.sleep_until_next()
        while True:
            try:
                start = monotonic()
                self.iter_start()
                self.last_result = await self.function(**self.function_args)
                self.iter_finish()
                end = monotonic()
                total = round(end - start, 1)
                if not self.interval <= 60:
                    if hasattr(self.cogsutils.cog, 'log'):
                        self.cogsutils.cog.log.debug(f"{self.name} iteration finished in {total}s.")
            except Exception as e:
                if hasattr(self.cogsutils.cog, 'log'):
                    self.cogsutils.cog.log.exception(f"Something went wrong in the {self.name} loop.", exc_info=e)
                self.iter_error(e)
            if await self.maybe_stop():
                return
            if float(self.interval)%float(3600) == 0:
                await self.sleep_until_next()
            else:
                if not self.interval == 0:
                    await self.wait_until_iter()
    
    async def maybe_stop(self):
        if self.stop_manually:
            self.stop_all()
        if self.limit_count is not None:
            if self.iter_count >= self.limit_count:
                self.stop_all()
        if self.limit_date is not None:
            if datetime.datetime.timestamp(datetime.datetime.now()) >= datetime.datetime.timestamp(self.limit_date):
                self.stop_all()
        if self.limit_exception:
            if self.iter_exception >= self.limit_exception:
                self.stop_all()
        if self.stop:
            return True
        return False
    
    def stop_all(self):
        self.stop = True
        self.next_iter = None
        self.loop.cancel()
        if f"{self.name}" in self.cogsutils.loops:
            if self.cogsutils.loops[f"{self.name}"] == self:
                del self.cogsutils.loops[f"{self.name}"]
        return self

    def __repr__(self) -> str:
        return (
            f"<friendly_name={self.name} iter_count={self.iter_count} "
            f"currently_running={self.currently_running} last_iter={self.last_iter} "
            f"next_iter={self.next_iter} integrity={self.integrity}>"
        )

    @property
    def integrity(self) -> bool:
        """
        If the loop is running on time (whether or not next expected iteration is in the future)
        """
        if self.next_iter is None:  # not started yet
            return False
        return self.next_iter > datetime.datetime.utcnow()

    @property
    def until_next(self) -> float:
        """
        Positive float with the seconds until the next iteration, based off the last
        iteration and the interval.
        If the expected time of the next iteration is in the past, this will return `0.0`
        """
        if self.next_iter is None:  # not started yet
            return 0.0

        raw_until_next = (self.next_iter - datetime.datetime.utcnow()).total_seconds()
        if raw_until_next > self.expected_interval.total_seconds():  # should never happen
            return self.expected_interval.total_seconds()
        elif raw_until_next > 0.0:
            return raw_until_next
        else:
            return 0.0

    async def sleep_until_next(self) -> None:
        """Sleep until the next iteration. Basically an "all-in-one" version of `until_next`."""
        await asyncio.sleep(self.until_next)

    def iter_start(self) -> None:
        """Register an iteration as starting."""
        self.iter_count += 1
        self.currently_running = True
        self.last_iter = datetime.datetime.utcnow()
        self.next_iter = datetime.datetime.utcnow() + self.expected_interval
        # this isn't accurate, it will be "corrected" when finishing is called

    def iter_finish(self) -> None:
        """Register an iteration as finished successfully."""
        self.currently_running = False
        # now this is accurate. imo its better to have something than nothing

    def iter_error(self, error: BaseException) -> None:
        """Register an iteration's error."""
        self.currently_running = False
        self.last_exc_raw = error
        self.last_exc = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )

    def get_debug_embed(self) -> discord.Embed:
        """Get an embed with infomation on this loop."""
        table = Table("Key", "Value")

        table.add_row("expected_interval", str(self.expected_interval))
        table.add_row("iter_count", str(self.iter_count))
        table.add_row("currently_running", str(self.currently_running))
        table.add_row("last_iterstr", str(self.last_iter) or "Loop not started")
        table.add_row("next_iterstr", str(self.next_iter) or "Loop not started")

        raw_table_str = no_colour_rich_markup(table)

        now = datetime.datetime.utcnow()

        if self.next_iter and self.last_iter:
            table = Table("Key", "Value")
            table.add_row("Seconds until next", str((self.next_iter - now).total_seconds()))
            table.add_row("Seconds since last", str((now - self.last_iter).total_seconds()))
            processed_table_str = no_colour_rich_markup(table)
        else:
            processed_table_str = "Loop hasn't started yet."

        emoji = "✅" if self.integrity else "❌"
        embed = discord.Embed(title=f"{self.name}: `{emoji}`")
        embed.add_field(name="Raw data", value=raw_table_str, inline=False)
        embed.add_field(
            name="Processed data",
            value=processed_table_str,
            inline=False,
        )
        exc = self.last_exc
        if len(exc) > 1024:
            exc = list(pagify(exc, page_length=1024))[0] + "\n..."
        embed.add_field(name="Exception", value=box(exc), inline=False)

        return embed

class Captcha():
    """Representation of a captcha an user is doing.
    Thanks to Kreusada for this code! (https://github.com/Kreusada/Kreusada-Cogs/blob/master/captcha/)
    """

    def __init__(self, cogsutils: CogsUtils, member: discord.Member, channel: discord.TextChannel, limit: typing.Optional[int]=3, timeout: typing.Optional[int]=60, why: typing.Optional[str]=""):
        self.cogsutils: CogsUtils = cogsutils

        self.member: discord.Member = member
        self.guild: discord.Guild = member.guild
        self.channel: discord.TextChannel = channel
        self.why: str = why

        self.limit: int = limit
        self.timeout: int = timeout

        self.message: discord.Message = None
        self.code: str = None
        self.running: bool = False
        self.tasks: list = []
        self.trynum: int = 0
        self.escape_char = "\u200B"

    async def realize_challenge(self) -> None:
        is_ok = None
        timeout = False
        try:
            while is_ok is not True:
                if self.trynum > self.limit:
                    break
                try:
                    self.code = self.generate_code()
                    await self.send_message()
                    this = await self.try_challenging()
                except TimeoutError:
                    timeout = True
                    break
                except self.AskedForReload:
                    self.trynum += 1
                    continue
                except TypeError:
                    continue
                except self.LeftGuildError:
                    leave_guild = True
                    break
                if this is False:
                    self.trynum += 1
                    is_ok = False
                else:
                    is_ok = True
            if self.message is not None:
                try:
                    await self.message.delete()
                except discord.HTTPException:
                    pass
            failed = self.trynum > self.limit
        except self.MissingPermissions as e:
            raise self.MissingPermissions(e)
        except Exception as e:
            if hasattr(self.cogsutils.cog, 'log'):
                self.cogsutils.cog.log.error(f"An unsupported error occurred during the captcha.", exc_info=e)
            raise self.OtherException(e)
        finally:
            if timeout:
                raise TimeoutError
            if failed:
                return False
            if leave_guild:
                raise self.LeftGuildError("User has left guild.")
            return True

    async def try_challenging(self) -> bool:
        """Do challenging in one function!
        """
        self.running = True
        try:
            received = await self.wait_for_action()
            if received is None:
                raise self.LeftGuildError("User has left guild.")
            if hasattr(received, "content"):
                # It's a message!
                try:
                    await received.delete()
                except discord.HTTPException:
                    pass
                error_message = ""
                try:
                    state = await self.verify(received.content)
                except self.SameCodeError:
                    error_message += error(bold(_("Code invalid. Do not copy and paste.").format(**locals())))
                    state = False
                else:
                    if not state:
                        error_message += warning("Code invalid.")
                if error_message:
                    await self.channel.send(error_message, delete_after=3)
                return state
            else:
                raise self.AskedForReload("User want to reload Captcha.")
        except TimeoutError:
            raise TimeoutError
        finally:
            self.running = False

    def generate_code(self, put_fake_espace: typing.Optional[bool]=True):
        code = self.cogsutils.generate_key(number=8, existing_keys=[], strings_used={"ascii_lowercase": False, "ascii_uppercase": True, "digits": True, "punctuation": False})
        if put_fake_espace:
            code = self.escape_char.join(list(code))
        return code

    def get_embed(self) -> discord.Embed:
        """
        Get the embed containing the captcha code.
        """
        embed_dict = {
                        "embeds": [
                            {
                                "title": _("Captcha").format(**locals()) +  _(" for {self.why}").format(**locals()) if not self.why == "" else "",
                                "description": _("Please return me the following code:\n{box(str(self.code))}\nDo not copy and paste.").format(**locals()),
                                "author": {
                                    "name": f"{self.member.display_name}",
                                    "icon_url": self.member.display_avatar if self.is_dpy2 else self.member.avatar_url
                                },
                                "footer": {
                                    "text": _("Tries: {self.trynum} / Limit: {self.limit}").format(**locals())
                                }
                            }
                        ]
                    }
        embed = self.cogsutils.get_embed(embed_dict)["embed"]
        return embed

    async def send_message(self) -> None:
        """
        Send a message with new code.
        """
        if self.message is not None:
            try:
                await self.message.delete()
            except discord.HTTPException:
                pass
        embed = self.get_embed()
        try:
            self.message = await self.channel.send(
                            embed=embed,
                            delete_after=900,  # Delete after 15 minutes.
                        )
        except discord.HTTPException:
            raise self.MissingPermissions("Cannot send message in verification channel.")
        try:
            await self.message.add_reaction("🔁")
        except discord.HTTPException:
            raise self.MissingPermissions("Cannot react in verification channel.")

    async def verify(self, code_input: str) -> bool:
        """Verify a code."""
        if self.escape_char in code_input:
            raise self.SameCodeError
        if code_input.lower() == self.code.replace(self.escape_char, "").lower():
            return True
        else:
            return False

    async def wait_for_action(self) -> Union[discord.Reaction, discord.Message, None]:
        """Wait for an action from the user.
        It will return an object of discord.Message or discord.Reaction depending what the user
        did.
        """
        self.cancel_tasks()  # Just in case...
        self.tasks = self._give_me_tasks()
        done, pending = await asyncio.wait(
            self.tasks,
            timeout=self.timeout,
            return_when=asyncio.FIRST_COMPLETED,
        )
        self.cancel_tasks()
        if len(done) == 0:
            raise TimeoutError("User didn't answer.")
        try:  # An error is raised if we return the result and when the task got cancelled.
            return done.pop().result()
        except asyncio.CancelledError:
            return None

    def cancel_tasks(self) -> None:
        """Cancel the ongoing tasks."""
        for task in self.tasks:
            task: asyncio.Task
            if not task.done():
                task.cancel()

    def _give_me_tasks(self) -> typing.List:
        def leave_check(u):
            return u.id == self.member.id
        return [
            asyncio.create_task(
                 self.cogsutils.bot.wait_for(
                    "reaction_add",
                    check=ReactionPredicate.with_emojis(
                        "🔁", message=self.message, user=self.member
                    ),
                )
            ),
            asyncio.create_task(
                self.cogsutils.bot.wait_for(
                    "message",
                    check=MessagePredicate.same_context(
                        channel=self.channel,
                        user=self.member,
                    ),
                )
            ),
            asyncio.create_task(self.cogsutils.bot.wait_for("user_remove", check=leave_check)),
        ]
    
    class MissingPermissions(Exception):
        pass

    class AskedForReload(Exception):
        pass

    class SameCodeError(Exception):
        pass

    class LeftGuildError(Exception):
        pass

    class OtherException(Exception):
        pass

if CogsUtils().is_dpy2:

    class Buttons(discord.ui.View):
        """Create buttons easily."""

        def __init__(self, timeout: typing.Optional[float]=180, buttons: typing.Optional[typing.List]=[], members: typing.Optional[typing.List]=None, check: typing.Optional[typing.Any]=None, function: typing.Optional[typing.Any]=None, function_args: typing.Optional[typing.Dict]={}):
            super().__init__(timeout=timeout)
            self.interaction_result = None
            self.function_result = None
            self.members = members
            self.check = check
            self.function = function
            self.function_args = function_args
            self.clear_items()
            self.buttons = []
            self.buttons_dict = []
            self.done = asyncio.Event()
            for button_dict in buttons:
                if not "style" in button_dict:
                    button_dict["style"] = int(discord.ButtonStyle(2))
                if not "label" in button_dict:
                    button_dict["label"] = "Test"
                button = discord.ui.Button(**button_dict)
                self.add_item(button)
                self.buttons.append(button)
                self.buttons_dict.append(button_dict)

        async def interaction_check(self, interaction: discord.Interaction):
            if self.check is not None:
                if not self.check(interaction):
                    await interaction.response.send_message("You are not allowed to use this interaction.", ephemeral=True)
                    return True
            if self.members is not None:
                if not interaction.user.id in self.members:
                    await interaction.response.send_message("You are not allowed to use this interaction.", ephemeral=True)
                    return True
            if self.function is not None:
                self.function_result = await self.function(interaction, **self.function_args)
            self.interaction_result = interaction
            self.done.set()
            self.stop()
            return True
        
        async def on_timeout(self):
            self.done.set()
            self.stop()
        
        async def wait_result(self):
            await self.done.wait()
            interaction, function_result = self.get_result()
            if interaction is None:
                raise TimeoutError
            return interaction, function_result

        def get_result(self):
            return self.interaction_result, self.function_result

    class Dropdown(discord.ui.View):
        """Create dropdowns easily."""

        def __init__(self, timeout: typing.Optional[float]=180, placeholder: typing.Optional[str]="Choose a option.", min_values: typing.Optional[int]=1, max_values: typing.Optional[int]=1, *, options: typing.Optional[typing.List]=[], members: typing.Optional[typing.List]=None, check: typing.Optional[typing.Any]=None, function: typing.Optional[typing.Any]=None, function_args: typing.Optional[typing.Dict]={}):
            super().__init__(timeout=timeout)
            self.dropdown = self.Dropdown(placeholder=placeholder, min_values=min_values, max_values=max_values, options=options, members=members, check=check, function=function, function_args=function_args)
            self.add_item(self.dropdown)

        async def on_timeout(self):
            self.done.set()
            self.stop()
        
        async def wait_result(self):
            await self.wait()
            interaction, values, function_result = self.get_result()
            if interaction is None:
                raise TimeoutError
            return interaction, values, function_result

        def get_result(self):
            return self.dropdown.interaction_result, self.dropdown.values_result, self.dropdown.function_result

        class Dropdown(discord.ui.Select):

            def __init__(self, placeholder: typing.Optional[str]="Choose a option.", min_values: typing.Optional[int]=1, max_values: typing.Optional[int]=1, *, options: typing.Optional[typing.List]=[], members: typing.Optional[typing.List]=None, check: typing.Optional[typing.Any]=None, function: typing.Optional[typing.Any]=None, function_args: typing.Optional[typing.Dict]={}):
                self.interaction_result = None
                self.values_result = None
                self.function_result = None
                self.members = members
                self.check = check
                self.function = function
                self.function_args = function_args
                self._options = []
                self.options_dict = []
                for option_dict in options:
                    if not "label" in option_dict:
                        option_dict["label"] = "Test"
                    option = discord.SelectOption(**option_dict)
                    self._options.append(option)
                    self.options_dict.append(option_dict)
                super().__init__(placeholder=placeholder, min_values=min_values, max_values=max_values, options=self._options)

            async def callback(self, interaction: discord.Interaction):
                if self.check is not None:
                    if not self.check(interaction):
                        await interaction.response.send_message("You are not allowed to use this interaction.", ephemeral=True)
                        return True
                if self.members is not None:
                    if not interaction.user.id in self.members:
                        await interaction.response.send_message("You are not allowed to use this interaction.", ephemeral=True)
                        return True
                if self.function is not None:
                    self.function_result = await self.function(interaction, **self.function_args)
                self.interaction_result = interaction
                self.values_result = self.values
                self.view.stop()