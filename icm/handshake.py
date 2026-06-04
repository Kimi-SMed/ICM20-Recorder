"""ICM2 BLE secret handshake — 5-step challenge-response protocol.

Takes a pre-connected BleakClient as dependency. No BLE connection logic here.
Protocol mirrors icm_control.py:334-399, 1544-1619 exactly.
"""

import os
import zlib
import asyncio
import logging

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic

from icm.crypto import encrypt_CBC, decrypt_CBC, CryptionMessage, append_crc16
from icm.config import UUID_UP_CMD, UUID_DOWN_CMD, HANDSHAKE_TIMEOUT_S

logger = logging.getLogger(__name__)

# BLE command bytes
BLE_CMD_ICC_TO_ICM = 0x31
BLE_CMD_ICM_TO_ICC = 0x32
BLE_CMD_ACKNOWLEDGE = 0xBF


class HandshakeError(Exception):
    """Raised when handshake times out or nonce verification fails."""


class SecretHandshake:
    """Implements the 5-step BLE challenge-response handshake for ICM2.

    Usage:
        hs = SecretHandshake(client, mac_address)
        cryption_msg = await hs.perform()
    """

    def __init__(self, client: BleakClient, mac_address: str) -> None:
        self._client = client
        self._mac = mac_address
        self._seq = 0

        # Shared key template — positions filled from MAC in set_shared_key()
        self._shared_key = bytearray([
            0x00, 0xF1, 0x7A, 0x00, 0x33, 0x2C,
            0x00, 0x5B, 0x14, 0x00, 0x55, 0x71,
            0x00, 0x17, 0x6B, 0x00,
        ])

        self._nonce1: bytearray | None = None
        self._secret_key1: bytearray | None = None
        self._secret_key2: bytearray | None = None

        # Asyncio events for step synchronisation
        self._step4_event = asyncio.Event()   # ICM echoes nonce1 (0x31)
        self._step6_event = asyncio.Event()   # ICM sends nonce2+key2 (0x32)
        self._done_event = asyncio.Event()    # final ACK (0xBF for 0x32)

        self._error: HandshakeError | None = None

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def set_shared_key(self) -> None:
        """Derive shared_key from MAC address octets."""
        parts = self._mac.split(":")
        self._shared_key[0] = int(parts[0], 16)
        self._shared_key[3] = int(parts[3], 16)
        self._shared_key[6] = int(parts[1], 16)
        self._shared_key[9] = int(parts[4], 16)
        self._shared_key[12] = int(parts[2], 16)
        self._shared_key[15] = int(parts[5], 16)
        logger.debug("shared_key set from MAC %s", self._mac)

    def generate_challenge(self) -> bytearray:
        """Generate nonce1 + secret_key1, return AES-CBC encrypted challenge."""
        self._nonce1 = bytearray(os.urandom(16))
        self._secret_key1 = bytearray(os.urandom(16))
        combined = encrypt_CBC(self._shared_key, self._nonce1 + self._secret_key1)
        logger.debug("challenge generated (%d bytes)", len(combined))
        return combined

    # ------------------------------------------------------------------
    # Frame builder
    # ------------------------------------------------------------------

    def _build_handshake_frame(
        self, cmd: int, parameters: bytearray | None = None
    ) -> bytearray:
        """Build the outer BLE frame for a handshake command.

        Inner frame layout:
            [len_byte, seq, cmd, <params>, <crc32_if_params>, checksum]
        Outer frame:
            [0x02] + inner + crc16_LE
        """
        self._seq %= 256

        # Inner frame
        inner = bytearray([4])        # length placeholder (min = 4: len+seq+cmd+checksum)
        inner.append(self._seq)
        inner.append(cmd)

        if parameters is not None:
            inner[0] += len(parameters) + 4   # +4 for the CRC32 that follows params
            inner.extend(parameters)
            crc32 = zlib.crc32(inner[3:])      # CRC over params bytes (index 3 onward)
            inner.extend(crc32.to_bytes(4, byteorder="little"))

        checksum = sum(inner) % 256
        inner.append(checksum)

        self._seq += 1

        # Outer frame
        outer = bytearray([0x02]) + inner
        append_crc16(outer)
        return outer

    # ------------------------------------------------------------------
    # BLE send helper
    # ------------------------------------------------------------------

    async def _send_cmd(self, cmd: int, parameters: bytearray | None = None) -> None:
        frame = self._build_handshake_frame(cmd, parameters)
        hex_str = " ".join(f"{b:02X}" for b in frame)
        logger.debug("TX handshake frame [cmd=0x%02X]: %s", cmd, hex_str)
        await self._client.write_gatt_char(UUID_DOWN_CMD, frame, response=True)

    # ------------------------------------------------------------------
    # Notification handler
    # ------------------------------------------------------------------

    def _make_notify_handler(self):
        """Return a notification handler that drives the handshake state machine."""

        async def handler(
            characteristic: BleakGATTCharacteristic, data: bytearray
        ) -> None:
            hex_str = " ".join(f"{b:02X}" for b in data)
            logger.debug("RX notify: %s", hex_str)

            if len(data) < 5:
                logger.warning("Notification too short (%d bytes), ignoring", len(data))
                return

            command = data[3]
            message = data[4:]

            try:
                if command == BLE_CMD_ICC_TO_ICM:
                    # Step 4: ICM echoed nonce1 encrypted with secret_key1
                    returned_nonce = decrypt_CBC(self._secret_key1, message[0:16])
                    if returned_nonce == self._nonce1:
                        logger.info("Handshake step 4 OK — nonce1 verified")
                        await self._send_cmd(
                            BLE_CMD_ACKNOWLEDGE,
                            bytearray([BLE_CMD_ICC_TO_ICM, 0, 0, 0, 0, 0, 0, 0]),
                        )
                        self._step4_event.set()
                    else:
                        self._error = HandshakeError("nonce1 mismatch")
                        self._done_event.set()

                elif command == BLE_CMD_ICM_TO_ICC:
                    # Step 6: ICM sends nonce2 + secret_key2, encrypted with shared_key
                    encrypted_message = decrypt_CBC(self._shared_key, message[0:32])
                    nonce2 = encrypted_message[0:16]
                    self._secret_key2 = bytearray(encrypted_message[16:32])
                    returned_message = encrypt_CBC(self._secret_key2, nonce2)
                    logger.info("Handshake step 6 OK — sending ICM→ICC response")
                    await self._send_cmd(BLE_CMD_ICM_TO_ICC, returned_message)
                    self._step6_event.set()

                elif command == BLE_CMD_ACKNOWLEDGE:
                    # Step 8: final ACK — handshake complete
                    if len(message) >= 2 and message[0] == BLE_CMD_ICM_TO_ICC and message[1] == 0:
                        logger.info("Handshake complete — final ACK received")
                        self._done_event.set()

            except Exception as exc:
                self._error = HandshakeError(f"Notification handler error: {exc}")
                self._done_event.set()

        return handler

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def perform(self) -> CryptionMessage:
        """Execute the full 5-step handshake.

        Returns CryptionMessage(nonce=secret_key1, key=secret_key2).
        Raises HandshakeError on timeout or protocol violation.
        """
        self.set_shared_key()
        challenge = self.generate_challenge()

        handler = self._make_notify_handler()

        try:
            await self._client.start_notify(UUID_UP_CMD, handler)
            logger.info("Subscribed to UP_CMD notifications")

            # Step 2: Send ICC→ICM challenge
            await self._send_cmd(BLE_CMD_ICC_TO_ICM, challenge)
            logger.info("Handshake step 2: challenge sent")

            # Wait for all steps to complete within the timeout window
            try:
                await asyncio.wait_for(
                    self._done_event.wait(),
                    timeout=HANDSHAKE_TIMEOUT_S,
                )
            except asyncio.TimeoutError:
                raise HandshakeError(
                    f"Handshake timed out after {HANDSHAKE_TIMEOUT_S}s"
                )

        finally:
            try:
                await self._client.stop_notify(UUID_UP_CMD)
            except Exception:
                pass  # best-effort cleanup

        if self._error is not None:
            raise self._error

        if self._secret_key2 is None:
            raise HandshakeError("Handshake ended without secret_key2")

        # CryptionMessage(nonce=secret_key1, key=secret_key2)
        return CryptionMessage(self._secret_key1, self._secret_key2)
