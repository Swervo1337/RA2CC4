# RawAccel → CC4 Converter

Convert RawAccel curve configurations into CustomCurve `.cc4` profiles using a fast Windows CLI tool.

---

## Overview

RA2CC4 converts supported RawAccel curves into CustomCurve-compatible profiles. It can export `.cc4` files or load profiles directly into CustomCurve.

The converter now uses a **CustomCurve-aware spline allocator** instead of simple polyline fitting. It simulates CustomCurve’s internal spline baking so generated points are placed where they best preserve the final displayed curve.

---

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

- Load profiles directly into:

```text
%APPDATA%\CustomCurve\profiles.json
```

- CustomCurve-aware spline generation:
  - 3-point curves use **rational quadratic Bézier**
  - 4+ point curves use **cubic clamped uniform B-splines**
  - all generated points use fixed `0.5` weights

- Configurable output point count

- Configurable JSON precision

- Fast keyboard-driven CLI

- Fully offline operation

- Does not modify RawAccel source files

---

## Requirements

- Windows OS
- Python 3.10+ when running from source
- `tkinter` included with Python for folder/file dialogs

> This project is Windows-only due to CustomCurve integration and process handling.

---

## Installation

### Prebuilt executable

```text
RA2CC4.exe
```

### Run from source

```powershell
python RA2CC4.py
```

---

## Usage

1. Launch the program
2. Choose a RawAccel curve mode or import from `settings.json`
3. Configure output settings
4. Choose output destination:
   - Save as `.cc4`
   - Load directly into CustomCurve

---

## Controls

| Key | Action |
|---|---|
| ↑ / ↓ | Navigate |
| ENTER | Select |
| ESC / Q | Back / Exit |

---

## Advanced Settings

- RawAccel folder path
- CustomCurve installation path
- Output point count
- JSON precision

---

## Spline-Aware Point Allocation

Older versions approximated curves using polyline error.

This version allocates points using the same spline logic CustomCurve uses internally, resulting in:
- more accurate final curves
- fewer wasted points
- better peak preservation
- smoother transitions
- improved low-point-count reconstruction

### Internal Spline Model

```text
3 points  -> rational quadratic Bézier
4+ points -> cubic clamped uniform B-spline
```

Generated curves are baked internally using:
- 500 spline samples
- fixed point weights of `0.5`

---

## Direct CustomCurve Integration

The converter can write generated profiles directly into:

```text
%APPDATA%\CustomCurve\profiles.json
```

The tool will:
- detect if CustomCurve is running
- prompt before overwriting profiles
- optionally reopen CustomCurve afterward

### Limitations

- CustomCurve supports up to 10 profiles in `profiles.json`
- Direct injection requires valid CustomCurve app data access

---

## Configuration File

Stored at:

```text
%APPDATA%\CurveGen\config.json
```

Stored settings may include:
- RawAccel path
- CustomCurve path
- preferred point count
- output precision

---

## Safety

- Does not modify RawAccel files
- Only reads `settings.json`
- No internet or network activity
- Safe to run fully offline

---

## Known Limitations

- Windows-only
- Direct injection requires CustomCurve installation
- CustomCurve profile limit of 10
- Point weights are fixed to `0.5`

---

## Build

```powershell
py -m PyInstaller --onefile --console --name RA2CC4 RA2CC4.py
```

---

## License

MIT License — free to use, modify, and distribute.

---

## Disclaimer

This project is not affiliated with RawAccel or CustomCurve.

Use at your own risk.
