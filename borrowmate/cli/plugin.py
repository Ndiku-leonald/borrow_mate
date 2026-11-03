from typing import Callable, List, Tuple

MenuEntry = Tuple[str, Callable[[], None]]


class MenuPlugin:
    """Optional extension point for CLI menus."""

    order = 100

    def __init__(self, community):
        self.community = community

    def menu_entries(self, cli) -> List[MenuEntry]:
        return []
