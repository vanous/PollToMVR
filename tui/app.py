# Copyright (C) 2025 vanous
#
# This file is part of PollToMVR.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import functools
import json
import os
import random
import traceback
import subprocess
from types import SimpleNamespace
from textual.app import App, ComposeResult
from textual import on, work
from textual.containers import Horizontal, Vertical, VerticalScroll, Grid
from textual.widgets import Header, Footer, Input, Button, Static
from textual.worker import Worker, WorkerState
from tui.screens import (
    ArtNetScreen,
    QuitScreen,
    ConfigScreen,
)
from textual.message import Message
from textual.reactive import reactive
from tui.messages import MvrParsed, Errors


class ListDisplay(Vertical):
    def update_items(self, items: list):
        self.remove_children()
        for item in items:
            tags = ""
            if hasattr(item, "tags"):
                tags = ", ".join(item.tags)
            if self.app.details_toggle:
                self.mount(
                    Static(
                        f"[green]{item.name}[/green] {item.uuid or ''} {f' {item.id or ""}' if hasattr(item, 'id') else ''}{f' [blue]Tags:[/blue] {tags}' if tags else ''}"
                    )
                )
            else:
                self.mount(
                    Static(
                        f"[green]{item.name}[/green]{f' [blue]Tags:[/blue] {tags}' if tags else ''}"
                    )
                )


class DictListDisplay(Vertical):
    def update_items(self, items: list):
        self.remove_children()
        for item in items:  # layers
            for fixture in item.fixtures:
                if self.app.details_toggle:
                    self.mount(Static(f"[green]{fixture.name}[/green] {fixture.uuid}"))
                else:
                    self.mount(Static(f"[green]{fixture.name}[/green]"))


class ArtPollToMVR(App):
    """A Textual app to manage Uptime Kuma MVR."""

    CSS_PATH = [
        "app.css",
        "quit_screen.css",
        "config_screen.css",
        "artnet_screen.css",
    ]
    BINDINGS = [
        ("left", "focus_previous", "Focus Previous"),
        ("right", "focus_next", "Focus Next"),
        ("up", "focus_previous", "Focus Previous"),
        ("down", "focus_next", "Focus Next"),
    ]
    HORIZONTAL_BREAKPOINTS = [
        (0, "-narrow"),
        (40, "-normal"),
        (80, "-wide"),
        (120, "-very-wide"),
    ]

    CONFIG_FILE = "config.json"
    timeout: str = "1"
    details_toggle: bool = False

    mvr_fixtures = []

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Footer()
        with Vertical(id="all_around"):
            with Vertical(id="json_output_container"):
                yield Static(
                    "Ready...",
                    id="json_output",
                )
                with Horizontal(id="mvr_data"):
                    yield Static("[b]MVR data:[/b]")
                    self.mvr_tag_display = ListDisplay()
                    yield self.mvr_tag_display
                    self.mvr_fixtures_display = DictListDisplay()
                    yield self.mvr_fixtures_display

            with Grid(id="action_buttons"):
                yield Button("Discover", id="network_discovery")
                yield Button("Configure", id="configure_button")
                yield Button("Quit", variant="error", id="quit")

    def on_mount(self) -> None:
        """Load the configuration from the JSON file when the app starts."""
        if os.path.exists(self.CONFIG_FILE):
            with open(self.CONFIG_FILE, "r") as f:
                try:
                    data = json.load(f)
                    self.timeout = data.get("timeout", "1")
                    self.details_toggle = data.get("details_toggle", False)
                    self.notify("Config loaded...", timeout=1)

                except json.JSONDecodeError:
                    # Handle empty or invalid JSON file
                    pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Called when a button is pressed."""

        if event.button.id == "delete_tags":
            self.query_one("#json_output").update(
                "Calling API via script, adding monitors..."
            )

        if event.button.id == "network_discovery":
            self.push_screen(ArtNetScreen())

        if event.button.id == "configure_button":
            current_config = {
                "timeout": self.timeout,
                "details_toggle": self.details_toggle,
            }

            def save_config(data: dict) -> None:
                """Called with the result of the configuration dialog."""
                if data:
                    self.timeout = data.get("timeout", "1")
                    self.details_toggle = data.get("details_toggle", False)
                    self.action_save_config()
                    self.notify("Configuration saved.", timeout=1)

            self.push_screen(ConfigScreen(data=current_config), save_config)

        if event.button.id == "quit":

            def check_quit(quit_confirmed: bool) -> None:
                """Called with the result of the quit dialog."""
                if quit_confirmed:
                    self.action_quit()

            self.push_screen(QuitScreen(), check_quit)

    def action_save_config(self) -> None:
        """Save the configuration to the JSON file."""
        data = {
            "timeout": self.timeout,
            "details_toggle": self.details_toggle,
        }
        with open(self.CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=4)

    def action_quit(self) -> None:
        """Save the configuration to the JSON file when the app closes."""
        self.action_save_config()
        self.exit()


if __name__ == "__main__":
    app = ArtPollToMVR()
    app.run()
