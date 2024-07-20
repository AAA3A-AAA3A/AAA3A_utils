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
from copy import copy
from functools import partial
from pathlib import Path
from random import choice

import aiohttp
from redbot.core.utils.chat_formatting import humanize_list
from redbot.logging import RotatingFileHandler

from .views import ConfirmationAskView

__all__ = ["CogsUtils"]


def _(untranslated: str) -> str:
    return untranslated


replacement_var_paths: bool = True


class CogsUtils:
    """Utils for AAA3A-cogs!"""

    # def __init__(
    #     self, cog: typing.Optional[commands.Cog] = None, bot: typing.Optional[Red] = None
    # ) -> None:
    #     if cog is not None:
    #         if isinstance(cog, str):
    #             cog = bot.get_cog(cog)
    #         self.cog: commands.Cog = cog
    #         self.bot: Red = self.cog.bot if hasattr(self.cog, "bot") else bot

    #     elif bot is not None:
    #         self.cog: typing.Optional[commands.Cog] = None
    #         self.bot: Red = bot
    #     else:
    #         self.cog: typing.Optional[commands.Cog] = None
    #         self.bot: typing.Optional[Red] = None

    @property
    def is_dpy2(self) -> bool:
        """
        Returns `True` if the current redbot instance is running under dpy2.
        """
        return discord.version_info.major >= 2

    @classmethod
    def replace_var_paths(cls, text: str, reverse: typing.Optional[bool] = False) -> str:
        if not reverse:
            if not replacement_var_paths:
                return text
            for env_var in ("USERPROFILE", "HOME", "USERNAME", "COMPUTERNAME"):
                if env_var in os.environ:
                    regex = re.compile(re.escape(os.environ[env_var]), re.I)
                    text = regex.sub(f"{{{env_var}}}", text)
                    regex = re.compile(re.escape(os.environ[env_var].replace("\\", "\\\\")), re.I)
                    text = regex.sub(f"{{{env_var}}}", text)
                    regex = re.compile(re.escape(os.environ[env_var].replace("\\", "/")), re.I)
                    text = regex.sub(f"{{{env_var}}}", text)
        else:

            class FakeDict(typing.Dict):
                def __missing__(self, key: str) -> str:
                    if (
                        key.upper() in ("USERPROFILE", "HOME", "USERNAME", "COMPUTERNAME")
                        and key.upper() in os.environ
                    ):
                        return os.environ[key.upper()]
                    return f"{{{key}}}"

            text = text.format_map(FakeDict())
        return text

    # async def add_cog(
    #     self, bot: typing.Optional[Red] = None, cog: typing.Optional[commands.Cog] = None, **kwargs
    # ) -> commands.Cog:
    #     """
    #     Load a cog by checking whether the required function is awaitable or not.
    #     """
    #     if bot is None:
    #         bot = self.bot
    #     if cog is None:
    #         cog = self.cog
    #         await self.change_config_unique_identifier(cog=cog)
    #         self._setup()
    #     value = bot.add_cog(cog, **kwargs)
    #     if inspect.isawaitable(value):
    #         await value
    #     return cog

    @classmethod
    def get_logger(
        cls, name: typing.Optional[str] = None, cog: typing.Optional[commands.Cog] = None
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
            from logging import CRITICAL, DEBUG, ERROR, FATAL, INFO, WARN, WARNING

            VERBOSE = DEBUG - 3
            TRACE = DEBUG - 5
            levels = {
                CRITICAL: "CRITICAL",
                DEBUG: "DEBUG",
                ERROR: "ERROR",
                FATAL: "FATAL",
                INFO: "INFO",
                WARN: "WARN",
                WARNING: "WARNING",
                VERBOSE: "VERBOSE",
                TRACE: "TRACE",
            }
            _level = levels.get(level, str(level))
            if _level not in cog.logs:
                cog.logs[_level] = []
            cog.logs[_level].append(
                {
                    "time": datetime.datetime.now(),
                    "level": level,
                    "message": msg,
                    "args": args,
                    "exc_info": exc_info,
                    "levelname": _level,
                }
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

        setattr(logger, "_log", _log)

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
                    maxBytes=1_000_0,
                    backupCount=0,
                    encoding="utf-8",
                )
                # file_handler.doRollover()
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
        cls, bot: Red, cog: typing.Union[commands.Cog, str]
    ) -> typing.Tuple[int, float, str]:
        cog_name = cog.lower() if isinstance(cog, str) else cog.qualified_name.lower()
        downloader_cog = bot.get_cog("Downloader")
        if downloader_cog is None:
            raise RuntimeError("The Downloader cog is not loaded.")

        if await bot._cog_mgr.find_cog(cog_name) is None:
            raise ValueError("This cog was not found in any cog path.")

        from redbot.cogs.downloader.repo_manager import ProcessFormatter, Repo

        repo = None
        path = Path(inspect.getsourcefile(cog.__class__))
        if not path.parent.parent == (await bot._cog_mgr.install_path()):
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
                "No results could be retrieved from the git command.", None
            )
        nb_commits = p.stdout.decode(encoding="utf-8").strip()
        nb_commits = int(nb_commits)

        version = round(1.0 + (nb_commits / 100), 2)

        if local is not None:
            commit = local.commit
        else:
            git_command = ProcessFormatter().format(
                "git -C {path} log HEAD -1 {cog_name}", path=repo.folder_path, cog_name=cog_name
            )
            p = await repo._run(git_command)
            if p.returncode != 0:
                raise asyncio.IncompleteReadError(
                    "No results could be retrieved from the git command.", None
                )
            commit = p.stdout.decode(encoding="utf-8").strip()
            commit = commit.split("\n")[0][7:]

        return nb_commits, version, commit

    @classmethod
    async def check_if_to_update(
        cls,
        bot: Red,
        cog: typing.Union[commands.Cog, str],
        repo_url: typing.Optional[str] = None,
    ) -> typing.Tuple[bool, str, str]:
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
                    r"(?:https?:\/\/)?git(?:hub|lab).com\/(?P<repo_owner>[A-z0-9-_.]*)\/(?P<repo>[A-z0-9-_.]*)(?:\/tree\/(?P<repo_branch>[A-z0-9-_.]*))?",
                    re.I,
                ).findall(repo_url)
            )[0]
        else:
            repo_owner, repo_name, repo_branch = repo_url
            repo_branch = repo_branch or repo.branch
        async with aiohttp.ClientSession() as session:
            async with session.get(
                (
                    f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits?sha={repo_branch}&path={cog_name}"  # Thanks Jack!
                    if repo_branch
                    else f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits?path={cog_name}"
                ),  # f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/refs/heads/{repo_branch}" & f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents?path={cog_name}"
                timeout=3,
            ) as r:
                online = await r.json()
        if (
            isinstance(online, typing.Dict)
            and "message" in online
            and "API rate limit exceeded" in online["message"]
        ):
            raise asyncio.LimitOverrunError("API rate limit exceeded.", 47)
        if online is None or not isinstance(online, typing.List) or len(online) == 0:
            raise asyncio.IncompleteReadError(
                "No results could be retrieved from the git API.", None
            )
        online_commit = online[0]["sha"]

        async def compare_commit_dates(repo_owner, repo_name, commit_sha1, commit_sha2):
            async def get_commit_date(
                repo_owner: str, repo_name: str, commit_sha: str, session: aiohttp.ClientSession
            ):
                url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/commits/{commit_sha}"
                headers = {"Accept": "application/vnd.github+json"}
                async with session.get(url, headers=headers) as response:
                    data = await response.json()
                    if "commit" not in data:
                        raise asyncio.TimeoutError(
                            "No results could be retrieved from the git API."
                        )
                    commit_date = data["commit"]["committer"]["date"]
                return commit_date

            async with aiohttp.ClientSession() as session:
                commit_date1 = await get_commit_date(repo_owner, repo_name, commit_sha1, session)
                commit_date2 = await get_commit_date(repo_owner, repo_name, commit_sha2, session)
                if commit_date1 > commit_date2:
                    # Commit `{commit_sha1}` is newer than commit `{commit_sha2}`.
                    return False
                elif commit_date1 < commit_date2:
                    # Commit `{commit_sha2}` is newer than commit `{commit_sha1}`.
                    return True
                else:
                    # Commits `{commit_sha1}` and `{commit_sha2}`are the same date.
                    return None

        try:
            to_update = await compare_commit_dates(
                repo_owner=repo_owner,
                repo_name=repo_name,
                commit_sha1=local_commit,
                commit_sha2=online_commit,
            )
        except ValueError:  # Failed API request (temporary).
            to_update = False
        else:
            path = Path(inspect.getsourcefile(cog.__class__))
            if not path.parent.parent == (await bot._cog_mgr.install_path()):
                to_update = False

        return to_update, local_commit, online_commit  # , online_commit_for_each_files

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
                if _object.parent is not None and not _object.parent.invoke_without_command:
                    _object.checks.extend(_object.parent.checks)
        await bot.tree.red_check_enabled()

    @classmethod
    async def ConfirmationAsk(
        cls,
        ctx: commands.Context,
        *args,
        timeout: typing.Optional[int] = 60,
        timeout_message: typing.Optional[str] = _("Timed out, please try again"),
        way: typing.Optional[typing.Literal["buttons", "message"]] = "buttons",  # , "reactions"
        delete_message: typing.Optional[bool] = True,
        members_authored: typing.Optional[typing.Iterable[discord.Member]] = [],
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

        # elif way == "reactions":
        #     message = await ctx.send(*args, **kwargs)
        #     try:
        #         start_adding_reactions(message, reactions)
        #     except discord.HTTPException:
        #         way = "message"
        #     view = Reactions(
        #         bot=ctx.bot,
        #         message=message,
        #         remove_reaction=False,
        #         timeout=timeout,
        #         reactions=reactions,
        #         members=[ctx.author.id] + list(ctx.bot.owner_ids)
        #         if check_owner
        #         else [] + [x.id for x in members_authored],
        #     )
        #     try:
        #         reaction, user, function_result = await view.wait_result()
        #         if str(reaction.emoji) == reactions[0]:
        #             end_reaction = True
        #             if delete_message:
        #                 await cls.delete_message(message)
        #             return True
        #         elif str(reaction.emoji) == reactions[1]:
        #             end_reaction = True
        #             if delete_message:
        #                 await cls.delete_message(message)
        #             return False
        #     except TimeoutError:
        #         if delete_message:
        #             await cls.delete_message(message)
        #         if timeout_message is not None:
        #             await ctx.send(timeout_message)
        #         return None

        elif way == "message":
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
                else:
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
                elif msg.content in ("no", "n"):
                    end_reaction = True
                    if delete_message:
                        await cls.delete_message(message)
                    await cls.delete_message(msg)
                    return False
            except asyncio.TimeoutError:
                if not end_reaction:
                    if delete_message:
                        await cls.delete_message(message)
                    if timeout_message is not None:
                        await ctx.send(timeout_message)
                    return None

    @classmethod
    async def delete_message(
        cls, message: discord.Message, delay: typing.Optional[float] = None
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
        prefix: typing.Optional[str] = None,
        message: typing.Optional[discord.Message] = None,
        dispatch_message: typing.Optional[bool] = False,
        invoke: typing.Optional[bool] = True,
        __is_mocked__: typing.Optional[bool] = True,
        created_at: typing.Optional[datetime.datetime] = None,
        **kwargs,
    ) -> typing.Union[commands.Context, discord.Message]:
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
                channel=channel, state=bot._connection, data=data
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

        if (  # Red's Alias
            not context.valid
            and context.prefix is not None
            and (alias_cog := bot.get_cog("Alias")) is not None
            and not await bot.cog_disabled_in_guild(alias_cog, context.guild)
        ):
            alias = await alias_cog._aliases.get_alias(context.guild, context.invoked_with)
            if alias is not None:

                async def command_callback(__, ctx: commands.Context):
                    await alias_cog.call_alias(ctx.message, ctx.prefix, alias)

                context.command = commands.command(name=command)(command_callback)
                context.command.cog = alias_cog
                context.command.params.clear()
                context.command.requires.ready_event.set()
        if (  # Red's CustomCommands
            not context.valid
            and context.prefix is not None
            and (custom_commands_cog := bot.get_cog("CustomCommands")) is not None
            and not await bot.cog_disabled_in_guild(custom_commands_cog, context.guild)
        ):
            try:
                raw_response, cooldowns = await custom_commands_cog.commandobj.get(
                    message=message, command=context.invoked_with
                )
                if isinstance(raw_response, list):
                    raw_response = random.choice(raw_response)
                elif isinstance(raw_response, str):
                    pass
            except Exception:
                pass
            else:

                async def command_callback(__, ctx: commands.Context):
                    # await custom_commands_cog.cc_callback(ctx)  # fake callback
                    try:
                        if cooldowns:
                            custom_commands_cog.test_cooldowns(
                                context, context.invoked_with, cooldowns
                            )
                    except Exception:
                        return
                    del ctx.args[0]
                    await custom_commands_cog.cc_command(
                        *ctx.args, **ctx.kwargs, raw_response=raw_response
                    )

                context.command = commands.command(name=command)(command_callback)
                context.command.cog = custom_commands_cog
                context.command.requires.ready_event.set()
                context.command.params = custom_commands_cog.prepare_args(raw_response)
        if (  # Phen/Lemon's Tags
            not context.valid
            and context.prefix is not None
            and (tags_cog := bot.get_cog("Tags")) is not None
            and not await bot.cog_disabled_in_guild(tags_cog, context.guild)
        ):
            tag = tags_cog.get_tag(context.guild, context.invoked_with, check_global=True)
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
            hook = await channel.create_webhook(name=f"red_bot_hook_{str(channel.id)}")
        return hook

    @classmethod
    def get_embed(
        cls, embed_dict: typing.Dict
    ) -> typing.Dict[str, typing.Union[discord.Embed, str]]:
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
        for x in data:
            if data[x] is None:
                del data[x]
            elif isinstance(data[x], typing.Dict):
                for y in data[x]:
                    if data[x][y] is None:
                        del data[x][y]
        try:
            embed = discord.Embed.from_dict(data)
            length = len(embed)
            if length > 6000:
                raise commands.BadArgument(
                    f"Embed size exceeds Discord limit of 6000 characters ({length})."
                )
        except Exception as e:
            raise commands.BadArgument(f"An error has occurred.\n{e}).")
        return {"embed": embed, "content": content}

    @classmethod
    def datetime_to_timestamp(
        cls,
        dt: datetime.datetime,
        format: typing.Literal["f", "F", "d", "D", "t", "T", "R"] = "f",
    ) -> str:
        """
        Generate a Discord timestamp from a datetime object.
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

    @classmethod
    def get_interval_string(
        cls,
        expires: typing.Optional[
            typing.Union[
                datetime.datetime, datetime.timedelta  # , dateutil.relativedelta.relativedelta
            ]
        ],
        utc_now: datetime.datetime = None,
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
            # delta.seconds = 0
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
    def check_permissions_for(
        cls,
        channel: typing.Union[discord.TextChannel, discord.VoiceChannel, discord.DMChannel],
        user: discord.User,
        check: typing.Union[typing.List, typing.Dict],
    ) -> bool:
        """
        Check all permissions specified as an argument.
        """
        if getattr(channel, "guild", None) is None:
            return True
        permissions = channel.permissions_for(user)
        if isinstance(check, typing.List):
            new_check = {p: True for p in check}
            check = new_check
        return not any(
            getattr(permissions, p, None)
            is not None  # Explicitly check whether the value is None.
            and (
                (check[p] and not getattr(permissions, p))
                or (not check[p] and getattr(permissions, p))
            )
            for p in check
        )

    # @classmethod
    # def create_loop(
    #     cls,
    #     cog: commands.Cog,
    #     function,
    #     name: typing.Optional[str] = None,
    #     days: typing.Optional[int] = 0,
    #     hours: typing.Optional[int] = 0,
    #     minutes: typing.Optional[int] = 0,
    #     seconds: typing.Optional[int] = 0,
    #     function_kwargs: typing.Optional[typing.Dict] = None,
    #     wait_raw: typing.Optional[bool] = False,
    #     limit_count: typing.Optional[int] = None,
    #     limit_date: typing.Optional[datetime.datetime] = None,
    #     limit_exception: typing.Optional[int] = None,
    # ) -> Loop:
    #     """
    #     Create a `Loop` class instance, with default values and loop object recording functionality.
    #     """
    #     if function_kwargs is None:
    #         function_kwargs = {}
    #     if name is None:
    #         name = cog.qualified_name
    #     if (
    #         datetime.timedelta(
    #             days=days, hours=hours, minutes=minutes, seconds=seconds
    #         ).total_seconds()
    #         == 0
    #     ):
    #         seconds = 900  # 15 minutes
    #     loop = Loop(
    #         cog=cog,
    #         name=name,
    #         function=function,
    #         days=days,
    #         hours=hours,
    #         minutes=minutes,
    #         seconds=seconds,
    #         function_kwargs=function_kwargs,
    #         wait_raw=wait_raw,
    #         limit_count=limit_count,
    #         limit_date=limit_date,
    #         limit_exception=limit_exception,
    #     )
    #     # if (existing_loop := discord.utils.get(self.cog.loops, name=name)) is not None:
    #     #     existing_loop.stop_all()
    #     cog.loops.append(loop)
    #     return loop

    @classmethod
    def get_all_repo_cogs_objects(cls, bot: Red) -> typing.Dict[str, commands.Cog]:
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
        length: typing.Optional[int] = 10,
        existing_keys: typing.Optional[typing.Union[typing.List, typing.Set]] = None,
        strings_used: typing.Optional[typing.List] = None,
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
        if "ascii_lowercase" in strings_used and strings_used["ascii_lowercase"]:
            strings += string.ascii_lowercase
        if "ascii_uppercase" in strings_used and strings_used["ascii_uppercase"]:
            strings += string.ascii_uppercase
        if "digits" in strings_used and strings_used["digits"]:
            strings += string.digits
        if "punctuation" in strings_used and strings_used["punctuation"]:
            strings += string.punctuation
        if "others" in strings_used and isinstance(strings_used["others"], typing.List):
            strings += strings_used["others"]
        while True:
            # This probably won't turn into an endless loop.
            key = "".join(choice(strings) for _ in range(length))
            if key not in existing_keys:
                return key

    @classmethod
    async def check_in_listener(
        cls,
        bot: Red,
        arg: typing.Union[discord.Message, discord.RawReactionActionEvent, discord.Interaction],
        allowed_by_whitelist_blacklist: bool = True,
    ) -> bool:
        """
        Check all parameters for the output of any listener.
        Thanks to Jack! (https://discord.com/channels/133049272517001216/160386989819035648/825373605000511518)
        """
        try:
            if isinstance(arg, discord.Message):
                # check whether the message was sent by a webhook
                if arg.webhook_id is not None:
                    raise discord.ext.commands.BadArgument()
                # check whether the message was sent in a guild
                if arg.guild is None:
                    raise discord.ext.commands.BadArgument()
                # check whether the message author isn't a bot
                if arg.author is None:
                    raise discord.ext.commands.BadArgument()
                if arg.author.bot:
                    raise discord.ext.commands.BadArgument()
                # check whether the bot can send messages in the given channel
                if arg.channel is None:
                    raise discord.ext.commands.BadArgument()
                if not arg.channel.permissions_for(arg.guild.me).send_messages:
                    raise discord.ext.commands.BadArgument()
                # check whether the cog isn't disabled
                # if self.cog is not None and await self.bot.cog_disabled_in_guild(
                #     self.cog, output.guild
                # ):
                #     raise discord.ext.commands.BadArgument()
                # check whether the channel isn't on the ignore list
                if not await bot.ignored_channel_or_guild(arg):
                    raise discord.ext.commands.BadArgument()
                # check whether the message author isn't on allowlist/blocklist
                if (
                    allowed_by_whitelist_blacklist
                    and not await bot.allowed_by_whitelist_blacklist(arg.author)
                ):
                    raise discord.ext.commands.BadArgument()
            elif isinstance(arg, discord.RawReactionActionEvent):
                # check whether the message was sent in a guild
                arg.guild = bot.get_guild(arg.guild_id)
                if arg.guild is None:
                    raise discord.ext.commands.BadArgument()
                # check whether the message author isn't a bot
                arg.author = arg.guild.get_member(arg.user_id)
                if arg.author is None:
                    raise discord.ext.commands.BadArgument()
                if arg.author.bot:
                    raise discord.ext.commands.BadArgument()
                # check whether the bot can send message in the given channel
                arg.channel = arg.guild.get_channel(arg.channel_id)
                if arg.channel is None:
                    raise discord.ext.commands.BadArgument()
                if not arg.channel.permissions_for(arg.guild.me).send_messages:
                    raise discord.ext.commands.BadArgument()
                # check whether the cog isn't disabled
                # if self.cog is not None and await self.bot.cog_disabled_in_guild(
                #     self.cog, output.guild
                # ):
                #     raise discord.ext.commands.BadArgument()
                # check whether the channel isn't on the ignore list
                if not await bot.ignored_channel_or_guild(arg):
                    raise discord.ext.commands.BadArgument()
                # check whether the message author isn't on allowlist/blocklist
                if (
                    allowed_by_whitelist_blacklist
                    and not await bot.allowed_by_whitelist_blacklist(arg.author)
                ):
                    raise discord.ext.commands.BadArgument()
            elif isinstance(arg, discord.Interaction):
                # check whether the message was sent in a guild
                if arg.guild is None:
                    raise discord.ext.commands.BadArgument()
                # check whether the message author isn't a bot
                if arg.author is None:
                    raise discord.ext.commands.BadArgument()
                if arg.author.bot:
                    raise discord.ext.commands.BadArgument()
                # check whether the bot can send message in the given channel
                if arg.channel is None:
                    raise discord.ext.commands.BadArgument()
                if not arg.channel.permissions_for(arg.guild.me).send_messages:
                    raise discord.ext.commands.BadArgument()
                # check whether the cog isn't disabled
                # if self.cog is not None and await self.bot.cog_disabled_in_guild(
                #     self.cog, output.guild
                # ):
                #     raise discord.ext.commands.BadArgument()
                # check whether the message author isn't on allowlist/blocklist
                if (
                    allowed_by_whitelist_blacklist
                    and not await bot.allowed_by_whitelist_blacklist(arg.author)
                ):
                    raise discord.ext.commands.BadArgument()
        except commands.BadArgument:
            return False
        return True
