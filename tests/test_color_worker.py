import copy
import hashlib
import json
import os
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, mock_open, patch

import pyautogui
import pytesseract
from PIL import Image, ImageGrab
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import vgamepad

import app


class ColorWorkerTests(unittest.TestCase):
    def setUp(self):
        self.config = copy.deepcopy(app.DEFAULTS)
        self.worker = app.ColorWorker(self.config)
        self.worker.focus_game = Mock(return_value=True)
        self.worker.find_team = Mock(return_value=(1090, 520))
        self.worker.afk = Mock()
        self.worker.idle = Mock(return_value=False)
        self.image = Image.new("RGB", (272, 46), "white")

    def test_clicks_repeatedly_until_deploying(self):
        with (
            patch.object(ImageGrab, "grab", return_value=self.image) as grab,
            patch.object(pytesseract, "image_to_string",
                         side_effect=["", "contract", "DEPLOYING"]) as ocr,
            patch.object(pyautogui, "click") as click,
        ):
            self.worker.work()

        self.assertEqual(click.call_count, 2)
        click.assert_called_with(1090, 520)
        self.assertEqual(self.worker.find_team.call_count, 2)
        self.assertEqual(ocr.call_count, 3)
        self.assertEqual(grab.call_count, 3)
        for call in grab.call_args_list:
            self.assertEqual(call.kwargs["bbox"], (713, 468, 985, 514))
        self.worker.afk.assert_called_once_with(self.config["color"])
        self.assertEqual(self.worker.idle.call_args_list, [
            unittest.mock.call(app.CLICK_INTERVAL),
            unittest.mock.call(app.CLICK_INTERVAL),
        ])

    def test_stop_during_ocr_prevents_click(self):
        def stop_during_ocr(*args, **kwargs):
            self.worker.stop()
            return ""

        with (
            patch.object(ImageGrab, "grab", return_value=self.image),
            patch.object(pytesseract, "image_to_string", side_effect=stop_during_ocr),
            patch.object(pyautogui, "click") as click,
        ):
            self.worker.work()

        click.assert_not_called()
        self.worker.find_team.assert_not_called()
        self.worker.afk.assert_not_called()

    def test_search_continues_if_color_not_found(self):
        self.worker.find_team.side_effect = [None, (1090, 520)]
        with (
            patch.object(ImageGrab, "grab", return_value=self.image),
            patch.object(pytesseract, "image_to_string", side_effect=["", "", "deploying"]),
            patch.object(pyautogui, "click") as click,
        ):
            self.worker.work()

        click.assert_called_once_with(1090, 520)
        self.worker.afk.assert_called_once()

    def test_afk_does_not_resume_search_even_with_legacy_setting(self):
        self.config["color"]["resume"] = True
        with (
            patch.object(ImageGrab, "grab", return_value=self.image),
            patch.object(pytesseract, "image_to_string", return_value="DEPLOYING") as ocr,
            patch.object(pyautogui, "click") as click,
        ):
            self.worker.work()

        click.assert_not_called()
        self.worker.afk.assert_called_once()
        ocr.assert_called_once()
        self.assertEqual(self.worker.focus_game.call_count, 1)

    def test_auto_afk_can_be_disabled_while_searching(self):
        self.worker.set_auto_afk(False)
        with (
            patch.object(ImageGrab, "grab", return_value=self.image),
            patch.object(pytesseract, "image_to_string", return_value="DEPLOYING"),
            patch.object(pyautogui, "click") as click,
        ):
            self.worker.work()

        click.assert_not_called()
        self.worker.afk.assert_not_called()
        self.assertEqual(self.worker.focus_game.call_count, 1)

    def test_ocr_failure_stops_and_reports_error(self):
        messages = []
        self.worker.log.connect(messages.append)
        with (
            patch.object(ImageGrab, "grab", return_value=self.image),
            patch.object(pytesseract, "image_to_string", side_effect=RuntimeError("OCR failed")),
            patch.object(pyautogui, "click") as click,
        ):
            self.worker.run()

        click.assert_not_called()
        self.assertTrue(any("OCR failed" in message for message in messages))

    def test_packaged_ocr_uses_bundled_executable_and_language_data(self):
        with (
            patch.object(app, "IS_PACKAGED", True),
            patch.object(app, "BUNDLED_TESSERACT", r"C:\bundle\tesseract\tesseract.exe"),
            patch.object(pytesseract.pytesseract, "tesseract_cmd", "original"),
            patch.object(ImageGrab, "grab", return_value=self.image),
            patch.object(pytesseract, "image_to_string", return_value="DEPLOYING") as ocr,
        ):
            self.worker.work()
            self.assertEqual(pytesseract.pytesseract.tesseract_cmd, r"C:\bundle\tesseract\tesseract.exe")
            self.assertIn('--tessdata-dir', ocr.call_args.kwargs["config"])
            self.assertIn(os.path.join(app.BASE_DIR, "tesseract", "tessdata"), ocr.call_args.kwargs["config"])

    def test_legacy_config_cannot_override_deploying_region_or_word(self):
        saved = {"color": {"region": [1, 2, 3, 4], "keywords": "contract", "team": "red", "resume": True}}
        with patch("builtins.open", mock_open(read_data=json.dumps(saved))):
            config = app.load_config()
        self.assertEqual(config["color"]["team"], "red")
        self.assertNotIn("region", config["color"])
        self.assertNotIn("keywords", config["color"])
        self.assertNotIn("resume", config["color"])


class AFKTests(unittest.TestCase):
    def setUp(self):
        self.config = copy.deepcopy(app.DEFAULTS)

    def test_manual_afk_focuses_game_and_skips_wait(self):
        worker = app.ManualAFKWorker(self.config)
        worker.focus_game = Mock(return_value=True)
        worker.afk = Mock()
        worker.work()
        worker.focus_game.assert_called_once_with(self.config["color"]["process_name"])
        worker.afk.assert_called_once_with(self.config["color"], wait=False)

    def test_manual_afk_does_not_run_if_game_missing(self):
        worker = app.ManualAFKWorker(self.config)
        worker.focus_game = Mock(return_value=False)
        worker.afk = Mock()
        worker.work()
        worker.afk.assert_not_called()

    def test_manual_afk_moves_and_resets_without_initial_wait(self):
        worker = app.ManualAFKWorker(self.config)
        worker.idle = Mock(side_effect=lambda duration: worker.stop())
        pad = Mock()
        with patch.object(app, "get_gamepad", return_value=pad):
            worker.afk(self.config["color"], wait=False)
        self.assertEqual(worker.idle.call_count, 1)
        self.assertEqual(pad.left_joystick.call_count, 2)
        pad.left_joystick.assert_called_with(x_value=0, y_value=0)

    def test_manual_and_automatic_afk_cannot_overlap(self):
        worker = app.ManualAFKWorker(self.config)
        messages = []
        worker.log.connect(messages.append)
        with app._afk_lock, patch.object(app, "get_gamepad") as get_gamepad:
            worker.afk(self.config["color"], wait=False)
        get_gamepad.assert_not_called()
        self.assertTrue(any("already running" in msg for msg in messages))

    def test_old_configuration_enables_automatic_afk_by_default(self):
        with patch("builtins.open", mock_open(read_data='{"color": {"team": "red"}}')):
            config = app.load_config()
        self.assertTrue(config["color"]["auto_afk"])


class AFKGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.application = QApplication.instance() or QApplication([])

    def test_tesseract_path_hidden_but_saved_setting_preserved(self):
        config = copy.deepcopy(app.DEFAULTS)
        config["general"]["tesseract_path"] = r"C:\Custom\tesseract.exe"
        with (
            patch.object(app, "keyboard", None),
            patch.object(app, "load_config", return_value=config),
            patch.object(app.MainWindow, "save_config"),
        ):
            window = app.MainWindow()
            try:
                from PySide6.QtWidgets import QLabel, QPushButton
                self.assertNotIn(("general", "tesseract_path"), window.widgets)
                self.assertNotIn("Tesseract path", [label.text() for label in window.findChildren(QLabel)])
                self.assertNotIn("Browse...", [button.text() for button in window.findChildren(QPushButton)])
                self.assertEqual(window.collect_config()["general"]["tesseract_path"], r"C:\Custom\tesseract.exe")
            finally:
                window.close()

    def test_tank_f5_switch_gates_only_tank_hotkey(self):
        config = copy.deepcopy(app.DEFAULTS)
        config["features"]["tank_hotkey_enabled"] = False
        with (
            patch.object(app, "keyboard", None),
            patch.object(app, "load_config", return_value=config),
            patch.object(app.MainWindow, "save_config"),
        ):
            window = app.MainWindow()
            try:
                window.toggle = Mock()
                switch = window.widgets[("features", "tank_hotkey_enabled")]
                self.assertIsInstance(switch, app.ToggleSwitch)
                self.assertFalse(switch.isChecked())
                window.on_hotkey("tank")
                window.toggle.assert_not_called()
                switch.setChecked(True)
                window.on_hotkey("tank")
                window.toggle.assert_called_once_with("tank")
                self.assertTrue(window.collect_config()["features"]["tank_hotkey_enabled"])
            finally:
                window.close()

    def test_team_selection_switch_gates_start_and_f6_but_keeps_team_choice(self):
        config = copy.deepcopy(app.DEFAULTS)
        with (
            patch.object(app, "keyboard", None),
            patch.object(app, "load_config", return_value=config),
            patch.object(app.MainWindow, "save_config"),
            patch.object(app, "ColorWorker") as color_worker,
        ):
            window = app.MainWindow()
            try:
                switch = window.widgets[("features", "team_selection_enabled")]
                team_picker = window.widgets[("color", "team")]
                start_button = window.toggle_buttons["color"][0]
                worker = Mock(alive=True)
                window.workers["color"] = worker
                window.toggle = Mock()

                self.assertIsInstance(switch, app.ToggleSwitch)
                self.assertTrue(switch.isChecked())
                self.assertTrue(start_button.isEnabled())
                switch.setChecked(False)
                worker.stop.assert_called_once()
                self.assertFalse(start_button.isEnabled())
                self.assertTrue(team_picker.isEnabled())
                window.on_hotkey("color")
                window.start("color")
                window.toggle.assert_not_called()
                color_worker.assert_not_called()
                self.assertFalse(window.collect_config()["features"]["team_selection_enabled"])

                switch.setChecked(True)
                self.assertTrue(start_button.isEnabled())
                window.on_hotkey("color")
                window.toggle.assert_called_once_with("color")
                self.assertTrue(window.collect_config()["features"]["team_selection_enabled"])
            finally:
                window.close()

    def test_quick_buy_switch_disables_buttons_and_gates_hotkeys(self):
        config = copy.deepcopy(app.DEFAULTS)
        with (
            patch.object(app, "keyboard", None),
            patch.object(app, "load_config", return_value=config),
            patch.object(app.MainWindow, "save_config"),
        ):
            window = app.MainWindow()
            try:
                window.start = Mock()
                switch = window.widgets[("features", "quick_buy_enabled")]
                self.assertIsInstance(switch, app.ToggleSwitch)
                self.assertTrue(switch.isChecked())
                self.assertTrue(all(button.isEnabled() for button in window.supply_buttons))
                switch.setChecked(False)
                self.assertTrue(all(not button.isEnabled() for button in window.supply_buttons))
                window.on_hotkey("bay_build")
                window.start.assert_not_called()
                self.assertFalse(window.collect_config()["features"]["quick_buy_enabled"])

                switch.setChecked(True)
                self.assertTrue(all(button.isEnabled() for button in window.supply_buttons))
                window.on_hotkey("bay_build")
                window.start.assert_called_once_with("bay", "build")
            finally:
                window.close()

    def test_auto_afk_switch_updates_worker_and_config(self):
        config = copy.deepcopy(app.DEFAULTS)
        config["color"]["auto_afk"] = False
        with (
            patch.object(app, "keyboard", None),
            patch.object(app, "load_config", return_value=config),
            patch.object(app.MainWindow, "save_config"),
        ):
            window = app.MainWindow()
            try:
                switch = window.widgets[("color", "auto_afk")]
                worker = app.ColorWorker(config)
                window.workers["color"] = worker
                window.show()
                self.application.processEvents()
                self.assertIsInstance(switch, app.ToggleSwitch)
                self.assertFalse(switch.isChecked())
                self.assertFalse(switch.grab().isNull())
                QTest.mouseClick(switch, Qt.MouseButton.LeftButton, pos=QPoint(40, 13))
                self.assertTrue(switch.isChecked())
                self.assertTrue(worker.auto_afk_enabled.is_set())
                self.assertTrue(window.collect_config()["color"]["auto_afk"])
                QTest.keyClick(switch, Qt.Key.Key_Space)
                self.assertFalse(switch.isChecked())
                self.assertFalse(worker.auto_afk_enabled.is_set())
                self.assertNotIn(("color", "resume"), window.widgets)
                self.assertNotIn("resume", window.collect_config()["color"])
                window.workers["color"] = None
            finally:
                window.close()

    def test_manual_button_and_stop_all(self):
        pad = Mock()
        with (
            patch.object(app, "keyboard", None),
            patch.object(app, "load_config", return_value=copy.deepcopy(app.DEFAULTS)),
            patch.object(app.MainWindow, "save_config"),
            patch.object(app.ManualAFKWorker, "focus_game", return_value=True),
            patch.object(app, "get_gamepad", return_value=pad),
            patch.object(app, "find_game_window", return_value=123),
            patch.object(app, "window_process_id", return_value=456),
        ):
            window = app.MainWindow()
            try:
                button = window.toggle_buttons["afk"][0]
                button.click()
                deadline = time.monotonic() + 2
                while not pad.left_joystick.called and time.monotonic() < deadline:
                    self.application.processEvents()
                    time.sleep(0.01)
                self.assertTrue(pad.left_joystick.called)
                self.assertEqual(button.text(), "Stop AFK")
                window.stop_all()
                self.assertTrue(window.workers["afk"].wait(2000))
                self.application.processEvents()
                self.assertEqual(button.text(), "Start AFK now")
                pad.left_joystick.assert_called_with(x_value=0, y_value=0)
            finally:
                window.close()

    def test_game_required_for_buttons_and_hotkeys(self):
        with (
            patch.object(app, "keyboard", None),
            patch.object(app, "load_config", return_value=copy.deepcopy(app.DEFAULTS)),
            patch.object(app.MainWindow, "save_config"),
            patch.object(app, "find_game_window", return_value=None),
            patch.object(app, "ColorWorker") as color,
            patch.object(app, "ManualAFKWorker") as afk,
            patch.object(app, "TankWorker") as tank,
            patch.object(app, "BayWorker") as bay,
        ):
            window = app.MainWindow()
            try:
                window.toggle_buttons["color"][0].click()
                window.toggle_buttons["afk"][0].click()
                window.toggle_buttons["tank"][0].click()
                for button in window.supply_buttons:
                    button.click()
                for action in ("color", "tank", "bay_build", "bay_ammo", "bay_fuel", "bay_mech"):
                    window.on_hotkey(action)
                for constructor in (color, afk, tank, bay):
                    constructor.assert_not_called()
                self.assertIn("Game window not found", window.log_view.toPlainText())
                self.assertFalse(window.game_monitor.isActive())
            finally:
                window.close()

    def test_game_close_stops_running_afk(self):
        pad = Mock()
        with (
            patch.object(app, "keyboard", None),
            patch.object(app, "load_config", return_value=copy.deepcopy(app.DEFAULTS)),
            patch.object(app.MainWindow, "save_config"),
            patch.object(app.ManualAFKWorker, "focus_game", return_value=True),
            patch.object(app, "get_gamepad", return_value=pad),
            patch.object(app, "find_game_window", return_value=123),
            patch.object(app, "window_process_id", return_value=456) as get_pid,
        ):
            window = app.MainWindow()
            try:
                window.start("afk")
                worker = window.workers["afk"]
                deadline = time.monotonic() + 2
                while not pad.left_joystick.called and time.monotonic() < deadline:
                    self.application.processEvents()
                    time.sleep(0.01)
                self.assertTrue(pad.left_joystick.called)
                self.assertTrue(window.game_monitor.isActive())
                get_pid.return_value = None
                window.check_game_windows()
                self.assertTrue(worker.wait(2000))
                self.assertTrue(worker.stop_event.is_set())
                self.assertFalse(window.game_monitor.isActive())
                pad.left_joystick.assert_called_with(x_value=0, y_value=0)
                self.assertIn("Game window closed", window.log_view.toPlainText())
            finally:
                window.close()

    def test_all_task_types_start_when_game_is_open_and_stop_on_window_reuse(self):
        created = []

        def make_worker(*args):
            worker = Mock()
            worker.alive = True
            worker.isFinished.return_value = False
            worker.supply = args[1] if len(args) > 1 else None
            created.append(worker)
            return worker

        with (
            patch.object(app, "keyboard", None),
            patch.object(app, "load_config", return_value=copy.deepcopy(app.DEFAULTS)),
            patch.object(app.MainWindow, "save_config"),
            patch.object(app, "find_game_window", return_value=123),
            patch.object(app, "window_process_id", return_value=456) as get_pid,
            patch.object(app, "ColorWorker", side_effect=make_worker),
            patch.object(app, "ManualAFKWorker", side_effect=make_worker),
            patch.object(app, "TankWorker", side_effect=make_worker),
            patch.object(app, "BayWorker", side_effect=make_worker),
        ):
            window = app.MainWindow()
            try:
                for name, args in (("color", ()), ("afk", ()), ("tank", ()), ("bay", ("build",))):
                    window.start(name, *args)
                self.assertEqual(len(created), 4)
                for worker in created:
                    worker.start.assert_called_once()
                get_pid.return_value = 789
                window.check_game_windows()
                for worker in created:
                    worker.stop.assert_called_once()
                self.assertFalse(window.game_monitor.isActive())
                window.all_workers.clear()
                window.workers = dict.fromkeys(window.workers)
            finally:
                window.close()

    def test_restart_controller_button_and_team_labels(self):
        with (
            patch.object(app, "keyboard", None),
            patch.object(app, "load_config", return_value=copy.deepcopy(app.DEFAULTS)),
            patch.object(app.MainWindow, "save_config"),
            patch.object(app, "restart_gamepad") as restart,
        ):
            window = app.MainWindow()
            try:
                self.assertFalse(window.windowIcon().isNull())
                from PySide6.QtWidgets import QPushButton, QTabWidget
                tabs = window.findChild(QTabWidget)
                self.assertEqual(tabs.tabText(0), "Team selection")
                self.assertEqual(app.HOTKEY_LABELS["color"], "Team selection (toggle)")
                button = next(b for b in window.findChildren(QPushButton)
                              if b.text() == "Restart controller")
                button.click()
                restart.assert_called_once()
                self.assertIn("Virtual controller reconnected", window.log_view.toPlainText())

                window.all_workers.append(Mock(isFinished=Mock(return_value=False)))
                button.click()
                restart.assert_called_once()
                self.assertIn("Stop all tasks", window.log_view.toPlainText())
                window.all_workers.clear()

                restart.side_effect = RuntimeError("connection failed")
                button.click()
                self.assertIn("connection failed", window.log_view.toPlainText())
            finally:
                window.close()


class ControllerRestartTests(unittest.TestCase):
    def test_disconnects_before_creating_replacement(self):
        events = []

        class FakePad:
            def __del__(self):
                events.append("disconnected")

        def create_pad():
            events.append("connected")
            return FakePad()

        with patch.object(app, "_gamepad", None), patch.object(vgamepad, "VX360Gamepad", side_effect=create_pad):
            app._gamepad = FakePad()
            app.restart_gamepad()
            self.assertEqual(events, ["disconnected", "connected"])
            self.assertIsInstance(app.get_gamepad(), FakePad)

    def test_failed_creation_leaves_controller_unset(self):
        with patch.object(app, "_gamepad", None), patch.object(vgamepad, "VX360Gamepad", side_effect=RuntimeError("failed")):
            with self.assertRaisesRegex(RuntimeError, "failed"):
                app.restart_gamepad()
            self.assertIsNone(app._gamepad)


class UpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.application = QApplication.instance() or QApplication([])

    def test_release_parser_accepts_only_the_expected_installer_and_version(self):
        digest = "a" * 64
        payload = {
            "tag_name": "v1.0.1",
            "html_url": "https://github.com/ghaiht95/wardogs-tools/releases/tag/v1.0.1",
            "assets": [{
                "name": app.INSTALLER_ASSET_NAME,
                "browser_download_url": (
                    "https://github.com/ghaiht95/wardogs-tools/releases/download/"
                    "v1.0.1/WarDogsTools-Setup.exe"
                ),
                "digest": f"sha256:{digest}",
                "size": 1024,
            }],
        }

        release = app.parse_latest_release(payload)
        self.assertEqual(release["tag"], "v1.0.1")
        self.assertEqual(release["digest"], f"sha256:{digest}")
        self.assertEqual(app.version_tuple(release["tag"]), (1, 0, 1))

        payload["assets"][0]["browser_download_url"] = "https://example.com/installer.exe"
        with self.assertRaisesRegex(ValueError, "unexpected installer URL"):
            app.parse_latest_release(payload)
        with self.assertRaisesRegex(ValueError, "Unsupported version"):
            app.version_tuple("latest")

    def test_update_prompt_is_shown_only_for_a_newer_version(self):
        with (
            patch.object(app, "keyboard", None),
            patch.object(app, "load_config", return_value=copy.deepcopy(app.DEFAULTS)),
            patch.object(app.MainWindow, "save_config"),
            patch.object(app.QMessageBox, "question", return_value=app.QMessageBox.StandardButton.No) as question,
        ):
            window = app.MainWindow()
            try:
                release = {
                    "tag": "v1.0.0",
                    "url": "https://github.com/ghaiht95/wardogs-tools/releases/latest",
                    "installer_url": "https://github.com/ghaiht95/wardogs-tools/releases/download/v1.0.1/WarDogsTools-Setup.exe",
                    "digest": "sha256:" + "a" * 64,
                }
                window.on_update_check_complete(release)
                question.assert_not_called()

                release["tag"] = "v1.0.1"
                with patch.object(window, "download_update") as download:
                    window.on_update_check_complete(release)
                    question.assert_called_once()
                    download.assert_not_called()
            finally:
                window.close()

    def test_download_checks_digest_before_returning_installer(self):
        data = b"installer payload"
        expected_digest = "sha256:" + hashlib.sha256(data).hexdigest()

        class FakeResponse:
            headers = {"Content-Length": str(len(data))}

            def __init__(self):
                self.remaining = data

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def geturl(self):
                return "https://objects.githubusercontent.com/installer"

            def read(self, size):
                chunk, self.remaining = self.remaining[:size], self.remaining[size:]
                return chunk

        url = (
            "https://github.com/ghaiht95/wardogs-tools/releases/download/"
            "v1.0.1/WarDogsTools-Setup.exe"
        )
        with tempfile.TemporaryDirectory() as directory:
            destination = os.path.join(directory, "WarDogsTools-Setup.exe")
            with patch.object(app, "urlopen", return_value=FakeResponse()):
                self.assertTrue(app.download_release_asset(
                    url, expected_digest, destination, threading.Event(),
                ))
            with open(destination, "rb") as installer:
                self.assertEqual(installer.read(), data)

            with patch.object(app, "urlopen", return_value=FakeResponse()):
                with self.assertRaisesRegex(ValueError, "checksum does not match"):
                    app.download_release_asset(
                        url, "sha256:" + "0" * 64, destination, threading.Event(),
                    )
            self.assertFalse(os.path.exists(destination))


if __name__ == "__main__":
    unittest.main()
