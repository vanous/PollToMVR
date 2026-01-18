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

import ifaddr
import sys


def get_network_cards(show_link_local_addresses: bool = False):
    all_cards = []
    if not sys.platform.startswith("win"):
        all_cards.append(("All Network Interfaces: 0.0.0.0", "0.0.0.0"))
    for adapter in ifaddr.get_adapters():
        for ip in adapter.ips:
            if isinstance(ip.ip, tuple):  # Skip IPv6
                continue
            if (not show_link_local_addresses) and ip.ip.startswith(
                "169.254."
            ):  # Skip link-local
                continue

            label = f"{adapter.nice_name}: {ip.ip}"
            value = ip.ip
            all_cards.append((label, value))
    return all_cards
