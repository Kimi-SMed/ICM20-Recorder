"""ICM2 BLE client — scan, connect, handshake, ECG notify.

All async methods must be called via async_bridge.submit_coro() from Qt thread.
ECG notify callback puts ParsedPacket into async_bridge.data_queue.
Qt QTimer(50ms) drains queue via data_queue.get_nowait().
"""

import asyncio
import logging
import time
from typing import Callable, Dict, List, Optional

from bleak import BleakClient, BleakScanner

from icm.config import UUID_ECG_DATA, DEVICE_NAME_PREFIX
from icm.ecg_parser import parse_ecg_packet
from icm.handshake import SecretHandshake, HandshakeError
from ui.async_bridge import AsyncBridge

logger = logging.getLogger(__name__)


class ICMBleClient:
    """Manages BLE scan, connect, handshake, ECG notify for ICM2 devices."""

    def __init__(self, async_bridge: AsyncBridge) -> None:
        self._bridge = async_bridge
        self._client: Optional[BleakClient] = None
        self._mac: Optional[str] = None
        self._connected: bool = False
        self._recording: bool = False

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
            await hs.perform()
            logger.info("Handshake complete")
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
        logger.info("Disconnected from %s", self._mac)

    def _on_disconnected_cb(self, client: BleakClient) -> None:
        """Bleak callback on unexpected disconnect."""
        logger.warning("Device disconnected: %s", self._mac)
        self._connected = False
        self._recording = False
        if self.on_disconnected:
            self.on_disconnected()

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
