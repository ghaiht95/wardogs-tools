import time
import keyboard
import pyautogui
from PIL import ImageGrab, ImageOps
import pytesseract
import random
import vgamepad as vg
# --- Tesseract Configuration (Change path if needed on Windows) ---
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
gamepad = vg.VX360Gamepad()
# Script running and stopping state
is_running = False

print("=" * 45)
print("     Color Detection & Auto-Click Script")
print("=" * 45)
print("[F7] : Toggle script (Start / Pause)")
print("[End] : Exit script completely")
print("-" * 45)
def random_move(duration=None):
    """تحريك عصا التحكم الافتراضية عشوائياً."""

    directions = [
        (0, -32768),      # إلى الأمام
        (0, 32767),       # إلى الخلف
        (-32768, 0),      # يسار
        (32767, 0),       # يمين
        (-23000, -23000), # أمام + يسار
        (23000, -23000),  # أمام + يمين
        (0, 0),            # توقف
    ]

    x, y = random.choice(directions)
    move_time = duration if duration is not None else random.uniform(0.3, 2.0)

    gamepad.left_joystick(x_value=x, y_value=y)
    gamepad.update()

    time.sleep(move_time)

    gamepad.left_joystick(x_value=0, y_value=0)
    gamepad.update()
def toggle_script():
    global is_running
    is_running = not is_running
    status = "ACTIVATED (Running)" if is_running else "STOPPED (Paused)"
    print(f"\n[!] Current script status: {status}")

# Bind the F7 key to toggle between running and stopped
keyboard.add_hotkey('f7', toggle_script)

def is_target_color(r, g, b):
    """
    Function to check if the color matches any of the target colors:
    1. Green (from original script)
    2. (242, 67, 50) with tolerance
    3. (63, 165, 231) with tolerance
    """
    is_green = (g > 130 and g > (r + 40) and g > (b + 40))
    is_color1 = (232 <= r <= 252) and (57 <= g <= 77) and (40 <= b <= 60)
    is_color2 = (53 <= r <= 73) and (155 <= g <= 175) and (221 <= b <= 241)
    return is_green or is_color1 or is_color2

# Coordinates of the area where "DEPLOYING" appears
LEFT = 700
TOP = 430
RIGHT = 1200
BOTTOM = 520

def check_for_deploying():
    """
    Takes a screenshot of the specified area and checks for 'deploying' or 'contract'.
    """
    try:
        bbox = (LEFT, TOP, RIGHT, BOTTOM)
        img = ImageGrab.grab(bbox=bbox)
        
        # Image preprocessing for better OCR recognition
        img_processed = ImageOps.grayscale(img)
        img_processed = ImageOps.invert(img_processed)
        img_processed = ImageOps.autocontrast(img_processed)
        
        text = pytesseract.image_to_string(img_processed, config='--psm 6').lower()
        
        if "deploying" in text or "deploy" in text or "contract" in text:
            return True
    except Exception as e:
        pass
    return False

# Main search loop
try:
    while True:
        # Check if the End key is pressed to exit completely
        if keyboard.is_pressed('end'):
            print("\n[!] Exit key (End) pressed. Script closed.")
            break

        if is_running:
            # 1. Check if "deploying" appears on the screen
            
            if check_for_deploying():
                is_running = False
                print(
                    "\n[!] Deploying detected. "
                    "Starting AFK random movement."
                )

                time.sleep(60)

                # Random movement for 60 seconds
                afk_end = time.monotonic() + 180

                while time.monotonic() < afk_end:
                    if keyboard.is_pressed('end'):
                        break

                    random_move()

                gamepad.left_joystick(x_value=0, y_value=0)
                gamepad.update()

                print("[!] AFK movement finished.")
                continue


            # 2. Get the current coordinates of the mouse pointer
            x, y = pyautogui.position()

            # Take a small screenshot (5x5 pixels) around the mouse for color detection
            bbox_mouse = (x - 2, y - 2, x + 3, y + 3)
            img_mouse = ImageGrab.grab(bbox=bbox_mouse)

            found_color = False
            for px in range(img_mouse.width):
                for py in range(img_mouse.height):
                    r, g, b = img_mouse.getpixel((px, py))[:3]
                    if is_target_color(r, g, b):
                        found_color = True
                        break
                if found_color:
                    break

            # If any of the target colors is found, perform a click
            if found_color:
                pyautogui.click()
                print(f"[+] Target color detected and clicked at: ({x}, {y})")
                
                # Slight delay to avoid excessively fast clicking
                time.sleep(0.3)

        # Short rest for the CPU
        time.sleep(0.01)

except Exception as e:
    print(f"\nAn error occurred: {e}")