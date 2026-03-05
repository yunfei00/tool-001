# tool-001
测试工具。

## 运行环境要求
- Windows 10/11（仅支持 Windows）
- Python 3.11+
- PySide6
- `adb` 命令行工具（需可在终端直接调用）
- 至少一台可通过 `adb devices` 识别的目标设备（用于执行/回读 EYE_SCAN 命令）

## 获取 Windows EXE（推荐）
仓库已配置 GitHub Actions 自动构建 **Windows 单文件 EXE**。

### 你需要做什么
1. 把代码推送到 GitHub。
2. 创建并推送一个 tag（例如 `v1.0.0`）：
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
3. 到 GitHub 的 **Releases** 页面下载 `tool-001.exe`。

### 手动触发构建（不发版）
也可以在 GitHub Actions 里手动运行 `Build and Release (Windows EXE)` workflow，
然后在该次运行的 Artifacts 中下载 `tool-001.exe`。
