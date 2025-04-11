from redbot.core import commands  # isort:skip
import discord  # isort:skip
import typing  # isort:skip

import asyncio
import datetime
import inspect
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
    Slimmed down version of rich_markup which ensures no colours (/ANSI) can exist.
    """
    temp_console = Console(
        color_system=None,
        file=StringIO(),
        force_terminal=True,
        width=80,
    )
    temp_console.print(*objects)
    content = temp_console.file.getvalue()
    return content if no_box else box(content, lang=lang)  # type: ignore


class Loop:
    """
    Create a loop with many features.
    Thanks to Vexed01 on GitHub!
    """

    def __init__(
        self,
        cog: commands.Cog,
        name: str,
        function: typing.Callable,
        days: int = 0,
        hours: int = 0,
        minutes: int = 0,
        seconds: int = 0,
        function_kwargs: typing.Optional[typing.Dict[str, typing.Any]] = None,
        wait_raw: bool = False,
        limit_count: typing.Optional[int] = None,
        limit_date: typing.Optional[datetime.datetime] = None,
        limit_exception: typing.Optional[int] = None,
        start_now: bool = True,
    ) -> None:
        self.cog = cog
        self.name = name
        self.function = function
        self.function_kwargs = function_kwargs or {}
        self.interval = datetime.timedelta(
            days=days, hours=hours, minutes=minutes, seconds=seconds
        ).total_seconds()
        self.wait_raw = wait_raw
        self.limit_count = limit_count
        self.limit_date = limit_date
        self.limit_exception = limit_exception
        self.stop_manually = False

        self.start_datetime = datetime.datetime.now(tz=datetime.timezone.utc)
        self.expected_interval = datetime.timedelta(seconds=self.interval)
        self.last_iteration = None
        self.next_iteration = None
        self.currently_running = False
        self.iteration_count = 0
        self.last_result = None
        self.last_iteration_duration = None
        self.iteration_exception = 0
        self.last_exc = "No exception has occurred yet."
        self.last_exc_raw = None
        self.stop = False

        self.task = None
        if start_now:
            self.start()

    def start(self) -> "Loop":
        self.task = self.cog.bot.loop.create_task(self.loop())
        return self

    @property
    def integrity(self) -> bool:
        """Check if the loop is running on time."""
        return self.next_iteration and self.next_iteration > datetime.datetime.now(tz=datetime.timezone.utc)

    @property
    def until_next(self) -> float:
        """Calculate seconds until the next iteration."""
        if not self.next_iteration:
            return 0.0
        raw_until_next = (
            self.next_iteration - datetime.datetime.now(tz=datetime.timezone.utc)
        ).total_seconds()
        return max(0.0, min(raw_until_next, self.expected_interval.total_seconds()))

    async def wait_until_iteration(self) -> None:
        """Sleep until the next iteration."""
        seconds_to_sleep = self.until_next
        if seconds_to_sleep > 0:
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
                self.adjust_next_iteration()
            await self.wait_until_iteration()

    async def execute(self) -> None:
        try:
            start = time.monotonic()
            self.iteration_start()
            self.last_result = await self.function(**self.function_kwargs)
            self.iteration_finish()
            self.log_iteration_time(start)
        except Exception as e:
            self.handle_iteration_error(e)

    def maybe_stop(self) -> bool:
        """Check if the loop should stop."""
        if self.stop or self.stop_manually:
            self.stop_all()
            return True
        if self.limit_count and self.iteration_count >= self.limit_count:
            self.stop_all()
            return True
        if self.limit_date and datetime.datetime.now(tz=datetime.timezone.utc) >= self.limit_date:
            self.stop_all()
            return True
        if self.limit_exception and self.iteration_exception >= self.limit_exception:
            self.stop_all()
            return True
        return False

    def stop_all(self) -> "Loop":
        """Stop the loop."""
        self.stop = True
        self.next_iteration = None
        if self.task:
            self.task.cancel()
        if hasattr(self.cog, "logger"):
            self.cog.logger.debug(
                f"{self.name} loop has been stopped after {self.iteration_count} iteration(s)."
            )
        return self

    def adjust_next_iteration(self) -> None:
        """Adjust the next iteration time for alignment."""
        if not self.next_iteration:
            return
        if self.interval % 3600 == 0:
            self.next_iteration = self.next_iteration.replace(minute=0, second=0, microsecond=0)
        elif self.interval % 60 == 0:
            self.next_iteration = self.next_iteration.replace(second=0, microsecond=0)
        else:
            self.next_iteration = self.next_iteration.replace(microsecond=0)

    def log_iteration_time(self, start: float) -> None:
        """Log the time taken for an iteration."""
        end = time.monotonic()
        total = round(end - start, 1)
        self.last_iteration_duration = total
        if hasattr(self.cog, "logger"):
            if self.iteration_count == 1:
                self.cog.logger.verbose(
                    f"{self.name} initial iteration finished in {total}s ({self.iteration_count})."
                )
            elif self.interval > 60:
                self.cog.logger.verbose(
                    f"{self.name} iteration finished in {total}s ({self.iteration_count})."
                )

    def handle_iteration_error(self, error: BaseException) -> None:
        """Handle errors during an iteration."""
        if hasattr(self.cog, "logger"):
            self.cog.logger.exception(
                f"Error in {self.name} loop iteration ({self.iteration_count}).", exc_info=error
            )
        self.iteration_error(error)

    def __repr__(self) -> str:
        return (
            f"<friendly_name={self.name!r} iteration_count={self.iteration_count} "
            f"currently_running={self.currently_running} last_iteration={self.last_iteration!r} "
            f"next_iteration={self.next_iteration!r} integrity={self.integrity}>"
        )

    def iteration_start(self) -> None:
        """Register an iteration as starting."""
        self.iteration_count += 1
        self.currently_running = True
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        self.last_iteration = now
        self.next_iteration = now + self.expected_interval

    def iteration_finish(self) -> None:
        """Register an iteration as finished successfully."""
        self.currently_running = False

    def iteration_error(self, error: BaseException) -> None:
        """Register an iteration's error."""
        self.currently_running = False
        self.last_exc_raw = error
        self.last_exc = "".join(traceback.format_exception(type(error), error, error.__traceback__))

    def get_debug_embed(self) -> discord.Embed:
        """Get an embed with detailed information about this loop."""
        now = datetime.datetime.now(tz=datetime.timezone.utc)

        def create_table(data: typing.List[typing.Tuple[str, str]]) -> str:
            table = Table("Key", "Value")
            for key, value in data:
                table.add_row(key, value)
            return no_colour_rich_markup(table, lang="py")

        raw_data = [
            ("expected_interval", str(self.expected_interval)),
            ("iteration_count", str(self.iteration_count)),
            ("currently_running", str(self.currently_running)),
            ("last_iteration", str(self.last_iteration)),
            ("next_iteration", str(self.next_iteration)),
            ("wait_raw", str(self.wait_raw)),
        ]
        datetime_data = [
            ("Start DateTime", str(self.start_datetime)),
            ("Now DateTime", str(now)),
            ("Runtime", f"{now - self.start_datetime}\n{(now - self.start_datetime).total_seconds()}s"),
            ("Last Duration", f"{self.last_iteration_duration}s"),
        ]
        function_data = [
            ("Function", repr(getattr(self.function, "__func__", self.function))[:-23] + ">"),
            ("Function parameters", repr(inspect.signature(self.function))),
            ("Function kwargs", repr(self.function_kwargs)),
        ]
        stopping_data = [
            ("Limit Count", str(self.limit_count)),
            ("Limit Date", str(self.limit_date)),
            ("Limit Exception", str(self.limit_exception)),
        ]

        emoji = "✅" if self.integrity else "❌"
        embed = discord.Embed(
            title=f"{self.name} Loop: `{emoji}`",
            color=discord.Color.green() if self.integrity else discord.Color.red(),
            timestamp=now,
        )
        embed.add_field(name="Raw data:", value=create_table(raw_data), inline=False)
        embed.add_field(name="DateTime data:", value=create_table(datetime_data), inline=False)
        embed.add_field(name="Function data:", value=create_table(function_data), inline=False)
        embed.add_field(name="Stopping data:", value=create_table(stopping_data), inline=False)

        exc = CogsUtils.replace_var_paths(self.last_exc)
        if len(exc) > 1024:
            exc = list(pagify(exc, page_length=1024))[0] + "\n..."
        embed.add_field(name="Exception:", value=box(exc), inline=False)

        return embed
