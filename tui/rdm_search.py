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

import serial
import time
import struct
import random

# Robe Universal Interface API constants
HEADER = 0xA5
PACKET_TYPE_RDM_RESPONSE = 0x11
PACKET_TYPE_RDM_PACKET_OUT = 0x10
PACKET_TYPE_RDM_DISCOVERY_UNIQUE_BRANCH = 0x12
PACKET_TYPE_RDM_DISCOVERY_RESPONSE = 0x13
PACKET_TYPE_RDM_INFO_COMMAND = 0x14
PACKET_TYPE_RDM_INFO_RESPONSE = 0x15

# RDM constants
RDM_START_CODE = 0xCC
RDM_SUB_START_CODE = 0x01
BROADCAST_ALL_DEVICES_ID = b"\xff\xff\xff\xff\xff\xff"
# This is the UID of the Robe Universal Interface itself, acting as the controller
CONTROLLER_UID = b"\x52\x53\x02\x00\x00\x15"

# RDM Command Class
DISCOVERY_COMMAND = 0x10
DISCOVERY_COMMAND_RESPONSE = 0x11
GET_COMMAND = 0x20
GET_COMMAND_RESPONSE = 0x21
SET_COMMAND = 0x30
SET_COMMAND_RESPONSE = 0x31

# RDM Parameter IDs (PID)
DISC_UNIQUE_BRANCH = 0x0001
DISC_MUTE = 0x0002
DISC_UN_MUTE = 0x0003
SUPPORTED_PARAMETERS = 0x0050
DEVICE_INFO = 0x0060
DEVICE_MODEL_DESCRIPTION = 0x0080
MANUFACTURER_LABEL = 0x0081
DEVICE_LABEL = 0x0082
SOFTWARE_VERSION_LABEL = 0x00C0
DMX_START_ADDRESS = 0x00F0

RDM_PARAMETER_NAMES = {
    v: k for k, v in globals().items() if k.isupper() and isinstance(v, int)
}

RDM_RESPONSE_TYPE_NAMES = {
    0x00: "RESPONSE_TYPE_ACK",
    0x01: "RESPONSE_TYPE_ACK_TIMER",
    0x02: "RESPONSE_TYPE_NACK_REASON",
    0x03: "RESPONSE_TYPE_ACK_OVERFLOW",
}


def calculate_byte_sum_crc(data: bytes) -> int:
    """Calculates the 1-byte sum of all bytes."""
    return sum(data) & 0xFF


def build_robe_packet(packet_type: int, rdm_packet: bytes) -> bytes:
    """Builds the final packet for the Robe Universal Interface."""
    data_to_wrap = rdm_packet
    # As per Robe API, 4 random bytes are appended for certain packet types
    if packet_type in [
        PACKET_TYPE_RDM_PACKET_OUT,
        PACKET_TYPE_RDM_DISCOVERY_UNIQUE_BRANCH,
    ]:
        data_to_wrap += bytes(random.getrandbits(8) for _ in range(4))

    data_len = len(data_to_wrap)
    header_part = bytearray(
        [HEADER, packet_type, data_len & 0xFF, (data_len >> 8) & 0xFF]
    )
    header_crc = calculate_byte_sum_crc(header_part)

    packet = bytearray()
    packet.extend(header_part)
    packet.append(header_crc)
    packet.extend(data_to_wrap)

    all_crc = calculate_byte_sum_crc(packet)
    packet.append(all_crc)

    return bytes(packet)


def calculate_rdm_checksum(data: bytes) -> int:
    """Calculates the 16-bit RDM checksum."""
    return sum(data)


def build_rdm_packet(
    dest_uid: bytes, tn: int, cc: int, pid: int, pd: bytes = b""
) -> bytes:
    """Builds an RDM packet (the part that goes into the Robe packet)."""
    pdl = len(pd)
    message_length = 24 + pdl  # Standard length without checksum

    packet_for_checksum = bytearray(
        [RDM_START_CODE, RDM_SUB_START_CODE, message_length]
    )
    packet_for_checksum.extend(dest_uid)
    packet_for_checksum.extend(CONTROLLER_UID)
    packet_for_checksum.extend([tn, 1, 0])  # TN, Port ID, Message Count
    packet_for_checksum.extend(b"\x00\x00")  # Sub-device
    packet_for_checksum.append(cc)
    packet_for_checksum.extend(struct.pack(">H", pid))
    packet_for_checksum.append(pdl)
    packet_for_checksum.extend(pd)

    checksum = calculate_rdm_checksum(packet_for_checksum)

    # Final RDM message (without Start Code) to be wrapped in a Robe packet
    rdm_message = packet_for_checksum[1:]
    rdm_message.extend(struct.pack(">H", checksum))

    return bytes(rdm_message)


def parse_text_response(pd: bytes):
    """Parses a simple null-terminated string response."""
    try:
        text = pd.decode("utf-8", errors="ignore").strip()
        print(f"    └─ Text: {text}")
        return text
    except Exception as e:
        print(f"    └─ Error decoding text: {e}")
        return None


def parse_supported_parameters(pd: bytes):
    """Parses a list of supported PIDs."""
    pids = struct.unpack(f">{len(pd) // 2}H", pd)
    print("    └─ Supported PIDs:")
    for pid in pids:
        name = RDM_PARAMETER_NAMES.get(pid, "Unknown")
        print(f"        - 0x{pid:04x} ({name})")
    return list(pids)


def parse_device_info(pd: bytes):
    """Parses the DEVICE_INFO response."""
    (
        rdm_version,
        model_id,
        category,
        sw_version,
        footprint,
        personality,
        dmx_address,
        sub_device_count,
        sensor_count,
    ) = struct.unpack(">HHHIHHHHB", pd)
    current_personality = personality >> 8
    total_personalities = personality & 0xFF
    print("    └─ Device Info:")
    print(f"        - RDM Version: {rdm_version >> 8}.{rdm_version & 0xFF}")
    print(f"        - Device Model ID: 0x{model_id:04x}")
    print(f"        - Product Category: 0x{category:04x}")
    print(f"        - Software Version ID: 0x{sw_version:08x}")
    print(f"        - DMX512 Footprint: {footprint}")
    print(
        f"        - DMX512 Personality: {current_personality} of {total_personalities}"
    )
    print(f"        - DMX Start Address: {dmx_address}")
    print(f"        - Sub-device Count: {sub_device_count}")
    print(f"        - Sensor Count: {sensor_count}")
    return {
        "rdm_protocol_version": f"{rdm_version >> 8}.{rdm_version & 0xFF}",
        "device_model_id": model_id,
        "product_category": category,
        "software_version_id": sw_version,
        "dmx512_footprint": footprint,
        "dmx_personality": {
            "current": current_personality,
            "count": total_personalities,
        },
        "dmx_start_address": dmx_address,
        "sub_device_count": sub_device_count,
        "sensor_count": sensor_count,
    }


def parse_dmx_start_address(pd: bytes):
    """Parses the DMX_START_ADDRESS response."""
    address = struct.unpack(">H", pd)[0]
    print(f"    └─ DMX Start Address: {address}")
    return address


def parse_ack(pd: bytes, pid: int, cc: int):
    """Parses a generic ACK response."""
    if not pd:
        print("    └─ Acknowledged (no data).")
        return True
    # For MUTE/UNMUTE, the PD is a 2-byte control field
    elif pid in [DISC_MUTE, DISC_UN_MUTE]:
        control_field = struct.unpack(">H", pd)[0]
        print(f"    └─ Acknowledged. Control Field: 0x{control_field:04x}")
        return control_field
    else:
        print(f"    └─ Acknowledged with data: {pd.hex(' ')}")
        return pd


def parse_discovery_response(rdm_data: bytes):
    """Parses a DISC_UNIQUE_BRANCH response and returns the decoded UID."""
    print("  └─ Parsing Discovery response...")
    try:
        # Find the preamble separator
        separator_index = rdm_data.find(b"\xaa")
        if separator_index == -1:
            print("    └─ Discovery response separator (0xAA) not found.")
            return None

        # The EUID and ECS follow the separator
        euid_ecs_data = rdm_data[separator_index + 1 :]
        if len(euid_ecs_data) < 16:
            print(
                f"    └─ Insufficient data for EUID and Checksum (found {len(euid_ecs_data)} bytes)."
            )
            return None

        euid = euid_ecs_data[:12]
        ecs = euid_ecs_data[12:16]

        # Decode UID
        uid = bytearray()
        for i in range(6):
            uid.append(euid[i * 2] & euid[i * 2 + 1])
        uid = bytes(uid)
        print(f"    ├─ Discovered UID: {uid.hex(':')}")

        # Verify checksum
        calculated_checksum = sum(euid)

        cs_msb = ecs[0] & ecs[1]
        cs_lsb = ecs[2] & ecs[3]
        received_checksum = (cs_msb << 8) | cs_lsb

        if calculated_checksum == received_checksum:
            print(f"    └─ Checksum OK (0x{received_checksum:04x})")
        else:
            print(
                f"    └─ Checksum mismatch! Calculated: 0x{calculated_checksum:04x}, Received: 0x{received_checksum:04x}"
            )

        return uid

    except Exception as e:
        print(f"    └─ Error parsing discovery response: {e}")
        return None


def parse_rdm_response(rdm_data: bytes, sent_pid: int):
    """Parses the core RDM response packet."""
    if not rdm_data:
        print("  └─ Empty RDM data.")
        return None, None

    try:
        sub_start = rdm_data[0]
        msg_len = rdm_data[1]
        dest_uid = rdm_data[2:8]
        src_uid = rdm_data[8:14]
        tn = rdm_data[14]
        response_type = rdm_data[15]
        msg_count = rdm_data[16]
        sub_device = struct.unpack(">H", rdm_data[17:19])[0]
        cc = rdm_data[19]
        pid = struct.unpack(">H", rdm_data[20:22])[0]
        pdl = rdm_data[22]
        pd = rdm_data[23 : 23 + pdl]
        checksum = struct.unpack(">H", rdm_data[-2:])[0]

        print("  ├─ RDM Response:")
        print(f"  │  - Source UID: {src_uid.hex(':')}")
        print(f"  │  - Transaction #: {tn}")
        print(
            f"  │  - Response Type: {RDM_RESPONSE_TYPE_NAMES.get(response_type, 'Unknown')}"
        )
        print(
            f"  │  - Command Class: 0x{cc:02x} ({RDM_PARAMETER_NAMES.get(cc, 'Unknown')}_RESPONSE)"
        )
        print(f"  │  - PID: 0x{pid:04x} ({RDM_PARAMETER_NAMES.get(pid, 'Unknown')})")
        print(f"  │  - PDL: {pdl}")

        response_data = None
        if response_type == 0x00:  # ACK
            if pid == DEVICE_INFO:
                response_data = parse_device_info(pd)
            elif pid == SUPPORTED_PARAMETERS:
                response_data = parse_supported_parameters(pd)
            elif pid in [
                DEVICE_LABEL,
                SOFTWARE_VERSION_LABEL,
                MANUFACTURER_LABEL,
                DEVICE_MODEL_DESCRIPTION,
            ]:
                response_data = parse_text_response(pd)
            elif pid == DMX_START_ADDRESS:
                response_data = parse_dmx_start_address(pd)
            else:
                response_data = parse_ack(pd, pid, cc)
        else:
            print("    └─ Received NACK or other response type.")

        return pid, response_data

    except Exception as e:
        print(f"  └─ Error parsing RDM response: {e} (Data: {rdm_data.hex()})")
        return None, None


def parse_robe_response(response: bytes, sent_pid: int):
    """
    Parses the outer Robe packet, dispatches RDM parsing,
    and returns a status tuple (type, data).
    """
    print("  ├─ Parsing Robe response...")
    if not response or response[0] != HEADER:
        print("  └─ Invalid or empty response.")
        return "error", None

    packet_type = response[1]
    data_len = struct.unpack("<H", response[2:4])[0]
    rdm_data_with_trailer = response[5:-1]

    print(f"  │  - Packet Type: 0x{packet_type:02x}")
    print(f"  │  - Data Length: {data_len}")

    # The Robe API appends 4 bytes to the end of the RDM data
    rdm_data = rdm_data_with_trailer[:-4]

    if packet_type == PACKET_TYPE_RDM_RESPONSE:
        pid, rdm_response_data = parse_rdm_response(rdm_data, sent_pid)
        return "ack", (
            pid,
            rdm_response_data,
        )  # Assuming any standard response is an ACK for our purposes
    elif packet_type == PACKET_TYPE_RDM_DISCOVERY_RESPONSE:
        # Per the Robe API, a 4-byte data length for a discovery response
        # means the interface timed out waiting for a real RDM response.
        if data_len == 4:
            print("  └─ Robe interface reported no RDM device response.")
            return "no_response", None

        uid = parse_discovery_response(rdm_data)
        if uid:
            return "uid", uid
        else:
            # If data was received but couldn't be parsed into a valid UID, it's a collision
            return "collision", rdm_data
    else:
        print(f"  └─ Unhandled packet type: 0x{packet_type:02x}")
        return "unhandled", None


def send_and_receive(
    ser: serial.Serial, description: str, robe_packet: bytes, sent_pid: int = None
):
    """
    Sends a packet, receives, and parses the response, returning a status tuple.
    """
    print(f"Sending: {description} ({robe_packet.hex(' ')})")
    ser.write(robe_packet)
    time.sleep(0.2)
    response = ser.read(ser.in_waiting)

    if response:
        print(f"Received: {response.hex(' ')}")
        status, data = parse_robe_response(response, sent_pid)
    else:
        print("No response received.")
        status, data = "no_response", None

    print("-" * 40)
    time.sleep(0.5)
    return status, data


def binary_search_branch(ser, tn, lower_bound, upper_bound, discovered_uids):
    """
    Recursively searches a branch of the UID tree for RDM devices.
    """
    if lower_bound > upper_bound:
        return tn

    # Base case: If we are searching a single UID, try to mute it.
    if lower_bound == upper_bound:
        print(f"\n--- Checking single UID: {lower_bound:012x} ---")
        uid_to_check = struct.pack(">Q", lower_bound)[2:]

        # Per RDM spec, send DISC_MUTE directly when at the lowest branch.
        # A device will respond with an ACK if it exists at this UID.
        rdm_packet_mute = build_rdm_packet(
            uid_to_check, tn, DISCOVERY_COMMAND, DISC_MUTE
        )
        robe_packet_mute = build_robe_packet(
            PACKET_TYPE_RDM_PACKET_OUT, rdm_packet_mute
        )

        status, data = send_and_receive(
            ser, f"Mute Check ({uid_to_check.hex()})", robe_packet_mute, DISC_MUTE
        )
        tn += 1

        if status == "ack":
            uid = uid_to_check
            if uid not in discovered_uids:
                print(f"--- Found new device: {uid.hex(':')} ---")
                discovered_uids.append(uid)
        return tn

    # Recursive step for a range
    print(f"\n--- Searching range: {lower_bound:012x} to {upper_bound:012x} ---")
    pd = struct.pack(">Q", lower_bound)[2:] + struct.pack(">Q", upper_bound)[2:]
    rdm_packet = build_rdm_packet(
        BROADCAST_ALL_DEVICES_ID, tn, DISCOVERY_COMMAND, DISC_UNIQUE_BRANCH, pd
    )
    robe_packet = build_robe_packet(PACKET_TYPE_RDM_DISCOVERY_UNIQUE_BRANCH, rdm_packet)

    status, data = send_and_receive(
        ser,
        f"Discovery Branch ({lower_bound:012x}-{upper_bound:012x})",
        robe_packet,
        DISC_UNIQUE_BRANCH,
    )
    tn += 1

    # If there was any kind of response (a single UID or a collision),
    # we need to take action.
    if status == "uid":
        uid = data
        if uid not in discovered_uids:
            print(f"--- Found new device: {uid.hex(':')} ---")
            discovered_uids.append(uid)
            # Mute the device so it doesn't respond to further discovery messages
            rdm_packet_mute = build_rdm_packet(uid, tn, DISCOVERY_COMMAND, DISC_MUTE)
            robe_packet_mute = build_robe_packet(
                PACKET_TYPE_RDM_PACKET_OUT, rdm_packet_mute
            )
            send_and_receive(
                ser, f"Mute Device ({uid.hex()})", robe_packet_mute, DISC_MUTE
            )
            tn += 1

        # After muting, search the same range again to find other devices.
        # If the muted device was the only one, the next search will yield 'no_response'.
        tn = binary_search_branch(ser, tn, lower_bound, upper_bound, discovered_uids)

    elif status == "collision":
        print("--- Collision detected, branching... ---")
        mid_point = (lower_bound + upper_bound) // 2
        tn = binary_search_branch(ser, tn, lower_bound, mid_point, discovered_uids)
        tn = binary_search_branch(ser, tn, mid_point + 1, upper_bound, discovered_uids)

    else:  # 'no_response' or other
        print("--- No devices in this range. ---")

    return tn


def discover_all_devices(ser: serial.Serial, tn: int):
    """
    Discovers all RDM devices on the line using a binary search algorithm.
    Finally, it un-mutes all discovered devices.
    """
    discovered_uids = []

    # 1. Un-mute all devices to start fresh
    print("\n--- Sending Un-Mute All to start discovery ---")
    rdm_packet_unmute = build_rdm_packet(
        BROADCAST_ALL_DEVICES_ID, tn, DISCOVERY_COMMAND, DISC_UN_MUTE
    )
    robe_packet_unmute = build_robe_packet(
        PACKET_TYPE_RDM_PACKET_OUT, rdm_packet_unmute
    )
    send_and_receive(ser, "Un-Mute All Devices", robe_packet_unmute, DISC_UN_MUTE)
    tn += 1

    # 2. Start the recursive binary search
    full_range_upper = 0xFFFFFFFFFFFF
    tn = binary_search_branch(ser, tn, 0, full_range_upper, discovered_uids)

    # 3. Un-mute all discovered devices so they can be addressed normally
    if discovered_uids:
        print("\n--- Un-muting all discovered devices ---")
        rdm_packet_unmute_final = build_rdm_packet(
            BROADCAST_ALL_DEVICES_ID, tn, DISCOVERY_COMMAND, DISC_UN_MUTE
        )
        robe_packet_unmute_final = build_robe_packet(
            PACKET_TYPE_RDM_PACKET_OUT, rdm_packet_unmute_final
        )
        send_and_receive(
            ser, "Un-Mute All Devices", robe_packet_unmute_final, DISC_UN_MUTE
        )
        tn += 1
    else:
        print("\n--- No devices were found during discovery. ---")

    return discovered_uids, tn


def get_device_parameters(ser: serial.Serial, discovered_uid: bytes, tn: int):
    """
    Retrieves a standard set of parameters from a discovered RDM device.
    """
    print(f"\n--- Getting parameters for device: {discovered_uid.hex(':')} ---")

    device_data = {"uid": discovered_uid.hex(":")}

    pids_to_get = [
        SUPPORTED_PARAMETERS,
        DEVICE_INFO,
        MANUFACTURER_LABEL,
        DEVICE_MODEL_DESCRIPTION,
        DEVICE_LABEL,
        SOFTWARE_VERSION_LABEL,
        DMX_START_ADDRESS,
    ]

    for pid in pids_to_get:
        rdm_packet = build_rdm_packet(discovered_uid, tn, GET_COMMAND, pid)
        robe_packet = build_robe_packet(PACKET_TYPE_RDM_PACKET_OUT, rdm_packet)

        pid_name = RDM_PARAMETER_NAMES.get(pid, f"0x{pid:04x}")
        status, data = send_and_receive(ser, f"Get {pid_name}", robe_packet, pid)
        tn += 1

        if status == "ack" and data and data[1] is not None:
            # data is (pid, response_data)
            returned_pid, response_data = data
            pid_name_key = RDM_PARAMETER_NAMES.get(
                returned_pid, f"pid_{returned_pid}"
            ).lower()
            device_data[pid_name_key] = response_data

    return device_data, tn


def get_device_info(device_port):
    try:
        ser = serial.Serial(device_port, baudrate=250000, timeout=0.1)
    except Exception as e:
        print(e)
        return False
    robe_packet = build_robe_packet(PACKET_TYPE_RDM_INFO_COMMAND, b"")
    ser.write(robe_packet)
    time.sleep(0.2)
    response = ser.read(ser.in_waiting)
    print("response", response)
    ser.close()
    if response and response[0] == HEADER:
        if response[1] == PACKET_TYPE_RDM_INFO_RESPONSE:
            return True


def get_devices(ser):
    """Main function to run the device search and communication flow."""

    tn = 0  # Transaction Number
    print("--- Starting RDM Discovery ---")
    discovered_uids, tn = discover_all_devices(ser, tn)
    print("found this", discovered_uids)
    return discovered_uids, tn


def get_device_details(ser, uid, tn):
    device_data, tn = get_device_parameters(ser, uid, tn)
    return device_data, tn


if __name__ == "__main__":
    try:
        ser = serial.Serial("/dev/ttyUSB0", baudrate=250000, timeout=0.1)
    except serial.SerialException as e:
        print(f"Error opening serial port: {e}")
    result = get_devices(ser)
    print(f"{result=}")
    tn = 0
    for uid in result:
        device_data, tn = get_device_parameters(ser, uid, tn)
        print(f"{device_data=}")
    ser.close()


def get_port(device_name):
    ser = None
    try:
        ser = serial.Serial(device_name, baudrate=250000, timeout=0.1)
    except serial.SerialException as e:
        print(f"Error opening serial port: {e}")
    return ser
