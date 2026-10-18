"""管理器界面语言；不翻译用户输入、文件路径或 Multiwfn 原生界面。"""

import tkinter as tk

AUTHOR = "Author: Qiu Xinhong | Wuhan Institute of Technology"

TEXTS = {
    "Multiwfn 多开管理器": "Multiwfn Session Manager",
    "准备就绪": "Ready",
    "每会话线程": "Threads",
    "打开多个文件": "Open Files",
    "启动空白会话": "Blank Session",
    "程序 / 输出设置": "Settings",
    "会话管理": "Sessions",
    "打开结果目录": "Open Results",
    "重新启动当前": "Restart Session",
    "关闭当前会话": "Close Session",
    "文件 / 会话": "File / Session",
    "状态": "Status",
    "开始": "Start",
    "开始新的分析": "Start an Analysis",
    "选择线程": "Select Threads",
    "打开或拖入文件": "Open or Drop Files",
    "输入分析命令": "Enter Commands",
    "协同 · 已关闭": "Sync: OFF",
    "协同 · 已开启": "Sync: ON",
    "回车同步全部窗口 · 拖文件仅本会话 · 请保持菜单一致":
        "Enter syncs commands; file drops stay local. Keep menus aligned.",
    "文件拖放区": "Drop Files Here",
    "释放以打开文件": "Release to Open",
    "仅在此处拖入一个或多个文件": "Drop one or more files here",
    "拖入文件到本会话  |  等待文件路径提示时使用，不新建窗口":
        "Drop a file into this session when Multiwfn asks for a path",
    "命令 / 文件路径": "Command / Path",
    "发送命令": "Send",
    "聚焦原生窗口": "Focus Window",
    "等待命令窗口": "Waiting for console",
    "命令窗口": "Console",
    "正在启动 Multiwfn 并嵌入窗口…": "Starting and embedding Multiwfn...",
    "空白会话": "Blank Session",
    "绘图窗口": "Plot",
    "运行中": "Running",
    "已退出": "Exited",
    "启动中": "Starting",
    "嵌入失败": "Embedding Failed",
    "正在发送上一条命令": "Previous command is being sent",
    "会话已退出": "Session has exited",
    "命令窗口尚未就绪": "Console is not ready",
    "命令窗口尚未就绪，请稍后发送。": "Console is not ready. Please try later.",
    "请一次发送一行命令。": "Send one line at a time.",
    "发送失败，命令已保留": "Send failed; command preserved",
    "已投递到输入队列；请查看 Multiwfn 的下一步提示":
        "Delivered to input queue. Check Multiwfn's next prompt.",
    "发送助手超时或已退出": "Input helper timed out or exited",
    "就绪：每次发送一行，等待下一步提示": "Ready: send one line, then wait for the next prompt",
    "当前会话每次接收一个文件，请按 Multiwfn 提示逐个拖入。":
        "Drop one file at a time, following Multiwfn's prompts.",
    "拖入的路径不是有效文件。": "Dropped path is not a valid file.",
    "当前命令仍在发送，请稍后拖入文件。": "Command is being sent. Drop the file later.",
    "输入框还有未发送内容，请先发送或清空后再拖入文件。":
        "Send or clear the draft before dropping a file.",
    "原生窗口焦点受限，请使用底部命令输入框。": "Use the bottom command box for reliable input.",
    "首次使用，请选择 Multiwfn 程序目录": "First use: select the Multiwfn program directory",
    "多窗口协同已开启": "Multi-window sync enabled",
    "多窗口协同已关闭，恢复独立输入": "Sync disabled; independent input restored",
    "该会话已退出，无法发起协同输入。": "This session has exited and cannot initiate sync.",
    "选择一个或多个输入文件": "Select One or More Input Files",
    "常见输入文件": "Supported Input Files",
    "所有文件": "All Files",
    "程序和输出设置": "Program and Output Settings",
    "Multiwfn 程序": "Multiwfn Program",
    "结果根目录": "Output Root",
    "选择": "Browse",
    "完成": "Done",
    "选择包含 Multiwfn.exe 的程序目录": "Select the Directory Containing Multiwfn.exe",
    "已记住 Multiwfn 程序目录": "Multiwfn directory saved",
    "目录未设置": "Directory Not Set",
    "选择结果根目录": "Select Output Root",
    "请选择结果根目录。": "Select an output root directory.",
    "确认批量启动": "Confirm Batch Launch",
    "无法启动": "Unable to Start",
    "启动失败": "Startup Failed",
    "请输入非空的单行会话名称。": "Enter a non-empty, single-line session name.",
    "修改会话名称": "Rename Session",
    "新会话名称：": "New session name:",
    "名称无效": "Invalid Name",
    "修改名称": "Rename",
    "关闭会话": "Close Session",
    "无法打开目录": "Unable to Open Directory",
    "将结束这个会话，未保存的计算结果可能丢失。继续吗？":
        "This will end the session. Unsaved results may be lost. Continue?",
    "该会话已退出。可重新启动，或关闭标签页。":
        "This session has exited. Restart it or close this tab.",
    "正在启动": "Starting",
    "请等待当前会话启动完成后再关闭。": "Wait for startup to finish before closing.",
    "关闭管理器": "Close Manager",
    "关闭软件将结束全部内部分析会话，未保存结果可能丢失。\n\n确定关闭？":
        "Closing the manager ends all analysis sessions. Unsaved results may be lost.\n\nClose now?",
    "所选目录中没有 Multiwfn.exe，请选择 Multiwfn 程序所在文件夹。":
        "Multiwfn.exe was not found. Select the Multiwfn program directory.",
    "所选目录缺少 settings.ini，请选择完整的 Multiwfn 程序目录。":
        "settings.ini is missing. Select a complete Multiwfn program directory.",
}

# 按模板匹配动态状态，避免对用户名称、路径和命令做替换。
TEMPLATES = {
    "新会话线程数: %s": "New session threads: %s",
    "会话 %s：%s。": "Session %s: %s",
    "正在发送到会话 %s…": "Sending to session %s...",
    "发送失败：%s": "Send failed: %s",
    "已发送到会话 %s：%s": "Sent to session %s: %s",
    "协同投递回执，会话 %s：%s": "Sync delivery, session %s: %s",
    "发送失败：%s；未投递内容：%s": "Send failed: %s; pending content: %s",
    "窗口嵌入失败：%s；请关闭并重新启动该会话。":
        "Embedding failed: %s; close and restart this session.",
    "协同未发送：会话 %s%s，请稍后重试。": "Sync not sent: session %s %s. Try later.",
    "协同部分发送：已提交 %s；失败 %s。请检查各会话，勿直接重复群发。":
        "Partial sync: sent %s; failed %s. Check sessions before retrying.",
    "协同命令已提交到 %s 个会话；执行结果请查看各窗口。":
        "Sync submitted to %s sessions. Check each window for results.",
    "线程数必须在 1 到 %s 之间。": "Threads must be between 1 and %s.",
    "不是有效文件：%s": "Not a valid file: %s",
    "即将启动 %s 个会话，每个使用 %s 个线程，继续吗？":
        "Start %s sessions with %s threads each?",
    "正在启动：%s": "Starting: %s",
    "已启动 %s（%s 线程），正在托管原生窗口。":
        "Started %s (%s threads); embedding windows.",
    "会话已重命名：%s": "Session renamed: %s",
    "当前会话：%s 线程 | 结果目录：%s": "Current session: %s threads | Results: %s",
    "窗口检测提示：%s": "Window detection: %s",
}


def translate(text, language):
    if not isinstance(text, str) or language != "en":
        return text
    if text in TEXTS:
        return TEXTS[text]
    import re
    for source, target in TEMPLATES.items():
        pattern = "(.*?)".join(re.escape(part) for part in source.split("%s"))
        match = re.fullmatch(pattern, text, flags=re.DOTALL)
        if match:
            return target % tuple(translate(item, language) for item in match.groups())
    return text


class LocalizedVar(tk.StringVar):
    def __init__(self, master, value=""):
        self.source = value
        super().__init__(master, value=translate(value, master.language))
        master.localized_vars.append(self)

    def set(self, value):
        self.source = value
        super().set(translate(value, self._root.language))

    def refresh(self):
        super().set(translate(self.source, self._root.language))


class Dialogs:
    def __init__(self, module):
        self.module = module

    def __getattr__(self, name):
        function = getattr(self.module, name)

        def localized(*args, **kwargs):
            root = kwargs.get("parent", tk._default_root)
            language = getattr(root, "language", "zh")
            args = tuple(translate(arg, language) for arg in args)
            for key in ("title", "message", "prompt"):
                if key in kwargs:
                    kwargs[key] = translate(kwargs[key], language)
            if "filetypes" in kwargs:
                kwargs["filetypes"] = [(translate(label, language), pattern)
                                       for label, pattern in kwargs["filetypes"]]
            return function(*args, **kwargs)
        return localized
