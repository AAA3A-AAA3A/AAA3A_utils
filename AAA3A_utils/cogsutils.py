import discord
import logging
import typing
import datetime
import asyncio
from copy import copy
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.utils.predicates import MessagePredicate
from redbot.core.utils.menus import start_adding_reactions
from redbot.core.data_manager import cog_data_path

__all__ = ["CogsUtils"]
TimestampFormat = typing.Literal["f", "F", "d", "D", "t", "T", "R"]

class CogsUtils(commands.Cog):
    """Tools for AAA3A-cogs!"""

    def __init__(self, cog: typing.Optional[commands.Cog]=None, bot: typing.Optional[Red]=None):
        if cog is None and bot is not None:
            self.bot = bot
        else:
            self.cog = cog
            self.bot = self.cog.bot
            self.__version__ = self.cog.__version__
            self.DataPath = cog_data_path(raw_name=self.cog.__class__.__name__.lower())
        self.__author__ = "AAA3A"
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
                            "SimpleSanction",
                            "Sudo",
                            "TicketTool",
                            "TransferChannel"
                        ]

    def format_help_for_context(self, ctx):
        """Thanks Simbad!"""
        context = super().format_help_for_context(ctx)
        return f"{context}\n\nAuthor: {self.__author__}\nVersion: {self.__version__}"

    async def red_delete_data_for_user(self, **kwargs):
        """Nothing to delete"""
        return

    def _setup(self):
        self.cog.log = logging.getLogger(f"red.{self.repo_name}.{self.cog.__class__.__name__}")
        self.add_dev_values()
        if not hasattr(self.cog, 'format_help_for_context'):
            setattr(self.cog, 'format_help_for_context', self.format_help_for_context)
        if not hasattr(self.cog, 'red_delete_data_for_user'):
            setattr(self.cog, 'red_delete_data_for_user', self.red_delete_data_for_user)

    def _end(self):
        self.remove_dev_values()

    def add_dev_values(self):
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
                self.bot.add_dev_env_value(self.cog.__class__.__name__, lambda x: self.cog)
            except Exception:
                pass

    def remove_dev_values(self):
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

    def class_instance_to_json(self, instance):
        instance = copy(instance)
        original_dict = instance.__dict__
        new_dict = self.to_id(original_dict)
        return new_dict

    def to_id(self, original_dict):
        new_dict = {}
        for e in original_dict.values():
            if isinstance(e, dict):
                new_dict[e] = self.to_id(e)
            elif hasattr(e, 'id'):
                new_dict[e] = int(e.id)
            elif isinstance(e, datetime.datetime):
                new_dict[e] = float(datetime.datetime.timestamp(e))
            else:
                new_dict[e] = e
        return new_dict

    async def from_id(self, id: int, who, type: str):
        instance = eval(f"{who}.get_{type}({id})")
        if instance is None:
            instance = await eval(f"await {who}.fetch_{type}({id})")
        return instance

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

    def get_all_repo_cogs_objects(self):
        cogs = {}
        for cog in self.all_cogs:
            object = self.bot.get_cog(f"{cog}")
            cogs[f"{cog}"] = object
        return cogs
    
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
    
    def all_dev_values(self):
        cogs = self.get_all_repo_cogs_objects()
        for cog in cogs:
            if cogs[cog] is not None:
                try:
                    CogsUtils(cogs[cog]).add_dev_values()
                except Exception:
                    pass
