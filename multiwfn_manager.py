"""Windows launcher for independent Multiwfn analysis sessions."""

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import uuid


BASE = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
CONFIG = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "MultiwfnManager" / "config.json"
DEFAULT_OUTPUT = Path.home() / "Multiwfn分析结果"
LOG = CONFIG.parent / "debug.log"


def log_debug(message):
    """Append a timestamped diagnostic line; never raises into the UI."""
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        if LOG.is_file() and LOG.stat().st_size > 400_000:
            LOG.replace(LOG.with_suffix(".old.log"))
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with LOG.open("a", encoding="utf-8") as file:
            file.write("%s %s\n" % (stamp, message))
    except OSError:
        pass


def save_config(data):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    temporary = CONFIG.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(CONFIG)


def executable_from_directory(directory):
    executable = Path(directory).expanduser().resolve() / "Multiwfn.exe"
    if not executable.is_file():
        raise ValueError("所选目录中没有 Multiwfn.exe，请选择 Multiwfn 程序所在文件夹。")
    if not (executable.parent / "settings.ini").is_file():
        raise ValueError("所选目录缺少 settings.ini，请选择完整的 Multiwfn 程序目录。")
    return str(executable)


def find_executable():
    direct = BASE / "Multiwfn.exe"
    if direct.is_file():
        return str(direct)
    return next((str(p) for p in sorted(BASE.glob("*/Multiwfn.exe"))), "")


def load_config():
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def prepare_workspace(executable, output_root, input_file, threads):
    executable = Path(executable).resolve()
    if not executable.is_file() or executable.name.lower() != "multiwfn.exe":
        raise ValueError("请选择有效的 Multiwfn.exe。")
    if input_file and not Path(input_file).is_file():
        raise ValueError("输入文件不存在，请重新选择。")
    if not 1 <= threads <= (os.cpu_count() or 1):
        raise ValueError("线程数超出本机逻辑处理器数量。")
    label = Path(input_file).stem if input_file else "空白会话"
    label = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", label)[:50].rstrip(". ")
    workspace = Path(output_root).resolve() / (
        datetime.now().strftime("%Y%m%d_%H%M%S_") + label + "_" + uuid.uuid4().hex[:8]
    )
    workspace.mkdir(parents=True, exist_ok=False)
    source = executable.parent / "settings.ini"
    if not source.is_file():
        raise ValueError("Multiwfn 目录缺少 settings.ini，请先恢复该配置文件。")
    # Preserve the original encoding and all parameters except per-session threads.
    settings = source.read_bytes()
    settings, count = re.subn(
        rb"(?m)^(\s*nthreads\s*=\s*)\d+",
        lambda match: match.group(1) + str(threads).encode("ascii"),
        settings,
    )
    if count != 1:
        raise ValueError("settings.ini 中未找到唯一的 nthreads 配置项。")
    # Relative paths in settings must still refer to the installation directory.
    path_keys = (
        "atmcolorfile", "ttfontfile", "vdwrfile", "gaupath", "cubegenpath",
        "formchkpath", "orcapath", "orca_2mklpath", "orca_2jsonpath", "dftd3path",
    )
    for key in path_keys:
        pattern = rb"(?m)^(\s*" + key.encode("ascii") + rb"\s*=\s*)(.*?)(\s*//.*)?$"

        def rebase(match):
            value = match.group(2).strip().decode("mbcs").strip('"')
            if value.lower() == "none" or not value or Path(value).is_absolute():
                return match.group(0)
            # Windows Fortran reads file paths with the system ANSI code page.
            path = str(executable.parent / value).encode("mbcs")
            return match.group(1) + b'"' + path + b'"' + (match.group(3) or b"")

        settings = re.sub(pattern, rebase, settings)
    (workspace / "settings.ini").write_bytes(settings)
    examples = executable.parent / "examples"
    if examples.is_dir():
        # A junction shares read-only example resources without duplicating ~94 MB.
        env = os.environ.copy()
        env["MWFN_LINK"] = str(workspace / "examples")
        env["MWFN_SOURCE"] = str(examples)
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
             "$ErrorActionPreference='Stop'; "
             "New-Item -ItemType Junction -Path $env:MWFN_LINK "
             "-Target $env:MWFN_SOURCE | Out-Null"],
            env=env, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=30,
        )
        if result.returncode:
            raise OSError("无法创建示例资源目录链接，请选择本地 NTFS 输出目录。")
    return workspace


@dataclass
class Session:
    process: subprocess.Popen
    workspace: Path
    input_file: str
    started: str


def launch_session(executable, output_root, input_file, threads):
    workspace = prepare_workspace(executable, output_root, input_file, threads)
    command = [str(Path(executable).resolve())]
    if input_file:
        command.append(str(Path(input_file).resolve()))
    env = os.environ.copy()
    env["PATH"] = str(Path(executable).resolve().parent) + os.pathsep + env.get("PATH", "")
    # Explicit conhost avoids Windows Terminal, whose tabs cannot be reparented.
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    process = subprocess.Popen(
        [str(Path(os.environ["WINDIR"]) / "System32" / "conhost.exe")] + command,
        cwd=str(workspace), env=env,
        creationflags=subprocess.CREATE_NO_WINDOW,
        startupinfo=startup,
    )
    return Session(process, workspace, input_file, datetime.now().strftime("%H:%M:%S"))


def activate_window(pid):
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    found = []

    @callback_type
    def visit(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True

    user32.EnumWindows(visit, 0)
    if found:
        user32.ShowWindow(found[0], 9)
        return bool(user32.SetForegroundWindow(found[0]))
    # Windows console windows can be owned by conhost rather than Multiwfn.
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.AttachConsole.argtypes = [wintypes.DWORD]
    kernel32.GetConsoleWindow.restype = wintypes.HWND
    if kernel32.AttachConsole(pid):
        try:
            hwnd = kernel32.GetConsoleWindow()
            if hwnd:
                user32.ShowWindow(hwnd, 9)
                return bool(user32.SetForegroundWindow(hwnd))
        finally:
            kernel32.FreeConsole()
    return False


class Manager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Multiwfn 多开管理器")
        self.geometry("1080x720")
        self.minsize(880, 600)
        self.configure(bg="#f3f5f9")
        self.sessions = {}
        self.counter = 0
        self.config_data = load_config()
        self.exe = tk.StringVar(value=self.config_data.get("executable", find_executable()))
        self.output = tk.StringVar(value=self.config_data.get("output", str(DEFAULT_OUTPUT)))
        self.input_file = tk.StringVar()
        self.threads = tk.StringVar(value=str(self.config_data.get("threads", min(2, os.cpu_count() or 1))))
        self.status = tk.StringVar(value="就绪：选择文件直接分析，或新建空白会话。")
        self.build_ui()
        self.protocol("WM_DELETE_WINDOW", self.close_manager)
        self.after(1000, self.refresh)

    def build_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=("Microsoft YaHei UI", 10))
        style.configure("TFrame", background="#f3f5f9")
        style.configure("TLabel", background="#f3f5f9", foreground="#25334a")
        style.configure("TButton", padding=(12, 8))
        style.configure("Primary.TButton", background="#245bd6", foreground="white")
        style.map("Primary.TButton", background=[("active", "#194bb8")])
        style.configure("Treeview", rowheight=34, background="white", fieldbackground="white")
        style.configure("Treeview.Heading", padding=8)
        frame = ttk.Frame(self, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Multiwfn 多开管理器",
                  font=("Microsoft YaHei UI", 23, "bold")).pack(anchor="w")
        ttk.Label(frame, text="独立分析窗口  ·  独立结果目录  ·  一键重新启动").pack(anchor="w", pady=(6, 20))
        settings = ttk.Frame(frame)
        settings.pack(fill="x")
        settings.columnconfigure(1, weight=1)
        for row, (label, variable, browse) in enumerate([
            ("程序位置", self.exe, self.browse_exe),
            ("结果根目录", self.output, self.browse_output),
            ("待分析文件", self.input_file, self.browse_input),
        ]):
            ttk.Label(settings, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=6)
            ttk.Entry(settings, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=6)
            ttk.Button(settings, text="选择…", command=browse).grid(row=row, column=2, padx=(10, 0))
        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=16)
        ttk.Button(actions, text="启动文件分析", style="Primary.TButton",
                   command=self.start_input).pack(side="left")
        ttk.Button(actions, text="新建空白会话", command=lambda: self.start("")).pack(side="left", padx=8)
        ttk.Button(actions, text="批量选择并启动", command=self.start_batch).pack(side="left")
        ttk.Label(actions, text="每会话线程").pack(side="left", padx=(18, 6))
        ttk.Spinbox(actions, from_=1, to=os.cpu_count() or 1, width=4,
                    textvariable=self.threads).pack(side="left")
        ttk.Label(frame, text="会话列表", font=("Microsoft YaHei UI", 12, "bold")).pack(anchor="w", pady=(6, 8))
        table = ttk.Frame(frame)
        columns = ("name", "state", "pid", "time", "folder")
        self.tree = ttk.Treeview(table, columns=columns, show="headings", selectmode="browse")
        for name, title, width in [
            ("name", "分析文件 / 会话", 230), ("state", "进程状态", 110),
            ("pid", "PID", 75), ("time", "启动时间", 85), ("folder", "结果目录", 340),
        ]:
            self.tree.heading(name, text=title)
            self.tree.column(name, width=width, minwidth=60, stretch=name in ("name", "folder"))
        self.tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind("<Double-1>", lambda _: self.show_window())
        bottom = ttk.Frame(frame)
        bottom.pack(side="bottom", fill="x")
        footer = ttk.Frame(bottom)
        footer.pack(fill="x", pady=(14, 10))
        for text, command in [
            ("切换到窗口", self.show_window), ("打开结果目录", self.open_results),
            ("重新启动所选", self.restart), ("结束所选进程", self.stop),
            ("清理已退出记录", self.clear_exited),
        ]:
            ttk.Button(footer, text=text, command=command).pack(side="left", padx=(0, 8))
        ttk.Label(bottom, textvariable=self.status, wraplength=950).pack(anchor="w", pady=4)
        ttk.Label(bottom, text="关闭管理器不会关闭分析窗口。进程状态不代表计算进度；多开时请留意内存占用。",
                  foreground="#62718a").pack(anchor="w", pady=(6, 0))
        # Reserve footer space before giving the remaining height to the table.
        table.pack(fill="both", expand=True)

    def browse_exe(self):
        path = filedialog.askopenfilename(title="选择 Multiwfn.exe", filetypes=[("Multiwfn", "Multiwfn.exe")])
        if path:
            self.exe.set(path)

    def browse_output(self):
        path = filedialog.askdirectory(title="选择结果根目录")
        if path:
            self.output.set(path)

    def browse_input(self):
        path = filedialog.askopenfilename(title="选择待分析文件", filetypes=[
            ("常见输入", "*.fch *.fchk *.wfn *.wfx *.molden *.mwfn *.xyz *.cube *.cub *.pdb *.out *.log *.gbw *.chk"),
            ("所有文件", "*.*"),
        ])
        if path:
            self.input_file.set(path)

    def save_config(self, threads):
        CONFIG.write_text(json.dumps({
            "executable": self.exe.get().strip(), "output": self.output.get().strip(),
            "threads": threads,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    def start(self, input_file):
        try:
            if not self.output.get().strip():
                raise ValueError("请选择结果根目录。")
            threads = int(self.threads.get())
            self.save_config(threads)
            session = launch_session(self.exe.get().strip(), self.output.get().strip(), input_file, threads)
            self.counter += 1
            key = str(self.counter)
            self.sessions[key] = session
            self.tree.insert("", "end", iid=key, values=self.session_values(session))
            self.tree.selection_set(key)
            self.tree.see(key)
            self.status.set("已启动独立分析窗口。结果目录：" + str(session.workspace))
            return True
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            messagebox.showerror("启动未完成", str(error), parent=self)
            return False

    def start_input(self):
        path = self.input_file.get().strip().strip('"')
        if not path:
            self.browse_input()
            path = self.input_file.get()
        if path:
            self.start(path)

    def start_batch(self):
        paths = filedialog.askopenfilenames(title="选择多个文件，每个文件启动一个独立会话")
        if len(paths) > 4 and not messagebox.askyesno(
            "确认批量启动", "即将启动 %d 个进程，可能占用较多内存。继续吗？" % len(paths), parent=self
        ):
            return
        for path in paths:
            if not self.start(path):
                break
            self.update_idletasks()

    def selected(self):
        selection = self.tree.selection()
        if not selection:
            self.status.set("请先选择一条会话记录。")
            return None
        return self.sessions[selection[0]]

    def session_values(self, session):
        code = session.process.poll()
        state = "运行中" if code is None else "已退出 (%d)" % code
        return (Path(session.input_file).name if session.input_file else "空白会话",
                state, session.process.pid, session.started, str(session.workspace))

    def refresh(self):
        for key, session in self.sessions.items():
            self.tree.item(key, values=self.session_values(session))
        self.after(1000, self.refresh)

    def show_window(self):
        session = self.selected()
        if session:
            if session.process.poll() is not None:
                self.status.set("该会话已退出，可以点击“重新启动所选”。")
            elif not activate_window(session.process.pid):
                self.status.set("Windows 未允许前台切换，请从任务栏选择 Multiwfn 窗口。")

    def open_results(self):
        session = self.selected()
        if session:
            try:
                os.startfile(str(session.workspace))
            except OSError as error:
                messagebox.showerror("无法打开目录", str(error), parent=self)

    def restart(self):
        session = self.selected()
        if session:
            # Starting a fresh process never destroys an in-progress calculation.
            self.start(session.input_file)

    def stop(self):
        session = self.selected()
        if session and session.process.poll() is None and messagebox.askyesno(
            "确认结束进程", "强制结束将丢失未保存的计算结果。确定结束所选会话？", parent=self
        ):
            try:
                session.process.kill()
            except OSError as error:
                messagebox.showerror("结束失败", str(error), parent=self)

    def clear_exited(self):
        for key, session in list(self.sessions.items()):
            if session.process.poll() is not None:
                self.tree.delete(key)
                del self.sessions[key]
        self.status.set("已清理退出记录，结果文件仍保留。")

    def close_manager(self):
        try:
            self.save_config(int(self.threads.get()))
        except (OSError, ValueError):
            pass
        self.destroy()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--console-server":
        from console_input import serve_console
        serve_console(int(sys.argv[2]))
        sys.exit(0)
    if len(sys.argv) == 4 and sys.argv[1] == "--console-input":
        from console_input import send_console_input
        try:
            send_console_input(int(sys.argv[2]), sys.argv[3])
        except (OSError, ValueError):
            sys.exit(1)
        sys.exit(0)
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    from embedded_ui import EmbeddedManager
    EmbeddedManager(sys.modules[__name__]).mainloop()
