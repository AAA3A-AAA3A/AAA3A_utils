from symtable import Function
import discord
import logging
import typing
import datetime
import asyncio
import contextlib
from copy import copy
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.utils.predicates import MessagePredicate
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.data_manager import cog_data_path
from redbot.core.utils.chat_formatting import *
import traceback
import math
from rich.table import Table
from io import StringIO

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

__all__ = ["CogsUtils", "Loop"]
TimestampFormat = typing.Literal["f", "F", "d", "D", "t", "T", "R"]

class CogsUtils(commands.Cog):
    """Tools for AAA3A-cogs!"""

    def __init__(self, cog: typing.Optional[commands.Cog]=None, bot: typing.Optional[Red]=None):
        if cog is None and bot is not None:
            self.cog = None
            self.bot = bot
        else:
            if isinstance(cog, str):
                cog = self.bot.get_cog(cog)
            self.cog = cog
            self.bot = self.cog.bot
            self.DataPath = cog_data_path(raw_name=self.cog.__class__.__name__.lower())
        self.__authors__ = ["AAA3A"]
        self.__version__ = 1.0
        if self.cog is not None:
            if hasattr(self.cog, '__authors__'):
                if isinstance(self.cog.__authors__, typing.List):
                    self.__authors__ = self.cog.__authors__
            elif hasattr(self.cog, '__author__'):
                if isinstance(self.cog.__author__, typing.List):
                    self.__authors__ = self.cog.__author__
            if hasattr(self.cog, '__version__'):
                if isinstance(self.cog.__version__, typing.List):
                    self.__version__ = self.cog.__version__
            if hasattr(self.cog, '__func_red__'):
                if not isinstance(self.cog.__func_red__, typing.List):
                    self.cog.__func_red__ = []
            else:
                self.cog.__func_red__ = []
        self.loops = {}
        self.repo_name = "AAA3A-cogs"
        self.all_cogs = [
                            "AntiNuke",
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

    def format_help_for_context(self, ctx):
        """Thanks Simbad!"""
        context = super().format_help_for_context(ctx)
        s = "s" if len(self.__authors__) > 1 else ""
        return f"{context}\n\n**Author{s}**: {', '.join(self.__authors__)}\n**Version**: {self.__version__}"

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete"""
        return

    async def red_get_data_for_user(self, *args, **kwargs) -> typing.Dict[typing.Any, typing.Any]:
        return {}
    
    def cog_unload(self):
        self.cogsutils._end()

    def _setup(self):
        self.cog.cogsutils = self
        self.cog.log = logging.getLogger(f"red.{self.repo_name}.{self.cog.__class__.__name__}")
        self.add_dev_env_value()
        if not "format_help_for_context" in self.cog.__func_red__:
            setattr(self.cog, 'format_help_for_context', self.format_help_for_context)
        if not "red_delete_data_for_user" in self.cog.__func_red__:
            setattr(self.cog, 'red_delete_data_for_user', self.red_delete_data_for_user)
        if not "red_get_data_for_user" in self.cog.__func_red__:
            setattr(self.cog, 'red_get_data_for_user', self.red_get_data_for_user)
        if not "cog_unload" in self.cog.__func_red__:
            setattr(self.cog, 'cog_unload', self.cog_unload)

    def _end(self):
        self.remove_dev_env_value()
        for loop in self.loops.values():
            loop.end_all()

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

    def get_embed(self, embed_dict: typing.Dict) -> typing.Dict[discord.Embed, str]:
        data = embed_dict
        if data.get("embed"):
            data = data["embed"]
        elif data.get("embeds"):
            data = data.get("embeds")[0]
        if timestamp := data.get("timestamp"):
            data["timestamp"] = timestamp.strip("Z")
        if data.get("content"):
            content = data["content"]
            del data["content"]
        else:
            content = ""
        try:
            embed = discord.Embed.from_dict(data)
            length = len(embed)
            if length > 6000:
                raise commands.BadArgument(
                    f"Embed size exceeds Discord limit of 6000 characters ({length})."
                )
        except Exception as e:
            raise commands.BadArgument(
                f"An error has occurred.\n{e})."
            )
        back = {"embed": embed, "content": content}
        return back

    _ReactableEmoji = typing.Union[str, discord.Emoji]

    async def ConfirmationAsk(
            self,
            ctx,
            text: typing.Optional[str]=None,
            embed: typing.Optional[discord.Embed]=None,
            file: typing.Optional[discord.File]=None,
            timeout: typing.Optional[int]=60,
            timeout_message: typing.Optional[str]="Timed out, please try again",
            use_reactions: typing.Optional[bool]=True,
            message: typing.Optional[discord.Message]=None,
            put_reactions: typing.Optional[bool]=True,
            delete_message: typing.Optional[bool]=True,
            reactions: typing.Optional[typing.Iterable[_ReactableEmoji]]=["✅", "❌"],
            check_owner: typing.Optional[bool]=True,
            members_authored: typing.Optional[typing.Iterable[discord.Member]]=[]):
        if message is None:
            if not text and not embed and not file:
                if use_reactions:
                    text = "To confirm the current action, please use the feedback below this message."
                else:
                    text = "To confirm the current action, please send yes/no in this channel."
            message = await ctx.send(content=text, embed=embed, file=file)
        if use_reactions:
            if put_reactions:
                try:
                    start_adding_reactions(message, reactions)
                except discord.HTTPException:
                    use_reactions = False
        async def delete_message(message: discord.Message):
            try:
                return await message.delete()
            except discord.HTTPException:
                pass
        if use_reactions:
            end_reaction = False
            def check(reaction, user):
                if check_owner:
                    return user == ctx.author or user.id in ctx.bot.owner_ids or user in members_authored and str(reaction.emoji) in reactions
                else:
                    return user == ctx.author or user in members_authored and str(reaction.emoji) in reactions
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
        if not use_reactions:
            def check(msg):
                if check_owner:
                    return msg.author == ctx.author or msg.author.id in ctx.bot.owner_ids or msg.author in members_authored and msg.channel is ctx.channel
                else:
                    return msg.author == ctx.author or msg.author in members_authored and msg.channel is ctx.channel
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
        Thanks to vexutils from Vexed01 in GitHub.
        """
        t = str(int(dt.timestamp()))
        return f"<t:{t}:{format}>"

    async def get_hook(self, channel: discord.TextChannel):
        try:
            for i in await channel.webhooks():
                if i.user.id == self.bot.user.id:
                    hook = i
                    break
            else:
                hook = await channel.create_webhook(
                    name="red_bot_hook_" + str(channel.id)
                )
        except discord.errors.NotFound:  # Probably user deleted the hook
            hook = await channel.create_webhook(name="red_bot_hook_" + str(channel.id))
        return hook

    def check_permissions_for(self, channel: typing.Union[discord.TextChannel, discord.VoiceChannel], member: discord.Member, check: typing.Dict):
        permissions = channel.permissions_for(member)
        for p in check:
            if getattr(permissions, f'{p}'):
                if check[p]:
                    if not eval(f"permissions.{p}"):
                        return False
                else:
                    if eval(f"permissions.{p}"):
                        return False
        return True
    
    def create_loop(self, function, name: typing.Optional[str]=None, interval: typing.Optional[float]=None, function_args: typing.Optional[typing.Dict]={}):
        if name is None:
            name = f"{self.cog.__class__.__name__}_loop"
        if interval is None:
            interval = 900 # 15 minutes
        loop = Loop(name=name, cogsutils=self, interval=interval, function=function, function_args=function_args)
        if f"{loop.name}" in self.loops:
            self.loops[f"{loop.name}"].stop_all()
        self.loops[f"{loop.name}"] = loop
        return loop

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
            raise "The cog downloader is not loaded."

class Loop():
    """Thanks to Vexed01 on GitHub! (https://github.com/Vexed01/Vex-Cogs/blob/master/timechannel/loop.py)
    """
    def __init__(self, name: str, cogsutils: CogsUtils, interval: float, function, function_args: typing.Optional[typing.Dict]={}) -> None:
        self.name: str = name
        self.interval: float = interval
        self.cogsutils: CogsUtils = cogsutils
        self.function: Function = function
        self.function_args: typing.Dict = function_args
        self.loop = self.cogsutils.bot.loop.create_task(self.loop())

        self.expected_interval = datetime.timedelta(seconds=self.interval)
        self.iter_count: int = 0
        self.currently_running: bool = False  # whether the loop is running or sleeping
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
        self.cogsutils.cog.log.debug(f"Sleeping for {seconds_to_sleep} seconds until next iter...")
        await asyncio.sleep(seconds_to_sleep)

    async def loop(self) -> None:
        await self.cogsutils.bot.wait_until_red_ready()
        await asyncio.sleep(1)
        self.cogsutils.cog.log.debug(f"{self.cog.__class__.__name__} loop has started.")
        while True:
            try:
                self.iter_start()
                await self.function(**self.function_args)
                self.iter_finish()
                self.cogsutils.cog.log.debug(f"{self.cog.__class__.__name__} iteration finished")
            except Exception as e:
                self.cogsutils.cog.log.exception(f"Something went wrong in the {self.cog.__class__.__name__} loop.", exc_info=e)
                self.iter_error(e)
            await self.wait_until_iter()
    
    def stop_all(self):
        self.loop.cancel()

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
        """Register an iteration's exception."""
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

        else:
            processed_table_str = "Loop hasn't started yet."

        emoji = "\N{HEAVY CHECK MARK}\N{VARIATION SELECTOR-16}" if self.integrity else "\N{CROSS MARK}"
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
