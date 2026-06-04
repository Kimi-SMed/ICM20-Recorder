'''
Author       : Kimi-SMed fanzhiyao@singularmedical.net
Date         : 2026-06-04 12:24:57
LastEditors  : Kimi-SMed fanzhiyao@singularmedical.net
LastEditTime : 2026-06-04 14:27:15
FilePath     : \ICM2-CoDemo-Ultrasonic\icm\config.py
Description  : 
Copyright (c) 2026 by Singlar Medical, All Rights Reserved. 
'''
"""ICM2 BLE ECG Recorder - Configuration constants"""

import os

# BLE UUIDs (from GEN2 reference icm_control.py:20-23)
UUID_UP_CMD = "5ac73403-3787-4203-856a-38199110db09"
UUID_DOWN_CMD = "5ac73402-3787-4203-856a-38199110db09"
UUID_ECG_DATA = "5ac73503-3787-4203-856a-38199110db09"

# ECG parameters
SAMPLE_RATE_HZ = 250
PACKET_SAMPLES = 32       # samples per BLE notify
PACKET_BYTES = 148        # 74 int16 * 2
ROLLING_WINDOW_PTS = 2500 # 10s * 250Hz per channel

# Handshake
HANDSHAKE_TIMEOUT_S = 20.0

# Device scan filter
DEVICE_NAME_PREFIX = "SM"

# CSV default path (UAC-safe)
CSV_DEFAULT_DIR = os.path.expanduser("~/Documents/ICM_ECG/")

# Amplitude conversion
AMPLITUDE_DIVISOR = 1760  # raw -> mV
