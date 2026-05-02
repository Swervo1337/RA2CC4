# RawAccel → CC4 Converter

Convert RawAccel configurations into CustomCurve (.cc4) profiles using a fast, interactive CLI tool.

---

## Features

* Supports multiple RawAccel curve types:

  * Classic / Linear
  * Jump
  * Natural
  * Synchronous
  * Motivity (1.6.1)
  * Power
  * LookUpTable (LUT)

* Import directly from `settings.json`

* Export as `.cc4` profile files

* Directly load profiles into CustomCurve

* Advanced configuration:

  * Point count
  * Precision
  * Point reduction modes

* Handles:

  * Input/Output caps
  * Gain vs Legacy modes
  * Lookup tables

* Smooth keyboard-based UI (arrow navigation)

---

## Requirements

* Windows OS
* Python 3.10+ (only if running from source)

> Note: `tkinter` must be included in your Python installation (default for most installs).

---

## Installation

### Option 1 — Prebuilt executable (recommended)

Download and run:

```
RawAccel-CC4-Converter.exe
```

---

### Option 2 — Run from source

No external dependencies required.

```
python Curvegen.py
```

---

## Usage

1. Launch the program
2. Select a curve mode or import from `settings.json`
3. Adjust curve parameters
4. Choose output method:

   * Save as `.cc4` file
   * Load directly into CustomCurve

---

## Controls

* ↑ ↓ → Navigate
* ENTER → Select
* ESC / Q → Go back / Exit

---

## Advanced Settings

Accessible from the main menu:

* Set RawAccel folder path
* Configure:

  * Point count
  * Output precision
  * Point reduction mode

---

## Direct CustomCurve Integration

The tool can:

* Inject profiles directly into CustomCurve
* Detect if the app is running
* Prompt to safely close and reopen it

### Limitations

* Maximum of 10 profiles (CustomCurve limit)

---

## Output Locations

### Saved Files

User-selected location when exporting manually

### Direct App Injection

```
%APPDATA%\CustomCurve\profiles.json
```

---

## Config File

Stored at:

```
%APPDATA%\CurveGen\config.json
```

Includes:

* RawAccel path
* Output preferences

---

## Safety

* Does NOT modify RawAccel
* Only reads `settings.json`
* No internet/network activity
* Safe to run offline

---

## Known Limitations

* Windows-only
* Requires CustomCurve for direct loading
* Profile limit enforced by CustomCurve

---

## License

MIT License — free to use, modify, and distribute.

---

## Disclaimer

This tool is not affiliated with RawAccel or CustomCurve.

Use at your own risk.
