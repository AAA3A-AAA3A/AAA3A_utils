from redbot.core import commands  # isort:skip
from redbot.core.bot import Red  # isort:skip
import discord  # isort:skip
import typing  # isort:skip

import asyncio
import datetime
import inspect
import logging
import os
import random
import re
import string
import time
from copy import copy
from functools import partial
from io import StringIO
from pathlib import Path
from random import choice

import aiohttp
from rich.console import Console

from redbot.core.commands.requires import PrivilegeLevel
from redbot.core.utils.chat_formatting import box, humanize_list
from redbot.logging import RotatingFileHandler

from .views import ConfirmationAskView

__all__ = ["CogsUtils"]


def _(untranslated: str) -> str:
    return untranslated


replacement_var_paths: bool = True
# Strong references to the tasks created with `CogsUtils.create_task`, to avoid garbage collection.
_background_tasks: set[asyncio.Task] = set()
# Cache of the GitHub API responses, to avoid reaching the rate limit (60 requests per hour per IP).
_github_api_cache: dict[str, tuple[float, typing.Any]] = {}
GITHUB_API_CACHE_TTL: int = 60 * 60


class CogsUtils:
    """Utils for AAA3A-cogs!"""

    @classmethod
    def replace_var_paths(cls, text: str, reverse: bool | None = False) -> str:
        if not reverse:
            if not replacement_var_paths:
                return text
            for env_var in ("USERPROFILE", "HOME", "USERNAME", "COMPUTERNAME"):
                if env_var in os.environ:
                    regex = re.compile(re.escape(os.environ[env_var]), re.IGNORECASE)
                    text = regex.sub(f"{{{env_var}}}", text)
                    regex = re.compile(
                        re.escape(os.environ[env_var].replace("\\", "\\\\")),
                        re.IGNORECASE,
                    )
                    text = regex.sub(f"{{{env_var}}}", text)
                    regex = re.compile(
                        re.escape(os.environ[env_var].replace("\\", "/")),
                        re.IGNORECASE,
                    )
                    text = regex.sub(f"{{{env_var}}}", text)
        else:

            class FakeDict(dict):
                def __missing__(self, key: str) -> str:
                    if (
                        key.upper() in ("USERPROFILE", "HOME", "USERNAME", "COMPUTERNAME")
                        and key.upper() in os.environ
                    ):
                        return os.environ[key.upper()]
                    return f"{{{key}}}"

            text = text.format_map(FakeDict())
        return text

    @classmethod
    def create_task(
        cls,
        coro: typing.Coroutine,
        *,
        name: str | None = None,
    ) -> asyncio.Task:
        """
        Create a task and keep a strong reference to it until it is done (no garbage collection).
        """
        task = asyncio.create_task(coro, name=name)
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return task

    @classmethod
    def no_colour_rich_markup(
        cls,
        *objects: typing.Any,
        lang: str = "",
        no_box: bool | None = False,
    ) -> str:
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
        if no_box:
            return temp_console.file.getvalue()
        return box(temp_console.file.getvalue(), lang=lang)  # type: ignore

    @classmethod
    def get_logger(
        cls,
        name: str | None = None,
        cog: commands.Cog | None = None,
    ) -> logging.Logger:
        """
        Get a logger for a provided name or a provided cog.
        Thanks to @laggron42 on GitHub! (https://github.com/laggron42/Laggron-utils/blob/master/laggron_utils/logging.py)
        """
        if name is None and cog is None:
            raise RuntimeError()
        if name is not None and cog is None:
            return (
                logging.getLogger(name)
                if name.startswith("red.")
                else logging.getLogger(f"red.AAA3A-cogs.{name}")
            )

        logger = (
            logging.getLogger(f"red.{cog.__repo_name__}.{cog.qualified_name}")
            if name is None
            else logging.getLogger(f"red.{cog.__repo_name__}.{cog.qualified_name}.{name}")
        )

        __log = partial(logging.Logger._log, logger)

        def _log(level, msg, args, exc_info=None, extra=None, stack_info=False, stacklevel=1):
            from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING

            VERBOSE = DEBUG - 3
            TRACE = DEBUG - 5
            levels = {
                CRITICAL: "CRITICAL",
                DEBUG: "DEBUG",
                ERROR: "ERROR",
                INFO: "INFO",
                WARNING: "WARNING",
                VERBOSE: "VERBOSE",
                TRACE: "TRACE",
            }
            _level = levels.get(level, str(level))
            if _level not in cog.logs:
                cog.logs[_level] = []
            cog.logs[_level].append(
                {
                    "time": datetime.datetime.now().astimezone(),
                    "level": level,
                    "message": msg,
                    "args": args,
                    "exc_info": exc_info,
                    "levelname": _level,
                },
            )
            __log(
                level=level,
                msg=msg,
                args=args,
                exc_info=exc_info,
                extra=extra,
                stack_info=stack_info,
                stacklevel=stacklevel,
            )

        logger._log = _log

        # Logging in a log file.
        # (File is automatically created by the module, if the parent foler exists.)
        try:
            formatter = logging.Formatter(
                "[{asctime}] {levelname} [{name}] {message}",
                datefmt="%Y-%m-%d %H:%M:%S",
                style="{",
            )
            if cog.data_path.exists():
                file_handler = RotatingFileHandler(
                    stem=cog.qualified_name,
                    directory=cog.data_path,
                    maxBytes=1_000_000,
                    backupCount=0,
                    encoding="utf-8",
                )
                file_handler.setLevel(logging.DEBUG)
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
        except Exception as e:
            logger.debug("Error when initiating the logger in a separate file.", exc_info=e)

        return logger

    @classmethod
    def close_logger(cls, logger: logging.Logger) -> None:
        """
        Closes the files for the logger of a cog.
        """
        for handler in logger.handlers:
            handler.close()
        logger.handlers = []

    @classmethod
    async def get_cog_version(
        cls,
        bot: Red,
        cog: commands.Cog | str,
    ) -> tuple[int, float, str]:
        cog_name = cog.lower() if isinstance(cog, str) else cog.qualified_name.lower()
        downloader_cog = bot.get_cog("Downloader")
        if downloader_cog is None:
            raise RuntimeError("The Downloader cog is not loaded.")

        if await bot._cog_mgr.find_cog(cog_name) is None:
            raise ValueError("This cog was not found in any cog path.")

        from redbot.cogs.downloader.repo_manager import ProcessFormatter, Repo

        repo = None
        path = Path(inspect.getsourcefile(cog.__class__))
        if path.parent.parent != await bot._cog_mgr.install_path():
            local = None
            repo = Repo(name="", url="", branch="", commit="", folder_path=path.parent.parent)
        else:
            local = discord.utils.get(await downloader_cog.installed_cogs(), name=cog_name)
            if local is not None:
                repo = local.repo
        if repo is None:
            raise ValueError("This cog is not installed on this bot with Downloader.")

        exists, __ = repo._existing_git_repo()
        if not exists:
            raise ValueError(f"A git repo does not exist at path: {repo.folder_path}")
        git_command = ProcessFormatter().format(
            "git -C {path} rev-list HEAD --count {cog_name}",
            path=repo.folder_path,
            cog_name=cog_name,
        )
        p = await repo._run(git_command)
        if p.returncode != 0:
            raise asyncio.IncompleteReadError(
                "No results could be retrieved from the git command.",
                None,
            )
        nb_commits = p.stdout.decode(encoding="utf-8").strip()
        nb_commits = int(nb_commits)

        version = round(1.0 + (nb_commits / 100), 2)

        if local is not None:
            commit = local.commit
        else:
            git_command = ProcessFormatter().format(
                "git -C {path} log HEAD -1 {cog_name}",
                path=repo.folder_path,
                cog_name=cog_name,
            )
            p = await repo._run(git_command)
            if p.returncode != 0:
                raise asyncio.IncompleteReadError(
                    "No results could be retrieved from the git command.",
                    None,
                )
            commit = p.stdout.decode(encoding="utf-8").strip()
            commit = commit.split("\n")[0][7:]

        return nb_commits, version, commit

    @classmethod
    async def check_if_to_update(
        cls,
        bot: Red,
        cog: commands.Cog | str,
        repo_url: str | None = None,
    ) -> tuple[bool, str, str]:
        cog_name = cog.lower() if isinstance(cog, str) else cog.qualified_name.lower()
        if repo_url is None:
            downloader_cog = bot.get_cog("Downloader")
            if downloader_cog is None:
                raise RuntimeError("The Downloader cog is not loaded.")
            if await bot._cog_mgr.find_cog(cog_name) is None:
                raise ValueError("This cog was not found in any cog path.")
            local = discord.utils.get(await downloader_cog.installed_cogs(), name=cog_name)
            if local is None:
                raise ValueError("This cog is not installed on this bot with the cog Downloader.")
            local_commit = local.commit
            repo = local.repo
            if repo is None:
                raise ValueError("This cog is not installed on this bot with the cog Downloader.")
            repo_url = repo.url
        else:
            cog = None
            cog_name = None

        if isinstance(repo_url, str):
            repo_owner, repo_name, repo_branch = (
                re.compile(
                    r"(?:https?:\/\/)?git(?:hub|lab)\.com\/(?P<repo_owner>[A-Za-z0-9_.-]*)\/(?P<repo>[A-Za-z0-9_.-]*)(?:\/tree\/(?P<repo_branch>[A-Za-z0-9_.-]*))?",
                    re.IGNORECASE,
                ).findall(repo_url)
            )[0]
        else:
            repo_owner, repo_name, repo_branch = repo_url
            repo_branch = repo_branch or repo.branch

        async with aiohttp.ClientSession() as session:
            online = await cls._get_github_api(
                session,
                (
                    f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits?sha={repo_branch}&path={cog_name}"  # Thanks Jack!
                    if repo_branch
                    else f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits?path={cog_name}"
                ),
            )
            if (
                isinstance(online, dict)
                and "message" in online
                and "API rate limit exceeded" in online["message"]
            ):
                raise asyncio.LimitOverrunError("API rate limit exceeded.", 47)
            if online is None or not isinstance(online, list) or len(online) == 0:
                raise asyncio.IncompleteReadError(
                    "No results could be retrieved from the git API.",
                    None,
                )
            online_commit = online[0]["sha"]
            if online_commit == local_commit:
                return False, local_commit, online_commit

            async def get_commit_date(commit_sha: str) -> str:
                data = await cls._get_github_api(
                    session,
                    f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits/{commit_sha}",
                )
                if not isinstance(data, dict) or "commit" not in data:
                    raise ValueError("No results could be retrieved from the git API.")
                return data["commit"]["committer"]["date"]

            try:
                # The cog has to be updated if the online commit is newer than the local one.
                to_update = await get_commit_date(local_commit) < await get_commit_date(
                    online_commit,
                )
            except ValueError:  # Failed API request (temporary).
                to_update = False
            else:
                path = Path(inspect.getsourcefile(cog.__class__))
                if path.parent.parent != (await bot._cog_mgr.install_path()):
                    to_update = False

        return to_update, local_commit, online_commit

    @classmethod
    async def _get_github_api(cls, session: aiohttp.ClientSession, url: str) -> typing.Any:
        """
        Get a GitHub API endpoint, with a cache to avoid reaching the rate limit.
        """
        now = time.monotonic()
        if (cached := _github_api_cache.get(url)) is not None and now - cached[0] < (
            GITHUB_API_CACHE_TTL
        ):
            return cached[1]
        async with session.get(
            url,
            headers={"Accept": "application/vnd.github+json"},
            timeout=aiohttp.ClientTimeout(total=3),
        ) as r:
            data = await r.json()
        if r.status == 200:  # Don't cache errors (rate limit...).
            _github_api_cache[url] = (now, data)
        return data

    @classmethod
    async def add_hybrid_commands(cls, bot: Red, cog: commands.Cog) -> None:
        if hasattr(cog, "settings") and hasattr(cog.settings, "commands_added"):
            await cog.settings.commands_added.wait()
        if cog.qualified_name == "Medicat" and hasattr(cog, "CC_added"):
            await cog.CC_added.wait()
        for _object in cog.walk_commands():
            if isinstance(_object, (commands.HybridCommand, commands.HybridGroup)):
                if _object.app_command is not None:
                    _object.app_command.description = _object.app_command.description.split("\n")[
                        0
                    ][:100]
                if _object.parent is not None:
                    _object.checks.extend(_object.parent.checks)
                    if _object.requires.privilege_level is PrivilegeLevel.NONE:
                        _object.requires.privilege_level = _object.parent.requires.privilege_level
                    if _object.requires.user_perms == discord.Permissions(0):
                        _object.requires.user_perms = _object.parent.requires.user_perms
                    if _object.requires.bot_perms == discord.Permissions(0):
                        _object.requires.bot_perms = _object.parent.requires.bot_perms

        await bot.tree.red_check_enabled()

    @classmethod
    async def ConfirmationAsk(
        cls,
        ctx: commands.Context,
        *args,
        timeout: int | None = 60,
        timeout_message: str | None = _("Timed out, please try again."),
        way: typing.Literal["buttons", "message"] | None = "buttons",  # , "reactions"
        delete_message: bool | None = True,
        members_authored: typing.Iterable[discord.Member] | None = [],
        **kwargs,
    ) -> bool:
        """
        Request a confirmation by the user., in the form of buttons/message, with many additional options.
        """
        check_owner = True

        if way == "buttons":
            return await ConfirmationAskView(
                ctx=ctx,
                timeout=timeout,
                timeout_message=timeout_message,
                delete_message=delete_message,
                members=members_authored,
            ).start(*args, **kwargs)

        if way == "message":
            message = await ctx.send(*args, **kwargs)

            def check(msg):
                if check_owner:
                    return (
                        msg.author.id == ctx.author.id
                        or msg.author.id in ctx.bot.owner_ids
                        or msg.author.id in [x.id for x in members_authored]
                        and msg.channel == ctx.channel
                        and msg.content in ("yes", "y", "no", "n")
                    )
                return (
                    msg.author.id == ctx.author.id
                    or msg.author.id in [x.id for x in members_authored]
                    and msg.channel == ctx.channel
                    and msg.content in ("yes", "y", "no", "n")
                )

            try:
                end_reaction = False
                msg = await ctx.bot.wait_for("message", timeout=timeout, check=check)
                if msg.content in ("yes", "y"):
                    end_reaction = True
                    if delete_message:
                        await cls.delete_message(message)
                    await cls.delete_message(msg)
                    return True
                if msg.content in ("no", "n"):
                    end_reaction = True
                    if delete_message:
                        await cls.delete_message(message)
                    await cls.delete_message(msg)
                    return False
            except (TimeoutError, asyncio.TimeoutError):
                if not end_reaction:
                    if delete_message:
                        await cls.delete_message(message)
                    if timeout_message is not None:
                        await ctx.send(timeout_message)
                    return None
        return None

    @classmethod
    async def delete_message(
        cls,
        message: discord.Message,
        delay: float | None = None,
    ) -> bool:
        """
        Delete a message, ignoring any exceptions.
        Easier than putting these 3 lines at each message deletion for each cog.
        """
        if message is None:
            return None
        try:
            await message.delete(delay=delay)
        except discord.NotFound:  # Already deleted.
            return True
        except discord.HTTPException:
            return False
        else:
            return True

    @classmethod
    async def invoke_command(
        cls,
        bot: Red,
        author: discord.User,
        channel: discord.TextChannel,
        command: str,
        prefix: str | None = None,
        message: discord.Message | None = None,
        dispatch_message: bool | None = False,
        invoke: bool | None = True,
        __is_mocked__: bool | None = True,
        created_at: datetime.datetime | None = None,
        **kwargs,
    ) -> commands.Context | discord.Message:
        """
        Invoke the specified command with the specified user in the specified channel.
        """
        if created_at is None:
            created_at = datetime.datetime.now(tz=datetime.timezone.utc)
        message_id = discord.utils.time_snowflake(created_at)
        if prefix == "/":  # For hybrid and slash commands.
            prefix = None
        if prefix is None:
            prefixes = await bot.get_valid_prefixes(guild=channel.guild)
            prefix = prefixes[0] if len(prefixes) < 3 else prefixes[2]
        old_content = f"{command}"
        content = f"{prefix}{old_content}"

        if message is None:
            message_content = content
            author_dict = {
                "id": f"{author.id}",
                "username": author.display_name,
                "avatar": author.avatar,
                "avatar_decoration": None,
                "discriminator": f"{author.discriminator}",
                "public_flags": author.public_flags,
                "bot": author.bot,
            }
            channel_id = channel.id
            timestamp = str(created_at).replace(" ", "T") + "+00:00"
            data = {
                "id": message_id,
                "type": 0,
                "content": message_content,
                "channel_id": f"{channel_id}",
                "author": author_dict,
                "attachments": [],
                "embeds": [],
                "mentions": [],
                "mention_roles": [],
                "pinned": False,
                "mention_everyone": False,
                "tts": False,
                "timestamp": timestamp,
                "edited_timestamp": None,
                "flags": 0,
                "components": [],
                "referenced_message": None,
            }
            message: discord.Message = discord.Message(
                channel=channel,
                state=bot._connection,
                data=data,
            )
        else:
            message = copy(message)
            message.author = author
            message.channel = channel
            message.content = content

        context: commands.Context = await bot.get_context(message)
        context.author = author
        context.guild = channel.guild
        context.channel = channel

        if not context.valid and context.prefix is not None:
            if (  # Red's Alias
                (Alias := bot.get_cog("Alias")) is not None
                and not await bot.cog_disabled_in_guild(Alias, context.guild)
            ):
                alias = await Alias._aliases.get_alias(context.guild, context.invoked_with)
                if alias is not None:

                    async def command_callback(__, ctx: commands.Context):
                        await Alias.call_alias(ctx.message, ctx.prefix, alias)

                    context.command = commands.command(name="alias")(command_callback)
                    context.command.name = context.invoked_with
                    context.command.cog = Alias
                    context.command.params.clear()
                    context.command.requires.ready_event.set()
            elif (  # Red's CustomCommands
                (CustomCommands := bot.get_cog("CustomCommands")) is not None
                and not await bot.cog_disabled_in_guild(CustomCommands, context.guild)
            ):
                from redbot.cogs.customcom.customcom import CCError

                try:
                    raw_response, cooldowns = await CustomCommands.commandobj.get(
                        message=message,
                        command=context.invoked_with,
                    )
                    if isinstance(raw_response, list):
                        raw_response = random.choice(raw_response)
                except CCError:  # `NotFound`.
                    pass
                else:

                    async def command_callback(__, ctx: commands.Context):
                        try:
                            if cooldowns:
                                CustomCommands.test_cooldowns(
                                    context,
                                    context.invoked_with,
                                    cooldowns,
                                )
                        except CCError:  # `OnCooldown`.
                            return
                        del ctx.args[0]
                        await CustomCommands.cc_command(
                            *ctx.args,
                            **ctx.kwargs,
                            raw_response=raw_response,
                        )

                    context.command = commands.command(name="customcom")(command_callback)
                    context.command.name = context.invoked_with
                    context.command.cog = CustomCommands
                    context.command.requires.ready_event.set()
                    context.command.params = CustomCommands.prepare_args(raw_response)
            elif (  # Phen/Lemon's Tags
                (Tags := bot.get_cog("Tags")) is not None
                and not await bot.cog_disabled_in_guild(Tags, context.guild)
            ):
                tag = Tags.get_tag(context.guild, context.invoked_with, check_global=True)
                if tag is not None:
                    message.content = f"{context.prefix}invoketag {command}"
                    context: commands.Context = await bot.get_context(message)
                    context.author = author
                    context.guild = channel.guild
                    context.channel = channel

        if __is_mocked__:
            context.__is_mocked__ = True
        context.__dict__.update(**kwargs)
        if not invoke:
            return context
        if context.valid:
            await bot.invoke(context)
        else:
            if dispatch_message:
                message.content = old_content
                bot.dispatch("message", message)
        return context

    @classmethod
    async def get_hook(cls, bot: Red, channel: discord.TextChannel) -> discord.Webhook:
        """
        Create a discord.Webhook object. It tries to retrieve an existing webhook created by the bot or to create it itself.
        """
        hook = next(
            (webhook for webhook in await channel.webhooks() if webhook.user.id == bot.user.id),
            None,
        )
        if hook is None:
            hook = await channel.create_webhook(name=f"red_bot_hook_{channel.id!s}")
        return hook

    @classmethod
    def get_interval_string(
        cls,
        expires: datetime.datetime | datetime.timedelta | None,
        utc_now: datetime.datetime | None = None,
        use_timestamp: bool = False,
    ) -> str:
        """
        Get a string from a given duration.
        """
        if expires is None:
            return "No future occurrence."
        if use_timestamp:
            expires = expires.replace(tzinfo=datetime.timezone.utc)
            return f"<t:{int(expires.timestamp())}:R>"
        if utc_now is None:
            utc_now = datetime.datetime.now(datetime.timezone.utc)
        if isinstance(expires, datetime.datetime):
            delta = utc_now - expires
        elif isinstance(expires, datetime.timedelta):
            delta = expires
        else:
            try:
                import dateutil
            except ImportError:
                delta = datetime.timedelta(seconds=expires)
            else:
                if isinstance(expires, dateutil.relativedelta.relativedelta):
                    delta = (utc_now + expires) - utc_now
                else:
                    delta = datetime.timedelta(seconds=expires)
        result = []
        total_secs = int(max(0, delta.total_seconds()))
        years, rem = divmod(total_secs, 3600 * 24 * 365)
        if years > 0:
            result.append(f"{years} year" + ("s" if years > 1 else ""))
        months, rem = divmod(rem, 3600 * 24 * 7 * 4)
        if months > 0:
            result.append(f"{months} month" + ("s" if months > 1 else ""))
        weeks, rem = divmod(rem, 3600 * 24 * 7)
        if weeks > 0:
            result.append(f"{weeks} week" + ("s" if weeks > 1 else ""))
        days, rem = divmod(rem, 3600 * 24)
        if days > 0:
            result.append(f"{days} day" + ("s" if days > 1 else ""))
        hours, rem = divmod(rem, 3600)
        if hours > 0:
            result.append(f"{hours} hour" + ("s" if hours > 1 else ""))
        minutes, rem = divmod(rem, 60)
        if minutes > 0:
            result.append(f"{minutes} minute" + ("s" if minutes > 1 else ""))
        seconds = rem
        if seconds > 0:
            result.append(f"{seconds} second" + ("s" if seconds > 1 else ""))
        return humanize_list(result) if result else "just now"  # "0 minute"

    @classmethod
    def get_all_repo_cogs_objects(cls, bot: Red) -> dict[str, commands.Cog]:
        """
        Get a dictionary containing the objects of all my cogs.
        """
        cogs = {}
        for cog in bot.cogs.values():
            if cog.qualified_name in ("CogGuide"):
                continue
            if getattr(cog, "__repo_name__", None) == "AAA3A-cogs":
                cogs[cog.qualified_name] = cog
        return cogs

    @classmethod
    def at_least_one_cog_loaded(cls, bot: Red) -> bool:
        """
        Return True if at least one cog of all my cogs is loaded.
        """
        return any(cog is not None for cog in cls.get_all_repo_cogs_objects(bot).values())

    @classmethod
    def generate_key(
        cls,
        length: int | None = 10,
        existing_keys: list | set | None = None,
        strings_used: list | None = None,
    ) -> str:
        """
        Generate a secret key, with the choice of characters, the number of characters and a list of existing keys.
        """
        if existing_keys is None:
            existing_keys = []
        if strings_used is None:
            strings_used = {
                "ascii_lowercase": True,
                "ascii_uppercase": False,
                "digits": True,
                "punctuation": False,
                "others": [],
            }
        strings = []
        if strings_used.get("ascii_lowercase"):
            strings += string.ascii_lowercase
        if strings_used.get("ascii_uppercase"):
            strings += string.ascii_uppercase
        if strings_used.get("digits"):
            strings += string.digits
        if strings_used.get("punctuation"):
            strings += string.punctuation
        if "others" in strings_used and isinstance(strings_used["others"], list):
            strings += strings_used["others"]
        while True:
            # This probably won't turn into an endless loop.
            key = "".join(choice(strings) for _ in range(length))
            if key not in existing_keys:
                return key
