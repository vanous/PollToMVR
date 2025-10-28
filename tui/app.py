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
from tui.screens import ArtNetScreen, QuitScreen, ConfigScreen, ImportDiscovery
from textual.message import Message
from textual.reactive import reactive
from tui.messages import MvrParsed, Errors
import uuid as py_uuid
from tui.create_mvr import create_mvr
from textual_fspicker import FileSave, Filters


class MVRDisplay(VerticalScroll):
    def update_items(self, items):
        print("update items", items)
        self.remove_children()
        for layer, fixtures in items.items():
            print("loop", layer)
            self.mount(Static(f"[blue]{self.app.get_layer_name(layer)}[/blue]"))

            for fixture in fixtures:
                print("looooo", fixture)
                self.mount(
                    Static(
                        f"[green]{fixture.short_name}[/green] {fixture.universe or ''} {fixture.address or ''} {fixture.ip_address} "
                    )
                )


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
    artnet_timeout: str = "1"
    show_debug: bool = False

    mvr_fixtures = {}
    mvr_layers = [("Default", str(py_uuid.uuid4()))]

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
                with Vertical(id="mvr_data"):
                    yield Static("[b]MVR data:[/b]")
                    self.mvr_display = MVRDisplay()
                    yield self.mvr_display

            with Grid(id="action_buttons"):
                yield Button("Discover", id="network_discovery")
                yield Button("Save MVR", id="save_mvr")
                yield Button("Configure", id="configure_button")
                yield Button("Quit", variant="error", id="quit")

    def on_mount(self) -> None:
        """Load the configuration from the JSON file when the app starts."""
        if os.path.exists(self.CONFIG_FILE):
            with open(self.CONFIG_FILE, "r") as f:
                try:
                    data = json.load(f)
                    self.artnet_timeout = data.get("artnet_timeout", "1")
                    self.show_debug = data.get("show_debug", False)
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

            def layer_selector(discovered):
                if discovered:
                    self.push_screen(
                        ImportDiscovery(data=discovered), import_discovered
                    )

            def import_discovered(data):
                print("import_data", "start")
                if data:
                    print(data)
                    layer_id = data.get("layer_id", None)
                    layer_name = data.get("layer_name", None)
                    devices = data.get("devices", [])
                    if not devices:
                        return
                    if layer_id and layer_id == "new_layer" and layer_name:
                        layer_uuid = str(py_uuid.uuid4())
                        self.mvr_layers.append((layer_name, layer_uuid))
                    else:
                        layer_uuid = layer_id
                    if layer_uuid not in self.mvr_fixtures:
                        self.mvr_fixtures[layer_uuid] = []
                    self.mvr_fixtures[layer_uuid] += devices

                    self.mvr_display.update_items(self.mvr_fixtures)

            self.push_screen(ArtNetScreen(), layer_selector)

        if event.button.id == "configure_button":
            current_config = {
                "artnet_timeout": self.artnet_timeout,
                "show_debug": self.show_debug,
            }

            def save_config(data: dict) -> None:
                """Called with the result of the configuration dialog."""
                if data:
                    self.artnet_timeout = data.get("artnet_timeout", "1")
                    self.show_debug = data.get("show_debug", False)
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
            "artnet_timeout": self.artnet_timeout,
            "show_debug": self.show_debug,
        }
        with open(self.CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=4)

    def action_quit(self) -> None:
        """Save the configuration to the JSON file when the app closes."""
        self.action_save_config()
        self.exit()

    def get_layer_name(self, uuid):
        for layer_name, layer_id in self.mvr_layers:
            if layer_id == uuid:
                return layer_name

    @on(Button.Pressed)
    @work
    async def save_a_file(self, event: Button.Pressed) -> None:
        if event.button.id == "save_mvr":
            if save_to := await self.app.push_screen_wait(
                FileSave(
                    default_file="discovered.mvr",
                    filters=Filters(("MVR", lambda p: p.suffix.lower() == ".mvr")),
                )
            ):
                create_mvr(self.mvr_fixtures, self.mvr_layers, save_to)
                self.notify("Saved", timeout=1)


if __name__ == "__main__":
    app = ArtPollToMVR()
    app.run()
