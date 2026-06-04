# ICM2 BLE ECG Recorder

A Windows desktop application for recording ECG data from ICM2 implantable cardiac monitors via BLE.

## Requirements

- Windows 10/11 (64-bit)
- Python 3.10+
- Bluetooth adapter (Windows BLE via WinRT)

## Installation

```bash
# Clone/download the project
cd ICM2-CoDemo-Ultrasonic

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

Dependencies: `bleak`, `cryptography`, `crcmod`, `PyQt5`, `pyqtgraph`, `pytest`, `pandas`

## Running

```bash
python main.py
```

Workflow:

1. Click **Scan** — device list clears and refreshes with discovered ICM devices
2. Select your device, click **Connect** (handshake + RTC sync + permission auth, ~5s)
3. ECG waveform starts streaming automatically after handshake
4. Real-time heart rate (BPM) shown in bottom-right corner
5. Click **Start Recording** to save ECG to CSV
6. Click **Stop Recording** when done — waveform keeps running
7. Click **Disconnect** to end the session — plot resets for next connection
8. CSV files saved to `%USERPROFILE%\Documents\ICM_ECG\`

## Display

- Cardiac-monitor sweep-line mode: waveform writes left→right, wraps and overwrites
- 10-second rolling window at 250 Hz
- Light grey background, blue curve, orange event markers
- Grey dashed cursor line marks the current write position
- Real-time BPM display (bold, bottom-right)

## Permission / Authentication

After handshake, the app automatically sends:
1. `CMD_PROGRAM_RTC_DELTA` (0x30) — syncs device clock to current system time (UTC+8)
2. `CMD_SET_HOST_INFO` (0x20, host_type=2) — grants 随访程控 (follow-up) permission

Both commands repeat every **14 minutes** to maintain the permission session (device enforces a 15-minute timeout). Without this, the device disconnects after ~1 minute.

## Building the Executable

```bash
pip install pyinstaller
pyinstaller --noconfirm icm_recorder.spec
```

Output: `dist\icm_recorder.exe` — runs on clean Windows without Python installed.

## CSV Output Format

Each recording produces one file: `ecg_<MAC>_<YYYYMMDD_HHMMSS>.csv`

| Column | Description |
|--------|-------------|
| timestamp_ms | Unix timestamp in milliseconds |
| sample_index | Global sample counter |
| channel_1 | CH1 raw int16 value |
| channel_2 | CH2 raw int16 value |
| marker_id | Marker type ID (empty if no marker) |
| marker_label | Marker label string (e.g. "S", "VT-ON") |
| rr_ms | RR interval in milliseconds |
| amplitude_mv | R-wave amplitude in mV |

Sample rate: 250 Hz (4 ms per sample)

## Running Tests

```bash
pytest tests/ -v
```

Expected: 30 tests, all pass.

## Project Structure

```
ICM2-CoDemo-Ultrasonic/
├── main.py                  # Application entry point
├── requirements.txt         # Python dependencies
├── icm_recorder.spec        # PyInstaller build spec
├── icm/
│   ├── ble_client.py       # BLE scan/connect/notify + RTC sync + permission auth
│   ├── config.py           # Constants and UUIDs
│   ├── crypto.py           # AES-CTR encryption (CryptionMessage)
│   ├── ecg_parser.py       # ECG packet parser (148-byte BLE notify)
│   ├── ecg_writer.py       # CSV streaming writer
│   └── handshake.py        # 5-step challenge-response handshake
├── ui/
│   ├── async_bridge.py     # asyncio ↔ Qt thread bridge (queue + QTimer)
│   ├── device_panel.py     # Scan list + connect/disconnect buttons
│   ├── main_window.py      # Main window, QTimer poll loop, BLE callbacks
│   └── plot_widget.py      # Sweep-line ECG plot (pyqtgraph, circular buffer)
└── tests/
    ├── test_crypto.py
    ├── test_ecg_parser.py
    ├── test_ecg_writer.py
    └── fixtures/
        └── sample_packets.py
```

## Architecture Notes

### Threading
- asyncio event loop runs in a daemon background thread (`AsyncBridge`)
- BLE notify callbacks → `queue.Queue.put_nowait()` (asyncio thread)
- `QTimer(50ms)` → `queue.Queue.get_nowait()` → plot + CSV (Qt main thread)
- All BLE state callbacks marshalled to Qt thread via `QMetaObject.invokeMethod(QueuedConnection)`

### Command Sequence (post-handshake)
- Handshake seq starts at **1** (matches firmware expectation)
- Post-handshake seq continues from handshake final value (no reset)
- Commands encrypted with `CryptionMessage(secret_key1, secret_key2)` from handshake
- Frame format: `[0x5A] + AES-CTR(inner_frame) + CRC16`

### Key Protocol Constants
- BLE UUIDs: UP_CMD `5ac73403-...`, DOWN_CMD `5ac73402-...`, ECG_DATA `5ac73503-...`
- ECG packet: `struct.unpack("<74h", 148 bytes)` — CH1[0:32], CH2[32:64], markers[64:68], RR[68:72], amplitude[73]
- Permission timeout: 15 minutes (app renews every 14 min)
- ICM epoch offset: `1609459200` (2021-01-01 00:00:00 UTC)

## Known Limitations

- No zoom/pan on ECG plot (intentional — monitor-style fixed view)
- Requires physical ICM2 GEN2 device for full operation
- Single BLE connection at a time
