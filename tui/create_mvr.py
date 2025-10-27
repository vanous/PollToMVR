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

import pymvr
from pathlib import Path


def get_layer_name(uuid, mvr_layers):
    for layer_name, layer_id in mvr_layers:
        if layer_id == uuid:
            return layer_name


def create_mvr(devices, mvr_layers, save_to):
    mvr_writer = pymvr.GeneralSceneDescriptionWriter()
    scene_obj = pymvr.Scene()
    aux_data = pymvr.AUXData()
    layers = pymvr.Layers()
    scene_obj.layers = layers
    scene_obj.aux_data = aux_data

    for layer_uuid, fixtures in devices.items():
        layer_name = get_layer_name(layer_uuid, mvr_layers)

        layer = pymvr.Layer(name=layer_name, uuid=layer_uuid)
        layers.append(layer)

        child_list = pymvr.ChildList()
        layer.child_list = child_list

        for net_fixture in fixtures:
            if net_fixture.ip_address is None:
                continue
            fixture = pymvr.Fixture(name=net_fixture.short_name)
            fixture.addresses.network.append(pymvr.Network(ipv4=net_fixture.ip_address))
            if net_fixture.address is not None:
                address = 1
                universe = 1
                try:
                    address = int(net_fixture.address or 1)
                    universe = int(net_fixture.universe or 1)
                except:
                    ...
                fixture.addresses.address.append(
                    pymvr.Address(
                        dmx_break=0,
                        universe=universe,
                        address=address,
                    )
                )

            child_list.fixtures.append(fixture)

    scene_obj.to_xml(parent=mvr_writer.xml_root)

    output_path = save_to.with_suffix(".mvr")
    mvr_writer.write_mvr(output_path)
