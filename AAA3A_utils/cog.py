from redbot.core import commands  # isort:skip
from redbot.core.bot import Red  # isort:skip
import discord  # isort:skip
import typing  # isort:skip

import asyncio
import datetime
import logging
import re
import traceback
from pathlib import Path
from uuid import uuid4

import aiohttp
from redbot.core.data_manager import cog_data_path
from redbot.core.utils.chat_formatting import humanize_list, inline, warning

from .__version__ import __version__ as __utils_version__
from .cogsutils import CogsUtils
from .context import Context, is_dev
from .loop import Loop
from .settings import Settings

SharedCog: commands.Cog = None

__all__ = ["Cog"]


def _(untranslated: str) -> str:
    return untranslated


# class Cog:
#     def __init__(self, bot: Red) -> None:
#         self.bot: Red = bot
#         self.cog: commands.Cog = None

#     @classmethod
#     def _setup(cls, bot: Red, cog: commands.Cog) -> None:
#         """
#         Adding additional functionality to the cog.
#         """
#         # for command in self.cog.walk_commands():
#         #     setattr(command, 'format_text_for_context', self.format_text_for_context)
#         #     setattr(command, 'format_shortdoc_for_context', self.format_shortdoc_for_context)
#         specials = [
#             "_setup",
#             "get_formatted_text",
#             "format_text_for_context",
#             "format_shortdoc_for_context",
#             "unsupported",
#             "verbose_forbidden_exception",
#         ]
#         self = cls(bot=bot)
#         self.cog = cog
#         for attr in dir(self):
#             if attr.startswith("__") and attr.endswith("__"):
#                 continue
#             if attr in specials:
#                 continue
#             if getattr(getattr(cog, attr, None), "__func__", "None1") != getattr(
#                 commands.Cog, attr, "None2"
#             ):
#                 continue
#             setattr(cog, attr, getattr(self, attr))


async def unsupported(ctx: commands.Context) -> None:
    """Thanks to Vexed for this (https://github.com/Vexed01/Vex-Cogs/blob/master/status/commands/statusdev_com.py#L33-L56)."""
    if is_dev(ctx.bot, ctx.author):
        return
    content = warning(
        "\nTHIS COMMAND IS INTENDED FOR DEVELOPMENT PURPOSES ONLY.\n\nUnintended "
        "things can happen.\n\nRepeat: THIS COMMAND IS NOT SUPPORTED.\nAre you sure "
        "you want to continue?"
    )
    try:
        result = await CogsUtils.ConfirmationAsk(ctx, content=content)
    except TimeoutError:
        await ctx.send("Timeout, aborting.")
        raise commands.CheckFailure("Confirmation timed out.")
    if result:
        return True
    await ctx.send("Aborting.")
    raise commands.CheckFailure("User choose no.")


class Cog(commands.Cog):
    __authors__: typing.List[str] = ["AAA3A"]
    __version__: float = 1.0
    __commit__: str = ""
    __repo_name__: str = "AAA3A-cogs"
    __utils_version__: float = __utils_version__

    # bot: Red
    # data_path: Path
    # logger: logging.Logger
    # logs: typing.Dict[
    #     str,
    #     typing.List[
    #         typing.Dict[
    #             str,
    #             typing.Optional[
    #                 typing.Union[datetime.datetime, int, str, typing.Tuple[typing.Any]]
    #             ],
    #         ]
    #     ],
    # ]
    # loops: typing.List[Loop]
    # views: typing.Dict[typing.Union[discord.Message, discord.PartialMessage, str], discord.ui.View]

    def __init__(self, bot: Red) -> None:
        self.bot: Red = bot
        self.data_path: Path = cog_data_path(cog_instance=self)

        self.logs: typing.Dict[
            str,
            typing.List[
                typing.Dict[
                    str,
                    typing.Optional[
                        typing.Union[datetime.datetime, int, str, typing.Tuple[typing.Any]]
                    ],
                ]
            ],
        ] = {}
        self.loops: typing.List[Loop] = []
        self.views: typing.Dict[
            typing.Union[discord.Message, discord.PartialMessage, str], discord.ui.View
        ] = {}  # `str` is for Views not linked to a message (in TicketTool for example).

    async def cog_load(self) -> None:
        # Init logger.
        self.logger: logging.Logger = CogsUtils.get_logger(cog=self)
        # Prevent Red `(timeout)` error.
        asyncio.create_task(self.cog_load_new_task())

    async def cog_load_new_task(self) -> None:
        # Wait until Red ready. But `(timeout)` when cog loading when bot starting...
        await self.bot.wait_until_red_ready()
        # Get cog version.
        try:
            nb_commits, version, commit = await CogsUtils.get_cog_version(bot=self.bot, cog=self)
            self.__version__: float = version
            self.__commit__: str = commit
        except (
            RuntimeError,
            asyncio.TimeoutError,
            ValueError,
            TypeError,  # `TypeError: <class 'extension.extension.Cog'> is a built-in class` is when the cog failed to load.
        ):
            pass
        except Exception as e:  # Really doesn't matter if this fails, so fine with debug level.
            self.logger.debug(
                f"Something went wrong checking `{self.qualified_name}` version.",
                exc_info=e,
            )
        # Check updates.
        try:
            (
                to_update,
                local_commit,
                online_commit,
                online_commit_for_each_files,
            ) = await CogsUtils.check_if_to_update(bot=self.bot, cog=self)
            if to_update:
                self.logger.warning(
                    f"Your `{self.qualified_name}` cog, from `{self.__repo_name__}`, is out of date."
                    " You can update your cogs with the '[p]cog update' command in Discord."
                )
            else:
                self.logger.debug(f"{self.qualified_name} cog is up to date.")
        except (
            RuntimeError,
            asyncio.TimeoutError,
            ValueError,
            asyncio.LimitOverrunError,
        ):
            pass
        except Exception as e:  # Really doesn't matter if this fails, so fine with debug level.
            self.logger.debug(
                f"Something went wrong checking if `{self.qualified_name}` cog is up to date.",
                exc_info=e,
            )
        # Add SharedCog.
        if self.qualified_name != "AAA3A_utils":
            try:
                old_cog = await self.bot.remove_cog("AAA3A_utils")
                AAA3A_utils = SharedCog(self.bot)
                try:
                    if getattr(old_cog, "sentry", None) is not None:
                        AAA3A_utils.sentry = old_cog.sentry
                        AAA3A_utils.sentry.cog = AAA3A_utils
                    AAA3A_utils.loops = old_cog.loops
                except AttributeError:
                    pass
                await self.bot.add_cog(
                    AAA3A_utils, override=True
                )  # `override` shouldn't be required...
            except discord.ClientException:  # Cog already loaded.
                pass
            except Exception as e:
                self.logger.debug("Error when adding the `AAA3A_utils` cog.", exc_info=e)
            else:
                await AAA3A_utils.sentry.maybe_send_owners(self)
        # Count this cog (anonymous stats).
        AAA3A_utils = self.bot.get_cog("AAA3A_utils")
        counted_cogs = await AAA3A_utils.config.counted_cogs()
        if self.qualified_name not in counted_cogs:
            try:
                async with aiohttp.ClientSession(raise_for_status=True) as session:
                    async with session.get(
                        f"https://api.counterapi.dev/v1/AAA3A-cogs/{self.qualified_name}/up"
                    ):
                        pass
            except Exception as e:
                pass
            else:
                counted_cogs.append(self.qualified_name)
                await AAA3A_utils.config.counted_cogs.set(counted_cogs)
        # Modify hybrid commands.
        await CogsUtils.add_hybrid_commands(bot=self.bot, cog=self)

    async def cog_unload(self) -> None:
        # Close logger.
        CogsUtils.close_logger(self.logger)
        # Stop loops.
        for loop in self.loops.copy():
            if self.qualified_name == "AAA3A_utils" and loop.name == "Sentry Helper":
                continue
            await loop.execute()  # Maybe is it a loop who save data... Might execute it a last time.
            loop.stop_all()
        # Stop views.
        for view in self.views.values():
            if not view.is_finished():
                await view.on_timeout()
                view.stop()
            try:
                self.bot.persistent_views.remove(view)
            except ValueError:
                pass
        self.views.clear()
        # Remove SharedCog.
        AAA3A_utils: SharedCog = self.bot.get_cog("AAA3A_utils")
        if AAA3A_utils is not None:
            if AAA3A_utils.sentry is not None:
                await AAA3A_utils.sentry.cog_unload(self)
            if not CogsUtils.at_least_one_cog_loaded(self.bot):
                try:
                    discord.utils.get(AAA3A_utils.loops, name="Sentry Helper").stop_all()
                except ValueError:
                    pass
                await self.bot.remove_cog("AAA3A_utils")

    def format_help_for_context(self, ctx: commands.Context) -> str:
        """Thanks Simbad!"""
        text = super().format_help_for_context(ctx)
        s = "s" if len(self.__authors__) > 1 else ""
        text = (
            f"{text}"
            f"\n\n**Author{s}**: {humanize_list(self.__authors__)}"
            f"\n**Cog version**: {self.__version__}"
            f"\n**Cog commit**: `{self.__commit__}`"
            f"\n**Repo name**: {self.__repo_name__}"
            f"\n**Utils version**: {self.__utils_version__}"
        )
        if self.qualified_name not in ("AAA3A_utils"):
            text += (
                "\n**Cog documentation**:"
                f" https://aaa3a-cogs.readthedocs.io/en/latest/cog_{self.qualified_name.lower()}.html\n**Translate"
                " my cogs**: https://crowdin.com/project/aaa3a-cogs"
            )
        return text

    async def red_delete_data_for_user(self, *args, **kwargs) -> None:
        """Nothing to delete."""
        return

    async def red_get_data_for_user(self, *args, **kwargs) -> typing.Dict[str, typing.Any]:
        """Nothing to get."""
        return {}

    async def cog_before_invoke(self, ctx: commands.Context) -> Context:
        if isinstance(ctx.command, commands.Group):
            view = ctx.view
            previous = view.index
            view.skip_ws()
            trigger = view.get_word()
            invoked_subcommand = ctx.command.all_commands.get(trigger, None)
            view.index = previous
            if invoked_subcommand is not None or not ctx.command.invoke_without_command:
                return
        context: commands.Context = await Context.from_context(ctx)
        if getattr(ctx.command, "__is_dev__", False):
            await unsupported(ctx)
        if context.interaction is None:
            for index, arg in enumerate(ctx.args.copy()):
                if isinstance(arg, commands.Context):
                    ctx.args[index] = context
        else:
            if context.command.__commands_is_hybrid__ and hasattr(context.command, "app_command"):
                __do_call = getattr(context.command.app_command, "_do_call")

                async def _do_call(interaction, params):
                    await __do_call(interaction=context, params=params)

                setattr(context.command.app_command, "_do_call", _do_call)
            try:
                await context.interaction.response.defer(ephemeral=False, thinking=True)
            except (discord.InteractionResponded, discord.NotFound):
                pass
        # Typing automatically.
        if (
            ctx.cog.qualified_name not in ("CmdChannel", "Sudo")
            and (
                not (isinstance(getattr(ctx.cog, "settings", None), Settings))
                or ctx.command not in ctx.cog.settings.commands.values()
            )
            and ctx.command.qualified_name != "devutils stoptyping"
        ):
            context._typing = context.channel.typing()
            try:
                await context._typing.__aenter__()
            except discord.InteractionResponded:
                pass
        return context

    async def cog_after_invoke(self, ctx: commands.Context) -> Context:
        if isinstance(ctx.command, commands.Group) and (
            ctx.invoked_subcommand is not None or not ctx.command.invoke_without_command
        ):
            return
        context: commands.Context = await Context.from_context(ctx)
        if (
            hasattr(context, "_typing")
            and hasattr(context._typing, "task")
            and hasattr(context._typing.task, "cancel")
        ):
            context._typing.task.cancel()
        if context.command_failed:
            await context.tick(reaction="❌")
        elif getattr(
            ctx.cog, "qualified_name", None
        ) != "Dev" or ctx.command.qualified_name not in ("eval", "debug", "eshell"):
            await context.tick()
        # from .menus import Menu
        # await Menu(pages=str("\n".join([str((x.function, x.frame)) for x in __import__("inspect").stack(30)])), lang="py").start(context)
        return context

    async def cog_command_error(self, ctx: commands.Context, error: Exception) -> None:
        AAA3A_utils = ctx.bot.get_cog("AAA3A_utils")
        is_command_error = isinstance(
            error, (commands.CommandInvokeError, commands.HybridCommandError)
        )
        if is_command_error and isinstance(
            error.original, discord.Forbidden
        ):  # Error can be changed into `commands.BotMissingPermissions` or not.
            e = verbose_forbidden_exception(ctx, error.original)
            if e is not None and isinstance(e, commands.BotMissingPermissions):
                error = e
                is_command_error = False

        if is_command_error:
            uuid = uuid4().hex
            no_sentry = AAA3A_utils is None or getattr(AAA3A_utils, "sentry", None) is None
            if not no_sentry:
                AAA3A_utils.sentry.last_errors[uuid] = {"ctx": ctx, "error": error}
            if isinstance(ctx.command, discord.ext.commands.HybridCommand):
                _type = "[hybrid|text]" if ctx.interaction is None else "[hybrid|slash]"
            elif ctx.interaction is not None:
                _type = "[slash]"
            else:
                _type = "[text]"
            message = await ctx.bot._config.invoke_error_msg()
            if not message:
                message = f"Error in {_type} command '{ctx.command.qualified_name}'."
                if ctx.author.id in ctx.bot.owner_ids:
                    message += (
                        " Check your console or logs for details. If necessary, please inform the"
                        " creator of the cog in which this command is located. Thank you."
                    )
                message = inline(message)
            else:
                message = message.replace("{command}", ctx.command.qualified_name)
            if (
                not no_sentry
                and getattr(AAA3A_utils.sentry, "display_sentry_manual_command", True)
                and await AAA3A_utils.senderrorwithsentry.can_run(ctx)
                and not getattr(AAA3A_utils.senderrorwithsentry, "__is_dev__", False)
            ):
                message += "\n" + inline(
                    "You can send this error to the developer by running the following"
                    f" command:\n{ctx.prefix}AAA3A_utils senderrorwithsentry {uuid}"
                )
            await ctx.send(message)
            asyncio.create_task(ctx.bot._delete_delay(ctx))
            self.logger.exception(
                f"Exception in {_type} command '{ctx.command.qualified_name}'.",
                exc_info=error.original,
            )
            exception_log = f"Exception in {_type} command '{ctx.command.qualified_name}':\n"
            exception_log += "".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            )
            exception_log = CogsUtils.replace_var_paths(exception_log)
            ctx.bot._last_exception = exception_log
            if not no_sentry:
                await AAA3A_utils.sentry.send_command_error(ctx, error)
        elif isinstance(error, commands.UserFeedbackCheckFailure):
            if error.message:
                message = error.message
                message = warning(message)
                await ctx.send(
                    message,
                    delete_after=3 if "delete_after" in error.args else None,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
        elif isinstance(error, commands.CheckFailure) and not isinstance(
            error, commands.BotMissingPermissions
        ):
            if ctx.interaction is not None:
                await ctx.send(
                    inline("You are not allowed to execute this command in this context."),
                    ephemeral=True,
                )
        else:
            await ctx.bot.on_command_error(ctx, error=error, unhandled_by_cog=True)


def verbose_forbidden_exception(
    ctx: commands.Context, error: discord.Forbidden
) -> commands.BotMissingPermissions:  # A little useless now.
    if not isinstance(error, discord.Forbidden):
        return ValueError(error)
    method = error.response.request_info.method
    url = str(error.response.request_info.url)
    url = url[len(discord.http.Route.BASE) :]
    url = url.split("?")[0]
    url = re.sub(r"\b\d{17,20}\b", "{snowflake}", url)
    key = f"{method.upper()} {url}"
    end_points = {
        "GET /guilds/{guild.id}/audit-logs": ["VIEW_AUDIT_LOG"],
        "GET /guilds/{guild.id}/auto-moderation/rules": ["MANAGE_GUILD"],
        "GET /guilds/{guild.id}/auto-moderation/rules/{auto_moderation_rule.id}": ["MANAGE_GUILD"],
        "POST /guilds/{guild.id}/auto-moderation/rules": ["MANAGE_GUILD"],
        "PATCH /guilds/{guild.id}/auto-moderation/rules/{auto_moderation_rule.id}": [
            "MANAGE_GUILD"
        ],
        "DELETE /guilds/{guild.id}/auto-moderation/rules/{auto_moderation_rule.id}": [
            "MANAGE_GUILD"
        ],
        "PATCH /channels/{channel.id}": ["MANAGE_CHANNELS"],  # &! MANAGE_THREADS
        "DELETE /channels/{channel.id}": ["MANAGE_CHANNELS"],  # &! MANAGE_THREADS
        "GET /channels/{channel.id}/messages": [
            "VIEW_CHANNEL",
            "READ_MESSAGE_HISTORY",
        ],  # empty messages list
        "GET /channels/{channel.id}/messages/{message.id}": [
            "VIEW_CHANNEL",
            "READ_MESSAGE_HISTORY",
        ],
        "POST /channels/{channel.id}/messages": [
            "VIEW_CHANNEL",
            "SEND_MESSAGES",
        ],  # [SEND_TTS_MESSAGES (tts), READ_MESSAGE_HISTORY (reply)]
        "POST /channels/{channel.id}/messages/{message.id}/crosspost": [
            "MANAGE_MESSAGES"
        ],  # not own message
        "PUT /channels/{channel.id}/messages/{message.id}/reactions/{emoji}/@me": [
            "ADD_REACTIONS"
        ],
        "DELETE /channels/{channel.id}/messages/{message.id}/reactions/{emoji}/@me": [],
        "DELETE /channels/{channel.id}/messages/{message.id}/reactions/{emoji}/{user.id}": [
            "MANAGE_MESSAGES"
        ],
        "GET /channels/{channel.id}/messages/{message.id}/reactions/{emoji}": [],
        "DELETE /channels/{channel.id}/messages/{message.id}/reactions": ["MANAGE_MESSAGES"],
        "DELETE /channels/{channel.id}/messages/{message.id}/reactions/{emoji}": [
            "MANAGE_MESSAGES"
        ],
        "PATCH /channels/{channel.id}/messages/{message.id}": [],
        "DELETE /channels/{channel.id}/messages/{message.id}": ["MANAGE_MESSAGES"],
        "POST /channels/{channel.id}/messages/bulk-delete": [
            "VIEW_CHANNEL",
            "READ_MESSAGE_HISTORY",
            "MANAGE_MESSAGES",
        ],
        "PUT /channels/{channel.id}/permissions/{overwrite.id}": ["MANAGE_ROLES"],
        "GET /channels/{channel.id}/invites": ["MANAGE_CHANNELS"],
        "POST /channels/{channel.id}/invites": ["CREATE_INSTANT_INVITE"],
        "DELETE /channels/{channel.id}/permissions/{overwrite.id}": ["MANAGE_ROLES"],
        "POST /channels/{channel.id}/followers": ["MANAGE_WEBHOOKS"],
        "POST /channels/{channel.id}/typing": ["VIEW_CHANNEL", "SEND_MESSAGES"],
        "GET /channels/{channel.id}/pins": ["VIEW_CHANNEL", "VIEW_MESSAGE_HISTORY"],
        "PUT /channels/{channel.id}/pins/{message.id}": ["MANAGE_MESSAGES"],
        "DELETE /channels/{channel.id}/pins/{message.id}": ["MANAGE_MESSAGES"],
        "POST /channels/{channel.id}/messages/{message.id}/threads": ["CREATE_PUBLIC_THREADS"],
        "POST /channels/{channel.id}/threads": [
            "CREATE_PUBLIC_THREADS",
            "CREATE_PRIVATE_THREADS",
            "SEND_MESSAGES",
        ],
        "PUT /channels/{channel.id}/thread-members/@me": [],
        "DELETE /channels/{channel.id}/thread-members/@me": [],
        "DELETE /channels/{channel.id}/thread-members/{user.id}": ["MANAGE_THREADS"],
        "GET /channels/{channel.id}/thread-members/{user.id}": [],
        "GET /channels/{channel.id}/thread-members": [],
        "GET /channels/{channel.id}/threads/archived/public": [
            "VIEW_CHANNEl",
            "READ_MESSAGE_HISTORY",
        ],
        "GET /channels/{channel.id}/threads/archived/private": [
            "VIEW_CHANNEL",
            "READ_MESSAGE_HISTORY",
            "MANAGE_THREADS",
        ],
        "GET /channels/{channel.id}/users/@me/threads/archived/private": [
            "VIEW_CHANNEL",
            "READ_MESSAGE_HISTORY",
        ],
        "GET /guilds/{guild.id}/emojis": [],
        "GET /guilds/{guild.id}/emojis/{emoji.id}": [],
        "POST /guilds/{guild.id}/emojis": ["MANAGE_EMOJIS_AND_STICKERS"],
        "PATCH /guilds/{guild.id}/emojis/{emoji.id}": ["MANAGE_EMOJIS_AND_STICKERS"],
        "DELETE /guilds/{guild.id}/emojis/{emoji.id}": ["MANAGE_EMOJIS_AND_STICKERS"],
        "GET /guilds/{guild.id}/preview": [],
        "PATCH /guilds/{guild.id}": ["MANAGE_GUILD"],
        "DELETE /guilds/{guild.id}": [],
        "GET /guilds/{guild.id}/channels": [],
        "POST /guilds/{guild.id}/channels": ["MANAGE_CHANNELS"],
        "PATCH /guilds/{guild.id}/channels": ["MANAGE_CHANNELS"],
        "GET /guilds/{guild.id}/threads/active": [],
        "GET /guilds/{guild.id}/members/{user.id}": [],
        "GET /guilds/{guild.id}/members": [],
        "GET /guilds/{guild.id}/members/search": [],
        "PUT /guilds/{guild.id}/members/{user.id}": [],
        "PATCH /guilds/{guild.id}/members/{user.id}": ["MANAGE_MEMBERS", "MOVE_MEMBERS"],
        "PATCH /guilds/{guild.id}/members/@me": [],
        "PUT /guilds/{guild.id}/members/{user.id}/roles/{role.id}": ["MANAGE_ROLES"],
        "DELETE /guilds/{guild.id}/members/{user.id}/roles/{role.id}": ["MANAGE_ROLES"],
        "DELETE /guilds/{guild.id}/members/{user.id}": ["KICK_MEMBERS"],
        "GET /guilds/{guild.id}/bans": ["BAN_MEMBERS"],
        "GET /guilds/{guild.id}/bans/{user.id}": ["BAN_MEMBERS"],
        "PUT /guilds/{guild.id}/bans/{user.id}": ["BAN_MEMBERS"],
        "DELETE /guilds/{guild.id}/bans/{user.id}": ["BAN_MEMBERS"],
        "GET /guilds/{guild.id}/roles": [],
        "POST /guilds/{guild.id}/roles": ["MANAGE_ROLES"],
        "PATCH /guilds/{guild.id}/roles": ["MANAGE_ROLES"],
        "PATCH /guilds/{guild.id}/roles/{role.id}": ["MANAGE_ROLES"],
        "POST /guilds/{guild.id}/mfa": ["MANAGE_GUILD"],
        "DELETE /guilds/{guild.id}/roles/{role.id}": ["MANAGE_ROLES"],
        "GET /guilds/{guild.id}/prune": ["KICK_MEMBERS"],
        "POST /guilds/{guild.id}/prune": ["KICK_MEMBERS"],
        "GET /guilds/{guild.id}/regions": [],
        "GET /guilds/{guild.id}/invites": ["MANAGE_GUILD"],
        "GET /guilds/{guild.id}/integrations": ["MANAGE_GUILD"],
        "DELETE /guilds/{guild.id}/integrations/{integration.id}": ["MANAGE_GUILD"],
        "GET /guilds/{guild.id}/widget": ["MANAGE_GUILD"],
        "PATCH /guilds/{guild.id}/widget": ["MANAGE_GUILD"],
        "GET /guilds/{guild.id}/widget.json": [],
        "GET /guilds/{guild.id}/vanity-url": ["MANAGE_GUILD"],
        "GET /guilds/{guild.id}/widget.png": [],
        "GET /guilds/{guild.id}/welcome-screen": ["MANAGE_GUILD"],
        "PATCH /guilds/{guild.id}/welcome-screen": ["MANAGE_GUILD"],
        "PATCH /guilds/{guild.id}/voice-states/@me": ["MUTE_MEMBERS", "REQUEST_TO_SPEAK"],
        "PATCH /guilds/{guild.id}/voice-states/{user.id}": ["MUTE_MEMBERS"],
        "GET /guilds/{guild.id}/scheduled-events": [],
        "POST /guilds/{guild.id}/scheduled-events": ["MANAGE_EVENTS"],
        "GET /guilds/{guild.id}/scheduled-events/{guild_scheduled_event.id}": [],
        "PATCH /guilds/{guild.id}/scheduled-events/{guild_scheduled_event.id}": ["MANAGE_EVENTS"],
        "DELETE /guilds/{guild.id}/scheduled-events/{guild_scheduled_event.id}": ["MANAGE_EVENTS"],
        "GET /guilds/{guild.id}/scheduled-events/{guild_scheduled_event.id}/users": [],
        "GET /guilds/templates/{template.code}": [],
        "POST /guilds/templates/{template.code}": [],
        "GET /guilds/{guild.id}/templates": ["MANAGE_GUILD"],
        "POST /guilds/{guild.id}/templates": ["MANAGE_GUILD"],
        "PUT /guilds/{guild.id}/templates/{template.code}": ["MANAGE_GUILD"],
        "PATCH /guilds/{guild.id}/templates/{template.code}": ["MANAGE_GUILD"],
        "DELETE /guilds/{guild.id}/templates/{template.code}": ["MANAGE_GUILD"],
        "GET /invites/{invite.code}": [],
        "DELETE /invites/{invite.code}": ["MANAGE_CHANNELS"],
        "POST /stage-instances": ["MANAGE_CHANNELS"],
        "GET /stage-instances/{channel.id}": [],
        "PATCH /stage-instances/{channel.id}": ["MANAGE_CHANNELS"],
        "DELETE /stage-instances/{channel.id}": ["MANAGE_CHANNELS"],
        "GET /stickers/{sticker.id}": [],
        "GET /sticker-packs": [],
        "GET /guilds/{guild.id}/stickers": ["MANAGE_EMOJIS_AND_STICKERS"],
        "GET /guilds/{guild.id}/stickers/{sticker.id}": ["MANAGE_EMOJIS_AND_STICKERS"],
        "POST /guilds/{guild.id}/stickers": ["MANAGE_EMOJIS_AND_STICKERS"],
        "PATCH /guilds/{guild.id}/stickers/{sticker.id}": ["MANAGE_EMOJIS_AND_STICKERS"],
        "DELETE/guilds/{guild.id}/stickers/{sticker.id}": ["MANAGE_EMOJIS_AND_STICKERS"],
        "GET /users/@me": [],
        "GET /users/{user.id}": [],
        "PATCH /users/@me": [],
        "GET /users/@me/guilds": [],
        "GET /users/@me/guilds/{guild.id}/member": [],
        "DELETE /users/@me/guilds/{guild.id}": [],
        "POST /users/@me/channels": [],
        "GET /users/@me/connections": [],
        "GET /users/@me/applications/{application.id}/role-connection": [],
        "PUT /users/@me/applications/{application.id}/role-connection": [],
        "GET /voice/regions": [],
        "POST /channels/{channel.id}/webhooks": ["MANAGE_WEBHOOKS"],
        "GET /channels/{channel.id}/webhooks": ["MANAGE_WEBHOOKS"],
        "GET /guilds/{guild.id}/webhooks": ["MANAGE_WEBHOOKS"],
        "GET /webhooks/{webhook.id}": [],
        "GET /webhooks/{webhook.id}/{webhook.token}": [],
        "PATCH /webhooks/{webhook.id}": ["MANAGE_WEBHOOKS"],
        "PATCH /webhooks/{webhook.id}/{webhook.token}": ["MANAGE_WEBHOOKS"],
        "DELETE /webhooks/{webhook.id}": ["MANAGE_WEBHOOKS"],
        "DELETE /webhooks/{webhook.id}/{webhook.token}": ["MANAGE_WEBHOOKS"],
        "POST /webhooks/{webhook.id}/{webhook.token}": [],
        "POST /webhooks/{webhook.id}/{webhook.token}/slack": [],
        "POST /webhooks/{webhook.id}/{webhook.token}/github": [],
        "GET /webhooks/{webhook.id}/{webhook.token}/messages/{message.id}": [],
        "PATCH /webhooks/{webhook.id}/{webhook.token}/messages/{message.id}": [],
        "DELETE /webhooks/{webhook.id}/{webhook.token}/messages/{message.id}": [],
    }

    class FakeObject:
        id: str = "{snowflake}"
        token: str = "{snowflake}"
        code: str = "{snowflake}"

        def __str__(self):
            return "{snowflake}"

    class FakeDict(dict):
        def __getitem__(self, *args, **kwargs):
            return FakeObject()

    end_points = {_key.format_map(FakeDict()): _value for _key, _value in end_points.items()}
    if key not in end_points:
        return None
    _permissions = end_points[key]
    permissions = {}
    for permission in _permissions:
        if permission.lower() not in discord.Permissions.VALID_FLAGS:
            continue
        if getattr(ctx.bot_permissions, permission.lower()):
            continue
        permissions[permission.lower()] = True
    return (
        commands.BotMissingPermissions(discord.Permissions(**permissions)) if permissions else None
    )
