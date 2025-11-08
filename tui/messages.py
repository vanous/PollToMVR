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

from textual.message import Message


class MvrParsed(Message):
    """Message sent when monitors are fetched from the API."""

    def __init__(self, fixtures: list | None = None, tags: list | None = None) -> None:
        self.fixtures = fixtures
        self.tags = tags
        super().__init__()


class Errors(Message):
    """Message sent when monitors are fetched from the API."""

    def __init__(self, error: str | None = None) -> None:
        self.error = error
        super().__init__()


class NetworkDevicesDiscovered(Message):
    """Message sent when monitors are fetched from the API."""

    def __init__(self, devices: list | None = None, error: str = "") -> None:
        self.devices = devices
        self.error = error
        super().__init__()


class RdmDevicesDiscovered(Message):
    """Message sent when monitors are fetched from the API."""

    def __init__(self, devices: list | None = None, error: str = "") -> None:
        self.devices = devices
        self.error = error
        super().__init__()
