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
from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical
from textual.widgets import Button, Static, Input, Label, Checkbox, Select, Switch
from textual import on, work, events
from textual_fspicker import FileOpen, Filters
from tui.messages import (
    Errors,
    NetworkDevicesDiscovered,
    RdmDevicesDiscovered,
    RdmDeviceDetailDiscovered,
    RdmDiscoveryMessage,
)
from tui.network import get_network_cards
from tui.artnet import ArtNetDiscovery
from tui.rdm_search import get_device_info, get_devices, get_port, get_device_details
import re
import sys
import json
import serial
import serial.tools.list_ports


class QuitScreen(ModalScreen[bool]):
    """Screen with a dialog to confirm quitting."""

    BINDINGS = [
        ("left", "focus_previous", "Focus Previous"),
        ("right", "focus_next", "Focus Next"),
        ("up", "focus_previous", "Focus Previous"),
        ("down", "focus_next", "Focus Next"),
    ]

    def compose(self) -> ComposeResult:
        yield Grid(
            Static("[bold]Are you sure you want to quit?[/bold]", id="question"),
            Horizontal(
                Button("Yes", variant="error", id="yes"),
                Button("No", "primary", id="no"),
                id="quit_buttons",
            ),
            id="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "yes":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_focus_next(self) -> None:
        self.focus_next()

    def action_focus_previous(self) -> None:
        self.focus_previous()

    async def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.dismiss()  # Close the modal


class ConfigScreen(ModalScreen[dict]):
    """Screen with a dialog to configure URL, username and password."""

    BINDINGS = [
        ("left", "focus_previous", "Focus Previous"),
        ("right", "focus_next", "Focus Next"),
        ("up", "focus_previous", "Focus Previous"),
        ("down", "focus_next", "Focus Next"),
    ]

    def __init__(self) -> None:
        super().__init__()

    def compose(self) -> ComposeResult:
        with Vertical(id="config_dialog"):
            yield Static("[bold]Settings[/bold]", id="config_question")
            with Horizontal(classes="input_container"):
                yield Label("Network Discovery Timeout:")
                yield Input(
                    placeholder="Enter timeout",
                    id="artnet_timeout",
                    type="number",
                    max_length=3,
                )
                yield Static("seconds", classes="unit")
            with Horizontal():
                yield Label("Show Debug Info:")
                with Horizontal(id="details_checkbox_container"):
                    yield Switch(id="show_debug")
            yield Static("[bold]GDTF Share Credentials[/bold]", id="credentials")
            with Horizontal(classes="input_container"):
                yield Label("Username:")
                yield Input(
                    placeholder="username",
                    id="gdtf_username",
                    type="text",
                )
            with Horizontal(classes="input_container"):
                yield Label("Password:")
                yield Input(
                    placeholder="password",
                    id="gdtf_password",
                    type="text",
                    password=True,
                )
            yield Horizontal(
                Button("Save", "success", id="save"),
                Button("Cancel", "error", id="cancel"),
                id="config_buttons",
            )

    def on_mount(self) -> None:
        """Load existing data into the input fields."""
        self.query_one("#artnet_timeout").value = self.app.configuration.artnet_timeout
        self.query_one("#show_debug").value = self.app.configuration.show_debug
        self.query_one("#gdtf_username").value = self.app.configuration.gdtf_username
        self.query_one("#gdtf_password").value = self.app.configuration.gdtf_password

    def update_config(self):
        self.app.configuration.artnet_timeout = self.query_one("#artnet_timeout").value
        self.app.configuration.show_debug = self.query_one("#show_debug").value
        self.app.configuration.gdtf_username = self.query_one("#gdtf_username").value
        self.app.configuration.gdtf_password = self.query_one("#gdtf_password").value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self.update_config()
            self.app.action_save_config()
            self.dismiss()
        else:
            self.dismiss()

    def action_focus_next(self) -> None:
        self.focus_next()

    def action_focus_previous(self) -> None:
        self.focus_previous()

    async def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.dismiss()  # Close the modal


class ArtNetScreen(ModalScreen):
    """Screen with a dialog to confirm quitting."""

    networks = []
    network = None
    BINDINGS = [
        ("left", "focus_previous", "Focus Previous"),
        ("right", "focus_next", "Focus Next"),
        ("up", "focus_previous", "Focus Previous"),
        ("down", "focus_next", "Focus Next"),
    ]
    discovered_devices = []

    def compose(self) -> ComposeResult:
        with Vertical(id="all_around"):
            yield Static("Art-Net Discovery", id="question")
            with Horizontal(id="row2"):
                yield Button("Discover", id="do_start")
                yield Button("Close", id="close_discovery")
            yield Select([("", "")], id="networks_select", allow_blank=False)
            yield Static("", id="network")
            yield Static("", id="results")

    def on_mount(self):
        select_widget = self.query_one("#networks_select", Select)
        self.networks = get_network_cards()
        if sys.platform.startswith("win"):
            self.networks.pop(0)  # the 0.0.0.0 does not really work on Win

        select_widget.set_options(self.networks)
        if any(ip == "0.0.0.0" for name, ip in self.networks):
            select_widget.value = "0.0.0.0"  # for Win
        select_widget.refresh()  # Force redraw
        self.get_robe_usb_devices()

    @work(thread=True)
    def get_robe_usb_devices(self) -> None:
        """Find USB devices in a background worker."""
        devices = []
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if port.description and "Runit WTX" in port.description:
                print(f"Found port: {port.device} - {port.description}")
                if get_device_info(port.device):
                    devices.append(port)
        self.app.call_from_thread(self.update_usb_devices_list, devices)

    def update_usb_devices_list(self, devices: list) -> None:
        """Update the Select widget with the found devices."""
        sel = self.query_one("#networks_select", Select)
        options = self.networks
        options += [(f"{port.product}: {port.device}", port.device) for port in devices]
        sel.set_options(options)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "do_start":
            if "dev" in self.network:
                self.run_rdm_discovery()
            else:
                self.run_network_discovery()
            btn = self.query_one("#do_start")
            btn.disabled = True
            btn.label = "...discovering..."
        if event.button.id == "close_discovery":
            self.dismiss(self.discovered_devices)

    def on_select_changed(self, event: Select.Changed) -> None:
        if str(event.value) and str(event.value) != "Select.BLANK":
            self.network = str(event.value)
            self.query_one("#network").update(f"{self.network}")
            self.query_one("#do_start").disabled = False

    @work(thread=True)
    async def run_rdm_discovery(self) -> str:
        port = None
        try:
            results_widget = self.query_one("#results", Static)
            results_widget.update("Searching...")
            port = get_port(self.network)
            discovered_uids, tn = get_devices(port)
            uid_list = [{"uid": uid.hex(":")} for uid in discovered_uids]
            self.post_message(RdmDevicesDiscovered(devices=uid_list))

            self.post_message(
                RdmDiscoveryMessage(label="...getting RDM data...", disabled=True)
            )
            for uid in discovered_uids:
                device_data, tn = get_device_details(port, uid, tn)
                self.post_message(RdmDeviceDetailDiscovered(data=device_data))
            self.post_message(RdmDiscoveryMessage(label="Discover", disabled=False))
        except Exception as e:
            self.post_message(RdmDevicesDiscovered(error=str(e)))
        finally:
            if port and port.is_open:
                port.close()

    @work(thread=True)
    async def run_network_discovery(self) -> str:
        try:
            results_widget = self.query_one("#results", Static)
            results_widget.update(
                f"Searching... timeout is {self.app.configuration.artnet_timeout} sec."
            )
            discovery = ArtNetDiscovery(bind_ip=self.network)
            discovery.start()
            timeout = float(self.app.configuration.artnet_timeout)
            result = discovery.discover_devices(timeout=timeout)
            discovery.stop()  # not really needed, as the thread will close...
            self.post_message(NetworkDevicesDiscovered(devices=result))
            self.post_message(RdmDiscoveryMessage(label="Discover", disabled=False))
        except Exception as e:
            self.post_message(NetworkDevicesDiscovered(error=str(e)))

    def extract_uni_dmx(self, long_name):
        address = None
        universe = None
        match = None
        if long_name is not None:
            match = re.search(r"DMX:\s*(\d+)\s*Universe:\s*(\d+)", long_name)
        if match:
            address = match.group(1)
            universe = match.group(2)
        return universe, address

    def on_rdm_discovery_message(self, message: RdmDiscoveryMessage) -> None:
        btn = self.query_one("#do_start")
        btn.disabled = message.disabled
        btn.label = message.label

    def on_rdm_devices_discovered(self, message: RdmDevicesDiscovered) -> None:
        devices = []

        # {
        #   "uid": "52:53:00:45:07:f8",
        #   "device_info": {
        #       "rdm_protocol_version": "1.0",
        #       "device_model_id": 75,
        #       "product_category": 256,
        #       "software_version_id": 43,
        #       "dmx512_footprint": 38,
        #       "dmx_personality": {"current": 1, "count": 4},
        #       "dmx_start_address": 1,
        #       "sub_device_count": 0,
        #       "sensor_count": 3,
        #   },
        #   "manufacturer_label": "Robe Lighting s.r.o.",
        #   "device_model_description": "Robin MMX Spot",
        #   "device_label": "aawww",
        #   "software_version_label": "Sw.ver. 4.3",
        #   "dmx_start_address": 1,
        # }
        results_widget = self.query_one("#results", Static)
        if message.devices:
            for device in message.devices:
                uid = device.get("uid", None)
                if uid is None:
                    continue

                short_name = device.get("device_model_description", uid)
                device_info = device.get("device_info", {})
                universe = 0
                ip_address = ""
                address = device_info.get("dmx_start_address", "")
                devices.append(
                    SimpleNamespace(
                        uid=uid,
                        ip_address=ip_address,
                        short_name=short_name,
                        universe=universe,
                        address=address,
                    )
                )
            result = "\n".join(
                f"{item.short_name} {f'IP Address: {item.ip_address}' if item.ip_address else ''} {f'Universe: {item.universe}' if item.universe else ''} {f'DMX: {item.address}' if item.address else ''}"
                for item in devices
            )

        if devices:
            result = f"[green]Found {len(devices)}:[/green]\n\n{result}"

        else:
            result = f"[red]No devices found {message.error}[/red]"

        self.discovered_devices = devices
        results_widget.update(result)

        if len(devices):
            btn = self.query_one("#close_discovery")
            btn.label = f"Add {len(devices)} device{'s' if len(devices) > 1 else ''} to MVR Layer"

    def on_rdm_device_detail_discovered(
        self, message: RdmDeviceDetailDiscovered
    ) -> None:
        """Update a single device with details."""
        if message.data:
            uid_to_update = message.data.get("uid")
            for i, device in enumerate(self.discovered_devices):
                if device.uid == uid_to_update:
                    device.short_name = message.data.get(
                        "device_model_description", device.uid
                    )
                    device_info = message.data.get("device_info", {})
                    device.address = device_info.get("dmx_start_address", "")
                    self.discovered_devices[i] = device
                    break

            # Regenerate the results text
            results_text = "\n".join(
                f"{item.short_name} {f'IP Address: {item.ip_address}' if item.ip_address else ''} {f'Universe: {item.universe}' if item.universe else ''} {f'DMX: {item.address}' if item.address else ''}"
                for item in self.discovered_devices
            )
            results_widget = self.query_one("#results", Static)
            results_widget.update(
                f"[green]Found {len(self.discovered_devices)}:[/green]\n\n{results_text}"
            )

    def on_network_devices_discovered(self, message: NetworkDevicesDiscovered) -> None:
        devices = []
        results_widget = self.query_one("#results", Static)
        if message.devices:
            for device in message.devices:
                short_name = device.get("short_name", "No Name")
                universe, address = self.extract_uni_dmx(device.get("long_name", ""))
                ip_address = device.get("source_ip", None)
                devices.append(
                    SimpleNamespace(
                        ip_address=ip_address,
                        short_name=short_name,
                        universe=universe,
                        address=address,
                    )
                )
            result = "\n".join(
                f"{item.short_name} {item.ip_address} {item.universe or ''} {item.address or ''}"
                for item in devices
            )

        if devices:
            result = f"[green]Found {len(devices)}:[/green]\n\n{result}"

        else:
            result = f"[red]No devices found {message.error}[/red]"

        self.discovered_devices = devices
        results_widget.update(result)
        if len(devices):
            btn = self.query_one("#close_discovery")
            btn.label = f"Add {len(devices)} device{'s' if len(devices) > 1 else ''} to MVR Layer"

    def action_focus_next(self) -> None:
        self.focus_next()

    def action_focus_previous(self) -> None:
        self.focus_previous()

    async def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.dismiss(self.discovered_devices)  # Close the modal


class ImportDiscovery(ModalScreen):
    BINDINGS = [
        ("left", "focus_previous", "Focus Previous"),
        ("right", "focus_next", "Focus Next"),
        ("up", "focus_previous", "Focus Previous"),
        ("down", "focus_next", "Focus Next"),
    ]
    selected_layer_id = None
    selected_layer_name = None

    def __init__(self, data: list | None = None) -> None:
        self.data = data or []
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("Add Discovered Devices", id="question"),
            Vertical(
                Label("Add Into MVR Layer:", id="existing_layer_label"),
                Select(
                    self.app.mvr_layers + [("Create New layer", "new_layer")],
                    id="layers_select",
                    allow_blank=False,
                ),
                id="existing_layer",
            ),
            Vertical(
                Label("New Layer name:"),
                Input(
                    value="Layer",
                    type="text",
                    valid_empty=False,
                    id="layer_name",
                ),
                id="new_layer_widget",
            ),
            Horizontal(Button("Add", id="add"), id="buttons2"),
            id="dialog",
        )

    def on_mount(self):
        pass
        # self.query_one("#new_layer_widget").disabled = True
        # self.query_one("#add").disabled = True
        # select_widget = self.query_one("#layers_select")
        # select_widget.value = self.app.mvr_layers[0][1]
        # select_widget.refresh()  # Force redraw

    def on_select_changed(self, event: Select.Changed) -> None:
        if str(event.value) and str(event.value) == "Select.BLANK":
            self.query_one("#add").disabled = True
            self.query_one("#new_layer_widget").disabled = True
            return
        if str(event.value) and str(event.value) == "new_layer":
            self.query_one("#new_layer_widget").disabled = False
            self.selected_layer_id = event.value
            self.query_one("#add").disabled = False

            new_layer_name = self.query_one("#layer_name").value
            layer_names = [x[0] for x in self.app.mvr_layers]
            if new_layer_name in layer_names:
                self.query_one("#add").disabled = True

            return
        self.query_one("#add").disabled = False
        self.selected_layer_id = event.value
        self.query_one("#new_layer_widget").disabled = True

    def on_input_changed(self, event: Input.Changed):
        select_widget = self.query_one("#layers_select")
        self.selected_layer_name = event.value
        if select_widget.value != "new_layer":
            return
        if event.value:
            layer_names = [x[0] for x in self.app.mvr_layers]
            if event.value in layer_names:
                self.query_one("#add").disabled = True
                self.notify(f"Layer name already exists", timeout=1)
            else:
                self.query_one("#add").disabled = False
        else:
            self.query_one("#add").disabled = True
            self.notify(f"Must not be empty", timeout=1)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add":
            self.dismiss(
                {
                    "layer_id": self.selected_layer_id,
                    "layer_name": self.selected_layer_name,
                    "devices": self.data,
                }
            )

    def action_focus_next(self) -> None:
        select_widget = self.query_one("#layers_select")
        new_layer_name = self.query_one("#layer_name").value
        if select_widget.value == "new_layer":
            layer_names = [x[0] for x in self.app.mvr_layers]
            if new_layer_name in layer_names:
                self.query_one("#add").disabled = True
                self.notify(f"Layer name already exists", timeout=1)
        self.focus_next()

    def action_focus_previous(self) -> None:
        select_widget = self.query_one("#layers_select")
        new_layer_name = self.query_one("#layer_name").value
        if select_widget.value == "new_layer":
            layer_names = [x[0] for x in self.app.mvr_layers]
            if new_layer_name in layer_names:
                self.query_one("#add").disabled = True
                self.notify(f"Layer name already exists", timeout=1)
        self.focus_previous()

    async def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.dismiss()  # Close the modal
