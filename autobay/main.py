
import time
import random
import threading
import keyboard
import pyautogui
import pydirectinput
import pytesseract
import os
from pytesseract import Output

# =========================================
# CONFIGURATION
# =========================================

SEARCH_TIMEOUT = 20

# First random click area
REGION_1 = (679, 156, 1236, 901)

# PALLETS OCR search area
PALLETS_REGION = (597, 22, 694, 51)

# Second random click areas
REGIONS = {
    "F7": (120, 211, 393, 359),
    "F8": (406, 208, 663, 372),
    "F9": (684, 206, 943, 360),
    "F10": (966, 208, 1235, 354)
}

# Tesseract path
pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

# State
closing = False
lock = threading.Lock()


# =========================================
# KEY PRESS
# =========================================

def press_key(key):

    pydirectinput.keyDown(key)
    time.sleep(0.2)
    pydirectinput.keyUp(key)


# =========================================
# RANDOM CLICK
# =========================================

def random_click(region, name):

    left, top, right, bottom = region

    x = random.randint(left, right)
    y = random.randint(top, bottom)

    print(f"[{name}] X={x}, Y={y}")

    pyautogui.click(x, y)

    time.sleep(0.5)


# =========================================
# RANDOM CLICK IN PALLETS REGION
# =========================================

def random_click_pallets_region():

    print("[STEP 3] Random click in pallets area")

    left, top, right, bottom = PALLETS_REGION

    x = random.randint(left, right)
    y = random.randint(top, bottom)

    print(f"[PALLETS AREA] X={x}, Y={y}")

    pyautogui.click(x, y)

    time.sleep(0.5)

    return True

# =========================================
# MAIN SEQUENCE
# =========================================

def execute(region_name):

    if not lock.acquire(blocking=False):
        print("[BUSY] Another sequence is running")
        return

    try:

        if closing:
            return

        print("\n========== START ==========")
        print(f"[MODE] {region_name}")

        # STEP 1: Press B
        print("[STEP 1] Pressing B")

        press_key("b")



        if closing:
            return

        # STEP 2: First random click
        print("[STEP 2] First random click")

        random_click(REGION_1, "REGION 1")

        if closing:
            return

        # STEP 3: Random click in pallets area
        print("[STEP 3] Random click in pallets area")

        random_click_pallets_region()

        if closing:
            return

        # STEP 4: Second random click
        print("[STEP 4] Second random click")

        random_click(
            REGIONS[region_name],
            region_name
        )

        if closing:
            return

        # STEP 5: Press ESC
        print("[STEP 5] Pressing ESC")

        press_key("esc")

        print("[SUCCESS] Sequence completed!")

    except Exception as e:

        print(f"[ERROR] {e}")

    finally:

        lock.release()


# =========================================
# EXIT SCRIPT
# =========================================

def exit_script():

    global closing

    closing = True

    print("[EXIT] Closing script...")

    keyboard.unhook_all()

    os._exit(0)


# =========================================
# HOTKEYS
# =========================================

print("================================")
print("AUTOMATION READY")
print("================================")
print("F7  = build supply")
print("F8  = Ammo supply")
print("F9  = fuel supply")
print("F10 = mechanical supply")
print("END = EXIT SCRIPT")
print("================================")

keyboard.add_hotkey(
    "F7",
    lambda: execute("F7")
)

keyboard.add_hotkey(
    "F8",
    lambda: execute("F8")
)

keyboard.add_hotkey(
    "F9",
    lambda: execute("F9")
)

keyboard.add_hotkey(
    "F10",
    lambda: execute("F10")
)

keyboard.add_hotkey(
    "end",
    exit_script
)

keyboard.wait()
