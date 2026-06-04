# Draft: PC ICM2 BLE ECG Recorder (Final)

## Original Request (User's Words)
> 想做一个可以在 android 平板上跑的 python 脚本，功能类似于：
> 1. 使用蓝牙和 ICM 通讯，具体可以参考 D:\Singular_Medical\ICM_And_ICD_Smart_Measurement_Tool\Dvlp\ICM-GEN1-PC-ATS\core\icm_communication.py
> 2. 将收到的 ecg 数据保存为 csv 格式的文件

## Pivot History
1. **Initial**: Android tablet via Termux + Python script
2. **Research finding**: bleak does NOT work in Termux (no BlueZ on Android, Termux 没 Bluetooth API)
3. **User pivot**: Windows PC desktop app, package via PyInstaller for distribution
4. **Protocol clarification**: User confirmed must use **ICM2 (GEN2) protocol**, not GEN1
5. **Reference shift**: Source moved to GEN2 codebase (`ICM-GEN2-PC-FWIT/ATSPythonBackend/icm_control.py`)

## Final Confirmed Requirements

| Item | Decision |
|---|---|
| Platform | Windows 10/11 PC, Python 3.10+ |
| GUI Framework | PyQt5 (用户已安装) |
| Plotting | PyQtGraph (rolling 20s window = 5000 pts/channel) |
| BLE Library | bleak |
| Encryption | `cryptography` package (NOT pycryptodome - 见下方 ##Library Names) |
| CRC | crcmod |
| Packaging | PyInstaller single .exe |
| Source ref | GEN2 (`icm_control.py`, `command_encryption.py`, `icm_plot.py`, `task_queue.py`) |
| Code reuse | Copy + trim into target dir, NO imports from reference dir |
| Target dir | `D:\Singular_Medical\ICM_GEN2\Dvlp\ICM2-CoDemo-Ultrasonic\` |
| CSV path | `%USERPROFILE%\Documents\ICM_ECG\` (UI 可配置) |
| CSV file naming | `ecg_<MAC>_<YYYYMMDD_HHMMSS>.csv` (一次录制一个文件) |
| Recording flow | Multi-stage: Scan → Connect → Handshake → Start Recording → Stop → 可重录 |
| Sample rate | 250 Hz |
| Handshake timeout | 20 seconds total |
| Marker sentinel | `marker_data == 0` means slot is empty |
| Test infra | NONE exists. Will set up pytest + Agent QA |

## Library Names (CRITICAL - Oracle correction)

`command_encryption.py` 第 4-6 行真实 import：
```python
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
```

**结论**：用 `cryptography` 包，**不是** `pycryptodome`。
- `requirements.txt`: `cryptography>=41.0.0`
- PyInstaller spec: `--collect-all cryptography`
- Metis 推荐的 `pycryptodome` / `Crypto` / `--collect-all Crypto` **作废**

## Confirmed Technical Facts

### ICM BLE Protocol (GEN2)
- **GATT Characteristics**:
  - `5ac73402-3787-4203-856a-38199110db09` (DOWN_CMD) - 写命令
  - `5ac73403-3787-4203-856a-38199110db09` (UP_CMD) - 命令通知（加密）
  - `5ac73503-3787-4203-856a-38199110db09` (ECG_DATA) - ECG 通知（明文）
- **设备发现**: 广播名以 "ICM" 开头
- **握手必需**：即使只接收 ECG，也必须先完成 secret_handshake
- **ECG 通道是明文**：不需要 decrypt

### GEN2 ECG Payload 结构 (CRITICAL)
每个 BLE notify = 一串 int16 LE，按以下偏移解析：

| 偏移 (int16) | 内容 | 长度 |
|---|---|---|
| `[0:32]` | 通道 1 数据 | 32 采样点 |
| `[32:64]` | 通道 2 数据 | 32 采样点 |
| `[64:68]` | 4 个 marker 槽位（低 8 位=包内位置 0-31，高 8 位=marker_id 高字节） | 4 |
| `[68:72]` | 4 个 RR 间隔（毫秒） | 4 |
| `[73]` | R 波振幅（除以 1760 = mV） | 1 |

- 总长度 = 74 个 int16 = 148 字节
- 包间隔 = 32/250 = 128 ms
- **防御性解析**: `if len(data) < 148: log+skip`

### Marker 类型 (从 ICM_STREAM_ECG_MARKER)
- 单字符: S, T, AS
- Pause: P-ON, P+, D-P, P-NS, P-
- Brady: B-ON, B+, D-B, B-NS, B-, B-ReON
- VT: VT-ON, VT+, D-VT, VT-NS, VT-, VT-ReON, VTx
- AT: AT-ON, AT+, D-AT, AT-NS, AT-, AT-ReON, ATx
- AF: AF-ON, AF+, D-AF, AF-NS, AF-, AF-ReON
- PVC: V-P, D-V, V-J
- MGT: MGT+, MGT-
- Morphology: MP+, MP-

### Handshake (GEN1=GEN2，文件 byte-identical)
1. shared_key 派生：MAC 字节填位 0,3,6,9,12,15
2. ICC→ICM: `AES-CBC(shared_key, nonce1+secret_key1)` 32 字节
3. ICM 验证回 nonce1 → ICC 比较 → ACK
4. ICM→ICC: `AES-CBC(shared_key, nonce2+secret_key2)` → ICC 解密
5. ICC 用 secret_key2 加密 nonce2 回发 → ACK
6. 完成: 构造 `CryptionMessage(secret_key1, secret_key2)` (CTR 模式)
7. 后续 ECG 通道不参与加密，**握手后零命令发送**

## CSV Format (FINAL)

单文件、逐采样点展开：

```csv
timestamp_ms,sample_index,channel_1,channel_2,marker_id,marker_label,rr_ms,amplitude_mv
1717000000000,0,1234,5678,,,,
1717000000004,1,1240,5680,,,,
...
1717000000128,32,1300,5720,256,S,800,1.23
```

- 8 列固定 schema
- `timestamp_ms` = `packet_received_ms + (i * 4)` ms (4ms = 1/250Hz)
- `packet_received_ms` 是 BLE 回调实际触发时刻
- `sample_index` 全局递增（不是包内）
- 非 marker 采样点：`marker_id, marker_label, rr_ms, amplitude_mv` 四列留空
- marker 采样点：四列填值（marker_id 是 16-bit 原值，marker_label 是查 stream_marker_map 的字符串）
- 流式写入 (csv.writer)，每包 32 行 flush 一次

## Architecture (FINAL - GUI version)

```
ICM2-CoDemo-Ultrasonic/
├── README.md                  # Windows 安装+运行+打包说明
├── requirements.txt           # bleak, cryptography, crcmod, PyQt5, pyqtgraph, pytest
├── icm_recorder.spec          # PyInstaller spec (--collect-all 各依赖)
├── main.py                    # 入口：构建 QApplication, 启动 asyncio 后台线程, MainWindow.show()
├── icm/
│   ├── __init__.py
│   ├── ble_client.py          # ICMBleClient: 扫描/连接/握手/notify 订阅
│   ├── handshake.py           # SecretHandshake 状态机
│   ├── crypto.py              # 复制 command_encryption.py 全部
│   ├── ecg_parser.py          # parse_ecg_packet() + ICM_STREAM_ECG_MARKER
│   └── ecg_writer.py          # ECGCsvWriter: 流式 CSV 写入
├── ui/
│   ├── __init__.py
│   ├── main_window.py         # QMainWindow: 整体布局 + closeEvent override
│   ├── device_panel.py        # 扫描列表 + 连接按钮 + 状态指示
│   ├── plot_widget.py         # PyQtGraph 双通道波形 + marker 叠加
│   └── async_bridge.py        # asyncio 后台 loop + Qt QTimer 数据桥
├── tests/
│   ├── __init__.py
│   ├── test_crypto.py         # AES-CBC/ECB 单元测试 + CryptionMessage
│   ├── test_ecg_parser.py     # 包解析（含变长、marker、边界）
│   ├── test_ecg_writer.py     # CSV 写入（行数、时间戳、marker 列）
│   └── fixtures/
│       └── sample_packets.py  # 构造的合成 BLE notify payload
└── .omo/                      # 已存在
    └── plans/icm-ecg-recorder.md  # 工作计划（待生成）
```

## GUI Workflow (FINAL)

```
[启动 main.py]
   ↓
QApplication 构建 + asyncio loop 启动后台线程
   ↓
MainWindow 显示
   ┌────────────────────────────────────────────┐
   │ [扫描] [断开] [开始录制] [停止]   状态: Idle │
   ├────────────────────────────────────────────┤
   │ 设备列表:                                   │
   │   ICM-001 (RSSI -65)  AA:BB:...   [选中]  │
   │   ICM-002 (RSSI -78)  CC:DD:...           │
   ├────────────────────────────────────────────┤
   │  CH1 ┌─────────────────────────────┐       │
   │      │  ╱╲    ╱╲S    ╱╲   ╱╲     │       │
   │      │ ╱  ╲  ╱  ╲   ╱  ╲ ╱  ╲    │       │
   │      └─────────────────────────────┘       │
   │  CH2 ┌─────────────────────────────┐       │
   │      │  ─────────────────────────  │       │
   │      └─────────────────────────────┘       │
   ├────────────────────────────────────────────┤
   │ HR: 75 bpm    Amplitude: 1.23 mV           │
   │ 已记录: 1234 samples (4.94 s)              │
   │ 文件: Documents\ICM_ECG\ecg_..._20260604_104530.csv │
   └────────────────────────────────────────────┘

[扫描] → bleak.BleakScanner.discover() 5s → 列表填入 "ICM*" 设备
[选中+连接] → BleakClient.connect() → 自动 secret_handshake (20s 超时)
[开始录制] → 打开 CSV + start_notify(ECG_UUID) + 启动 QTimer 50ms 轮询
[停止] → stop_notify + flush+close CSV，可再次开始
[关闭窗口] → closeEvent: 录制中 → 自动停止+保存 → 才允许关闭
```

## Threading / Async Architecture (MUST FOLLOW)

```python
# main.py
loop = asyncio.new_event_loop()
asyncio_thread = threading.Thread(target=loop.run_forever, daemon=True)
asyncio_thread.start()

# Qt 槽 → 提交 bleak 协程
def on_scan_clicked(self):
    asyncio.run_coroutine_threadsafe(
        self.ble_client.scan(),
        self.async_loop
    )

# bleak notify 回调 (asyncio 线程) → 投递到 queue.Queue
def _on_ecg_notify(self, char, data):
    parsed = parse_ecg_packet(data)
    self.data_queue.put_nowait(parsed)

# Qt 主线程 QTimer(50ms) → 取 queue → 更新 UI + 写 CSV
def _poll_data_queue(self):
    while not self.data_queue.empty():
        packet = self.data_queue.get_nowait()
        self.plot_widget.append_packet(packet)
        self.csv_writer.write_packet(packet)
```

**严禁**:
- ❌ Qt 槽里 `asyncio.run()` / `run_until_complete()`
- ❌ bleak 回调里直接调 Qt widget 方法
- ❌ 引入 `qasync` 库
- ❌ 用 `asyncio.run()` 启动 loop（要用 `loop.run_forever()` 才能跨线程提交）

## PyInstaller .spec 要点

```python
# icm_recorder.spec (片段)
a = Analysis(['main.py'],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    ...)

# 必须 --collect-all 的包
collect_all = ['bleak', 'winrt', 'PyQt5', 'pyqtgraph', 'cryptography']
# winrt 是 bleak 在 Windows 下的依赖
```

构建命令: `pyinstaller --noconfirm icm_recorder.spec`

部署目标: 单 `dist/icm_recorder.exe` 可在裸 Windows 10/11 (无 Python) 运行。

## Hard Guardrails

### 必须不做
- ❌ 复制 USB CDC / DMM / 电源 / ATS 测试序列代码
- ❌ 实现命令通道发送（握手后零命令发送）
- ❌ 修改 `ICM-GEN2-PC-FWIT\ATSPythonBackend\` 任何文件
- ❌ 添加 GEN1 兼容
- ❌ 添加配置文件持久化（除 CSV 路径外，无 INI/JSON）
- ❌ 添加云上传 / REST API / OTA / 远程监控
- ❌ 添加 zoom/pan/export/FFT/spectrogram
- ❌ CSV 加 metadata 头部块
- ❌ 用 `pycryptodome`（用 `cryptography`）

### 必须做
- ✅ `len(data) < 148` 防御性检查
- ✅ deque(maxlen=5000) 滚动窗口
- ✅ closeEvent 重写
- ✅ BLE disconnected 回调里关 CSV
- ✅ disk full / OSError 处理
- ✅ asyncio 后台线程 + queue.Queue + QTimer 50ms 桥接

## Test Strategy

- **单元测试** (pytest, 自动化, 在 plan 范围内):
  - test_crypto.py: AES-CBC encrypt/decrypt round-trip, CryptionMessage 加解密
  - test_ecg_parser.py: 标准 148B 包、变长包（短包丢弃）、含 marker 包、marker=0 边界
  - test_ecg_writer.py: 行数与时间戳单调、marker 列稀疏正确、文件 close 后可读
- **Agent QA** (在 plan 范围内, 强制每个任务):
  - 启动应用 → 截图主窗口
  - 扫描按钮（无 ICM 设备时） → tmux 看 stdout 日志/错误处理
  - CSV writer 用合成数据跑通 → 检查输出文件结构
  - PyInstaller 打包 → 启动 exe → 截图
  - 注意：所有 QA 不依赖真实 ICM 硬件
- **真实硬件集成验收** (OUT of scope, 用户验收阶段):
  - 与真实 ICM2 设备的端到端测试由用户自己在收到交付后完成
  - Prometheus 生成的 plan 不包括需要真实硬件的任务
  - 这是用户接受性测试 (UAT)，不是 Sisyphus 执行范围

## All Decisions Made (Recap Table)

| 问题 | 决策 |
|---|---|
| 部署平台 | Windows PC (放弃 Android Termux) |
| 协议版本 | GEN2 (ICM2) |
| GUI | PyQt5 + PyQtGraph |
| 实时窗口 | 20 秒滚动 (5000 点/通道) |
| CSV 路径 | %USERPROFILE%\Documents\ICM_ECG\ (UI 可配) |
| CSV 命名 | ecg_<MAC>_<时间戳>.csv (一次一文件) |
| CSV schema | 8 列，逐采样点展开 |
| 采样率 | 250 Hz |
| 握手超时 | 20 秒 |
| Marker 哨兵 | marker_data == 0 |
| 加密库 | cryptography (不是 pycryptodome) |
| 打包 | PyInstaller single exe |
| 项目位置 | 当前目录直接放 |
| 测试 | pytest 单元测试 + Agent QA |
| 命令通道 | 不实现 (握手后零发送) |
