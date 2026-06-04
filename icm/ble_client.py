"""ICM2 BLE client — scan, connect, handshake, ECG notify.

All async methods must be called via async_bridge.submit_coro() from Qt thread.
ECG notify callback puts ParsedPacket into async_bridge.data_queue.
Qt QTimer(50ms) drains queue via data_queue.get_nowait().
"""

import asyncio
import logging
import random
import struct
import time
import zlib
from typing import Callable, Dict, List, Optional
from bleak import BleakClient, BleakScanner

from icm.config import UUID_ECG_DATA, UUID_DOWN_CMD, UUID_UP_CMD, DEVICE_NAME_PREFIX
from icm.crypto import CryptionMessage, append_crc16
from icm.ecg_parser import parse_ecg_packet
from icm.handshake import SecretHandshake, HandshakeError
from ui.async_bridge import AsyncBridge

logger = logging.getLogger(__name__)

# CMD_SET_HOST_INFO = 0x20, host_type=2 (随访程控权限)
_CMD_SET_HOST_INFO = 0x20
_HOST_TYPE_FOLLOW_UP = 2

# CMD_PROGRAM_RTC_DELTA = 0x30 (时间同步)
_CMD_PROGRAM_RTC_DELTA = 0x30
_ICM_EPOCH_OFFSET = 1609459200  # ICM epoch = 2021-01-01 00:00:00 UTC
_TIME_ZONE_UTC8 = 32            # 32/4 * 3600 = UTC+8


def _build_host_info_payload() -> bytes:
    """Build the 16-byte HOST_INFO payload: 12-byte serial + host_type + 3 reserved."""
    serial = str(random.randint(100000000000, 999999999999)).encode()
    return struct.pack('<12sBBBB', serial, _HOST_TYPE_FOLLOW_UP, 0, 0, 0)


def _build_cmd_struct(seq: int, cmd: int, data: Optional[bytes] = None) -> bytearray:
    """Build cmd_struct exactly as create_icm_cmd does.

    Format: [len, seq, cmd, <data>, <data_crc32>, <crc8>]
    This matches icm_control.create_icm_cmd().
    """
    if data is None:
        frame = struct.pack('<BBB', 4, seq & 0xFF, cmd)
        crc8_val = _crc8(frame)
        return bytearray(frame) + bytearray([crc8_val])
    else:
        data_crc32 = struct.pack('<I', zlib.crc32(data) & 0xFFFFFFFF)
        frame = struct.pack('<BBB', len(data) + 4, seq & 0xFF, cmd)
        frame = frame + data + data_crc32
        crc8_val = _crc8(frame)
        return bytearray(frame) + bytearray([crc8_val])


def _crc8(data: bytes) -> int:
    """CRC8 lookup table matching icm_control.crc8()."""
    crc8_tab = [
        0x00, 0x31, 0x62, 0x53, 0xc4, 0xf5, 0xa6, 0x97, 0xb9, 0x88, 0xdb, 0xea, 0x7d, 0x4c, 0x1f, 0x2e,
        0x43, 0x72, 0x21, 0x10, 0x87, 0xb6, 0xe5, 0xd4, 0xfa, 0xcb, 0x98, 0xa9, 0x3e, 0x0f, 0x5c, 0x6d,
        0x86, 0xb7, 0xe4, 0xd5, 0x42, 0x73, 0x20, 0x11, 0x3f, 0x0e, 0x5d, 0x6c, 0xfb, 0xca, 0x99, 0xa8,
        0xc5, 0xf4, 0xa7, 0x96, 0x01, 0x30, 0x63, 0x52, 0x7c, 0x4d, 0x1e, 0x2f, 0xb8, 0x89, 0xda, 0xeb,
        0x3d, 0x0c, 0x5f, 0x6e, 0xf9, 0xc8, 0x9b, 0xaa, 0x84, 0xb5, 0xe6, 0xd7, 0x40, 0x71, 0x22, 0x13,
        0x7e, 0x4f, 0x1c, 0x2d, 0xba, 0x8b, 0xd8, 0xe9, 0xc7, 0xf6, 0xa5, 0x94, 0x03, 0x32, 0x61, 0x50,
        0xbb, 0x8a, 0xd9, 0xe8, 0x7f, 0x4e, 0x1d, 0x2c, 0x02, 0x33, 0x60, 0x51, 0xc6, 0xf7, 0xa4, 0x95,
        0xf8, 0xc9, 0x9a, 0xab, 0x3c, 0x0d, 0x5e, 0x6f, 0x41, 0x70, 0x23, 0x12, 0x85, 0xb4, 0xe7, 0xd6,
        0x7a, 0x4b, 0x18, 0x29, 0xbe, 0x8f, 0xdc, 0xed, 0xc3, 0xf2, 0xa1, 0x90, 0x07, 0x36, 0x65, 0x54,
        0x39, 0x08, 0x5b, 0x6a, 0xfd, 0xcc, 0x9f, 0xae, 0x80, 0xb1, 0xe2, 0xd3, 0x44, 0x75, 0x26, 0x17,
        0xfc, 0xcd, 0x9e, 0xaf, 0x38, 0x09, 0x5a, 0x6b, 0x45, 0x74, 0x27, 0x16, 0x81, 0xb0, 0xe3, 0xd2,
        0xbf, 0x8e, 0xdd, 0xec, 0x7b, 0x4a, 0x19, 0x28, 0x06, 0x37, 0x64, 0x55, 0xc2, 0xf3, 0xa0, 0x91,
        0x47, 0x76, 0x25, 0x14, 0x83, 0xb2, 0xe1, 0xd0, 0xfe, 0xcf, 0x9c, 0xad, 0x3a, 0x0b, 0x58, 0x69,
        0x04, 0x35, 0x66, 0x57, 0xc0, 0xf1, 0xa2, 0x93, 0xbd, 0x8c, 0xdf, 0xee, 0x79, 0x48, 0x1b, 0x2a,
        0xc1, 0xf0, 0xa3, 0x92, 0x05, 0x34, 0x67, 0x56, 0x78, 0x49, 0x1a, 0x2b, 0xbc, 0x8d, 0xde, 0xef,
        0x82, 0xb3, 0xe0, 0xd1, 0x46, 0x77, 0x24, 0x15, 0x3b, 0x0a, 0x59, 0x68, 0xff, 0xce, 0x9d, 0xac,
    ]
    result = 0
    for b in data:
        result = crc8_tab[(result ^ b) & 0xFF]
    return result


def _build_general_cmd(seq: int, cmd: int, data: Optional[bytes] = None) -> bytearray:
    """Assemble inner command frame as generate_general_cmd does.

    This is the frame that gets encrypted and sent.
    It is built from cmd_code + params extracted from cmd_struct,
    matching the send_icm_cmd → generate_cmd → generate_general_cmd path.

    cmd_struct = [len, seq, cmd, <data>, <data_crc32>, <crc8>]
    params passed to generate_general_cmd = cmd_struct[3:-1] = <data> + <data_crc32>
    generate_general_cmd then appends ANOTHER crc32 over params + checksum.
    """
    # Step 1: build cmd_struct (same as create_icm_cmd)
    cmd_struct = _build_cmd_struct(seq, cmd, data)

    # Step 2: extract params as send_icm_cmd does: cmd_struct[3:-1]
    params = bytes(cmd_struct[3:-1]) if len(cmd_struct) > 3 else None

    # Step 3: call generate_general_cmd logic with cmd and params
    frame = bytearray([4, seq & 0xFF, cmd])
    if params is not None:
        frame[0] += len(params) + 4
        frame.extend(params)
        crc32 = zlib.crc32(frame[3:]) & 0xFFFFFFFF
        frame.extend(crc32.to_bytes(4, byteorder='little'))
    frame.append(sum(frame) % 256)
    return frame


class ICMBleClient:
    """Manages BLE scan, connect, handshake, ECG notify for ICM2 devices."""

    def __init__(self, async_bridge: AsyncBridge) -> None:
        self._bridge = async_bridge
        self._client: Optional[BleakClient] = None
        self._mac: Optional[str] = None
        self._connected: bool = False
        self._recording: bool = False
        self._cryption: Optional[CryptionMessage] = None  # set after handshake
        self._seq: int = 0

        # UI callback hooks (called from asyncio thread)
        self.on_connected: Optional[Callable[[str], None]] = None
        self.on_disconnected: Optional[Callable[[], None]] = None
        self.on_handshake_done: Optional[Callable[[], None]] = None
        self.on_handshake_error: Optional[Callable[[str], None]] = None
        self.on_scan_result: Optional[Callable[[List[Dict]], None]] = None

    async def scan(self, timeout: float = 5.0) -> List[Dict]:
        """Scan for ICM BLE devices. Returns list of {name, address, rssi} dicts."""
        logger.info("Starting BLE scan (%ss)", timeout)
        try:
            devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
        except Exception as e:
            logger.error("BLE scan failed: %s", e)
            return []

        results = []
        for device, adv_data in devices.values():
            name = device.name or (adv_data.local_name if adv_data else "") or ""
            if name.upper().startswith(DEVICE_NAME_PREFIX):
                rssi = getattr(adv_data, "rssi", -99) if adv_data else -99
                results.append({
                    "name": name,
                    "address": device.address,
                    "rssi": rssi if rssi is not None else -99,
                })

        results.sort(key=lambda d: d["rssi"], reverse=True)
        logger.info("Found %d ICM device(s)", len(results))

        if self.on_scan_result:
            self.on_scan_result(results)
        return results

    async def connect(self, mac_address: str) -> None:
        """Connect and perform handshake. Raises HandshakeError / BleakError on failure."""
        if self._connected:
            logger.warning("Already connected")
            return

        self._mac = mac_address
        self._client = BleakClient(
            mac_address,
            disconnected_callback=self._on_disconnected_cb,
        )

        logger.info("Connecting to %s", mac_address)
        await asyncio.wait_for(self._client.connect(), timeout=20.0)
        self._connected = True
        logger.info("Connected to %s", mac_address)

        if self.on_connected:
            self.on_connected(mac_address)

        try:
            hs = SecretHandshake(self._client, mac_address)
            self._cryption, self._seq = await hs.perform()
            logger.info("Handshake complete, next seq=%d", self._seq)
            if self.on_handshake_done:
                self.on_handshake_done()
        except HandshakeError as e:
            logger.error("Handshake failed: %s", e)
            if self.on_handshake_error:
                self.on_handshake_error(str(e))
            raise

    async def start_recording(self) -> None:
        """Subscribe to ECG DATA notifications."""
        if not self._connected or self._client is None:
            raise RuntimeError("Not connected")
        if self._recording:
            return
        await self._client.start_notify(UUID_ECG_DATA, self._on_ecg_notify)
        self._recording = True
        logger.info("ECG recording started")

    async def stop_recording(self) -> None:
        """Unsubscribe from ECG DATA notifications."""
        if not self._recording or self._client is None:
            return
        try:
            await self._client.stop_notify(UUID_ECG_DATA)
        except Exception as e:
            logger.warning("stop_notify error: %s", e)
        self._recording = False
        logger.info("ECG recording stopped")

    async def sync_rtc(self) -> None:
        """Send CMD_PROGRAM_RTC_DELTA (0x30) to sync device clock.

        Required before SET_HOST_INFO per reference icm_control.py run_test_4 sequence.
        timestamp = current Unix time - ICM_EPOCH_OFFSET (2021-01-01)
        timezone  = 32 → UTC+8
        """
        if not self._connected or self._client is None or self._cryption is None:
            return
        try:
            timestamp = int(time.time()) - _ICM_EPOCH_OFFSET
            payload = struct.pack('<Ibbbb', timestamp, _TIME_ZONE_UTC8, 0, 0, 0)
            inner = _build_general_cmd(self._seq, _CMD_PROGRAM_RTC_DELTA, payload)
            self._seq = (self._seq + 1) % 256
            encrypted = self._cryption.encrypt(bytearray(inner))
            frame = bytearray([0x5A]) + encrypted
            append_crc16(frame)
            await self._client.write_gatt_char(UUID_DOWN_CMD, frame, response=True)
            logger.info("RTC sync sent (delta=%d, tz=%d)", timestamp, _TIME_ZONE_UTC8)
        except Exception as e:
            logger.error("sync_rtc failed: %s", e, exc_info=True)

    async def set_host_info(self) -> None:
        """Send CMD_SET_HOST_INFO (0x20) with host_type=2 (随访程控权限).

        Must be called after handshake. Encrypted with CryptionMessage.
        Call once after handshake, then every <15 minutes to maintain permission.
        """
        if not self._connected or self._client is None:
            logger.warning("set_host_info: not connected, skipping")
            return
        if self._cryption is None:
            logger.warning("set_host_info: no cryption key, skipping")
            return

        try:
            payload = _build_host_info_payload()
            inner = _build_general_cmd(self._seq, _CMD_SET_HOST_INFO, payload)
            self._seq = (self._seq + 1) % 256

            inner_hex = ' '.join(f'{b:02X}' for b in inner)
            logger.info("SET_HOST_INFO inner frame: %s", inner_hex)

            encrypted = self._cryption.encrypt(bytearray(inner))
            frame = bytearray([0x5A]) + encrypted
            append_crc16(frame)

            hex_str = ' '.join(f'{b:02X}' for b in frame)
            logger.info("Sending SET_HOST_INFO (host_type=2, seq=%d): %s", self._seq - 1, hex_str)

            await self._client.write_gatt_char(UUID_DOWN_CMD, frame, response=True)
            logger.info("SET_HOST_INFO write OK")
        except Exception as e:
            logger.error("set_host_info failed: %s", e, exc_info=True)

    async def disconnect(self) -> None:
        """Stop recording and disconnect cleanly."""
        if self._recording:
            await self.stop_recording()
        if self._client and self._connected:
            try:
                await asyncio.wait_for(self._client.disconnect(), timeout=5.0)
            except Exception as e:
                logger.warning("Disconnect error: %s", e)
        self._connected = False
        self._client = None
        self._cryption = None
        self._seq = 0
        logger.info("Disconnected from %s", self._mac)

    def _on_disconnected_cb(self, client: BleakClient) -> None:
        """Bleak callback on unexpected disconnect."""
        logger.warning("Device disconnected: %s", self._mac)
        self._connected = False
        self._recording = False
        if self.on_disconnected:
            self.on_disconnected()

    def _on_cmd_indication(self, characteristic, data: bytearray) -> None:
        """UP_CMD indication handler for general command responses after handshake.

        Decrypts the response (if cryption key available) and logs it.
        Device expects this subscription to be active to deliver ACKs.
        """
        if self._cryption is not None:
            try:
                decrypted = self._cryption.decrypt(bytearray(data[1:-2]))
                hex_str = ' '.join(f'{b:02X}' for b in decrypted)
                logger.debug("UP_CMD indication (decrypted): %s", hex_str)
            except Exception as e:
                logger.debug("UP_CMD indication decrypt error: %s", e)
        else:
            hex_str = ' '.join(f'{b:02X}' for b in data)
            logger.debug("UP_CMD indication (raw): %s", hex_str)

    def _on_ecg_notify(self, characteristic, data: bytearray) -> None:
        """BLE notify callback — runs in asyncio thread. Puts ParsedPacket into queue."""
        received_ms = int(time.time() * 1000)
        packet = parse_ecg_packet(bytes(data), received_ms=received_ms)
        if packet is not None:
            self._bridge.put_data(packet)

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def mac_address(self) -> Optional[str]:
        return self._mac
