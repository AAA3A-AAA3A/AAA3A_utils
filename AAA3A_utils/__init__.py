import json
import os

from .cog import Cog
from .cogsutils import CogsUtils
from .context import Context
from .dev import DevEnv, DevSpace
from .loop import Loop
from .menus import Menu, Reactions

try:
    from .sentry import SentryHelper
except ImportError:
    SentryHelper = None
from .settings import Settings
from .shared_cog import SharedCog

from .views import (
    Buttons,
    ChannelSelect,
    ConfirmationAskView,
    Dropdown,
    MentionableSelect,
    Modal,
    RoleSelect,
    Select,
    UserSelect,
)  # NOQA

__author__ = "AAA3A"
__all__ = [
    "CogsUtils",
    "Loop",
    "SharedCog",
    "DevEnv",
    "DevSpace",
    "Cog",
    "Menu",
    "Context",
    "Settings",
    "SentryHelper",
    "ConfirmationAskView",
    "Buttons",
    "Dropdown",
    "Select",
    "ChannelSelect",
    "MentionableSelect",
    "RoleSelect",
    "UserSelect",
    "Modal",
    "Reactions",
]

with open(os.path.join(os.path.dirname(__file__), "version.json"), mode="r") as f:
    data = json.load(f)
__version__ = data["version"]
