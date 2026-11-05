"""Windows integration, kept separate so desktop behavior can be tested."""
import ctypes
import os
import subprocess
import sys
from pathlib import Path

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
RUN_NAME = 'PNG Wanderer'

def startup_command():
    if getattr(sys, 'frozen', False):
        return subprocess.list2cmdline([sys.executable])
    executable = Path(sys.executable).with_name('pythonw.exe')
    return subprocess.list2cmdline([str(executable), str(Path(__file__).with_name('main.py').resolve())])

def startup_enabled():
    if sys.platform != 'win32': return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, RUN_NAME)
            return value == startup_command()
    except OSError:
        return False

def set_startup(enabled):
    if sys.platform != 'win32': raise OSError('Start with Windows is available on Windows only.')
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, startup_command())
        else:
            try: winreg.DeleteValue(key, RUN_NAME)
            except FileNotFoundError: pass

def foreground_fullscreen(rectangles):
    """Match the foreground window against a display, excluding shell/own windows."""
    if sys.platform != 'win32': return False
    from ctypes import wintypes
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    hwnd = user32.GetForegroundWindow()
    if not hwnd: return False
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value == os.getpid(): return False
    name = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, name, 256)
    if name.value in ('Progman', 'WorkerW', 'Shell_TrayWnd', 'Shell_SecondaryTrayWnd'): return False
    r = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(r)): return False
    # Native bounds avoid mixed-DPI coordinate conversion.
    return any(abs(r.left-x)<=2 and abs(r.top-y)<=2 and abs(r.right-(x+w))<=2 and abs(r.bottom-(y+h))<=2 for x,y,w,h in rectangles)

def native_monitors():
    if sys.platform != 'win32': return []
    from ctypes import wintypes
    result=[]
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HANDLE, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    def collect(monitor, dc, rect, data):
        r=rect.contents
        result.append((r.left,r.top,r.right-r.left,r.bottom-r.top))
        return True
    ctypes.windll.user32.EnumDisplayMonitors(None,None,callback_type(collect),0)
    return result
