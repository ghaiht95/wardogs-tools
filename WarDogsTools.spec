import os
from pathlib import Path

from PIL import Image
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

root = Path(SPECPATH)
icon_png = root / "assets" / "icon.png"
icon_ico = root / "assets" / "icon.ico"
if not icon_png.is_file():
    raise SystemExit(f"Application icon not found: {icon_png}")
Image.open(icon_png).save(str(icon_ico), format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])

tesseract = Path(os.environ.get("TESSERACT_DIR", r"C:\Program Files\Tesseract-OCR"))
required = [
    tesseract / "tesseract.exe",
    tesseract / "tessdata" / "eng.traineddata",
    tesseract / "doc" / "LICENSE",
]
missing = [str(path) for path in required if not path.is_file()]
if missing:
    raise SystemExit("Required Tesseract files missing: " + ", ".join(missing))

datas = [
    (str(root / "assets"), "assets"),
    (str(root / "tank" / "*.png"), "tank"),
    (str(tesseract / "tesseract.exe"), "tesseract"),
    (str(tesseract / "*.dll"), "tesseract"),
    (str(tesseract / "tessdata" / "eng.traineddata"), "tesseract/tessdata"),
    (str(tesseract / "doc"), "tesseract/doc"),
    (str(root / "DISTRIBUTION.txt"), "."),
]
datas += collect_data_files("vgamepad", includes=["win/vigem/client/**/*"])
for package in [
    "PySide6", "PySide6_Essentials", "shiboken6", "keyboard", "PyAutoGUI",
    "PyDirectInput", "Pillow", "pytesseract", "vgamepad", "opencv-python",
    "numpy", "mss", "pymsgbox", "pytweening", "pyscreeze", "pygetwindow",
    "mouseinfo", "pyrect", "pyperclip", "packaging",
]:
    datas += copy_metadata(package)

a = Analysis(
    [str(root / "app.py")],
    datas=datas,
    hiddenimports=["pyautogui", "pydirectinput", "pytesseract", "vgamepad", "cv2", "numpy", "mss"],
    excludes=["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtPdf"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="WarDogsTools",
    icon=str(icon_ico), console=False, disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="WarDogsTools")
