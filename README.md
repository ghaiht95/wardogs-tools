# WarDogs Tools

A Windows application built with PySide6 to manage team selection, AFK, Tank, and quick-buy features in WARDOGS. The application uses screen capture and fixed screen regions; you may need to adjust it for your display resolution and game layout.

> **Note:** The game must be open before starting tasks. Use this application in accordance with the game's rules and policies.

## Requirements

- Windows 10 or later, 64-bit.
- Python 3.11 to run the source code or tests.
- Tesseract OCR on the development machine. The default path is `C:\Program Files\Tesseract-OCR\tesseract.exe`.
- ViGEmBus is required for virtual gamepad features. The generated installer bundles the driver MSI and requests administrator privileges when installing it.
- Inno Setup 6 is required to build the installer.

## Run from source

From PowerShell in the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\app.py
```

When run from source, settings are stored in `wardogs_gui_config.json` in the project root. This local file is excluded by `.gitignore`.

## Default hotkeys

| Key | Action |
| --- | --- |
| F6 | Toggle team selection |
| F5 | Toggle Tank arrows (can be disabled with the Tank switch) |
| F7–F10 | Quick buy (buttons and hotkeys can be disabled with the Quick Buy switch) |
| End | Stop all tasks |

The team-selection switch only enables or disables the F6 hotkey; the Start button remains available. The selected team can be changed at any time. Hotkeys can be changed in Settings. AFK can also be started manually from the UI.

## Automatic updates

The packaged application checks the latest public GitHub Release at startup. If a newer release is available, the application asks before downloading and launching `WarDogsTools-Setup.exe`. The downloaded file is checked against GitHub's SHA-256 asset digest. Windows may request administrator permission when the installer starts. An internet connection is required; if a release has no verified installer asset, the release page is opened instead.

When publishing an update, increment `APP_VERSION` in `app.py` and `AppVersion` in `WarDogsTools.iss`, create a matching `vX.Y.Z` GitHub Release, and attach the installer with the exact name `WarDogsTools-Setup.exe`.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

GitHub Actions runs the tests on Windows with Python 3.11 for each push and pull request.

## Build a distribution

Install the build dependencies, then run this from PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\build-release.ps1
```

This creates the application folder at `dist\WarDogsTools`. To create the installer, install Inno Setup 6 and run:

```powershell
.\build-installer.ps1
```

The installer is created at `dist\WarDogsTools-Setup.exe`. The project license is copied into the distribution folder and installer. Do not commit `dist` or `build` output to the source repository; attach the installer to a GitHub Release when appropriate. Tesseract must be installed on the build machine. Set the `TESSERACT_DIR` environment variable to use a non-default Tesseract location.

See [DISTRIBUTION.txt](DISTRIBUTION.txt) and the license files under `installer/licenses` for distribution notes and third-party notices.

## Project files

- `app.py`: the main UI included in the packaged application.
- `auto.py`, `autobay/main.py`, and `tank/tankauto-relod.py`: standalone scripts; they are not included in the main UI build.
- `tests/`: unit and integration tests.

## License

This project is licensed under the GNU General Public License v3.0; see [LICENSE](LICENSE). The included ViGEmBus license applies to that component only and does not replace the project's license.
