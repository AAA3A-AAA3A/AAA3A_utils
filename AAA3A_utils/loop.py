from redbot.core import commands  # isort:skip
import discord  # isort:skip
import typing  # isort:skip

# import typing_extensions  # isort:skip

import asyncio
import datetime
import inspect
import math
import time
import traceback
from io import StringIO

from redbot.core.utils.chat_formatting import box, pagify
from rich.console import Console
from rich.table import Table

from .cogsutils import CogsUtils

__all__ = ["Loop"]


def _(untranslated: str) -> str:
    return untranslated


def no_colour_rich_markup(
    *objects: typing.Any, lang: str = "", no_box: typing.Optional[bool] = False
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


class Loop:
    """
    Create a loop, with many features.
    Thanks to Vexed01 on GitHub! (https://github.com/Vexed01/Vex-Cogs/blob/master/timechannel/loop.py and https://github.com/Vexed01/vex-cog-utils/vexutils/loop.py)
    """

    def __init__(
        self,
        cog: commands.Cog,
        name: str,
        function: typing.Callable,
        days: typing.Optional[int] = 0,
        hours: typing.Optional[int] = 0,
        minutes: typing.Optional[int] = 0,
        seconds: typing.Optional[int] = 0,
        function_kwargs: typing.Optional[typing.Dict[str, typing.Any]] = None,
        wait_raw: typing.Optional[bool] = False,
        limit_count: typing.Optional[int] = None,
        limit_date: typing.Optional[datetime.datetime] = None,
        limit_exception: typing.Optional[int] = None,
        start_now: typing.Optional[bool] = True,
    ) -> None:
        if function_kwargs is None:
            function_kwargs = {}
        self.cog: commands.Cog = cog

        self.name: str = name
        self.function: typing.Callable = function
        self.function_kwargs: typing.Dict[str, typing.Any] = function_kwargs
        self.interval: float = datetime.timedelta(
            days=days, hours=hours, minutes=minutes, seconds=seconds
        ).total_seconds()
        self.wait_raw: bool = wait_raw
        self.limit_count: int = limit_count
        self.limit_date: datetime.datetime = limit_date
        self.limit_exception: int = limit_exception
        self.stop_manually: bool = False

        self.start_datetime: datetime.datetime = datetime.datetime.now(tz=datetime.timezone.utc)
        self.expected_interval = datetime.timedelta(seconds=self.interval)
        self.last_iteration: typing.Optional[datetime.datetime] = None
        self.next_iteration: typing.Optional[datetime.datetime] = None
        self.currently_running: bool = False  # whether the function is running
        self.iteration_count: int = 0
        self.last_result: typing.Optional[typing.Any] = None
        self.iteration_exception: int = 0
        self.last_exc: str = "No exception has occurred yet."
        self.last_exc_raw: typing.Optional[BaseException] = None
        self.stop: bool = False

        self.task: typing.Optional[asyncio.Task] = None
        if start_now:
            self.start()

    def start(self) -> typing.Any:  # typing_extensions.Self
        self.task = self.cog.bot.loop.create_task(self.loop())
        return self

    async def wait_until_iteration(self) -> None:
        """Sleep during the raw interval."""
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        time = now.timestamp()
        time = math.ceil(time / self.interval) * self.interval
        next_iteration = datetime.datetime.fromtimestamp(time, tz=datetime.timezone.utc) - now
        seconds_to_sleep = (next_iteration).total_seconds()
        if self.interval > 60 and hasattr(self.cog, "logger"):
            self.cog.logger.verbose(
                f"Sleeping for {seconds_to_sleep} seconds until {self.name} loop next iteration"
                f" ({self.iteration_count + 1})..."
            )
        await asyncio.sleep(seconds_to_sleep)

    async def loop(self) -> None:
        await self.cog.bot.wait_until_red_ready()
        await asyncio.sleep(1)
        if hasattr(self.cog, "logger"):
            self.cog.logger.debug(f"{self.name} loop has started.")
        while True:
            await self.execute()
            if self.maybe_stop():
                return
            if not self.wait_raw:
                # both iteration_finish and iteration_error set next_iteration as not None
                assert self.next_iteration is not None
                if float(self.interval) % float(3600) == 0:
                    self.next_iteration = self.next_iteration.replace(
                        minute=0, second=0, microsecond=0
                    )  # ensure further iterations are on the hour
                elif float(self.interval) % float(60) == 0:
                    self.next_iteration = self.next_iteration.replace(
                        second=0, microsecond=0
                    )  # ensure further iterations are on the minute
                else:
                    self.next_iteration = self.next_iteration.replace(
                        microsecond=0
                    )  # ensure further iterations are on the second
                if self.interval != 0:
                    await self.wait_until_iteration()
            else:
                await self.sleep_until_next()

    async def execute(self) -> None:
        try:
            start = time.monotonic()
            self.iteration_start()
            self.last_result: typing.Any = await self.function(**self.function_kwargs)
            self.iteration_finish()
            end = time.monotonic()
            total = round(end - start, 1)
            if hasattr(self.cog, "logger"):
                if self.iteration_count == 1:
                    self.cog.logger.verbose(
                        f"{self.name} initial iteration finished in {total}s"
                        f" ({self.iteration_count})."
                    )
                elif self.interval > 60:
                    self.cog.logger.verbose(
                        f"{self.name} iteration finished in {total}s ({self.iteration_count})."
                    )
        except Exception as e:
            if hasattr(self.cog, "logger"):
                if self.iteration_count == 1:
                    self.cog.logger.exception(
                        (
                            f"Something went wrong in the {self.name} loop"
                            f" ({self.iteration_count})."
                        ),
                        exc_info=e,
                    )
                else:
                    self.cog.logger.exception(
                        (
                            f"Something went wrong in the {self.name} loop iteration"
                            f" ({self.iteration_count})."
                        ),
                        exc_info=e,
                    )
            self.iteration_error(e)

    def maybe_stop(self) -> bool:
        if self.stop:
            return True
        if self.stop_manually:
            self.stop_all()
            return True
        if self.limit_count is not None and self.iteration_count >= self.limit_count:
            self.stop_all()
            return True
        if self.limit_date is not None and datetime.datetime.timestamp(
            datetime.datetime.now()
        ) >= datetime.datetime.timestamp(self.limit_date):
            self.stop_all()
            return True
        if self.limit_exception is not None and self.iteration_exception >= self.limit_exception:
            self.stop_all()
            return True
        return False

    def stop_all(self) -> typing.Any:  # typing_extensions.Self
        self.stop = True
        self.next_iteration = None
        self.task.cancel()
        # if self.loops.get(self.name) == self:
        #     del self.cog.loops[self.cog.loops.index(self)]
        if hasattr(self.cog, "logger"):
            self.cog.logger.debug(
                f"{self.name} loop has been stopped after {self.iteration_count} iteration(s)."
            )
        return self

    def __repr__(self) -> str:
        return (
            f"<friendly_name={self.name!r} iteration_count={self.iteration_count} "
            f"currently_running={self.currently_running} last_iteration={self.last_iteration!r} "
            f"next_iteration={self.next_iteration!r} integrity={self.integrity}>"
        )

    @property
    def integrity(self) -> bool:
        """
        If the loop is running on time (whether or not next expected iteration is in the future)
        """
        if self.next_iteration is None:  # not started yet
            return False
        return self.next_iteration > datetime.datetime.now(tz=datetime.timezone.utc)

    @property
    def until_next(self) -> float:
        """
        Positive float with the seconds until the next iteration, based off the last
        iteration and the interval.
        If the expected time of the next iteration is in the past, this will return `0.0`
        """
        if self.next_iteration is None:  # not started yet
            return 0.0

        raw_until_next = (
            self.next_iteration - datetime.datetime.now(tz=datetime.timezone.utc)
        ).total_seconds()
        if raw_until_next > self.expected_interval.total_seconds():  # should never happen
            return self.expected_interval.total_seconds()
        elif raw_until_next > 0.0:
            return raw_until_next
        else:
            return 0.0

    async def sleep_until_next(self) -> None:
        """Sleep until the next iteration. Basically an "all-in-one" version of `until_next`."""
        await asyncio.sleep(self.until_next)

    def iteration_start(self) -> None:
        """Register an iteration as starting."""
        self.iteration_count += 1
        self.currently_running = True
        self.last_iteration = datetime.datetime.now(tz=datetime.timezone.utc)
        self.next_iteration = datetime.datetime.now(tz=datetime.timezone.utc) + self.expected_interval
        # this isn't accurate, it will be "corrected" when finishing is called

    def iteration_finish(self) -> None:
        """Register an iteration as finished successfully."""
        self.currently_running = False
        # now this is accurate. imo its better to have something than nothing

    def iteration_error(self, error: BaseException) -> None:
        """Register an iteration's error."""
        self.currently_running = False
        self.last_exc_raw = error
        self.last_exc = "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )

    def get_debug_embed(self) -> discord.Embed:
        """Get an embed with many infomations on this loop."""
        now: datetime.datetime = datetime.datetime.now(tz=datetime.timezone.utc)

        raw_table = Table("Key", "Value")
        raw_table.add_row("expected_interval", str(self.expected_interval))
        raw_table.add_row("iteration_count", str(self.iteration_count))
        raw_table.add_row("currently_running", str(self.currently_running))
        raw_table.add_row("last_iteration", str(self.last_iteration))
        raw_table.add_row("next_iteration", str(self.next_iteration))
        raw_table.add_row("wait_raw", str(self.wait_raw))
        raw_table_str = no_colour_rich_markup(raw_table, lang="py")

        if self.next_iteration is not None and self.last_iteration is not None:
            processed_table = Table("Key", "Value")
            processed_table.add_row(
                "Seconds until next", str((self.next_iteration - now).total_seconds())
            )
            processed_table.add_row(
                "Seconds since last", str((now - self.last_iteration).total_seconds())
            )
            processed_table.add_row(
                "Raw interval",
                str(
                    (self.next_iteration - now).total_seconds()
                    + (now - self.last_iteration).total_seconds()
                ),
            )
            processed_table_str = no_colour_rich_markup(processed_table, lang="py")
        elif self.iteration_count:
            processed_table_str = "Loop isn't running."
        else:
            processed_table_str = "Loop hasn't started yet."

        datetime_table = Table("Key", "Value")
        datetime_table.add_row("Start DateTime", str(self.start_datetime))
        datetime_table.add_row("Now DateTime", str(now))
        datetime_table.add_row(
            "Runtime",
            (
                str(now - self.start_datetime)
                + "\n"
                + str((now - self.start_datetime).total_seconds())
                + "s"
            ),
        )
        datetime_table_str = no_colour_rich_markup(datetime_table, lang="py")

        function_table = Table("Key", "Value")
        function_table.add_row(
            "Function", repr(getattr(self.function, "__func__", self.function))[:-23] + ">"
        )
        function_table.add_row("Function parameters", repr(inspect.signature(self.function)))
        function_table.add_row("Function kwargs", repr(self.function_kwargs))
        function_table_str = no_colour_rich_markup(function_table, lang="py")

        stopping_table = Table("Key", "Value")
        stopping_table.add_row("Limit Count", str(self.limit_count))
        stopping_table.add_row("Limit Date", str(self.limit_date))
        stopping_table.add_row("Limit Exception", str(self.limit_exception))
        stopping_table_str = no_colour_rich_markup(stopping_table, lang="py")

        emoji = "✅" if self.integrity else "❌"
        embed: discord.Embed = discord.Embed(
            title=f"{self.name} Loop: `{emoji}`",
            color=discord.Color.green() if self.integrity else discord.Color.red(),
            timestamp=now,
        )
        embed.add_field(name="Raw data:", value=raw_table_str, inline=False)
        embed.add_field(
            name="Processed data:",
            value=processed_table_str,
            inline=False,
        )
        embed.add_field(
            name="DateTime data:",
            value=datetime_table_str,
            inline=False,
        )
        embed.add_field(
            name="Function data:",
            value=function_table_str,
            inline=False,
        )
        embed.add_field(
            name="Stopping data:",
            value=stopping_table_str,
            inline=False,
        )
        exc = self.last_exc
        exc = CogsUtils.replace_var_paths(exc)
        if len(exc) > 1024:
            exc = list(pagify(exc, page_length=1024))[0] + "\n..."
        embed.add_field(name="Exception:", value=box(exc), inline=False)

        return embed
