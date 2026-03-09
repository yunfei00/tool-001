# tool-001

用于 **MTK 平台 CAMERA CTLE 参数筛选** 的 Windows 图形化工具（PySide6）。
支持单步调试、自动化压测以及结果分析，核心通过 `adb shell` 下发 `EYE_SCAN` 指令并做回读校验。

## 已实现功能

### 1) ADB 设备管理
- 一键扫描在线设备（`adb devices`）并在界面中选择目标设备。
- 设备不可用或 `adb` 不存在时，界面会给出明确日志提示。

### 2) 单步调试（手动模式）
- 支持以下参数的逐项发送与验证：
  - `CDR delay`
  - `EQ offset`
  - `EQ dg0 enable`
  - `EQ sr0`
  - `EQ dg1 enable`
  - `EQ sr1`
  - `EQ bw`
- 支持手动输入命令发送（Command Debug）。
- 支持“起流调试 / 停止流”按钮，便于验证参数生效条件。
- 每个步骤会在日志中输出发送结果（SUCCESS / FAIL / PENDING）。

### 3) 自动化测试
- 支持按参数范围与候选集合进行组合压测。
- 支持多轮循环执行（`auto_loop_count`）。
- 支持多 `sensor idx`、多 `sensor mode` 组合测试。
- 支持自动起流；也支持“手动起流（不自动后台起流）”模式。
- 支持运行中停止测试。
- 自动产出结果文件：
  - `.csv`：结构化结果
  - `.log/.txt`：详细执行日志

### 4) 结果分析
- 内置“结果分析”页：
  - 浏览并加载结果文件
  - 按状态过滤（仅成功/全部/失败/待定）
  - 按关键字过滤
  - 表格展示明细

### 5) 配置持久化
- 支持手动模式和自动模式参数的加载/保存。
- 配置字段带有合法化处理（范围裁剪、候选值过滤、模式兼容）。

### 6) 平台与运行限制
- 程序当前仅支持 Windows 运行；非 Windows 启动会直接提示并退出。
- 依赖目标设备可通过 `adb` 访问，且设备侧存在可写 `seninf` 调试节点。

---

## 运行环境要求
- Windows 10/11
- Python 3.11+
- `adb` 命令行工具（需在 PATH 中可直接调用）
- 至少一台可通过 `adb devices` 识别的 Android 设备

## 安装与启动

### 1) 安装依赖
```bash
pip install -r requirements.txt
```

### 2) 启动程序（源码方式）
在项目根目录执行：
```bash
python -m src.app.main
```

> 程序启动后先点击 **Scan ADB**，再进入单步调试或自动化测试。

---

## 配置文件说明

默认配置文件：`configs/default.yaml`（当前内容为 JSON 格式，程序按 JSON 读取）。

常用字段示例：
- `mode`: `manual` / `auto`
- `adb_device`: 目标设备序列号
- `is_dphy`: 是否 DPHY（影响 CDR delay 上限）
- `sensor_idx`, `sensor_mode`: 目标传感器配置
- `auto_*`: 自动化测试参数范围与候选值
- `auto_loop_count`: 自动化循环次数

---

## 输出结果

自动化任务执行后会在结果目录生成记录文件，包含：
- CSV 汇总（便于筛选统计）
- 文本详细日志（便于追踪每一步 adb 执行与回读）

你可以在 GUI 的“运行结果/结果分析”区域直接打开目录、查看并过滤结果。

---

## Windows EXE（推荐）
仓库已配置 GitHub Actions 自动构建 Windows 单文件 EXE。

### 方式 A：通过发版 tag 触发
```bash
git tag v1.0.0
git push origin v1.0.0
```
然后在 GitHub Releases 下载 `tool-001.exe`。

### 方式 B：手动触发 workflow
在 GitHub Actions 手动运行 `Build and Release (Windows EXE)`，
从该次运行的 Artifacts 下载 `tool-001.exe`。
