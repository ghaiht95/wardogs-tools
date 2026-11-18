"""WarDogs Tools - PySide6 control panel for all automation features.

Install:  pip install PySide6 keyboard pyautogui pydirectinput pillow pytesseract
                      vgamepad opencv-python numpy mss
Run:      python app.py
"""
import json
import ctypes
import hashlib
import os
import random
import subprocess
import sys
import tempfile
import threading
import time
from ctypes import wintypes
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from PySide6.QtCore import QRectF, QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QDoubleSpinBox, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QSpinBox, QTabWidget, QToolButton, QVBoxLayout,
    QWidget,
)

try:
    import keyboard
except ImportError:
    keyboard = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TANK_DIR = os.path.join(BASE_DIR, "tank")
IS_PACKAGED = getattr(sys, "frozen", False)
APP_VERSION = "1.0.2"
RELEASES_API_URL = "https://api.github.com/repos/ghaiht95/wardogs-tools/releases/latest"
RELEASES_PAGE_URL = "https://github.com/ghaiht95/wardogs-tools/releases/latest"
INSTALLER_ASSET_NAME = "WarDogsTools-Setup.exe"
MAX_UPDATE_SIZE = 500 * 1024 * 1024
CONFIG_PATH = (
    os.path.join(os.environ["LOCALAPPDATA"], "WarDogsTools", "wardogs_gui_config.json")
    if IS_PACKAGED else os.path.join(BASE_DIR, "wardogs_gui_config.json")
)
BUNDLED_TESSERACT = os.path.join(BASE_DIR, "tesseract", "tesseract.exe")

DEFAULTS = {
    "general": {
        "tesseract_path": r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        "steam_app_id": "1867240",
    },
    "hotkeys": {
        "color": "f6",
        "tank": "f5",
        "bay_build": "f7",
        "bay_ammo": "f8",
        "bay_fuel": "f9",
        "bay_mech": "f10",
        "stop_all": "end",
    },
    "features": {
        "team_selection_enabled": True,
        "tank_hotkey_enabled": True,
        "quick_buy_enabled": True,
    },
    "color": {
        "process_name": "WardogsClient-Win64-Shipping.exe",
        "team": "green",
        "afk_wait": 60,
        "afk_duration": 180,
        "auto_afk": True,
        "team_regions": {
            "green": [1087, 512, 1105, 537],
            "red": [926, 498, 939, 508],
            "blue": [778, 503, 790, 517],
        },
    },
    "bay": {
        "region1": [679, 156, 1236, 901],
        "pallets": [597, 22, 694, 51],
        "build": [120, 211, 393, 359],
        "ammo": [406, 208, 663, 372],
        "fuel": [684, 206, 943, 360],
        "mech": [966, 208, 1235, 354],
        "key_hold": 0.2,
        "click_delay": 0.5,
    },
    "tank": {
        "region": [885, 600, 1035, 650],
        "threshold": 0.75,
        "press": 0.08,
        "release": 0.05,
        "seq_delay": 0.8,
    },
}

HOTKEY_LABELS = {
    "color": "Team selection (toggle)",
    "tank": "Tank arrows (toggle)",
    "bay_build": "Bay: build supply",
    "bay_ammo": "Bay: ammo supply",
    "bay_fuel": "Bay: fuel supply",
    "bay_mech": "Bay: mechanical supply",
    "stop_all": "Stop everything",
}

SUPPLIES = [
    ("build", "Build supply", "bay_build"),
    ("ammo", "Ammo supply", "bay_ammo"),
    ("fuel", "Fuel supply", "bay_fuel"),
    ("mech", "Mechanical supply", "bay_mech"),
]

JOYSTICK_DIRECTIONS = [
    (0, -32768), (0, 32767), (-32768, 0), (32767, 0),
    (-23000, -23000), (23000, -23000), (0, 0),
]

_gamepad = None
_gamepad_lock = threading.Lock()
_gamepad_update_lock = threading.Lock()
_afk_lock = threading.Lock()

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.GetForegroundWindow.restype = wintypes.HWND
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SW_RESTORE = 9


def process_exe_name(pid):
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value).lower()
        return ""
    finally:
        kernel32.CloseHandle(handle)


def find_game_window(process_name):
    """Returns the handle of the largest visible window owned by the process, or None."""
    target = process_name.strip().lower()
    if not target.endswith(".exe"):
        target += ".exe"
    best = {"hwnd": None, "area": -1}

    @WNDENUMPROC
    def callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.GetWindowTextLengthW(hwnd) == 0:
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if process_exe_name(pid.value) != target:
            return True
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        area = (rect.right - rect.left) * (rect.bottom - rect.top)
        if area > best["area"]:
            best["hwnd"], best["area"] = hwnd, area
        return True

    user32.EnumWindows(callback, 0)
    return best["hwnd"]


def window_process_id(hwnd):
    pid = wintypes.DWORD()
    if not user32.IsWindow(hwnd) or not user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid)):
        return None
    return pid.value or None


def focus_window(hwnd):
    """Restores and brings the window to the foreground. Returns True on success."""
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    foreground = user32.GetForegroundWindow()
    fg_thread = user32.GetWindowThreadProcessId(foreground, None) if foreground else 0
    this_thread = kernel32.GetCurrentThreadId()
    attached = bool(fg_thread) and fg_thread != this_thread and user32.AttachThreadInput(this_thread, fg_thread, True)
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(this_thread, fg_thread, False)
    return user32.GetForegroundWindow() == hwnd


def get_gamepad():
    """Single shared virtual Xbox controller (created on first use)."""
    global _gamepad
    with _gamepad_lock:
        if _gamepad is None:
            import vgamepad as vg
            _gamepad = vg.VX360Gamepad()
        return _gamepad


def restart_gamepad():
    """Disconnect the current virtual controller and create a new one."""
    global _gamepad
    with _gamepad_lock:
        import vgamepad as vg
        # vgamepad removes the virtual device when the last reference is released.
        _gamepad = None
        _gamepad = vg.VX360Gamepad()


TEAM_COLORS = {
    "green": lambda r, g, b: g > 130 and g > r + 40 and g > b + 40,
    "red": lambda r, g, b: r > 180 and r > g + 80 and r > b + 80,
    "blue": lambda r, g, b: b > 200 and g > 130 and b > r + 80 and r < 130,
}
MIN_TEAM_PIXELS = 6
SCAN_INTERVAL = 0.05
CLICK_INTERVAL = 0.3
DEPLOYING_REGION = (713, 468, 985, 514)


def version_tuple(version):
    value = version.strip()
    if value.startswith("v"):
        value = value[1:]
    parts = value.split(".")
    if len(parts) != 3 or any(not part.isdecimal() for part in parts):
        raise ValueError(f"Unsupported version: {version}")
    return tuple(int(part) for part in parts)


def parse_latest_release(payload):
    if not isinstance(payload, dict):
        raise ValueError("GitHub returned an invalid release response")
    tag = payload.get("tag_name")
    if not isinstance(tag, str):
        raise ValueError("GitHub release is missing a version tag")
    version_tuple(tag)

    release_url = payload.get("html_url")
    if not isinstance(release_url, str):
        release_url = ""
    release_page = urlsplit(release_url or "")
    if (
        release_page.scheme != "https"
        or release_page.hostname != "github.com"
        or not release_page.path.startswith("/ghaiht95/wardogs-tools/releases/")
    ):
        release_url = RELEASES_PAGE_URL

    assets = payload.get("assets", [])
    if not isinstance(assets, list):
        raise ValueError("GitHub release contains an invalid assets list")
    installer = next(
        (asset for asset in assets
         if isinstance(asset, dict) and asset.get("name") == INSTALLER_ASSET_NAME),
        None,
    )
    if installer is None:
        return {
            "tag": tag,
            "url": release_url,
            "installer_url": None,
            "digest": None,
        }

    installer_url = installer.get("browser_download_url")
    if not isinstance(installer_url, str):
        raise ValueError("GitHub release is missing the installer download URL")
    parsed_url = urlsplit(installer_url)
    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname != "github.com"
        or not parsed_url.path.startswith("/ghaiht95/wardogs-tools/releases/download/")
    ):
        raise ValueError("GitHub release contains an unexpected installer URL")

    digest = installer.get("digest")
    if digest is not None and (
        not isinstance(digest, str)
        or not digest.startswith("sha256:")
        or len(digest) != 71
        or any(char not in "0123456789abcdefABCDEF" for char in digest[7:])
    ):
        raise ValueError("GitHub release contains an invalid installer checksum")

    size = installer.get("size")
    if isinstance(size, int) and size > MAX_UPDATE_SIZE:
        raise ValueError("The published installer exceeds the download size limit")

    return {
        "tag": tag,
        "url": release_url,
        "installer_url": installer_url,
        "digest": digest,
    }


def download_release_asset(url, digest, destination, cancel_event):
    if not isinstance(url, str):
        raise ValueError("The installer download URL is invalid")
    parsed_url = urlsplit(url)
    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname != "github.com"
        or not parsed_url.path.startswith("/ghaiht95/wardogs-tools/releases/download/")
    ):
        raise ValueError("Refusing to download an installer from an unexpected URL")
    if not isinstance(digest, str) or not digest.startswith("sha256:") or len(digest) != 71:
        raise ValueError("The release does not provide a SHA-256 checksum")

    request = Request(url, headers={"User-Agent": "WarDogsTools-Updater"})
    try:
        with urlopen(request, timeout=10) as response:
            final_url = urlsplit(response.geturl())
            if (
                final_url.scheme != "https"
                or final_url.hostname not in {
                    "github.com", "objects.githubusercontent.com",
                    "release-assets.githubusercontent.com",
                }
            ):
                raise ValueError("Installer download redirected to an unexpected host")

            content_length = response.headers.get("Content-Length")
            expected_size = int(content_length) if content_length else None
            if expected_size is not None and expected_size > MAX_UPDATE_SIZE:
                raise ValueError("The installer exceeds the download size limit")

            hasher = hashlib.sha256()
            downloaded = 0
            cancelled = False
            with open(destination, "wb") as target:
                while True:
                    if cancel_event.is_set():
                        cancelled = True
                        break
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if downloaded > MAX_UPDATE_SIZE:
                        raise ValueError("The installer exceeds the download size limit")
                    target.write(chunk)
                    hasher.update(chunk)

            if cancelled:
                os.remove(destination)
                return False
            if expected_size is not None and downloaded != expected_size:
                raise ValueError("The installer download was incomplete")
            if f"sha256:{hasher.hexdigest()}" != digest.lower():
                raise ValueError("The installer checksum does not match the release")
        return True
    except (OSError, ValueError, URLError):
        try:
            os.remove(destination)
        except FileNotFoundError:
            pass
        raise


# =====================================================================
# Workers
# =====================================================================
class UpdateCheckWorker(QThread):
    checked = Signal(object)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        request = Request(
            RELEASES_API_URL,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "WarDogsTools-Updater",
            },
        )
        try:
            with urlopen(request, timeout=10) as response:
                payload_bytes = response.read(2 * 1024 * 1024 + 1)
            if len(payload_bytes) > 2 * 1024 * 1024:
                raise ValueError("GitHub release response is unexpectedly large")
            release = parse_latest_release(json.loads(payload_bytes.decode("utf-8")))
            if not self.cancel_event.is_set():
                self.checked.emit(release)
        except (OSError, ValueError, URLError) as exc:
            if not self.cancel_event.is_set():
                self.failed.emit(str(exc))


class UpdateDownloadWorker(QThread):
    downloaded = Signal(str)
    failed = Signal(str)

    def __init__(self, release, parent=None):
        super().__init__(parent)
        self.release = release
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        filename = f"WarDogsTools-Setup-{self.release['tag']}.exe"
        destination = os.path.join(tempfile.gettempdir(), filename)
        try:
            if download_release_asset(
                self.release["installer_url"],
                self.release["digest"],
                destination,
                self.cancel_event,
            ):
                self.downloaded.emit(destination)
        except (OSError, ValueError, URLError) as exc:
            if not self.cancel_event.is_set():
                self.failed.emit(str(exc))


class BaseWorker(QThread):
    log = Signal(str)
    done = Signal()

    def __init__(self, cfg):
        super().__init__()
        self.cfg = cfg
        self.stop_event = threading.Event()
        self.alive = True

    def stop(self):
        self.stop_event.set()

    def idle(self, seconds):
        """Interruptible sleep. Returns True when a stop was requested."""
        return self.stop_event.wait(max(0.0, seconds))

    def run(self):
        try:
            self.work()
        except Exception as e:
            self.log.emit(f"[ERROR] {e}")
        finally:
            self.alive = False
            self.done.emit()

    def work(self):
        raise NotImplementedError


class ColorWorker(BaseWorker):
    def __init__(self, cfg):
        super().__init__(cfg)
        self.auto_afk_enabled = threading.Event()
        self.set_auto_afk(cfg["color"]["auto_afk"])

    def set_auto_afk(self, enabled):
        if enabled:
            self.auto_afk_enabled.set()
        else:
            self.auto_afk_enabled.clear()

    def focus_game(self, process_name):
        """Returns False when the game is required but not running."""
        if not process_name:
            return True
        hwnd = find_game_window(process_name)
        if hwnd is None:
            self.log.emit(f"[COLOR] Game not running ({process_name}) - open it first")
            return False
        if focus_window(hwnd):
            self.log.emit("[COLOR] Game window brought to front")
        else:
            self.log.emit("[COLOR] Could not force the game to the foreground, continuing anyway")
        self.idle(0.5)
        return True

    def work(self):
        try:
            import pyautogui
            import pytesseract
            from PIL import ImageGrab, ImageOps
        except ImportError as e:
            self.log.emit(f"[COLOR] Missing package: {e}")
            return

        pytesseract.pytesseract.tesseract_cmd = (
            BUNDLED_TESSERACT if IS_PACKAGED else self.cfg["general"]["tesseract_path"]
        )
        ocr_config = "--psm 6"
        if IS_PACKAGED:
            # Env var avoids quoting problems with spaces in the install path
            os.environ["TESSDATA_PREFIX"] = os.path.join(BASE_DIR, "tesseract", "tessdata")
        c = self.cfg["color"]
        team = c["team"] if c["team"] in TEAM_COLORS else "green"

        self.log.emit(f"[COLOR] Started - team: {team}")
        try:
            if not self.focus_game(c["process_name"]):
                return
            while not self.stop_event.is_set():
                img = ImageGrab.grab(bbox=DEPLOYING_REGION)
                img = ImageOps.autocontrast(ImageOps.invert(ImageOps.grayscale(img)))
                text = pytesseract.image_to_string(img, config=ocr_config).lower()
                if self.stop_event.is_set():
                    break
                if "deploying" in text:
                    if not self.auto_afk_enabled.is_set():
                        self.log.emit("[COLOR] DEPLOYING detected - automatic AFK disabled")
                        break
                    self.log.emit("[COLOR] DEPLOYING detected - starting AFK movement")
                    self.afk(c)
                    break

                point = self.find_team(team, c["team_regions"][team], ImageGrab)
                if self.stop_event.is_set():
                    break
                if point is not None:
                    pyautogui.click(*point)
                    self.log.emit(f"[COLOR] Team {team} found - clicked at {point}")
                    self.idle(CLICK_INTERVAL)
                else:
                    self.idle(SCAN_INTERVAL)
        finally:
            self.log.emit("[COLOR] Stopped")

    def find_team(self, team, region, image_grab):
        """Returns the screen point at the center of the team's color inside its region, or None."""
        left, top, right, bottom = region
        img = image_grab.grab(bbox=(left, top, right, bottom)).convert("RGB")
        match = TEAM_COLORS[team]
        xs, ys = [], []
        for py in range(img.height):
            for px in range(img.width):
                if match(*img.getpixel((px, py))):
                    xs.append(px)
                    ys.append(py)
        if len(xs) < MIN_TEAM_PIXELS:
            return None
        return left + sum(xs) // len(xs), top + sum(ys) // len(ys)

    def afk(self, c, wait=True):
        if not _afk_lock.acquire(blocking=False):
            self.log.emit("[AFK] Movement is already running")
            return
        try:
            if wait and self.idle(c["afk_wait"]):
                return
            if self.stop_event.is_set():
                return
            try:
                pad = get_gamepad()
            except Exception as e:
                self.log.emit(f"[AFK] Virtual gamepad unavailable: {e}")
                return
            end = time.monotonic() + c["afk_duration"]
            self.log.emit("[AFK] Movement started")
            try:
                while not self.stop_event.is_set() and time.monotonic() < end:
                    x, y = random.choice(JOYSTICK_DIRECTIONS)
                    with _gamepad_update_lock:
                        pad.left_joystick(x_value=x, y_value=y)
                        pad.update()
                    self.idle(min(random.uniform(0.3, 2.0), max(0, end - time.monotonic())))
            finally:
                with _gamepad_update_lock:
                    pad.left_joystick(x_value=0, y_value=0)
                    pad.update()
            self.log.emit("[AFK] Movement finished")
        finally:
            _afk_lock.release()


class ManualAFKWorker(ColorWorker):
    def work(self):
        c = self.cfg["color"]
        if self.focus_game(c["process_name"]) and not self.stop_event.is_set():
            self.afk(c, wait=False)


class TankWorker(BaseWorker):
    preview = Signal(QImage)
    FILES = {"left": "left.png", "right": "right.png", "up": "up.png", "down": "down.png"}

    def load_templates(self, cv2, np):
        templates, missing = {}, []
        for name, filename in self.FILES.items():
            path = os.path.join(TANK_DIR, filename)
            img = None
            if os.path.exists(path):
                img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
            if img is None:
                missing.append(filename)
            else:
                templates[name] = img
        return templates, missing

    def detect(self, cv2, np, gray, templates, threshold):
        found = []
        for name, template in templates.items():
            res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
            for pt in zip(*np.where(res >= threshold)[::-1]):
                found.append((pt[0], name))
        found.sort(key=lambda item: item[0])
        sequence, last_x = [], -50
        for x, arrow in found:
            if abs(x - last_x) > 15:
                sequence.append(arrow)
                last_x = x
        return sequence

    def send(self, pad, buttons, sequence, t):
        for arrow in sequence:
            if self.stop_event.is_set():
                return
            with _gamepad_update_lock:
                pad.press_button(button=buttons[arrow])
                pad.update()
            self.idle(t["press"])
            with _gamepad_update_lock:
                pad.release_button(button=buttons[arrow])
                pad.update()
            self.idle(t["release"])

    def work(self):
        try:
            import cv2
            import mss
            import numpy as np
            import vgamepad as vg
        except ImportError as e:
            self.log.emit(f"[TANK] Missing package: {e}")
            return

        templates, missing = self.load_templates(cv2, np)
        if missing:
            self.log.emit(f"[TANK] Missing template files in tank/: {', '.join(missing)}")
            return

        t = self.cfg["tank"]
        pad = get_gamepad()
        x = vg.XUSB_BUTTON
        buttons = {
            "left": x.XUSB_GAMEPAD_DPAD_LEFT,
            "right": x.XUSB_GAMEPAD_DPAD_RIGHT,
            "up": x.XUSB_GAMEPAD_DPAD_UP,
            "down": x.XUSB_GAMEPAD_DPAD_DOWN,
        }
        left, top, right, bottom = t["region"]
        box = {"left": left, "top": top, "width": right - left, "height": bottom - top}
        last_sequence, last_preview = None, 0.0

        self.log.emit("[TANK] Started")
        try:
            with mss.mss() as sct:
                while not self.stop_event.is_set():
                    frame = np.array(sct.grab(box))
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)

                    now = time.monotonic()
                    if now - last_preview > 0.07:
                        last_preview = now
                        h, w = frame.shape[:2]
                        self.preview.emit(QImage(frame.data, w, h, w * 4, QImage.Format.Format_RGB32).copy())

                    sequence = self.detect(cv2, np, gray, templates, t["threshold"])
                    if sequence and sequence != last_sequence:
                        self.log.emit(f"[TANK] Detected: {sequence}")
                        self.send(pad, buttons, sequence, t)
                        last_sequence = sequence
                        self.idle(t["seq_delay"])
                    elif not sequence:
                        last_sequence = None
                    self.idle(0.01)
        finally:
            with _gamepad_update_lock:
                for button in buttons.values():
                    pad.release_button(button=button)
                pad.update()
            self.log.emit("[TANK] Stopped")


class BayWorker(BaseWorker):
    def __init__(self, cfg, supply):
        super().__init__(cfg)
        self.supply = supply

    def press(self, pydirectinput, key):
        pydirectinput.keyDown(key)
        try:
            self.idle(self.cfg["bay"]["key_hold"])
        finally:
            pydirectinput.keyUp(key)

    def click(self, pyautogui, region):
        left, top, right, bottom = region
        x, y = random.randint(left, right), random.randint(top, bottom)
        self.log.emit(f"[BAY] Click X={x}, Y={y}")
        pyautogui.click(x, y)
        self.idle(self.cfg["bay"]["click_delay"])

    def work(self):
        try:
            import pyautogui
            import pydirectinput
        except ImportError as e:
            self.log.emit(f"[BAY] Missing package: {e}")
            return

        b = self.cfg["bay"]
        steps = [
            ("Press B", lambda: self.press(pydirectinput, "b")),
            ("Random click in main area", lambda: self.click(pyautogui, b["region1"])),
            ("Random click in pallets area", lambda: self.click(pyautogui, b["pallets"])),
            (f"Random click in {self.supply} area", lambda: self.click(pyautogui, b[self.supply])),
            ("Press ESC", lambda: self.press(pydirectinput, "esc")),
        ]
        self.log.emit(f"[BAY] ===== {self.supply} sequence =====")
        for number, (title, action) in enumerate(steps, 1):
            if self.stop_event.is_set():
                self.log.emit("[BAY] Cancelled")
                return
            self.log.emit(f"[BAY] Step {number}: {title}")
            action()
        self.log.emit("[BAY] Sequence completed")


# =====================================================================
# Widgets
# =====================================================================
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
TEAM_ICON_SIZE = 72


class ToggleSwitch(QCheckBox):
    def __init__(self):
        super().__init__()
        self.setFixedSize(44, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(2, 4, 40, 18)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#2e9e44") if self.isChecked() else QColor("#777777"))
        painter.drawRoundedRect(track, 9, 9)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QRectF(24 if self.isChecked() else 4, 6, 14, 14))
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(self.palette().color(self.foregroundRole()), 1, Qt.PenStyle.DashLine))
            painter.drawRoundedRect(QRectF(0.5, 1.5, 43, 23), 11, 11)


class TeamPicker(QWidget):
    """Exclusive icon buttons (assets/<Team>.png) for choosing the team."""

    def __init__(self):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = {}
        for key in ("green", "red", "blue"):
            button = QToolButton()
            button.setCheckable(True)
            button.setToolTip(key.capitalize())
            icon_path = os.path.join(ASSETS_DIR, f"{key.capitalize()}.png")
            if os.path.exists(icon_path):
                button.setIcon(QIcon(icon_path))
                button.setIconSize(QSize(TEAM_ICON_SIZE, TEAM_ICON_SIZE))
            else:
                button.setText(key.capitalize())
            button.setStyleSheet(
                "QToolButton { border: 2px solid transparent; border-radius: 8px; padding: 4px; }"
                "QToolButton:hover { background: #2a2a2a; }"
                "QToolButton:checked { border-color: #f1c40f; background: #333; }"
            )
            self.group.addButton(button)
            self.buttons[key] = button
            row.addWidget(button)
        row.addStretch()
        self.buttons["green"].setChecked(True)

    def value(self):
        for key, button in self.buttons.items():
            if button.isChecked():
                return key
        return "green"

    def set_value(self, key):
        self.buttons.get(key, self.buttons["green"]).setChecked(True)


def read_widget(w):
    if isinstance(w, TeamPicker):
        return w.value()
    if isinstance(w, QCheckBox):
        return w.isChecked()
    if isinstance(w, QLineEdit):
        return w.text().strip()
    return w.value()


def write_widget(w, value):
    if isinstance(w, TeamPicker):
        w.set_value(value)
    elif isinstance(w, QCheckBox):
        w.setChecked(bool(value))
    elif isinstance(w, QLineEdit):
        w.setText(str(value))
    else:
        w.setValue(value)


def spin(lo, hi):
    s = QSpinBox()
    s.setRange(lo, hi)
    return s


def dspin(lo, hi, step, decimals):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setSingleStep(step)
    s.setDecimals(decimals)
    return s


def load_config():
    cfg = {sec: dict(vals) for sec, vals in DEFAULTS.items()}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
        for sec, vals in saved.items():
            if sec in cfg and isinstance(vals, dict):
                for key, value in vals.items():
                    if key in cfg[sec]:
                        cfg[sec][key] = value
    except (OSError, ValueError):
        pass
    return cfg


# =====================================================================
# Main window
# =====================================================================
class MainWindow(QMainWindow):
    hotkey_fired = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("WarDogs Tools")
        self.setWindowIcon(QIcon(os.path.join(ASSETS_DIR, "icon.png")))
        self.resize(820, 720)

        self.initial = load_config()
        self.widgets = {}
        self.workers = {"color": None, "afk": None, "tank": None, "bay": None}
        self.all_workers = []
        self.worker_windows = {}
        self.status_labels = {}
        self.toggle_buttons = {}
        self.supply_buttons = []
        self.hotkey_handles = []
        self.update_check_worker = None
        self.update_download_worker = None
        self.game_monitor = QTimer(self)
        self.game_monitor.setInterval(250)
        self.game_monitor.timeout.connect(self.check_game_windows)

        central = QWidget()
        layout = QVBoxLayout(central)
        self.setCentralWidget(central)

        tabs = QTabWidget()
        tabs.addTab(self.build_color_tab(), "Team selection")
        tabs.addTab(self.build_bay_tab(), "Autobay")
        tabs.addTab(self.build_tank_tab(), "Tank arrows")
        tabs.addTab(self.build_settings_tab(), "Settings")
        layout.addWidget(tabs, 3)

        bar = QHBoxLayout()
        launch = QPushButton("Launch game")
        launch.clicked.connect(self.launch_game)
        restart_controller = QPushButton("Restart controller")
        restart_controller.clicked.connect(self.restart_controller)
        stop_all = QPushButton("Stop all")
        stop_all.clicked.connect(self.stop_all)
        save = QPushButton("Save settings")
        save.clicked.connect(self.save_config)
        bar.addWidget(launch)
        bar.addWidget(restart_controller)
        bar.addWidget(stop_all)
        bar.addWidget(save)
        bar.addStretch()
        layout.addLayout(bar)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(1000)
        layout.addWidget(self.log_view, 2)

        self.hotkey_fired.connect(self.on_hotkey)
        self.refresh()
        if keyboard is None:
            self.log("[WARN] 'keyboard' package missing - global hotkeys disabled")
        else:
            self.register_hotkeys()
        if IS_PACKAGED:
            QTimer.singleShot(2000, self.check_for_updates)

    # ---- helpers -----------------------------------------------------
    def make(self, section, key, widget):
        write_widget(widget, self.initial[section][key])
        self.widgets[(section, key)] = widget
        return widget

    def control_row(self, name, start_text):
        row = QHBoxLayout()
        button = QPushButton(start_text)
        button.clicked.connect(lambda: self.toggle(name))
        label = QLabel()
        row.addWidget(button)
        row.addWidget(label, 1)
        self.toggle_buttons[name] = (button, start_text)
        self.status_labels[name] = label
        return row

    def build_color_tab(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.addLayout(self.control_row("color", "Start"))
        team_selection = self.make("features", "team_selection_enabled", ToggleSwitch())
        team_selection.setAccessibleName("Enable team selection hotkey")
        team_selection_row = QHBoxLayout()
        team_selection_row.addWidget(QLabel("Enable team selection hotkey"))
        team_selection_row.addWidget(team_selection)
        team_selection_row.addStretch()
        v.addLayout(team_selection_row)
        v.addLayout(self.control_row("afk", "Start AFK now"))
        box = QGroupBox("Settings")
        form = QFormLayout(box)
        form.addRow("Team", self.make("color", "team", TeamPicker()))
        form.addRow("Wait before AFK (s)", self.make("color", "afk_wait", spin(0, 3600)))
        form.addRow("AFK duration (s)", self.make("color", "afk_duration", spin(0, 36000)))
        auto_afk = self.make("color", "auto_afk", ToggleSwitch())
        auto_afk.setAccessibleName("Automatic AFK after DEPLOYING")
        auto_afk.toggled.connect(self.set_auto_afk)
        form.addRow("Automatic AFK after DEPLOYING", auto_afk)
        v.addWidget(box)
        v.addStretch()
        return page

    def build_bay_tab(self):
        page = QWidget()
        v = QVBoxLayout(page)

        row = QHBoxLayout()
        for key, title, _ in SUPPLIES:
            button = QPushButton(title)
            button.clicked.connect(lambda _=False, k=key: self.start("bay", k))
            row.addWidget(button)
            self.supply_buttons.append(button)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(lambda: self.stop("bay"))
        row.addWidget(cancel)
        v.addLayout(row)
        self.status_labels["bay"] = QLabel()
        v.addWidget(self.status_labels["bay"])
        quick_buy = self.make("features", "quick_buy_enabled", ToggleSwitch())
        quick_buy.setAccessibleName("Enable quick buy")
        quick_buy.toggled.connect(self.set_quick_buy_enabled)
        quick_buy_row = QHBoxLayout()
        quick_buy_row.addWidget(QLabel("Enable quick buy"))
        quick_buy_row.addWidget(quick_buy)
        quick_buy_row.addStretch()
        v.addLayout(quick_buy_row)

        box = QGroupBox("Timing")
        form = QFormLayout(box)
        form.addRow("Key hold (s)", self.make("bay", "key_hold", dspin(0.01, 5.0, 0.05, 2)))
        form.addRow("Click delay (s)", self.make("bay", "click_delay", dspin(0.0, 10.0, 0.05, 2)))
        v.addWidget(box)
        v.addStretch()
        return page

    def build_tank_tab(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.addLayout(self.control_row("tank", "Start"))

        self.preview = QLabel("Preview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(110)
        self.preview.setStyleSheet("background: #111; color: #888;")
        v.addWidget(self.preview)

        box = QGroupBox("Settings")
        form = QFormLayout(box)
        tank_hotkey = self.make("features", "tank_hotkey_enabled", ToggleSwitch())
        tank_hotkey.setAccessibleName("Enable Tank F5 hotkey")
        form.addRow("Enable Tank F5 hotkey", tank_hotkey)
        form.addRow("Match threshold", self.make("tank", "threshold", dspin(0.3, 1.0, 0.01, 2)))
        form.addRow("Button press (s)", self.make("tank", "press", dspin(0.01, 2.0, 0.01, 3)))
        form.addRow("Between buttons (s)", self.make("tank", "release", dspin(0.0, 2.0, 0.01, 3)))
        form.addRow("Delay after sequence (s)", self.make("tank", "seq_delay", dspin(0.0, 10.0, 0.1, 2)))
        v.addWidget(box)
        v.addStretch()
        return page

    def build_settings_tab(self):
        page = QWidget()
        v = QVBoxLayout(page)

        hotkeys = QGroupBox("Global hotkeys")
        hform = QFormLayout(hotkeys)
        for action, title in HOTKEY_LABELS.items():
            hform.addRow(title, self.make("hotkeys", action, QLineEdit()))
        apply_btn = QPushButton("Apply hotkeys")
        apply_btn.clicked.connect(self.register_hotkeys)
        hform.addRow("", apply_btn)
        v.addWidget(hotkeys)
        v.addStretch()
        return page

    # ---- config ------------------------------------------------------
    def collect_config(self):
        # Screen regions are not shown in the UI; they keep their built-in/saved values.
        cfg = {sec: dict(vals) for sec, vals in self.initial.items()}
        for (section, key), widget in self.widgets.items():
            cfg[section][key] = read_widget(widget)
        return cfg

    def save_config(self):
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.collect_config(), f, indent=2)
            self.log(f"[GUI] Settings saved to {CONFIG_PATH}")
        except OSError as e:
            self.log(f"[GUI] Could not save settings: {e}")

    # ---- logging / state --------------------------------------------
    def log(self, message):
        self.log_view.appendPlainText(f"{time.strftime('%H:%M:%S')}  {message}")

    def is_active(self, name):
        worker = self.workers[name]
        return worker is not None and worker.alive

    def refresh(self):
        for name, (button, start_text) in self.toggle_buttons.items():
            active = self.is_active(name)
            button.setText(("Stop AFK" if name == "afk" else "Stop") if active else start_text)
            label = self.status_labels[name]
            label.setText("RUNNING" if active else "STOPPED")
            label.setStyleSheet("color: #2e9e44; font-weight: bold;" if active else "color: #c0392b; font-weight: bold;")
        bay_active = self.is_active("bay")
        self.status_labels["bay"].setText(f"Sequence running: {self.workers['bay'].supply}" if bay_active else "Idle")
        for button in self.supply_buttons:
            button.setEnabled(not bay_active and self.quick_buy_enabled())

    # ---- worker control ---------------------------------------------
    def start(self, name, *args):
        if name == "bay" and not self.quick_buy_enabled():
            self.log("[GUI] Quick buy is disabled")
            return
        if self.is_active(name):
            self.log(f"[GUI] {name} is already running")
            return
        cfg = self.collect_config()
        process_name = cfg["color"]["process_name"].strip()
        hwnd = find_game_window(process_name) if process_name else None
        pid = window_process_id(hwnd) if hwnd is not None else None
        if pid is None:
            self.log("[GUI] Game window not found - open WARDOGS before starting tasks")
            return
        if name == "color":
            worker = ColorWorker(cfg)
        elif name == "afk":
            worker = ManualAFKWorker(cfg)
        elif name == "tank":
            worker = TankWorker(cfg)
            worker.preview.connect(self.on_preview)
        else:
            worker = BayWorker(cfg, *args)
        worker.log.connect(self.log)
        worker.done.connect(self.refresh)

        self.all_workers = [w for w in self.all_workers if not w.isFinished()]
        self.all_workers.append(worker)
        self.workers[name] = worker
        self.worker_windows[worker] = (hwnd, pid)
        worker.start()
        self.game_monitor.start()
        self.refresh()

    def check_game_windows(self):
        for worker, (hwnd, pid) in list(self.worker_windows.items()):
            if worker.isFinished():
                del self.worker_windows[worker]
            elif window_process_id(hwnd) != pid:
                self.log("[GUI] Game window closed - stopping task")
                worker.stop()
                del self.worker_windows[worker]
        if not self.worker_windows:
            self.game_monitor.stop()

    def stop(self, name):
        worker = self.workers[name]
        if worker is not None and worker.alive:
            worker.stop()

    def set_auto_afk(self, enabled):
        worker = self.workers["color"]
        if worker is not None and worker.alive:
            worker.set_auto_afk(enabled)

    def team_selection_enabled(self):
        return read_widget(self.widgets[("features", "team_selection_enabled")])

    def quick_buy_enabled(self):
        return read_widget(self.widgets[("features", "quick_buy_enabled")])

    def set_quick_buy_enabled(self, enabled):
        if not enabled:
            self.stop("bay")
        self.refresh()

    def check_for_updates(self):
        if self.update_check_worker is not None and self.update_check_worker.isRunning():
            return
        worker = UpdateCheckWorker(self)
        worker.checked.connect(self.on_update_check_complete)
        worker.failed.connect(lambda message: self.log(f"[Update] Check failed: {message}"))
        worker.finished.connect(lambda: setattr(self, "update_check_worker", None))
        self.update_check_worker = worker
        self.log("[Update] Checking for updates...")
        worker.start()

    def on_update_check_complete(self, release):
        if version_tuple(release["tag"]) <= version_tuple(APP_VERSION):
            self.log(f"[Update] You are using the latest version ({APP_VERSION})")
            return

        if not release["installer_url"] or not release["digest"]:
            self.log(f"[Update] Version {release['tag']} is available without a verified installer")
            QMessageBox.information(
                self,
                "Update available",
                f"Version {release['tag']} is available. Open the release page to download it.",
            )
            if not QDesktopServices.openUrl(QUrl(release["url"])):
                self.log("[Update] Could not open the GitHub release page")
            return

        answer = QMessageBox.question(
            self,
            "Update available",
            f"WarDogs Tools {release['tag']} is available. Download and run its installer now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.download_update(release)

    def download_update(self, release):
        if self.update_download_worker is not None and self.update_download_worker.isRunning():
            return
        worker = UpdateDownloadWorker(release, self)
        worker.downloaded.connect(self.launch_update_installer)
        worker.failed.connect(lambda message: self.log(f"[Update] Download failed: {message}"))
        worker.finished.connect(lambda: setattr(self, "update_download_worker", None))
        self.update_download_worker = worker
        self.log(f"[Update] Downloading version {release['tag']}...")
        worker.start()

    def launch_update_installer(self, installer_path):
        try:
            subprocess.Popen([installer_path], close_fds=True)
        except OSError as exc:
            self.log(f"[Update] Could not launch installer: {exc}")
            QMessageBox.warning(self, "Update failed", f"Could not launch the installer:\n{exc}")
            return
        self.log("[Update] Installer launched; Windows may request administrator permission")
        self.close()

    def toggle(self, name):
        if self.is_active(name):
            self.stop(name)
        else:
            self.start(name)

    def launch_game(self):
        cfg = self.collect_config()
        hwnd = find_game_window(cfg["color"]["process_name"])
        if hwnd is not None:
            focus_window(hwnd)
            self.log("[GUI] Game is already running - brought to front")
            return
        try:
            os.startfile(f"steam://rungameid/{cfg['general']['steam_app_id']}")
            self.log("[GUI] Launching WARDOGS through Steam...")
        except OSError as e:
            self.log(f"[GUI] Could not launch the game (is Steam installed?): {e}")

    def restart_controller(self):
        if any(not worker.isFinished() for worker in self.all_workers):
            self.log("[GUI] Stop all tasks and wait for them to finish before restarting the controller")
            return
        try:
            restart_gamepad()
        except Exception as e:
            self.log(f"[GUI] Could not restart the virtual controller: {e}")
            return
        self.log("[GUI] Virtual controller reconnected")

    def stop_all(self):
        for name in self.workers:
            self.stop(name)

    def on_preview(self, image):
        pixmap = QPixmap.fromImage(image).scaled(
            self.preview.width(), self.preview.height(),
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation,
        )
        self.preview.setPixmap(pixmap)

    # ---- hotkeys -----------------------------------------------------
    def register_hotkeys(self):
        for handle in self.hotkey_handles:
            try:
                keyboard.remove_hotkey(handle)
            except (KeyError, ValueError):
                pass
        self.hotkey_handles = []
        for action in HOTKEY_LABELS:
            combo = read_widget(self.widgets[("hotkeys", action)])
            if not combo:
                continue
            try:
                handle = keyboard.add_hotkey(combo, lambda a=action: self.hotkey_fired.emit(a))
                self.hotkey_handles.append(handle)
            except Exception as e:
                self.log(f"[GUI] Invalid hotkey '{combo}' for {action}: {e}")
        self.log("[GUI] Hotkeys registered")

    def on_hotkey(self, action):
        if action == "tank":
            if read_widget(self.widgets[("features", "tank_hotkey_enabled")]):
                self.toggle("tank")
        elif action == "color":
            if self.team_selection_enabled():
                self.toggle(action)
        elif action == "stop_all":
            self.stop_all()
        elif action.startswith("bay_"):
            if not self.quick_buy_enabled():
                return
            for key, _, hotkey_action in SUPPLIES:
                if hotkey_action == action:
                    self.start("bay", key)

    # ---- shutdown ----------------------------------------------------
    def closeEvent(self, event):
        self.stop_all()
        for worker in self.all_workers:
            worker.wait(3000)
        for worker in (self.update_check_worker, self.update_download_worker):
            if worker is not None and worker.isRunning():
                worker.cancel()
                if not worker.wait(15000):
                    self.log("[Update] Wait for the update task to finish before closing")
                    event.ignore()
                    return
        for handle in self.hotkey_handles:
            try:
                keyboard.remove_hotkey(handle)
            except (KeyError, ValueError):
                pass
        self.save_config()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
