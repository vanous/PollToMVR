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

from types import SimpleNamespace
from textual.message import Message
from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.containers import (
    Grid,
    Horizontal,
    Vertical,
    HorizontalGroup,
    VerticalScroll,
)
from textual.widgets import Button, Static, Input, Label, Checkbox, Select, Switch
from textual import on, work, events
from textual_fspicker import FileOpen, Filters
from tui.messages import Errors, DevicesDiscovered
from tui.network import get_network_cards
from tui.artnet import ArtNetDiscovery
from tui.share_api_client import update_data, download_files
import re
import sys
from pathlib import Path
import json
import asyncio


class FileDownloaded(Message): ...


class ShareUpdated(Message): ...


class LocalFile(HorizontalGroup):
    name = ""
    filename = None

    def __init__(self, filename=None):
        if filename:
            self.filename = filename
            # sections = filename.split("@")
            self.name = Path(filename).stem
        super().__init__()

    def compose(self):
        yield Static(f"{self.name}", id="name")
        yield Button("Delete", id="delete")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "delete":
            path = Path(self.filename)
            if path.exists():
                path.unlink()
            self.screen.refresh_local_listing()


class GDTFFile(HorizontalGroup):
    fixture = None
    name = ""
    brand = ""
    creator = ""
    manufacturer_file = False

    def callback(self, function, result):
        function(result)

    def downloaded(self, result):
        if result.status:
            self.post_message(FileDownloaded())
            self.notify(f"Downloaded, status: {result.result.status_code}", timeout=1)
        else:
            self.notify(f"Failed, status: {result.result.status_code}", timeout=1)

    def __init__(self, fixture=None):
        if fixture:
            self.fixture = fixture
            self.name = fixture.get("fixture")
            self.brand = fixture.get("manufacturer")
            self.manufacturer_file = fixture.get("uploader") == "Manuf."
            self.creator = fixture.get("creator")
        super().__init__()

    def compose(self):
        yield Static(
            f"{self.name} ({self.brand}) {'🏭' if self.manufacturer_file else '🧑'}",
            id="name",
        )
        yield Button("Download", id="download")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "download":
            if (
                not self.app.configuration.gdtf_username
                or not self.app.configuration.gdtf_password
            ):
                self.notify("Set GDTF Credentials in Config")
                return
            self.notify(f"Downloading {self.name}", timeout=1)
            file_path = Path("gdtf_files")
            download_files(
                self.app.configuration.gdtf_username,
                self.app.configuration.gdtf_password,
                file_path,
                [self.fixture],
                self.callback,
                self.downloaded,
                self.screen.data_file,
            )


class GDTFScreen(ModalScreen):
    """Screen with a dialog to confirm quitting."""

    BINDINGS = [
        ("left", "focus_previous", "Focus Previous"),
        ("right", "focus_next", "Focus Next"),
        ("up", "focus_previous", "Focus Previous"),
        ("down", "focus_next", "Focus Next"),
    ]

    data_file = Path("data.json")
    gdtf_data = []
    debounce_task = None

    def compose(self) -> ComposeResult:
        with Vertical(id="all_around"):
            yield Static("GDTF Files", id="question")
            with Horizontal(id="row2"):
                yield Button("Update GDTF Share data", id="do_update")
                yield Button("Close", id="close")
            with Horizontal(id="search_bar"):
                yield Input(
                    placeholder="Filter GDTF Name", type="text", id="filter_filename"
                )
                yield Input(
                    placeholder="Filter Manufacturer",
                    type="text",
                    id="filter_manufacturer",
                )
                yield Select(
                    options=[
                        ("🏭 Manufacturer Only", "Manuf."),
                        ("🧑 User Only", "User"),
                        ("🏭 🧑 Show All Files", "all"),
                    ],
                    prompt="",
                    allow_blank=False,
                    id="uploader",
                    value="all",
                )
            with Horizontal():
                with VerticalScroll(id="listing_share"):
                    yield Static("...")
                with VerticalScroll(id="listing_local"):
                    yield Static("...")

    def on_select_changed(self, event: Select.Changed):
        self.refresh_share_listing()

    def on_input_changed(self, event: Input.Changed):
        if self.debounce_task and not self.debounce_task.done():
            self.debounce_task.cancel()

        self.debounce_task = asyncio.create_task(self.debounced_update(event.value))

    async def debounced_update(self, value: str):
        await asyncio.sleep(0.25)
        self.refresh_share_listing()

    def on_mount(self):
        self.gdtf_data = []
        if self.data_file.exists():
            with open(self.data_file, "r") as f:
                self.gdtf_data = json.load(f)
        self.refresh_share_listing()
        self.refresh_local_listing()

    def refresh_share_listing(self):
        listing = self.query_one("#listing_share")
        listing.remove_children()

        filter_uploader = self.query_one("#uploader").value
        filter_filename = self.query_one("#filter_filename").value
        filter_manufacturer = self.query_one("#filter_manufacturer").value

        filters = []

        if filter_filename:
            filters.append(
                lambda fix: filter_filename.lower() in fix["fixture"].lower()
            )
        if filter_manufacturer:
            filters.append(
                lambda fix: filter_manufacturer.lower() in fix["manufacturer"].lower()
            )

        if filter_uploader != "all":
            filters.append(lambda fix: fix["uploader"] == filter_uploader)

        filtered_data = [fix for fix in self.gdtf_data if all(f(fix) for f in filters)]

        listing.mount(
            Static(
                f"[bold]GDTF Share Files:[/bold] Showing 50 of {len(filtered_data)}:"
            )
        )

        self.set_focus(self.query_one("#filter_filename"))
        for fixture in filtered_data[0:50]:
            listing.mount(GDTFFile(fixture))

    def refresh_local_listing(self):
        listing = self.query_one("#listing_local")
        listing.remove_children()
        path = Path("gdtf_files")
        gdtf_files_list = [p for p in path.iterdir() if p.suffix == ".gdtf"]

        listing.mount(Static("[bold]Downloaded Files:[/bold]"))
        for fixture in gdtf_files_list:
            listing.mount(LocalFile(fixture))

    def callback(self, function, result):
        function(result)

    def updated(self, result):
        if result.status:
            self.notify(f"Updated, status: {result.result.status_code}", timeout=1)
            self.post_message(ShareUpdated())
        else:
            self.notify(f"Failed, status: {result.result.status_code}", timeout=1)

    def reload_share_data(self):
        if self.data_file.exists():
            with open(self.data_file, "r") as f:
                self.gdtf_data = json.load(f)
        if self.query_one("#filter_manufacturer").value == "":
            self.refresh_share_listing()
        else:
            self.query_one("#filter_filename").value = self.query_one(
                "#filter_manufacturer"
            ).value = ""  # this will cause data refresh

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "do_update":
            if (
                not self.app.configuration.gdtf_username
                or not self.app.configuration.gdtf_password
            ):
                self.notify("Set GDTF Credentials in Config")
                return
            self.notify("Updating GDTF Share data", timeout=2)

            update_data(
                self.app.configuration.gdtf_username,
                self.app.configuration.gdtf_password,
                self.callback,
                self.updated,
                self.data_file,
            )

        if event.button.id == "close":
            self.dismiss()

    @work(thread=True)
    async def run_discovery(self) -> str:
        pass

    def action_focus_next(self) -> None:
        self.focus_next()

    def action_focus_previous(self) -> None:
        self.focus_previous()

    async def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.dismiss()  # Close the modal

    def on_file_downloaded(self, message: FileDownloaded) -> None:
        self.refresh_local_listing()
        self.app.gdtf_mapping.update_items()

    def on_share_updated(self, message: ShareUpdated) -> None:
        self.reload_share_data()
