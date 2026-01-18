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

import json
import os
from types import SimpleNamespace
from textual.app import App, ComposeResult
from textual import on, work
from textual.containers import Horizontal, Vertical, VerticalScroll, Grid
from textual.widgets import Header, Button, Static, Select
from tui.screens import ArtNetScreen, QuitScreen, ConfigScreen, ImportDiscovery
import uuid as py_uuid
from tui.create_mvr import create_mvr
from textual_fspicker import FileSave, Filters
from tui.gdtf_share.gdtf import GDTFScreen
from pathlib import Path

try:
    import keyring
    from keyring.errors import KeyringError
except ImportError:  # pragma: no cover - optional dependency at runtime
    keyring = None
    KeyringError = Exception


class MVRDisplay(VerticalScroll):
    def update_items(self, items):
        self.remove_children()
        for layer, fixtures in items.items():
            self.mount(Static(f"Layer: [blue]{self.app.get_layer_name(layer)}[/blue]"))

            for index, fixture in enumerate(fixtures):
                self.mount(MVRFixtureRow(layer, index, fixture))


class MVRFixtureRow(Horizontal):
    def __init__(self, layer_id, index, fixture):
        super().__init__()
        self.layer_id = layer_id
        self.index = index
        self.fixture = fixture

    def compose(self) -> ComposeResult:
        yield Button("x", classes="remove_fixture", variant="error")
        yield Static(
            f"[green]{self.fixture.short_name}[/green] "
            f"{f'IP Address: {self.fixture.ip_address}' if self.fixture.ip_address else ''} "
            f"{f'Universe: {self.fixture.universe}' if self.fixture.universe else ''} "
            f"{f'DMX: {self.fixture.address}' if self.fixture.address else ''}"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if "remove_fixture" in event.button.classes:
            self.app.remove_mvr_fixture(self.layer_id, self.index)


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


class PollToMVR(App):
    """A Textual app to manage Uptime Kuma MVR."""

    APP_NAME = "PollToMVR"
    TITLE = APP_NAME
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
    KEYRING_SERVICE = APP_NAME
    KEYRING_USERNAME_KEY = "gdtf_username"
    KEYRING_PASSWORD_KEY = "gdtf_password"
    configuration = SimpleNamespace(
        artnet_timeout="1",
        show_debug=False,
        show_link_local_addresses=False,
        gdtf_username="",
        gdtf_password="",
    )

    mvr_fixtures = {}
    mvr_layers = [("Default", str(py_uuid.uuid4()))]
    gdtf_map = {}
    gdtf_data = []

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
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
                yield Button("Save MVR", id="save_mvr", disabled=True)
                yield Button("GDTF Files", id="gdtf_files")
                yield Button("Configure", id="configure_button")
                yield Button("Quit", variant="error", id="quit")

    def on_mount(self) -> None:
        """Load the configuration from the JSON file when the app starts."""
        path = Path("gdtf_files")
        path.mkdir(parents=True, exist_ok=True)
        config_data = {}
        if os.path.exists(self.CONFIG_FILE):
            with open(self.CONFIG_FILE, "r") as f:
                try:
                    config_data = json.load(f)
                    vars(self.configuration).update(config_data)
                    self.notify("Configuration loaded...", timeout=1)

                except json.JSONDecodeError:
                    # Handle empty or invalid JSON file
                    pass
        migrated = self._load_credentials(config_data)
        if migrated:
            with open(self.CONFIG_FILE, "w") as f:
                json.dump(config_data, f, indent=4)
            self.notify("Credentials moved to system keyring.", timeout=2)

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
                    self.query_one("#save_mvr").disabled = False
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
                    self._update_save_button_state()

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
        config_data = vars(self.app.configuration).copy()
        self._persist_credentials(config_data)
        with open(self.CONFIG_FILE, "w") as f:
            json.dump(config_data, f, indent=4)

    def action_quit(self) -> None:
        """Save the configuration to the JSON file when the app closes."""
        self.action_save_config()
        self.exit()

    def get_layer_name(self, uuid):
        for layer_name, layer_id in self.mvr_layers:
            if layer_id == uuid:
                return layer_name
        return None

    def remove_mvr_fixture(self, layer_id, index) -> None:
        fixtures = self.mvr_fixtures.get(layer_id, [])
        if index < 0 or index >= len(fixtures):
            return
        fixtures.pop(index)
        if not fixtures:
            self.mvr_fixtures.pop(layer_id, None)
        self._cleanup_gdtf_map()
        self.mvr_display.update_items(self.mvr_fixtures)
        self.gdtf_mapping.update_items()
        self._update_save_button_state()

    def _cleanup_gdtf_map(self) -> None:
        active_fixtures = {
            fixture.short_name
            for layer in self.mvr_fixtures.values()
            for fixture in layer
        }
        for name in list(self.gdtf_map.keys()):
            if name not in active_fixtures:
                self.gdtf_map.pop(name, None)

    def _update_save_button_state(self) -> None:
        save_button = self.query_one("#save_mvr", Button)
        save_button.disabled = not any(self.mvr_fixtures.values())

    def _keyring_get(self, key):
        if not keyring:
            return None
        try:
            return keyring.get_password(self.KEYRING_SERVICE, key)
        except KeyringError:
            return None

    def _keyring_set(self, key, value):
        if not keyring:
            return False
        try:
            if value:
                keyring.set_password(self.KEYRING_SERVICE, key, value)
            else:
                try:
                    keyring.delete_password(self.KEYRING_SERVICE, key)
                except KeyringError:
                    pass
            return True
        except KeyringError:
            return False

    def _load_credentials(self, config_data):
        migrated = False
        username = self._keyring_get(self.KEYRING_USERNAME_KEY)
        password = self._keyring_get(self.KEYRING_PASSWORD_KEY)
        config_username = config_data.get("gdtf_username", "")
        config_password = config_data.get("gdtf_password", "")
        if (config_username or config_password) and (
            username is None or password is None
        ):
            stored_user = self._keyring_set(self.KEYRING_USERNAME_KEY, config_username)
            stored_pass = self._keyring_set(self.KEYRING_PASSWORD_KEY, config_password)
            if stored_user and stored_pass:
                config_data.pop("gdtf_username", None)
                config_data.pop("gdtf_password", None)
                migrated = True
                username = self._keyring_get(self.KEYRING_USERNAME_KEY)
                password = self._keyring_get(self.KEYRING_PASSWORD_KEY)
        if username is None:
            username = config_username
        if password is None:
            password = config_password
        self.configuration.gdtf_username = username or ""
        self.configuration.gdtf_password = password or ""
        return migrated

    def _persist_credentials(self, config_data):
        stored_user = self._keyring_set(
            self.KEYRING_USERNAME_KEY, self.configuration.gdtf_username
        )
        stored_pass = self._keyring_set(
            self.KEYRING_PASSWORD_KEY, self.configuration.gdtf_password
        )
        if stored_user and stored_pass:
            config_data.pop("gdtf_username", None)
            config_data.pop("gdtf_password", None)
        else:
            config_data["gdtf_username"] = self.configuration.gdtf_username
            config_data["gdtf_password"] = self.configuration.gdtf_password

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
    app = PollToMVR()
    app.run()
