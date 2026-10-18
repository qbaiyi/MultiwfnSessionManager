# Multiwfn Session Manager / Multiwfn 多开管理器

**Author: Qiu Xinhong**  
**Affiliation: Wuhan Institute of Technology**

## 中文介绍

面向 Windows 的 Multiwfn 多会话桌面管理工具，将原生命令窗口和常规绘图窗口嵌入标签页，方便对多个体系进行波函数分析与结果对比。适用于量子化学研究、教学演示以及重复执行相同分析步骤的工作场景。

### 开发初衷

本工具源于作者个人使用 Multiwfn 时的实际需求：有时需要对多个分子或模型采用相同的分析方法，逐个重复打开 Multiwfn 并输入相同操作较为繁琐。因此开发了这个多开管理器，用于集中管理多个分析会话，减少重复打开程序和重复输入的操作，方便开展同类分析与结果对比。它是辅助个人工作流程的管理工具，不替代 Multiwfn 本体。

### 主要功能

- 选择每会话线程数，一次打开多个输入文件，或启动空白会话。
- 左上角拖入文件新建会话；会话内拖入文件只向该会话发送路径。
- 内嵌命令和绘图窗口，支持双击改名、右键关闭、独立结果目录。
- 多窗口协同：开启后，命令框按回车向所有运行中的会话提交相同文本；各窗口拖入的文件仍独立。
- 右上角切换中文和英文界面，自动记住语言与 Multiwfn 程序目录。
- 常驻输入助手与本地诊断日志，帮助处理输入失败和异常退出。

### 使用方法

1. 下载最新发布中的 `Multiwfn多开管理器.exe`。
2. 从 Multiwfn 官方渠道获取完整 Windows 版程序。首次运行管理器时选择包含 `Multiwfn.exe` 和 `settings.ini` 的目录。
3. 选择线程数，打开文件或启动空白会话。
4. 使用底部命令框输入一行命令并按回车。等待 Multiwfn 的下一步提示后再继续。
5. 后续提示输入路径时，将文件拖入对应会话区域。主菜单换文件时先输入 `r`。

### 限制与注意

- 目标平台：Windows 10/11 x64。EXE 不要求安装 Python，但仍需独立安装 Multiwfn。
- 本工具是窗口管理器，不包含或修改 Multiwfn 分析算法，也不保证错误输入不会导致 Multiwfn 自身退出。
- 协同模式不自动识别各窗口菜单或计算状态。请保持输入步骤一致；`q` 等退出命令也会同步。
- 文件拖放独立，但手动键入的路径属于命令文本，会在协同模式下同步。
- 不同步原生绘图窗口的鼠标或键盘操作；特殊原生对话框可能独立弹出。
- 关闭管理器会结束其管理的分析会话。请先保存结果。
- 日志在 `%LOCALAPPDATA%\MultiwfnManager\debug.log`，可能包含命令及文件路径，分享前请检查。

## English

A Windows desktop session manager for Multiwfn. It embeds native console and regular plotting windows in tabs, making it easier to analyze multiple systems and compare results. Intended for quantum chemistry research, teaching demonstrations, and repeated analysis workflows.

### Motivation

This tool grew out of the author's personal experience with Multiwfn. Sometimes, the same analysis method needs to be applied to several molecules or models, and repeatedly opening Multiwfn and entering the same commands for each system becomes cumbersome. This manager brings multiple analysis sessions together, reducing repeated program launches and command entry while making similar analyses and result comparisons more convenient. It supports a personal workflow and does not replace Multiwfn itself.

### Features

- Set threads per session, open multiple input files, or start a blank session.
- Drop files in the upper-left zone to create sessions; in-session file drops stay local.
- Embedded console and plot tabs, double-click renaming, right-click closing, and separate result directories.
- Multi-window sync: Enter in a command box submits identical text to all running sessions. File drops remain independent.
- Chinese/English interface switch at the upper right; language and Multiwfn directory are remembered.
- Persistent input helpers and local diagnostic logs.

### Getting Started

1. Download `Multiwfn多开管理器.exe` from the latest release.
2. Obtain a complete Windows distribution of Multiwfn from its official source. On first launch, select its directory containing `Multiwfn.exe` and `settings.ini`.
3. Choose threads and open files or start a blank session.
4. Enter a single command in the bottom command box and press Enter. Wait for the next Multiwfn prompt before proceeding.
5. Drop a file into the corresponding session when a path is requested. To reload at the main menu, send `r` first.

### Requirements and Limitations

- Target platform: Windows 10/11 x64. The EXE does not require Python, but Multiwfn must be installed separately.
- This tool manages windows; it does not include or alter Multiwfn's analysis algorithms. Invalid input can still cause Multiwfn itself to exit.
- Sync does not detect menu or calculation states. Keep sessions at matching input steps; exit commands such as `q` are also broadcast.
- File drops stay local; manually typed paths are command text and are broadcast when sync is enabled.
- Native plot mouse/keyboard actions are not synchronized. Special native dialogs may appear separately.
- Closing the manager ends managed sessions. Save results first.
- Diagnostics: `%LOCALAPPDATA%\MultiwfnManager\debug.log`. Logs may contain commands and file paths; inspect before sharing.

## Development / 开发

```powershell
python -m pip install -r requirements.txt
python multiwfn_manager.py
```

Build on Windows / Windows 打包:

```powershell
python -m PyInstaller --noconfirm --onefile --windowed --collect-all tkinterdnd2 --name MultiwfnSessionManager multiwfn_manager.py
```

## Attribution / 归属声明

The author attribution above applies to this session manager only. Multiwfn is a separate third-party program developed by Tian Lu and Feiwu Chen. Its rights, license, and required scientific citations remain those of its authors.

以上作者署名仅指本管理器。Multiwfn 是 Tian Lu 与 Feiwu Chen 开发的独立第三方软件，其版权、使用许可与科研引用要求属于原作者。

Multiwfn official site / Multiwfn 官网: http://sobereva.com/multiwfn/

No third-party Multiwfn binaries, personal configuration, scientific input files, or analysis results are included in the intended GitHub distribution.

发布内容不包含 Multiwfn 本体、个人配置、计算输入文件或分析结果。
