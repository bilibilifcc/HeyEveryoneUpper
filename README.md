# HeyEveryoneUpper — 接收机上位机 GUI

基于 ESP-NOW 的多对一课堂互动装置的上位机监控程序。配合 [HeyEveryone](https://github.com/your-repo/HeyEveryone) 固件使用，通过串口读取接收机数据，实时展示每个发送机的按键和编码器状态。

## 架构

```
发送机 1 ─┐
发送机 2 ─┤ ESP-NOW ── 接收机 (ESP8266) ── UART ── HeyEveryoneUpper (本程序)
发送机 3 ─┘
```

## 界面示意

```
┌─────────────────────────────────────────────────┐
│ [Port: COM3 ▼] [Baud: 115200 ▼] [Connect]  ●   │  ← 顶部工具栏
├─────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  TX #0   │  │  TX #1   │  │  TX #2   │       │
│  │  ┌─────┐ │  │  ┌─────┐ │  │  ┌─────┐ │       │
│  │  │  ▲  │ │  │  │  ▲  │ │  │  │  ▲  │ │       │
│  │  │◀ ● ▶│ │  │  │◀ ● ▶│ │  │  │◀ ● ▶│ │       │
│  │  │  ▼  │ │  │  │  ▼  │ │  │  │  ▼  │ │       │
│  │  │ A B │ │  │  │ A B │ │  │  │ A B │ │       │
│  │  └─────┘ │  │  └─────┘ │  │  └─────┘ │       │
│  │  Enc: 42 │  │  Enc: -3 │  │  Enc: 128│       │
│  └──────────┘  └──────────┘  └──────────┘       │
│  ┌──────────┐                                    │
│  │  TX #3   │  ...                               │
│  └──────────┘                                    │
└─────────────────────────────────────────────────┘
```

每张卡片实时展示对应发送机的：
- **7 个按键**：方向键（▲ ◀ ● ▶ ▼）和动作键（A B），按下时橙色高亮 250ms
- **编码器值**：弧形仪表盘 + 数字显示
- **活跃状态**：15 秒内有数据时卡片边框为青色
- **最后事件**：底部文字描述最近一次操作

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2. 运行

```bash
python main.py
```

### 3. 使用

1. 将接收机（ESP8266）通过 USB 连接电脑
2. 在设备管理器中找到 CH340 对应的 COM 口
3. 在 GUI 中选择对应端口和波特率（115200）
4. 点击 **Connect**
5. 发送机按下按键或旋转编码器，对应卡片实时更新

## 项目结构

```
HeyEveryoneUpper/
├── main.py                      # 入口
├── requirements.txt             # 依赖
├── README.md
├── .gitignore
└── gui/
    ├── __init__.py
    ├── serial_parser.py         # 串口协议解析（解耦层）
    ├── data_model.py            # 数据模型（解耦层）
    ├── transmitter_widget.py    # 发送机卡片组件
    └── main_window.py           # 主窗口
```

### 设计说明

程序分三层解耦：

| 层 | 文件 | 职责 |
|---|---|---|
| **串口解析层** | `serial_parser.py` | 后台线程读取串口，按 `0xFC` 定长协议拆帧、校验和验证，吐出 `ParsedEvent` |
| **数据模型层** | `data_model.py` | 纯 Python 状态管理，维护每个发送机的按键状态和编码器累计值 |
| **GUI 层** | `main_window.py` / `transmitter_widget.py` | PyQt6 界面展示，通过信号桥接收事件并更新卡片 |

替换任何一层不影响其他层：例如可将 GUI 替换为 Web 前端，只需替换 `main_window.py` 和 `transmitter_widget.py`。

## 串口协议

接收机通过 UART 输出不定长帧：

```
0xFC [Length=N] [Payload N bytes] [Checksum]
```

Payload 由若干 3 字节条目组成：`[SenderID][Data_H][Data_L]`

按键值解码：
| 值 | 含义 |
|---|---|
| 0x0001 | 上 (UP) |
| 0x0002 | 下 (DOWN) |
| 0x0003 | 左 (LEFT) |
| 0x0004 | 右 (RIGHT) |
| 0x0005 | 中 (CENTER) |
| 0x0006 | A |
| 0x0007 | B |
| 0x0Bxx | 编码器顺时针 (CW) xx = 步数 |
| 0x0Cxx | 编码器逆时针 (CCW) xx = 步数 |

Checksum = (FrameHeader + Length + 所有 Payload 字节) & 0xFF

## 依赖

- Python >= 3.10
- PyQt6 >= 6.5
- pyserial >= 3.5
