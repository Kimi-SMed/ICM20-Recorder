# Learnings - icm-ecg-recorder

## 2026-06-04 Atlas Session Init

### BLE UUIDs (from icm_control.py:20-23)
- UUID_UP_CMD = "5ac73403-3787-4203-856a-38199110db09"
- UUID_DOWN_CMD = "5ac73402-3787-4203-856a-38199110db09"
- UUID_ECG_DATA = "5ac73503-3787-4203-856a-38199110db09"

### ECG Packet Format (from icm_control.py notify_handler)
- int16 LE unpacking: struct.unpack("<74h", data) -- 74 int16s = 148 bytes
- [0:32] = CH1, [32:64] = CH2
- [64:68] = 4 marker slots (low byte = position in packet, high byte = marker_id)
- marker sentinel: if marker_data == 0 -> skip
- marker_type key = marker_data & 0xFF00
- [68:72] = 4 RR interval values (ms)
- [73] = R amplitude (divide by 1760 = mV)
- Defensive check: if len(data) < 148 -> skip

### Handshake Protocol (from icm_control.py:334-399, 1544-1619)
- BLE_CMD_ICC_TO_ICM = 0x31, BLE_CMD_ICM_TO_ICC = 0x32, BLE_CMD_ACKNOWLEDGE = 0xBF
- Step1: set_shared_key() - MAC bytes -> positions 0,3,6,9,12,15 of shared_key
- Step2: generate_challenge() - random nonce1+secret_key1, AES-CBC encrypt with shared_key
- Step3: send 0x31 with 32-byte challenge
- Step4: ICM returns encrypted nonce1 -- decrypt with secret_key1, verify == nonce1
- Step5: send ACK [0x31, 0,0,0,0,0,0,0]
- Step6: ICM sends 0x32 -- decrypt with shared_key -> nonce2+secret_key2
- Step7: encrypt nonce2 with secret_key2, send 0x32 response
- Step8: ICM sends ACK [0x32, 0] -> success
- Final: CryptionMessage(secret_key1, secret_key2) -- ECG channel is PLAINTEXT

### BLE Command Frame Structure
- Handshake: [0x02] + [len, seq, cmd, params, crc32, checksum] + crc16_LE
- generate_general_cmd builds the inner frame

### Threading (MUST follow)
- asyncio loop in daemon thread via loop.run_forever()
- BLE callback -> queue.Queue.put_nowait()
- Qt QTimer(50ms) -> queue.Queue.get_nowait() -> plot + CSV

### Encryption Library
- 'cryptography' package (NOT pycryptodome)
- from cryptography.hazmat.backends import default_backend
- from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

### CSV: 8 cols
timestamp_ms, sample_index, channel_1, channel_2, marker_id, marker_label, rr_ms, amplitude_mv
- timestamp_ms = packet_received_ms + (i * 4)
- Non-marker rows: last 4 cols empty; flush every 32 rows

### ICM_STREAM_ECG_MARKER key lookup
- Key = marker_data & 0xFF00
- NIL=0x0000, S=0x0100, T=0x0200, AS=0x0300
- Pause:0x1100-0x1500, Brady:0x2100-0x2600, VT:0x3100-0x3700
- AT:0x4100-0x4700, AF:0x5100-0x5600
- PVC:0x6100-0x6300, MGT:0x7100-0x7200, Morph:0x8100-0x8200
