# Issues - icm-ecg-recorder

## 2026-06-04 Atlas Session Init
No issues logged yet. Session starting.

## 2026-06-04 Hardware Debugging Session — Resolved Issues

### [RESOLVED] No ECG data after connect
- Symptom: handshake OK, no waveform
- Root cause 1: start_recording() never called — it was gated behind "Start Recording" button
- Root cause 2: BLE callbacks called Qt UI from asyncio thread (thread-safety violation)
- Fix: auto-call start_recording() in _qt_on_handshake_done; marshal all callbacks via QMetaObject

### [RESOLVED] Device disconnects after ~1 minute
- Symptom: GattSessionStatus.CLOSED ~60s after connect
- Root cause 1: No permission command sent (CMD_SET_HOST_INFO never implemented)
- Root cause 2: seq reset to 0 after handshake; device rejected commands with wrong seq
- Root cause 3: RTC not synced before SET_HOST_INFO (reference run_test_4 requires it)
- Fix: seq starts at 1, passed through from handshake; sync_rtc() + set_host_info() called
  immediately after handshake and every 14 minutes

### [RESOLVED] Marker ghost on sweep-line display
- Symptom: two identical markers visible simultaneously during wrap-around
- Root cause: old TextItem not removed before write pointer overwrites that buffer position
- Fix: _evict_markers(overwrite_set) called before writing new samples
