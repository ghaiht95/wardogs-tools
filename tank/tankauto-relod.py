
import os
import time
import cv2
import numpy as np
import vgamepad as vg
import mss
import keyboard

# =====================================================
# WARDOGS ARROW INPUT
# Fast D-PAD taps
# No training / No game memory access
# =====================================================

gamepad = vg.VX360Gamepad()

BUTTON_MAPPING = {
    'left': vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
    'right': vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT,
    'up': vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
    'down': vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN
}

# Timing
PRESS_TIME = 0.08       # 80 ms button press
RELEASE_TIME = 0.05     # 50 ms between buttons
SEQUENCE_DELAY = 0.8    # Delay after sequence

ARROW_BOX = {
    "top": 600,
    "left": 885,
    "width": 150,
    "height": 50
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

template_files = {
    'left': 'left.png',
    'right': 'right.png',
    'up': 'up.png',
    'down': 'down.png'
}

templates = {}
missing_files = []

for name, filename in template_files.items():
    path = os.path.join(BASE_DIR, filename)
    img = cv2.imread(path, 0)

    if img is None:
        missing_files.append(filename)
    else:
        templates[name] = img

if missing_files:
    print("Missing template files:")
    for f in missing_files:
        print(" -", f)
    raise SystemExit(1)


def detect_sequence(screen_gray):
    detected_arrows = []
    threshold = 0.75

    for name, template in templates.items():
        res = cv2.matchTemplate(
            screen_gray,
            template,
            cv2.TM_CCOEFF_NORMED
        )

        loc = np.where(res >= threshold)

        for pt in zip(*loc[::-1]):
            detected_arrows.append((pt[0], name))

    detected_arrows.sort(key=lambda x: x[0])

    final_sequence = []
    last_x = -50

    for x, arrow in detected_arrows:
        if abs(x - last_x) > 15:
            final_sequence.append(arrow)
            last_x = x

    return final_sequence


def release_all():
    gamepad.reset()
    gamepad.update()


def send_xbox_inputs(sequence):
    for arrow in sequence:

        if keyboard.is_pressed('end'):
            break

        button = BUTTON_MAPPING[arrow]

        # Quick press
        gamepad.press_button(button=button)
        gamepad.update()

        start = time.perf_counter()

        while time.perf_counter() - start < PRESS_TIME:
            if keyboard.is_pressed('end'):
                break
            time.sleep(0.001)

        # Release immediately
        gamepad.release_button(button=button)
        gamepad.update()

        time.sleep(RELEASE_TIME)


is_running = False
last_sequence = None

print("=== WARDOGS INPUT ===")
print("F7  : START")
print("F8  : PAUSE")
print("END : EXIT")
print("=====================")

sct = mss.MSS()

try:
    while True:

        if keyboard.is_pressed('end'):
            print("Closing...")
            break

        if keyboard.is_pressed('f7'):
            if not is_running:
                is_running = True
                last_sequence = None
                print("RUNNING")
                time.sleep(0.3)

        if keyboard.is_pressed('f8'):
            if is_running:
                is_running = False
                last_sequence = None
                release_all()
                print("PAUSED")
                time.sleep(0.3)

        sct_img = sct.grab(ARROW_BOX)
        frame = np.array(sct_img)

        gray_frame = cv2.cvtColor(
            frame,
            cv2.COLOR_BGRA2GRAY
        )

        preview_frame = frame.copy()

        status_text = (
            "Status: RUNNING"
            if is_running
            else "Status: PAUSED"
        )

        color = (
            (0, 255, 0)
            if is_running
            else (0, 0, 255)
        )

        cv2.putText(
            preview_frame,
            status_text,
            (10, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            1
        )

        cv2.imshow(
            "Target Region (mss)",
            preview_frame
        )

        cv2.waitKey(1)

        if is_running:

            sequence = detect_sequence(gray_frame)

            if sequence and sequence != last_sequence:

                print("Detected:", sequence)

                send_xbox_inputs(sequence)

                last_sequence = sequence

                time.sleep(SEQUENCE_DELAY)

            elif not sequence:
                last_sequence = None

        time.sleep(0.01)

finally:
    release_all()
    sct.close()
    cv2.destroyAllWindows()
