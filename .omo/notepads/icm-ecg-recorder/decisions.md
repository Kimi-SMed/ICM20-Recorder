# Decisions - icm-ecg-recorder

## 2026-06-04 Atlas Session Init

### Architecture Decisions
- Platform: Windows PC, Python 3.10+
- GUI: PyQt5 + PyQtGraph
- BLE: bleak (WinRT backend on Windows)
- Encryption: cryptography package (NOT pycryptodome)
- Packaging: PyInstaller single .exe

### Threading Decision
- asyncio.new_event_loop() + threading.Thread(target=loop.run_forever)
- NO qasync, NO asyncio.run() in Qt slots
- queue.Queue (thread-safe) for asyncio->Qt data bridge
- QTimer(50ms) in Qt thread to drain queue

### CSV Decision
- One file per recording session
- ecg_<MAC>_<YYYYMMDD_HHMMSS>.csv naming
- 8 fixed columns, streaming write, flush every packet
- Path: ~/Documents/ICM_ECG/ (UAC-safe)

### No Command Channel
- After handshake: zero commands sent post-handshake
- ECG channel is plaintext -- no decryption needed after handshake

### Plot Buffer
- deque(maxlen=5000) per channel (20s at 250Hz)

### Test Strategy
- pytest unit tests for crypto, parser, writer
- No real hardware tests in plan scope
- Agent QA for UI + CSV + packaging

## 2026-06-04 Hardware Debugging Session — Updated Decisions

### Permission Command Channel (replaces "No Command Channel")
- Post-handshake commands ARE required for device to stay connected
- Sequence: sync_rtc() -> set_host_info() immediately after handshake
- Renewal: QTimer(14 * 60 * 1000) repeats both commands every 14 min
- Commands encrypted with CryptionMessage from handshake

### Sequence Number Continuity
- SecretHandshake._seq starts at 1 (matches firmware)
- perform() returns (CryptionMessage, final_seq) tuple
- ble_client._seq = final_seq after handshake, increments from there
- Never reset seq on disconnect until full object recreation

### Plot Buffer (updated)
- Replaced deque with fixed numpy circular buffer (ROLLING_WINDOW_PTS=2500, 10s)
- Sweep-line monitor mode instead of scrolling
- Marker eviction by buf_idx membership in overwrite_set (not by age/count)

### UI Thread Safety
- All BLE->UI callbacks via QMetaObject.invokeMethod(QueuedConnection)
- @pyqtSlot decorators on all target methods
- No direct widget access from asyncio thread ever

### Logging
- DEBUG level enabled in main.py for hardware debugging
- Can revert to INFO for production build
