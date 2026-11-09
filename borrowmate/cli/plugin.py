"""Extension point for adding features to the CLI without editing it.

A feature subclasses MenuPlugin and lives in its own file inside
borrowmate/plugins/. load_plugins() finds and creates every plugin
automatically, so teammates can each add a feature in new files only,
and their pull requests never edit the same lines.
"""

import importlib
import pkgutil
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Callable, List, Tuple

from borrowmate.services.community import Community

if TYPE_CHECKING:  # avoid a circular import at runtime
    from borrowmate.cli.app import BorrowMateCLI

MenuEntry = Tuple[str, Callable[[], None]]


class MenuPlugin(ABC):
    """Base class for a feature that adds options to the menu."""

    #: Lower numbers appear earlier in the menu.
    order: int = 100

    def __init__(self, community: Community):
        self.community = community

    @abstractmethod
    def menu_entries(self, cli: "BorrowMateCLI") -> List[MenuEntry]:
        """Menu options for the user currently logged in to ``cli``."""

    def on_tick(self, now: datetime) -> None:
        """Called before each menu is shown (e.g. to expire old requests)."""


def load_plugins(community: Community, package: str = "borrowmate.plugins") -> List[MenuPlugin]:
    """Import every module in ``package`` and create each MenuPlugin found."""
    module = importlib.import_module(package)
    for info in pkgutil.iter_modules(module.__path__):
        importlib.import_module(f"{package}.{info.name}")
    plugins = [cls(community) for cls in _concrete_subclasses(MenuPlugin)
               if cls.__module__.startswith(package)]
    return sorted(plugins, key=lambda p: (p.order, type(p).__name__))


def _concrete_subclasses(base: type) -> List[type]:
    found = []
    for sub in base.__subclasses__():
        if not getattr(sub, "__abstractmethods__", None):
            found.append(sub)
        found.extend(_concrete_subclasses(sub))
    return found
