"""Tabbed Windows host for native Multiwfn consoles and plotting windows."""

import os
from pathlib import Path
import subprocess
import threading
import ctypes
import sys
import json
import queue
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

import psutil
import win32con
import win32gui
import win32process
from tkinterdnd2 import DND_FILES, TkinterDnD
from ui_widgets import DropZone, RoundedButton, rounded
from localization import AUTHOR, Dialogs, LocalizedVar, translate

filedialog = Dialogs(filedialog)
messagebox = Dialogs(messagebox)
simpledialog = Dialogs(simpledialog)


class NativeWindow:
    def __init__(self, hwnd, parent):
        self.hwnd = hwnd
        self.original_parent = win32gui.GetParent(hwnd)
        self.style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        self.rect = win32gui.GetWindowRect(hwnd)
        parent.update_idletasks()
        win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
        win32gui.SetParent(hwnd, parent.winfo_id())
        child_style = (self.style & ~(
            win32con.WS_POPUP | win32con.WS_CAPTION | win32con.WS_THICKFRAME
            | win32con.WS_MINIMIZEBOX | win32con.WS_MAXIMIZEBOX
        )) | win32con.WS_CHILD
        win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, child_style)
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        self.resize(parent.winfo_width(), parent.winfo_height())

    def resize(self, width, height):
        if win32gui.IsWindow(self.hwnd):
            win32gui.SetWindowPos(
                self.hwnd, 0, 0, 0, max(10, width), max(10, height),
                win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE | win32con.SWP_FRAMECHANGED,
            )

    def focus(self):
        if not win32gui.IsWindow(self.hwnd):
            return
        target_thread = win32process.GetWindowThreadProcessId(self.hwnd)[0]
        current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
        attached = False
        try:
            if target_thread != current_thread:
                attached = bool(ctypes.windll.user32.AttachThreadInput(
                    current_thread, target_thread, True
                ))
            win32gui.SetFocus(self.hwnd)
        finally:
            if attached:
                ctypes.windll.user32.AttachThreadInput(current_thread, target_thread, False)

    def detach(self):
        if win32gui.IsWindow(self.hwnd):
            win32gui.SetParent(self.hwnd, self.original_parent)
            win32gui.SetWindowLong(self.hwnd, win32con.GWL_STYLE, self.style)
            left, top, right, bottom = self.rect
            win32gui.SetWindowPos(
                self.hwnd, 0, left, top, right - left, bottom - top,
                win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED,
            )
            win32gui.ShowWindow(self.hwnd, win32con.SW_SHOW)


class SessionView:
    def __init__(self, app, key, session, threads):
        self.app, self.key, self.session = app, key, session
        self.threads = threads
        self.pids = {session.process.pid}
        self.windows = {}
        self.embedding_error = ""
        self.alive = True
        self.last_sent = None
        self.panel = ttk.Frame(app.notebook)
        self.file_drop = tk.Label(
            self.panel, text="拖入文件到本会话  |  等待文件路径提示时使用，不新建窗口",
            bg="#edf5f6", fg="#34616a", padx=10, pady=6,
            font=("Microsoft YaHei UI", 9),
        )
        self.file_drop.pack(side="top", fill="x")
        for widget in (self.file_drop,):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", self.drop_session_file)
            widget.dnd_bind("<<DropEnter>>", lambda _: self.highlight_file_drop(True))
            widget.dnd_bind("<<DropLeave>>", lambda _: self.highlight_file_drop(False))
        self.tabs = ttk.Notebook(self.panel)
        input_bar = ttk.Frame(self.panel, padding=(10, 8), style="Card.TFrame")
        input_bar.pack(side="bottom", fill="x")
        ttk.Label(input_bar, text="命令 / 文件路径").pack(side="left", padx=(0, 8))
        self.command = tk.StringVar()
        self.command_entry = ttk.Entry(input_bar, textvariable=self.command)
        self.command_entry.pack(side="left", fill="x", expand=True)
        self.command_entry.bind("<Return>", lambda _: self.send_command())
        self.command_entry.drop_target_register(DND_FILES)
        self.command_entry.dnd_bind("<<Drop>>", self.drop_session_file)
        self.send_button = ttk.Button(input_bar, text="发送命令", style="Primary.TButton", command=self.send_command)
        self.send_button.pack(side="left", padx=6)
        ttk.Button(input_bar, text="聚焦原生窗口", command=self.focus_native).pack(side="left")
        self.pending_input = None
        self.input_helper = None
        self.input_replies = queue.Queue()
        self.request_counter = 0
        self.input_deadline = 0
        self.input_state = LocalizedVar(app, value="等待命令窗口")
        ttk.Label(self.panel, textvariable=self.input_state, style="Muted.TLabel",
                  padding=(8, 2)).pack(side="bottom", fill="x")
        self.tabs.pack(fill="both", expand=True)
        self.tabs.bind("<<NotebookTabChanged>>", lambda _: self.app.after_idle(self.focus_input))
        self.console = tk.Frame(self.tabs, bg="#101010")
        self.tabs.add(self.console, text="命令窗口")
        self.waiting = tk.Label(
            self.console, text="正在启动 Multiwfn 并嵌入窗口…",
            fg="white", bg="#101010", font=("Microsoft YaHei UI", 11),
        )
        self.waiting.pack(expand=True)
        self.console.bind("<Configure>", lambda event: self.resize(self.console, event))

    def focus_input(self):
        if self.app.selected() is self and self.tabs.select() == str(self.console):
            self.command_entry.focus_set()

    def highlight_file_drop(self, active):
        self.file_drop.configure(bg="#dceff1" if active else "#edf5f6")
        return "copy"

    def drop_session_file(self, event):
        self.highlight_file_drop(False)
        paths = list(self.app.tk.splitlist(event.data))
        if len(paths) != 1:
            self.app.status.set("当前会话每次接收一个文件，请按 Multiwfn 提示逐个拖入。")
            return "refuse_drop"
        path = Path(paths[0])
        if not path.is_file():
            self.app.status.set("拖入的路径不是有效文件。")
            return "refuse_drop"
        if self.pending_input is not None:
            self.app.status.set("当前命令仍在发送，请稍后拖入文件。")
            return "refuse_drop"
        if self.command.get().strip():
            self.app.status.set("输入框还有未发送内容，请先发送或清空后再拖入文件。")
            return "refuse_drop"
        self.command.set(str(path.resolve()))
        # File drops are always local, even while keyboard commands are broadcast.
        if not self.send_text(self.command.get()):
            return "refuse_drop"
        return "copy"

    def focus_native(self):
        if self.app.selected() is not self:
            return
        selected = self.tabs.select()
        for native, parent in self.windows.values():
            if str(parent) == selected:
                try:
                    native.focus()
                except Exception:
                    self.app.status.set("原生窗口焦点受限，请使用底部命令输入框。")
                return

    def send_command(self):
        return self.app.submit_command(self, self.command.get())

    def input_ready(self):
        if self.pending_input is not None:
            return "正在发送上一条命令"
        if self.session.process.poll() is not None:
            return "会话已退出"
        if not any(parent is self.console for _, parent in self.windows.values()):
            return "命令窗口尚未就绪"
        return None

    def send_text(self, text, clear_entry=True):
        error = self.input_ready()
        if error:
            self.app.status.set("会话 %s：%s。" % (self.key, error))
            return False
        console_hwnd = next(
            (hwnd for hwnd, (_, parent) in self.windows.items() if parent is self.console), None
        )
        if not console_hwnd:
            self.app.status.set("命令窗口尚未就绪，请稍后发送。")
            return False
        pid = win32process.GetWindowThreadProcessId(console_hwnd)[1]
        if "\n" in text or "\r" in text:
            self.app.status.set("请一次发送一行命令。")
            return False
        self.tabs.select(self.console)
        # AttachConsole runs in a persistent helper, never on the UI process.
        if getattr(sys, "frozen", False):
            args = [sys.executable]
        else:
            args = [sys.executable, str(self.app.backend.BASE / "multiwfn_manager.py")]
        try:
            if self.input_helper is None or self.input_helper.poll() is not None:
                self.close_input_helper()
                self.input_replies = queue.Queue()
                self.input_helper = subprocess.Popen(
                    args + ["--console-server", str(pid)],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    text=True, encoding="utf-8", bufsize=1,
                )
                helper, replies = self.input_helper, self.input_replies

                def receive():
                    try:
                        for line in helper.stdout:
                            replies.put(json.loads(line))
                    except (OSError, ValueError):
                        pass

                threading.Thread(target=receive, daemon=True).start()
            self.request_counter += 1
            self.pending_input = self.request_counter
            self.input_deadline = time.monotonic() + 12
            self.input_helper.stdin.write(json.dumps(
                {"id": self.pending_input, "text": text}, ensure_ascii=True
            ) + "\n")
            self.input_helper.stdin.flush()
            self.last_sent = (time.time(), text)
            self.app.backend.log_debug("发送 会话%s 内容=%r" % (self.key, text))
            self.send_button.configure(state="disabled")
            self.input_state.set("正在发送到会话 %s…" % self.key)
            self.app.after(50, lambda: self.check_input(text, clear_entry))
            return True
        except OSError as error:
            self.pending_input = None
            self.close_input_helper()
            self.app.backend.log_debug("发送失败 会话%s：%s" % (self.key, error))
            self.app.status.set("发送失败：" + str(error))
            self.input_state.set("发送失败，命令已保留")
            return False

    def check_input(self, text, clear_entry=True):
        if self.pending_input is None or self.input_helper is None:
            return
        try:
            response = None
            while not self.input_replies.empty():
                item = self.input_replies.get_nowait()
                if item.get("id") == self.pending_input:
                    response = item
            if response is None and time.monotonic() < self.input_deadline and self.input_helper.poll() is None:
                self.app.after(50, lambda: self.check_input(text, clear_entry))
                return
            self.pending_input = None
            self.send_button.configure(state="normal")
            if response and response.get("ok"):
                if clear_entry and self.command.get() == text:
                    self.command.set("")
                self.app.backend.log_debug("投递成功 会话%s" % self.key)
                self.app.status.set(("协同投递回执，会话 %s：%s" if self.app.collaborative.get()
                                     else "已发送到会话 %s：%s") % (self.key, text or "回车"))
                self.input_state.set("已投递到输入队列；请查看 Multiwfn 的下一步提示")
            else:
                error = response.get("error", "") if response else "发送助手超时或已退出"
                self.app.backend.log_debug("投递失败 会话%s 原因=%s 内容=%r" % (self.key, error, text))
                self.input_state.set("发送失败：" + error + "；未投递内容：" + (text or "空行"))
                self.app.status.set(self.input_state.get())
                self.close_input_helper()
            self.focus_input()
        except tk.TclError:
            # The session tab may have been closed while a reply was in flight.
            self.pending_input = None

    def close_input_helper(self):
        helper = self.input_helper
        self.input_helper = None
        self.pending_input = None
        if not helper:
            return
        try:
            if helper.poll() is None and helper.stdin:
                # Ask the helper to detach cleanly before falling back to kill.
                helper.stdin.write(json.dumps({"action": "close"}) + "\n")
                helper.stdin.flush()
                helper.wait(timeout=0.8)
        except (OSError, subprocess.TimeoutExpired):
            pass
        if helper.poll() is None:
            helper.terminate()
        for stream in (helper.stdin, helper.stdout):
            if stream:
                try:
                    stream.close()
                except OSError:
                    pass

    def resize(self, container, event):
        for native, parent in self.windows.values():
            if parent is container:
                try:
                    native.resize(event.width, event.height)
                except Exception:
                    pass

    def discover_pids(self):
        try:
            for process in psutil.Process(self.session.process.pid).children(recursive=True):
                self.pids.add(process.pid)
        except psutil.Error:
            pass

    def capture(self, hwnd, title, kind):
        if hwnd in self.windows or not win32gui.IsWindow(hwnd):
            return
        if kind == "ConsoleWindowClass":
            parent = self.console
        else:
            parent = tk.Frame(self.tabs, bg="#e9edf4")
            self.tabs.add(parent, text=(title or "绘图窗口")[:40])
            parent.bind("<Configure>", lambda event, host=parent: self.resize(host, event))
        try:
            native = NativeWindow(hwnd, parent)
        except Exception as error:
            if parent is not self.console:
                self.tabs.forget(parent)
                parent.destroy()
            self.embedding_error = str(error)
            self.app.backend.log_debug("窗口嵌入失败 会话%s hwnd=%s：%s" % (self.key, hwnd, error))
            win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
            self.app.status.set("窗口嵌入失败：" + str(error) + "；请关闭并重新启动该会话。")
            return
        self.windows[hwnd] = (native, parent)
        if parent is self.console:
            self.waiting.pack_forget()
            self.input_state.set("就绪：每次发送一行，等待下一步提示")
        else:
            self.tabs.select(parent)
        self.app.after_idle(self.focus_input)

    def clean_windows(self):
        for hwnd, (_, parent) in list(self.windows.items()):
            if not win32gui.IsWindow(hwnd):
                del self.windows[hwnd]
                if parent is not self.console:
                    self.tabs.forget(parent)
                    parent.destroy()

    def detach(self):
        self.close_input_helper()
        self.pending_input = None
        for native, _ in self.windows.values():
            try:
                native.detach()
            except Exception:
                pass

    def stop(self):
        self.close_input_helper()
        self.pending_input = None
        self.app.backend.log_debug("会话%s由用户关闭" % self.key)
        self.discover_pids()
        # Children are stopped before the console host, only within this session.
        try:
            host = psutil.Process(self.session.process.pid)
            for child in host.children(recursive=True):
                try:
                    child.kill()
                except psutil.Error:
                    pass
        except psutil.Error:
            pass
        if self.session.process.poll() is None:
            self.session.process.kill()


class EmbeddedManager(TkinterDnD.Tk):
    def __init__(self, backend):
        super().__init__()
        self.backend = backend
        self.title("Multiwfn 多开管理器")
        self.configure(bg="#f3f6f9", cursor="arrow")
        self.geometry("1160x740")
        self.minsize(860, 560)
        self.views = {}
        self.counter = 0
        self.launch_queue = []
        self.busy = False
        self.closing = False
        config = backend.load_config()
        self.language = config.get("language", "zh")
        if self.language not in ("zh", "en"):
            self.language = "zh"
        self.localized_vars = []
        self.locale_text = {}
        self.locale_tabs = {}
        self.exe = tk.StringVar(value=config.get("executable", ""))
        self.output = tk.StringVar(value=config.get("output", str(backend.DEFAULT_OUTPUT)))
        self.threads = tk.StringVar(value=str(min(
            max(1, int(config.get("threads", 2))), os.cpu_count() or 1
        )))
        self.status = LocalizedVar(self, value="准备就绪")
        self.collaborative = tk.BooleanVar(value=False)
        self.collaboration_status = LocalizedVar(self, value="")
        self.thread_status = LocalizedVar(self)
        self.threads.trace_add("write", lambda *_: self.thread_status.set("新会话线程数: " + self.threads.get()))
        self.thread_status.set("新会话线程数: " + self.threads.get())
        self.build_ui()
        self.apply_language()
        self.protocol("WM_DELETE_WINDOW", self.close_manager)
        self.backend.log_debug("管理器启动")
        self.after(300, self.refresh)
        self.after_idle(self.ensure_program_directory)

    def ensure_program_directory(self):
        try:
            self.backend.executable_from_directory(Path(self.exe.get()).parent)
            return True
        except ValueError:
            self.status.set("首次使用，请选择 Multiwfn 程序目录")
        return self.choose_exe()

    def build_ui(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=("Microsoft YaHei UI", 10), background="#f3f6f9", foreground="#20344d")
        style.configure("TFrame", background="#f3f6f9")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("TLabel", background="#f3f6f9", foreground="#20344d")
        style.configure("Card.TLabel", background="#ffffff", foreground="#20344d")
        style.configure("Muted.TLabel", foreground="#4a5568")
        style.configure("TButton", padding=(14, 10), background="#ffffff",
                        foreground="#20344d", borderwidth=0)
        style.map("TButton", background=[("active", "#e0e9f1"), ("disabled", "#e6ecf2")],
                  foreground=[("disabled", "#8391a3")])
        style.configure("Primary.TButton", background="#087f8c", foreground="#ffffff")
        style.map("Primary.TButton", background=[("disabled", "#a3c9cd"), ("active", "#066873")],
                  foreground=[("disabled", "#ffffff"), ("active", "#ffffff")])
        style.configure("TEntry", padding=9, fieldbackground="#ffffff", foreground="#152e48")
        style.configure("TSpinbox", padding=7, fieldbackground="#ffffff")
        style.configure("TNotebook", background="#ffffff", borderwidth=0, tabmargins=(0, 0, 0, 0))
        style.configure("TNotebook.Tab", padding=(13, 7), background="#edf2f6",
                        foreground="#51657c", borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", "#ffffff")],
                  foreground=[("selected", "#087f8c")])
        style.configure("Treeview", rowheight=32, background="#ffffff",
                        fieldbackground="#ffffff", foreground="#20344d", borderwidth=0)
        style.map("Treeview", background=[("selected", "#d8efef")],
                  foreground=[("selected", "#075f68")])
        style.configure("Treeview.Heading", background="#f3f6f9", foreground="#4a5568",
                        padding=8, relief="flat", borderwidth=0)
        toolbar = ttk.Frame(self, padding=(16, 10))
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="Multiwfn", font=("Segoe UI", 16, "bold")).pack(side="left", padx=(0, 14))
        ttk.Label(toolbar, text="每会话线程").pack(side="left")
        ttk.Spinbox(toolbar, from_=1, to=os.cpu_count() or 1, width=4,
                    textvariable=self.threads).pack(side="left", padx=6)
        for text, command in [
            ("打开多个文件", self.open_files),
            ("启动空白会话", lambda: self.queue_files([""])),
            ("程序 / 输出设置", self.settings_dialog),
        ]:
            RoundedButton(toolbar, text, command,
                          variant="primary" if text == "打开多个文件" else "secondary",
                          width=130).pack(side="left", padx=4)
        self.language_button = ttk.Button(toolbar, text="English / 中文",
                                          command=self.switch_language, padding=(8, 6))
        self.language_button.pack(side="right", padx=(8, 0))
        self.collaboration_button = tk.Button(
            toolbar, text="协同 · 已关闭", command=self.toggle_collaboration,
            font=("Microsoft YaHei UI", 11, "bold"), bg="#526174", fg="#ffffff",
            activebackground="#64748b", activeforeground="#ffffff",
            relief="flat", borderwidth=0, padx=14, pady=6, cursor="hand2",
            highlightthickness=0,
        )
        self.collaboration_button.pack(side="right")
        self.collaborative.trace_add("write", lambda *_: self.update_collaboration_visual())
        footer = ttk.Frame(self, padding=(12, 5))
        footer.pack(side="bottom", fill="x")
        ttk.Label(footer, text=AUTHOR, style="Muted.TLabel",
                  font=("Segoe UI", 9)).pack(side="bottom", anchor="e", pady=(4, 0))
        ttk.Label(footer, textvariable=self.collaboration_status, style="Muted.TLabel",
                  font=("Segoe UI", 9)).pack(side="bottom", anchor="w")
        ttk.Label(footer, textvariable=self.thread_status, style="Muted.TLabel").pack(side="right", padx=8)
        ttk.Label(footer, textvariable=self.status, wraplength=820,
                  style="Muted.TLabel").pack(side="left")
        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        sidebar = ttk.Frame(body, width=218)
        body.add(sidebar, weight=0)
        self.drop_zone = DropZone(sidebar)
        self.drop_zone.pack(fill="x", pady=(0, 8))
        self.register_drop(self.drop_zone)
        ttk.Label(sidebar, text="会话管理", font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w", pady=6)
        tools = ttk.Frame(sidebar)
        tools.pack(side="bottom", fill="x", pady=6)
        for text, command, icon, variant in [
            ("打开结果目录", self.open_results, "folder", "secondary"),
            ("重新启动当前", self.restart, "restart", "secondary"),
            ("关闭当前会话", self.close_session, "close", "danger"),
        ]:
            RoundedButton(tools, text, command, icon=icon, variant=variant).pack(fill="x", pady=4)
        self.tree = ttk.Treeview(sidebar, columns=("state",), show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="文件 / 会话")
        self.tree.heading("state", text="状态")
        self.tree.column("#0", width=140, minwidth=90)
        self.tree.column("state", width=72, minwidth=58)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.select_tree)
        self.tree.bind("<Double-1>", self.rename_session)
        self.tree.bind("<Button-3>", self.session_menu)
        self.notebook = ttk.Notebook(body)
        body.add(self.notebook, weight=1)
        self.notebook.bind("<<NotebookTabChanged>>", self.select_tab)
        self.notebook.bind("<Double-1>", self.rename_session)
        self.notebook.bind("<Button-3>", self.session_menu)
        self.welcome = ttk.Frame(self.notebook, padding=24, style="Card.TFrame")
        self.notebook.add(self.welcome, text="开始")
        guide = ttk.Frame(self.welcome, style="Card.TFrame")
        guide.place(relx=0.5, rely=0.44, anchor="center")
        illustration = tk.Canvas(guide, width=80, height=64, background="white", highlightthickness=0)
        illustration.pack()
        rounded(illustration, 10, 6, 70, 52, fill="#eef7f8", outline="#c7e3e5")
        for y, length in ((18, 34), (28, 44), (38, 26)):
            illustration.create_line(22, y, 22 + length, y, fill="#087f8c", width=2.5, capstyle=tk.ROUND)
        ttk.Label(guide, text="开始新的分析", style="Card.TLabel",
                  font=("Microsoft YaHei UI", 18, "bold")).pack(pady=(10, 16))
        steps = ttk.Frame(guide, style="Card.TFrame")
        steps.pack()
        for number, title in enumerate(("选择线程", "打开或拖入文件", "输入分析命令"), 1):
            card = ttk.Frame(steps, padding=(14, 10), style="Card.TFrame")
            card.pack(side="left", padx=6)
            ttk.Label(card, text="%02d" % number, style="Card.TLabel",
                      foreground="#087f8c", font=("Segoe UI", 13, "bold")).pack()
            ttk.Label(card, text=title, style="Card.TLabel").pack(pady=(6, 0))

    def switch_language(self):
        self.language = "en" if self.language == "zh" else "zh"
        self.apply_language()
        try:
            self.save_config()
        except (OSError, ValueError) as error:
            self.backend.log_debug("语言设置保存失败：%s" % error)

    def apply_language(self):
        self.title(translate("Multiwfn 多开管理器", self.language))
        self.language_button.configure(text="中文" if self.language == "en" else "English")
        self.update_collaboration_visual()
        for variable in self.localized_vars:
            variable.refresh()

        def visit(widget):
            if widget is self.language_button or widget is self.collaboration_button:
                return
            if isinstance(widget, RoundedButton):
                source = self.locale_text.setdefault(widget, widget.text)
                widget.text = translate(source, self.language)
                widget.draw()
            elif isinstance(widget, DropZone):
                widget.language = self.language
                widget.draw()
            elif isinstance(widget, (ttk.Label, ttk.Button, tk.Label)):
                if not widget.cget("textvariable"):
                    current = str(widget.cget("text"))
                    source, rendered = self.locale_text.get(widget, (current, current))
                    if current != rendered:
                        source = current
                    rendered = translate(source, self.language)
                    self.locale_text[widget] = (source, rendered)
                    widget.configure(text=rendered)
            for child in widget.winfo_children():
                visit(child)
        visit(self)
        for column, source in (("#0", "文件 / 会话"), ("state", "状态")):
            self.tree.heading(column, text=translate(source, self.language))
        if str(self.welcome) in self.notebook.tabs():
            self.notebook.tab(self.welcome, text=translate("开始", self.language))
        for view in self.views.values():
            if str(view.console) in view.tabs.tabs():
                view.tabs.tab(view.console, text=translate("命令窗口", self.language))
            if not getattr(view, "custom_name", False) and not view.session.input_file:
                name = translate("空白会话", self.language)
                self.tree.item(view.key, text=name)
                self.notebook.tab(view.panel, text="%s · %s" % (view.key, name))

    def toggle_collaboration(self):
        self.collaborative.set(not self.collaborative.get())
        self.status.set("多窗口协同已开启" if self.collaborative.get()
                        else "多窗口协同已关闭，恢复独立输入")

    def update_collaboration_visual(self):
        enabled = self.collaborative.get()
        self.collaboration_button.configure(
            text=translate("协同 · " + ("已开启" if enabled else "已关闭"), self.language),
            bg="#089eae" if enabled else "#526174",
            activebackground="#078797" if enabled else "#64748b",
        )
        self.collaboration_status.set(
            "回车同步全部窗口 · 拖文件仅本会话 · 请保持菜单一致" if enabled else ""
        )

    def submit_command(self, source, text):
        if not self.collaborative.get():
            return source.send_text(text)
        if source.session.process.poll() is not None:
            self.status.set("该会话已退出，无法发起协同输入。")
            return False
        if "\n" in text or "\r" in text:
            self.status.set("请一次发送一行命令。")
            return False
        targets = [view for view in self.views.values() if view.session.process.poll() is None]
        for view in targets:
            error = view.input_ready()
            if error:
                self.status.set("协同未发送：会话 %s%s，请稍后重试。" % (view.key, error))
                return False
        sent, failed = [], []
        for view in targets:
            # Broadcast submitted text, leaving other sessions' unsent drafts untouched.
            if view.send_text(text, clear_entry=view is source):
                sent.append(view.key)
            else:
                failed.append(view.key)
        if failed:
            source.command.set(text)
            self.status.set("协同部分发送：已提交 %s；失败 %s。请检查各会话，勿直接重复群发。"
                            % (", ".join(sent) or "无", ", ".join(failed)))
            self.backend.log_debug("协同部分发送 成功=%s 失败=%s 内容=%r"
                                   % (",".join(sent) or "无", ",".join(failed), text))
            return False
        self.status.set("协同命令已提交到 %d 个会话；执行结果请查看各窗口。" % len(sent))
        return True

    def register_drop(self, widget):
        widget.drop_target_register(DND_FILES)
        widget.dnd_bind("<<Drop>>", self.drop_files)
        widget.dnd_bind("<<DropEnter>>", lambda _: self.drop_hover(True))
        widget.dnd_bind("<<DropLeave>>", lambda _: self.drop_hover(False))

    def drop_hover(self, active):
        self.drop_zone.highlight(active)
        return "copy"

    def drop_files(self, event):
        if event.widget is not self.drop_zone:
            return "refuse_drop"
        self.queue_files(list(self.tk.splitlist(event.data)))
        self.drop_zone.highlight(False)
        return "copy"

    def open_files(self):
        paths = filedialog.askopenfilenames(
            parent=self, title="选择一个或多个输入文件",
            filetypes=[("常见输入文件", "*.molden.input *.molden *.fch *.fchk *.wfn *.wfx *.mwfn *.xyz *.cube *.cub *.pdb *.out *.log *.gbw *.chk"),
                       ("所有文件", "*.*")],
        )
        if paths:
            self.queue_files(paths)

    def settings_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("程序和输出设置")
        dialog.transient(self)
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        for row, (title, variable, command) in enumerate([
            ("Multiwfn 程序", self.exe, self.choose_exe),
            ("结果根目录", self.output, self.choose_output),
        ]):
            ttk.Label(frame, text=title).grid(row=row, column=0, padx=6, pady=8)
            ttk.Entry(frame, textvariable=variable, width=65).grid(row=row, column=1)
            ttk.Button(frame, text="选择", command=command).grid(row=row, column=2, padx=8)
        ttk.Button(frame, text="完成", command=dialog.destroy).grid(row=2, column=2, pady=12)
        self.apply_language()

    def choose_exe(self):
        path = filedialog.askdirectory(
            parent=self, title="选择包含 Multiwfn.exe 的程序目录",
            initialdir=str(Path(self.exe.get()).parent) if self.exe.get() else str(self.backend.BASE),
        )
        if path:
            try:
                executable = self.backend.executable_from_directory(path)
                self.exe.set(executable)
                self.save_config()
                self.status.set("已记住 Multiwfn 程序目录")
                return True
            except (OSError, ValueError) as error:
                messagebox.showerror("目录未设置", str(error), parent=self)
        return False

    def choose_output(self):
        path = filedialog.askdirectory(title="选择结果根目录")
        if path:
            self.output.set(path)

    def queue_files(self, paths):
        try:
            if not self.exe.get() and not self.ensure_program_directory():
                return
            threads = int(self.threads.get())
            if not 1 <= threads <= (os.cpu_count() or 1):
                raise ValueError("线程数必须在 1 到 %d 之间。" % (os.cpu_count() or 1))
            if not self.output.get().strip():
                raise ValueError("请选择结果根目录。")
            for path in paths:
                if path and not Path(path).is_file():
                    raise ValueError("不是有效文件：" + str(path))
            if len(paths) > 4 and not messagebox.askyesno(
                "确认批量启动", "即将启动 %d 个会话，每个使用 %d 个线程，继续吗？" % (len(paths), threads), parent=self
            ):
                return
            self.save_config()
            for path in paths:
                self.launch_queue.append((str(path), threads, self.exe.get().strip(), self.output.get().strip()))
            self.launch_next()
        except (OSError, ValueError) as error:
            messagebox.showerror("无法启动", str(error), parent=self)

    def save_config(self):
        self.backend.save_config({
            "executable": self.exe.get().strip(), "output": self.output.get().strip(),
            "threads": int(self.threads.get()),
            "language": self.language,
        })

    def launch_next(self):
        if self.busy or not self.launch_queue or self.closing:
            return
        self.busy = True
        path, threads, exe, output = self.launch_queue.pop(0)
        self.status.set("正在启动：" + (Path(path).name if path else "空白会话"))
        result = {}

        def work():
            try:
                result["session"] = self.backend.launch_session(exe, output, path, threads)
            except Exception as error:
                result["error"] = str(error)
            result["done"] = True

        threading.Thread(target=work, daemon=True).start()

        def collect():
            if not result.get("done"):
                self.after(50, collect)
                return
            self.busy = False
            if "error" in result:
                self.backend.log_debug("启动失败：%s" % result["error"])
                messagebox.showerror("启动失败", result["error"], parent=self)
            else:
                self.counter += 1
                key = str(self.counter)
                session = result["session"]
                view = SessionView(self, key, session, threads)
                self.views[key] = view
                name = Path(path).name if path else "空白会话"
                if str(self.welcome) in self.notebook.tabs():
                    self.notebook.forget(self.welcome)
                self.notebook.add(view.panel, text="%s · %s" % (key, name))
                self.tree.insert("", "end", iid=key, text=name, values=("启动中",))
                self.notebook.select(view.panel)
                self.status.set("已启动 %s（%d 线程），正在托管原生窗口。" % (name, threads))
                self.apply_language()
            self.after(50, self.launch_next)

        self.after(50, collect)

    def selected(self):
        tab = self.notebook.select()
        return next((view for view in self.views.values() if str(view.panel) == tab), None)

    def select_tree(self, _=None):
        selected = self.tree.selection()
        if selected and selected[0] in self.views:
            view = self.views[selected[0]]
            if self.notebook.select() != str(view.panel):
                self.notebook.select(view.panel)

    def set_session_name(self, key, name):
        name = name.strip()
        if not name or "\n" in name or "\r" in name:
            raise ValueError("请输入非空的单行会话名称。")
        view = self.views.get(key)
        if view is None:
            return False
        view.custom_name = True
        self.tree.item(key, text=name)
        self.notebook.tab(view.panel, text="%s · %s" % (key, name))
        self.status.set("会话已重命名：" + name)
        return True

    def event_session_key(self, event):
        if event.widget is self.tree:
            if self.tree.identify_region(event.x, event.y) not in ("tree", "cell"):
                return None
            return self.tree.identify_row(event.y)
        if event.widget is self.notebook:
            if not self.notebook.identify(event.x, event.y):
                return None
            try:
                tab = self.notebook.tabs()[self.notebook.index("@%d,%d" % (event.x, event.y))]
            except tk.TclError:
                return None
            return next((key for key, view in self.views.items() if str(view.panel) == tab), None)
        return None

    def prompt_session_name(self, key):
        if key not in self.views:
            return
        self.tree.selection_set(key)
        name = simpledialog.askstring(
            "修改会话名称", "新会话名称：",
            initialvalue=self.tree.item(key, "text"), parent=self,
        )
        if name is not None:
            try:
                self.set_session_name(key, name)
            except ValueError as error:
                messagebox.showerror("名称无效", str(error), parent=self)

    def rename_session(self, event):
        key = self.event_session_key(event)
        if key in self.views:
            self.prompt_session_name(key)
            return "break"

    def session_menu(self, event):
        key = self.event_session_key(event)
        if key not in self.views:
            return
        self.tree.selection_set(key)
        self.notebook.select(self.views[key].panel)
        menu = tk.Menu(self, tearoff=False)
        menu.add_command(label=translate("修改名称", self.language), command=lambda: self.prompt_session_name(key))
        menu.add_separator()
        menu.add_command(label=translate("关闭会话", self.language), command=lambda: self.close_session(key),
                         foreground="#b44742")
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def select_tab(self, _=None):
        view = self.selected()
        if view:
            if self.tree.selection() != (view.key,):
                self.tree.selection_set(view.key)
            self.status.set("当前会话：%d 线程 | 结果目录：%s" % (view.threads, view.session.workspace))
            self.after_idle(lambda: self.resize_view(view))
            self.after_idle(view.focus_input)

    def resize_view(self, view):
        for native, parent in view.windows.values():
            try:
                native.resize(parent.winfo_width(), parent.winfo_height())
            except Exception:
                pass

    def refresh(self):
        if self.closing:
            return
        owners = {}
        for view in self.views.values():
            view.discover_pids()
            view.clean_windows()
            for pid in view.pids:
                owners[pid] = view
            alive = view.session.process.poll() is None
            if view.alive and not alive:
                detail = ""
                if view.last_sent:
                    sent_time, sent_text = view.last_sent
                    detail = "；最后发送=%r（%.1f 秒前）" % (sent_text, time.time() - sent_time)
                self.backend.log_debug("会话%s进程退出%s" % (view.key, detail))
            view.alive = alive
            state = "运行中" if alive else "已退出"
            if alive and not view.windows:
                state = "嵌入失败" if view.embedding_error else "启动中"
            self.tree.item(view.key, values=(translate(state, self.language),))
            if not alive and not view.windows:
                view.waiting.configure(text="该会话已退出。可重新启动，或关闭标签页。")
                view.waiting.pack(expand=True)
        candidates = []

        def visit(hwnd, _):
            pid = win32process.GetWindowThreadProcessId(hwnd)[1]
            if pid in owners:
                kind = win32gui.GetClassName(hwnd)
                # Native modal dialogs stay modal, rather than becoming tabs.
                if kind == "ConsoleWindowClass" or (
                    win32gui.IsWindowVisible(hwnd) and kind not in (
                        "#32770", "IME", "MSCTFIME UI", "tooltips_class32", "iFLY_notify_window"
                    ) and win32gui.GetWindowText(hwnd)
                ):
                    candidates.append((owners[pid], hwnd, win32gui.GetWindowText(hwnd), kind))
            return True

        try:
            win32gui.EnumWindows(visit, None)
            for view, hwnd, title, kind in candidates:
                view.capture(hwnd, title, kind)
        except Exception as error:
            self.status.set("窗口检测提示：" + str(error))
        self.apply_language()
        self.after(300, self.refresh)

    def open_results(self):
        view = self.selected()
        if view:
            try:
                os.startfile(str(view.session.workspace))
            except OSError as error:
                messagebox.showerror("无法打开目录", str(error), parent=self)

    def restart(self):
        view = self.selected()
        if view:
            self.queue_files([view.session.input_file])

    def close_session(self, key=None):
        view = self.views.get(key) if key is not None else self.selected()
        if not view:
            return
        if view.session.process.poll() is None and not messagebox.askyesno(
            "关闭会话", "将结束这个会话，未保存的计算结果可能丢失。继续吗？", parent=self
        ):
            return
        view.stop()
        self.notebook.forget(view.panel)
        view.panel.destroy()
        self.tree.delete(view.key)
        del self.views[view.key]
        if not self.views:
            self.notebook.add(self.welcome, text="开始")

    def close_manager(self):
        if self.busy:
            messagebox.showinfo("正在启动", "请等待当前会话启动完成后再关闭。", parent=self)
            return
        live = [view for view in self.views.values() if view.session.process.poll() is None]
        if live:
            answer = messagebox.askyesno(
                "关闭管理器",
                "关闭软件将结束全部内部分析会话，未保存结果可能丢失。\n\n确定关闭？",
                parent=self,
            )
            if not answer:
                return
        self.closing = True
        self.launch_queue.clear()
        for view in self.views.values():
            view.stop()
        try:
            self.save_config()
        except (OSError, ValueError):
            pass
        self.destroy()
