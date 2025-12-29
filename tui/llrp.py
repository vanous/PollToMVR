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

import random
import select
import socket
import struct
import time
import uuid


LLRP_REQUEST_GRP = "239.255.250.133"
LLRP_RESPONSE_GRP = "239.255.250.134"
LLRP_PORT = 5569
LLRP_BROADCAST_CID = "fbad822c-bd0c-4d4c-bdc8-7eabebc85aff"

VECTOR_ROOT_LLRP = 0x0000000A
VECTOR_LLRP_PROBE_REQUEST = 0x00000001
VECTOR_LLRP_PROBE_REPLY = 0x00000002
VECTOR_LLRP_RDM_CMD = 0x00000003

VECTOR_PROBE_REQUEST_DATA = 0x01
VECTOR_PROBE_REPLY_DATA = 0x01
VECTOR_RDM_CMD_RDM_DATA = 0xCC

E120_GET_COMMAND = 0x20
E120_GET_COMMAND_RESPONSE = 0x21
E120_DEVICE_LABEL = 0x0082

RDM_START_CODE = 0xCC
RDM_SUB_START_CODE = 0x01

ACN_PACKET_IDENTIFIER = b"ASC-E1.17\x00\x00\x00"


def _flags_length(length: int) -> bytes:
    return bytes(
        [(0x70 | ((length >> 16) & 0x0F)), (length >> 8) & 0xFF, length & 0xFF]
    )


def _rdm_checksum(data: bytes) -> int:
    return sum(data) & 0xFFFF


def _build_probe_request(manager_cid: uuid.UUID, transaction: int) -> bytes:
    lower_uid = b"\x00" * 6
    upper_uid = b"\xff" * 6
    llrp_filter = 0x0000

    probe_len = 3 + 1 + 6 + 6 + 2
    llrp_len = 3 + 4 + 16 + 4 + probe_len
    root_len = 3 + 4 + 16 + llrp_len

    preamble = struct.pack(">HH12s", 0x0010, 0x0000, ACN_PACKET_IDENTIFIER)
    root_pdu = _flags_length(root_len) + struct.pack(
        ">I16s", VECTOR_ROOT_LLRP, manager_cid.bytes
    )
    llrp_pdu = _flags_length(llrp_len) + struct.pack(
        ">I16sI",
        VECTOR_LLRP_PROBE_REQUEST,
        uuid.UUID(LLRP_BROADCAST_CID).bytes,
        transaction,
    )
    probe_pdu = _flags_length(probe_len) + struct.pack(
        ">B6s6sH", VECTOR_PROBE_REQUEST_DATA, lower_uid, upper_uid, llrp_filter
    )
    return preamble + root_pdu + llrp_pdu + probe_pdu


def _build_rdm_get_label(
    manager_cid: uuid.UUID,
    target_cid: bytes,
    manager_uid: bytes,
    target_uid: bytes,
    transaction: int,
    rdm_transaction: int,
) -> bytes:
    message_length = 24
    rdm_message = bytearray([RDM_START_CODE, RDM_SUB_START_CODE, message_length])
    rdm_message.extend(target_uid)
    rdm_message.extend(manager_uid)
    rdm_message.extend([rdm_transaction & 0xFF, 1, 0])
    rdm_message.extend(b"\x00\x00")
    rdm_message.append(E120_GET_COMMAND)
    rdm_message.extend(struct.pack(">H", E120_DEVICE_LABEL))
    rdm_message.append(0x00)

    checksum = _rdm_checksum(rdm_message)
    rdm_message_no_sc = rdm_message[1:]
    rdm_message_no_sc.extend(struct.pack(">H", checksum))

    rdm_pdu_len = 3 + 1 + len(rdm_message_no_sc)
    llrp_len = 3 + 4 + 16 + 4 + rdm_pdu_len
    root_len = 3 + 4 + 16 + llrp_len

    preamble = struct.pack(">HH12s", 0x0010, 0x0000, ACN_PACKET_IDENTIFIER)
    root_pdu = _flags_length(root_len) + struct.pack(
        ">I16s", VECTOR_ROOT_LLRP, manager_cid.bytes
    )
    llrp_pdu = _flags_length(llrp_len) + struct.pack(
        ">I16sI", VECTOR_LLRP_RDM_CMD, target_cid, transaction
    )
    rdm_pdu = (
        _flags_length(rdm_pdu_len)
        + struct.pack(">B", VECTOR_RDM_CMD_RDM_DATA)
        + rdm_message_no_sc
    )
    return preamble + root_pdu + llrp_pdu + rdm_pdu


def _parse_probe_reply(data: bytes):
    if len(data) < 16 + 23 + 27 + 17:
        return None

    offset = 16
    root_vector = struct.unpack(">I", data[offset + 3 : offset + 7])[0]
    if root_vector != VECTOR_ROOT_LLRP:
        return None
    sender_cid = data[offset + 7 : offset + 23]

    offset += 23
    llrp_vector = struct.unpack(">I", data[offset + 3 : offset + 7])[0]
    if llrp_vector != VECTOR_LLRP_PROBE_REPLY:
        return None

    offset += 27
    if data[offset + 3] != VECTOR_PROBE_REPLY_DATA:
        return None

    uid = data[offset + 4 : offset + 10]
    hw = data[offset + 10 : offset + 16]
    comp_type = data[offset + 16]
    return sender_cid, uid, hw, comp_type


def _parse_rdm_label_response(data: bytes):
    if len(data) < 16 + 23 + 27 + 4:
        return None

    offset = 16 + 23
    llrp_vector = struct.unpack(">I", data[offset + 3 : offset + 7])[0]
    if llrp_vector != VECTOR_LLRP_RDM_CMD:
        return None

    offset += 27
    if data[offset + 3] != VECTOR_RDM_CMD_RDM_DATA:
        return None

    rdm = data[offset + 4 :]
    if len(rdm) < 24:
        return None

    command_class = rdm[20]
    pid = struct.unpack(">H", rdm[21:23])[0]
    pdl = rdm[23]
    if command_class != E120_GET_COMMAND_RESPONSE or pid != E120_DEVICE_LABEL:
        return None

    label = rdm[24 : 24 + pdl].decode("ascii", errors="ignore").strip("\x00")
    return label


class LlrpDiscovery:
    def __init__(self, bind_ip: str | None = None, manufacturer_id: int = 0x7FF0):
        self.bind_ip = bind_ip or "0.0.0.0"
        self.manager_cid = uuid.uuid4()
        device_id = random.getrandbits(32)
        self.manager_uid = struct.pack(">H", manufacturer_id & 0xFFFF) + struct.pack(
            ">I", device_id
        )
        self.rx_socket = None
        self.tx_socket = None

    def start(self):
        self.rx_socket = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
        )
        self.rx_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.rx_socket.bind((self.bind_ip, LLRP_PORT))
        mreq = socket.inet_aton(LLRP_RESPONSE_GRP) + socket.inet_aton(self.bind_ip)
        self.rx_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        self.tx_socket = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
        )
        self.tx_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
        if self.bind_ip != "0.0.0.0":
            self.tx_socket.setsockopt(
                socket.IPPROTO_IP,
                socket.IP_MULTICAST_IF,
                socket.inet_aton(self.bind_ip),
            )

    def stop(self):
        if self.rx_socket:
            self.rx_socket.close()
        if self.tx_socket:
            self.tx_socket.close()

    def discover_devices(self, timeout: float = 1.5):
        devices = {}
        transaction = int(time.time()) & 0xFFFFFFFF
        probe = _build_probe_request(self.manager_cid, transaction=transaction)
        self.tx_socket.sendto(probe, (LLRP_REQUEST_GRP, LLRP_PORT))

        deadline = time.time() + timeout
        while time.time() < deadline:
            remaining = deadline - time.time()
            r, _, _ = select.select([self.rx_socket], [], [], min(0.1, remaining))
            if not r:
                continue
            data, addr = self.rx_socket.recvfrom(1500)
            parsed = _parse_probe_reply(data)
            if not parsed:
                continue
            sender_cid, uid, _hw, comp_type = parsed
            ip = addr[0]
            if ip in devices:
                continue
            devices[ip] = {
                "source_ip": ip,
                "short_name": "",
                "long_name": "",
                "uid": ":".join(f"{b:02x}" for b in uid),
                "component_type": comp_type,
                "target_cid": sender_cid,
                "target_uid": uid,
            }

        if not devices:
            return []

        for index, device in enumerate(devices.values()):
            rdm_packet = _build_rdm_get_label(
                manager_cid=self.manager_cid,
                target_cid=device["target_cid"],
                manager_uid=self.manager_uid,
                target_uid=device["target_uid"],
                transaction=(transaction + index + 1) & 0xFFFFFFFF,
                rdm_transaction=index + 1,
            )
            self.tx_socket.sendto(rdm_packet, (LLRP_REQUEST_GRP, LLRP_PORT))

        label_deadline = time.time() + timeout
        while time.time() < label_deadline:
            remaining = label_deadline - time.time()
            r, _, _ = select.select([self.rx_socket], [], [], min(0.1, remaining))
            if not r:
                continue
            data, addr = self.rx_socket.recvfrom(1500)
            label = _parse_rdm_label_response(data)
            if not label:
                continue
            ip = addr[0]
            if ip in devices:
                devices[ip]["short_name"] = label

        for device in devices.values():
            device.pop("target_cid", None)
            device.pop("target_uid", None)

        return list(devices.values())
