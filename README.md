# RawAccel → CC4 Converter

Convert RawAccel curve configurations into CustomCurve `.cc4` profiles using a fast, keyboard-driven CLI tool.

## Overview

This repository provides a Windows-native converter for RawAccel curve profiles. It reads RawAccel `settings.json`, converts supported curve types into CustomCurve-compatible profiles, and exports them as `.cc4` files or injects them directly into CustomCurve.

## Key Features

- Supports RawAccel curve types:
  - Classic / Linear
  - Jump
  - Natural
  - Synchronous
  - Motivity (1.6.1)
  - Power
  - LookUpTable (LUT)
- Import curves directly from RawAccel `settings.json`
- Export profiles as `.cc4` files
- Directly load converted profiles into CustomCurve via `%APPDATA%\CustomCurve\profiles.json`
- Advanced configuration options:
  - Curve point count
  - Output precision
  - Point reduction mode
  - Optional weight support
- Smooth keyboard-driven CLI with arrow-key navigation
- Works offline and does not modify RawAccel source files

## Requirements

- Windows OS
- Python 3.10+ (required when running from source)
- `tkinter` included in the Python installation for folder selection dialogs

> Note: The tool uses Windows APIs and process detection, so it is designed for Windows only.

## Installation

### Option 1 — Prebuilt executable

If available, run the bundled executable:

```powershell
RA2CC4.exe
```

### Option 2 — Run from source

No external Python dependencies are required beyond the standard library.

```powershell
python RA2CC4.py
```

## Usage

1. Launch the program.
2. Choose a RawAccel curve mode or import from `settings.json`.
3. Configure output parameters and advanced settings.
4. Choose an output destination:
   - Save as `.cc4` file
   - Load directly into CustomCurve

## Controls

- `↑` / `↓` — Navigate menu items
- `ENTER` — Select
- `ESC` / `Q` — Back / Exit

## Advanced Settings

Available from the main menu:

- Configure the RawAccel folder path
- Configure the CustomCurve installation path
- Set output point count
- Set JSON precision
- Set point reduction mode
- Enable or disable weight usage

## Direct CustomCurve Integration

The converter can write generated profiles directly into CustomCurve's `profiles.json`.

It will:

- detect if CustomCurve is running
- prompt to close CustomCurve safely before writing
- optionally reopen the app after updating profiles

### Limitations

- CustomCurve supports up to 10 profiles in `profiles.json`
- If the limit is reached, profiles must be saved to file instead
- Direct injection requires CustomCurve app data to be accessible

## Output Locations

### Saved Files

Profiles saved manually are written to the user-selected output path.

### Direct App Injection

The tool writes directly to:

```text
%APPDATA%\CustomCurve\profiles.json
```

## Configuration File

The tool stores its configuration in:

```text
%APPDATA%\CurveGen\config.json
```

Stored settings may include:

- RawAccel installation path
- CustomCurve installation path
- preferred point count
- output precision
- point reduction mode
- weight usage mode

## Safety

- Does not modify RawAccel files
- Only reads `settings.json`
- No internet or network activity is performed
- Safe to run offline

## Known Limitations

- Windows-only due to Windows-specific process handling and CustomCurve integration
- Direct loading into CustomCurve requires a valid CustomCurve installation
- CustomCurve profile count is limited to 10

## Build

To create a standalone executable:

```powershell
py -m PyInstaller --onefile --console --name RA2CC4 RA2CC4.py
```

## License

MIT License — free to use, modify, and distribute.

## Disclaimer

This project is not affiliated with RawAccel or CustomCurve. Use at your own risk.
