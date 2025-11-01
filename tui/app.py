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
from textual.widgets import Header, Footer, Input, Button, Static, Select
from textual.worker import Worker, WorkerState
from tui.screens import ArtNetScreen, QuitScreen, ConfigScreen, ImportDiscovery
from textual.message import Message
from textual.reactive import reactive
from tui.messages import MvrParsed, Errors
import uuid as py_uuid
from tui.create_mvr import create_mvr
from textual_fspicker import FileSave, Filters
from tui.gdtf_share.gdtf import GDTFScreen
from pathlib import Path


class MVRDisplay(VerticalScroll):
    def update_items(self, items):
        self.remove_children()
        for layer, fixtures in items.items():
            self.mount(Static(f"Layer: [blue]{self.app.get_layer_name(layer)}[/blue]"))

            for fixture in fixtures:
                self.mount(
                    Static(
                        f"[green]{fixture.short_name}[/green] {fixture.universe or ''} {fixture.address or ''} {fixture.ip_address} "
                    )
                )


class GDTFMapping(VerticalScroll):
    def get_fixture(self, rid):
        if not self.app.gdtf_data:
            data_file = Path("data.json")
            if data_file.exists():
                with open(data_file, "r") as f:
                    self.app.gdtf_data = json.load(f)
        for fixture in self.app.gdtf_data:
            if str(fixture.get("rid")) == str(rid):
                return fixture
        return {}

    def create_label(self, stem):
        sections = stem.split("@")
        rid = sections[-1]
        share_fixture = self.get_fixture(rid)
        name = share_fixture.get("fixture", stem)
        manufacturer = share_fixture.get("manufacturer")
        revision = share_fixture.get("revision")
        return (
            f"{name}"
            f"{f' ({manufacturer})' if manufacturer else ''}"
            f"{f' {revision}' if revision else ''}"
        )
        return stem

    def update_items(self):
        self.remove_children()

        path = Path("gdtf_files")

        gdtf_files_list = sorted(
            [
                (self.create_label(p.stem), p.name)
                for p in path.iterdir()
                if p.suffix == ".gdtf"
            ]
        )

        fixtures = set(
            [
                fixture.short_name
                for layer in self.app.mvr_fixtures.values()
                for fixture in layer
            ]
        )

        for fixture in fixtures:
            self.mount(GDTFMappedFixture(fixture, gdtf_files_list))


class GDTFMappedFixture(Horizontal):
    def __init__(self, fixture, gdtf_files_list):
        self.fixture = fixture
        self.gdtf_files_list = gdtf_files_list
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Static(f"[green]{self.fixture}[/green]", id="gdtf_select")
        yield Select(options=self.gdtf_files_list, id="select_gdtf", compact=False)

    def on_mount(self):
        if self.fixture in self.app.gdtf_map:
            select = self.query_one("#select_gdtf")
            select.value = self.app.gdtf_map[self.fixture]

    def on_select_changed(self, event: Select.Changed):
        if str(event.value) and str(event.value) != "Select.BLANK":
            self.app.gdtf_map[self.fixture] = event.value


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
    configuration = SimpleNamespace(
        artnet_timeout="1", show_debug=False, gdtf_username="", gdtf_password=""
    )

    mvr_fixtures = {}
    mvr_layers = [("Default", str(py_uuid.uuid4()))]
    gdtf_map = {}
    gdtf_data = []

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Footer()
        with Vertical(id="all_around"):
            with Horizontal():
                with Vertical(id="mvr_data"):
                    yield Static("[b]MVR data:[/b]")
                    self.mvr_display = MVRDisplay()
                    yield self.mvr_display
                with Vertical(id="gdtf_mapping"):
                    yield Static("[b]GDTF Mapping:[/b]")
                    self.gdtf_mapping = GDTFMapping()
                    yield self.gdtf_mapping

            with Grid(id="action_buttons"):
                yield Button("Discover", id="network_discovery")
                yield Button("Save MVR", id="save_mvr")
                yield Button("GDTF Files", id="gdtf_files")
                yield Button("Configure", id="configure_button")
                yield Button("Quit", variant="error", id="quit")

    def on_mount(self) -> None:
        """Load the configuration from the JSON file when the app starts."""
        path = Path("gdtf_files")
        path.mkdir(parents=True, exist_ok=True)
        if os.path.exists(self.CONFIG_FILE):
            with open(self.CONFIG_FILE, "r") as f:
                try:
                    vars(self.configuration).update(json.load(f))
                    self.notify("Config loaded...", timeout=1)

                except json.JSONDecodeError:
                    # Handle empty or invalid JSON file
                    pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Called when a button is pressed."""
        if event.button.id == "gdtf_files":
            self.push_screen(GDTFScreen())

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
                if data:
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
                    self.gdtf_mapping.update_items()

            self.push_screen(ArtNetScreen(), layer_selector)

        if event.button.id == "configure_button":
            self.push_screen(ConfigScreen())

        if event.button.id == "quit":

            def check_quit(quit_confirmed: bool) -> None:
                """Called with the result of the quit dialog."""
                if quit_confirmed:
                    self.action_quit()

            self.push_screen(QuitScreen(), check_quit)

    def action_save_config(self) -> None:
        """Save the configuration to the JSON file."""
        with open(self.CONFIG_FILE, "w") as f:
            json.dump(vars(self.app.configuration), f, indent=4)

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
                create_mvr(self.mvr_fixtures, self.mvr_layers, self.gdtf_map, save_to)
                self.notify("Saved", timeout=1)


if __name__ == "__main__":
    app = ArtPollToMVR()
    app.run()
