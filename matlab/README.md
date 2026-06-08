# ICM2 BLE ECG Recorder — MATLAB 版

这是 Python 工程（根目录）到 MATLAB 的功能对等移植。实现同样的能力：通过 BLE
从 ICM2 植入式心脏监测仪采集心电数据，加密握手鉴权、维持随访程控权限、实时显示
波形、录制 CSV、录后复查，以及局域网 TCP 远程控制。

## 运行环境

- MATLAB **R2022a 或更高**
- **Bluetooth Toolbox**（真实设备扫描/连接所需）
- 一个支持 BLE 的蓝牙适配器 + 真实 ICM2 GEN2 设备（完整功能所需）
- 远程控制与 demo 服务端用到 `tcpserver`/`tcpclient`（R2022a 起在 MATLAB 基础库中）

无需额外第三方库：AES 与 CRC32 通过 MATLAB 自带的 JVM（`javax.crypto`、
`java.util.zip.CRC32`）实现，CRC16/CRC8 为纯 MATLAB 实现。

## 运行

```matlab
cd matlab
main
```

操作流程与 Python 版一致：

1. 点 **Scan** — 列表刷新，显示名称以 `SM` 开头的 ICM 设备（按 RSSI 排序）
2. 选中设备点 **Connect** — 连接 + 握手 + RTC 同步 + 权限鉴权（约 5 秒，期间界面会短暂阻塞）
3. 握手完成后自动开始 ECG 波形串流
4. 右下角实时显示心率 BPM
5. 点 **Start Recording** 保存 CSV
6. 点 **Stop Recording** 停止保存（波形继续）；该次录制会自动加载到下方复查图
7. 点 **Disconnect** 结束会话
8. CSV 保存在 `~/Documents/ICM_ECG/`

## 运行测试

不依赖硬件的逻辑（加密、CRC、解析、CSV）可直接自测：

```matlab
cd matlab
run_tests          % 或 run('tests/run_tests.m')
```

预期全部通过（10 项）。

## 工程结构

```
matlab/
├── main.m                      % 入口
├── icm_remote.m                % 远程控制客户端（类）
├── icm_server_demo.m           % 调试用服务端
├── +icm/                       % 协议/IO 层（与界面无关）
│   ├── Config.m                % 常量与 UUID
│   ├── Crypto.m                % AES-CBC/ECB + CRC16/CRC8/CRC32（静态方法）
│   ├── CryptionMessage.m       % CTR 流加密上下文
│   ├── SecretHandshake.m       % 5 步握手状态机
│   ├── parseEcgPacket.m        % 148 字节 ECG 包解析
│   ├── markerMap.m             % 标记码 -> 标签表
│   ├── EcgCsvWriter.m          % 流式 CSV 写入
│   ├── IcmBleClient.m          % BLE 扫描/连接/通知/发命令
│   ├── RemoteControlServer.m   % TCP 远程控制服务器
│   └── findCharacteristic.m    % 按特征 UUID 解析 characteristic
├── +ui/
│   ├── MainWindow.m            % 主窗口（编排中枢）
│   ├── EcgPlotWidget.m         % 实时扫描线绘图
│   └── ReviewPlotWidget.m      % 录后复查图
└── tests/
    └── run_tests.m
```

## 与 Python 版的架构差异

**线程模型大幅简化。** Python 版需要「asyncio 后台线程 + 线程安全队列 +
QTimer(50ms) 轮询」来把 bleak 的异步回调安全地搬到 Qt 主线程。MATLAB 是
单线程事件模型：BLE 特征的 `DataAvailableFcn`、`timer` 回调、`tcpserver` 回调
都在 MATLAB 主线程的事件队列中执行。因此：

- ECG 数据回调直接解析并更新绘图/CSV，**不再需要 AsyncBridge、队列和轮询定时器**。
- 跨线程编组（Python 里的 `QMetaObject.invokeMethod`）也不再需要。
- 握手作为同步流程实现：发出挑战后用 `pause` 让出时间片以执行通知回调，直到
  完成或超时（因此 Connect 会短暂阻塞界面约 5 秒）。
- 权限续期（每 14 分钟同步 RTC + SET_HOST_INFO）用 MATLAB `timer` 实现。

**协议字节级保持一致。**

- 握手：MAC 推导 shared_key → AES-CBC 挑战 → 回显验证 → 协商 secret_key2。
- 指令帧：`[0x5A] + AES-CTR(内层帧) + CRC16`；内层帧含 len/seq/cmd/params/CRC32/CRC8。
- 加密：AES-128（CBC/ECB），CTR 计数器按参考固件保持不递增。
- CRC16 = CCITT-FALSE（poly 0x1021, init 0xFFFF）；CRC32 = zlib 兼容；CRC8 为查表实现。
- ECG 包：`typecast(bytes,'int16')` 取 74 个小端 int16，布局与 Python 完全一致。
- ICM 纪元偏移 1609459200（2021-01-01 UTC），时区字节 32（UTC+8）。

## 已知限制

- 实时图刻意禁用缩放/平移（监护仪固定视图）；复查图支持平移与按钮缩放。
- 同一时间仅支持单个 BLE 连接。
- 完整运行需真实 ICM2 GEN2 设备与 Bluetooth Toolbox。
- 远程控制 token（`icm2024`）与端口（9527）为硬编码，仅适合可信局域网。
- MATLAB BLE 连接通常更适合用设备名/地址；不同平台 `ble()` 的标识方式可能略有差异。
```
