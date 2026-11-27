# RA2CC4

### Turn Raw Accel formulas into CustomCurve 4 profiles.

Raw Accel describes acceleration with formulas. CustomCurve 4 builds curves from editable points. RA2CC4 bridges those two formats, fitting the formula to the CC4 spline so you can bring your Raw Accel curve into CustomCurve and keep editing it there.

[Download the latest release](https://github.com/Swervo1337/RA2CC4/releases/latest)

## Why use RA2CC4?

Converting a formula into points is more than sampling it at evenly spaced X values. Too few points can lose the curve's shape; too many can clutter flat or straight sections. RA2CC4 uses the CC4 spline model while fitting, placing points where they help follow the formula and treating curve edges and bends as part of the fit.

The point count in App Settings is a maximum. RA2CC4 can use fewer points when the curve fits within that limit and the selected precision.

## What you can do

- Build CC4 profiles from Raw Accel curve formulas, including Classic/Linear, Natural, Jump, Synchronous, Motivity, Power, and Lookup Table.
- Import a Raw Accel `settings.json`, choose a profile, then edit its settings or convert one or all profiles.
- Choose Gain or Legacy output and configure supported caps and formula parameters.
- Set separate X and Y curves, or adjust directional sensitivity, axis scaling, smoothing, rotation, and angle snapping.
- Save profiles as `.cc4` files or load them directly into CustomCurve 4.

## Quick start

1. Download `Setup.exe` from [GitHub Releases](https://github.com/Swervo1337/RA2CC4/releases/latest) and run it, or use the portable `RA2CC4.exe`.
2. Open **Generate curve** to choose a Raw Accel formula and set its parameters, or open **Import settings.json** to start from an existing Raw Accel profile.
3. Choose **Save as a file** or **Load into CustomCurve**, then generate the profile.

Close CustomCurve before loading a profile directly into it. RA2CC4 will warn you if CustomCurve is open.

## Build from source

On 64-bit Windows, run `build.bat` from this folder. It installs a per-user .NET 8 SDK if needed, restores dependencies, and creates the portable app and installer in the `Output` folder.

The first build requires an internet connection. No Visual Studio installation is required.

## Support

Report a problem or request a feature on the [GitHub issue tracker](https://github.com/Swervo1337/RA2CC4/issues).
