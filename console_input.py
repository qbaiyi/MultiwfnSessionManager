"""Send Unicode input records through a short-lived attached console helper."""

import ctypes
from ctypes import wintypes
import json
import sys
import time


class SelectionInfo(ctypes.Structure):
    _fields_ = [
        ("flags", wintypes.DWORD), ("anchor", wintypes._COORD),
        ("rectangle", wintypes._SMALL_RECT),
    ] if hasattr(wintypes, "_COORD") else [
        ("flags", wintypes.DWORD), ("anchor", wintypes.DWORD),
        ("rectangle", ctypes.c_short * 4),
    ]


class KeyEvent(ctypes.Structure):
    _fields_ = [
        ("down", wintypes.BOOL), ("repeat", wintypes.WORD),
        ("key", wintypes.WORD), ("scan", wintypes.WORD),
        ("char", ctypes.c_wchar), ("control", wintypes.DWORD),
    ]


class EventUnion(ctypes.Union):
    _fields_ = [("key", KeyEvent), ("padding", ctypes.c_byte * 16)]


class InputRecord(ctypes.Structure):
    _fields_ = [("kind", wintypes.WORD), ("event", EventUnion)]


def send_console_input(pid, text):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.AttachConsole.argtypes = [wintypes.DWORD]
    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.WriteConsoleInputW.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(InputRecord), wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.GetConsoleSelectionInfo.argtypes = [ctypes.POINTER(SelectionInfo)]
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    # The console owner (Multiwfn or conhost) must still be alive; otherwise the
    # input would land in a stale console and the send would look successful.
    probe = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not probe:
        raise OSError("目标进程已退出，输入未发送。")
    kernel.CloseHandle(probe)
    kernel.FreeConsole()
    # Rapid attach/detach cycles can transiently return ERROR_ACCESS_DENIED (5).
    for attempt in range(3):
        ctypes.set_last_error(0)
        if kernel.AttachConsole(pid):
            break
        error = ctypes.get_last_error()
        if error != 5 or attempt == 2:
            raise ctypes.WinError(error)
        time.sleep(0.12)
    handle = None
    try:
        handle = kernel.CreateFileW("CONIN$", 0xC0000000, 3, None, 3, 0, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        mode = wintypes.DWORD()
        if kernel.GetConsoleMode(handle, ctypes.byref(mode)):
            # Quick Edit can pause Multiwfn indefinitely after a mouse selection.
            kernel.SetConsoleMode(handle, (mode.value | 0x80) & ~0x40)
        selection = SelectionInfo()
        if kernel.GetConsoleSelectionInfo(ctypes.byref(selection)) and selection.flags:
            raise OSError("控制台正在选择文本，请点击命令窗口并按 Esc 取消选择后再发送。")
        # UTF-16 units preserve non-ASCII Windows file paths, including surrogates.
        units = (text + "\r").encode("utf-16-le", errors="surrogatepass")
        records = (InputRecord * (len(units)))()
        for index in range(len(units) // 2):
            char = chr(int.from_bytes(units[index * 2:index * 2 + 2], "little"))
            for offset, down in enumerate((True, False)):
                record = records[index * 2 + offset]
                record.kind = 1
                record.event.key = KeyEvent(
                    down, 1, 13 if char == "\r" else 0, 0, char, 0,
                )
        written = wintypes.DWORD()
        if not kernel.WriteConsoleInputW(handle, records, len(records), ctypes.byref(written)):
            raise ctypes.WinError(ctypes.get_last_error())
        if written.value != len(records):
            raise OSError("Console input was only partially written")
    finally:
        if handle and handle != ctypes.c_void_p(-1).value:
            kernel.CloseHandle(handle)
        kernel.FreeConsole()


def serve_console(pid):
    """A single helper per session avoids repeated GUI executable startup."""
    for line in sys.stdin:
        request = {}
        try:
            request = json.loads(line)
            if request.get("action") == "close":
                break
            send_console_input(pid, request["text"])
            response = {"id": request["id"], "ok": True}
        except Exception as error:
            response = {"id": request.get("id") if isinstance(request, dict) else None,
                        "ok": False, "error": str(error)}
        sys.stdout.write(json.dumps(response, ensure_ascii=True) + "\n")
        sys.stdout.flush()
