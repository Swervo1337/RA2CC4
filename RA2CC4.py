import json
import math
import uuid
import os
import msvcrt
import ctypes
import subprocess
import time
import tkinter as tk
from tkinter import filedialog
from fractions import Fraction
GRAY = "\033[90m"
BRACKET_GRAY = "\033[37m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
WHITE = "\033[97m"
SOFT_CYAN = "\033[36m"
RESET = "\033[0m"
def sep(width=60):
    return f"{GRAY}{'=' * width}{RESET}"
def color_gui_brackets(text, active_color=RESET):
    return str(text).replace("[", f"{GRAY}[").replace("]", f"]{active_color}")
def menu_footer(esc_text="go back"):
    print(f"\n{GRAY}Use ↑ ↓ to move | ENTER to select | ESC to {esc_text}{RESET}")
def main_menu_footer():
    print(f"\n{GRAY}Use ↑ ↓ to move | ENTER to select | Q or ESC to quit{RESET}")
def pause_footer(action="return to menu"):
    print(f"\n{GRAY}Use ENTER or ESC to {action}{RESET}")
POINT_TENSION = "0"
CONFIG_KEYS = {
    "rawaccel_path",
    "point_count",
    "precision",
    "point_reduction_mode",
}
APPDATA_DIR = os.getenv("APPDATA")
if APPDATA_DIR:
    CONFIG_DIR = os.path.join(APPDATA_DIR, "CurveGen")
else:
    CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
LAST_CONFIG_FILE = CONFIG_PATH  
LEGACY_CONFIG_PATHS = [
    os.path.join(os.getcwd(), "config.json"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"),
]
POINT_OPTIONS = [32, 64, 96, 128, 160, 192, 256, 320, 384, 512, 640, 768, 1024, 2048, 4096]
PRECISION_OPTIONS = list(range(1, 11))
REDUCTION_OPTIONS = ["off", "safe", "aggressive"]
RECOMMENDED_POINTS = 128
RECOMMENDED_PRECISION = 6
RECOMMENDED_REDUCTION = "off"
MODES = [
    ("Classic/Linear", True),
    ("Jump", True),
    ("Natural", True),
    ("Synchronous", True),
    ("Motivity (1.6.1)", True),
    ("Power", True),
    ("LookUpTable", True),
    ("Import from settings.json", True),
    ("Advanced Settings", True),
]
def clear():
    os.system("cls" if os.name == "nt" else "clear")
def print_menu(selected, last=None):
    clear()
    last = last if isinstance(last, dict) else {}
    print(sep(70))
    print(" RAWACCEL → CC4 CONVERTER")
    print(" Version 1.0 | (discord - boraboraboraboraboraboraborabora)")
    print(sep(70))
    print("\nSelect Mode:\n")
    rawaccel_path = get_saved_rawaccel_path(last)
    import_label = f"Import from settings.json [{rawaccel_path}]" if rawaccel_path else "Import from settings.json"
    for i, (name, supported) in enumerate(MODES):
        prefix = "➤ " if i == selected else "  "
        name_lower = name.lower()
        if name_lower == "import from settings.json":
            print()
            print(f"{prefix}{CYAN}{color_gui_brackets(import_label, CYAN)}{RESET}")
            continue
        if name_lower == "advanced settings":
            print(f"{prefix}{YELLOW}{name}{RESET}")
            continue
        if supported:
            color = "\033[92m"
            status = "SUPPORTED"
        else:
            color = "\033[91m"
            status = "UNSUPPORTED"
        print(f"{prefix}{color}{name:<20} {GRAY}[{color}{status}{GRAY}]{RESET}")
    main_menu_footer()
def mode_selector():
    supported_indices = [i for i, (_, supported) in enumerate(MODES) if supported]
    if not supported_indices:
        return None
    selected_pos = 0
    while True:
        selected = supported_indices[selected_pos]
        print_menu(selected, clean_invalid_rawaccel_path())
        key = msvcrt.getch()
        if key == b'\xe0':
            key = msvcrt.getch()
            if key == b'H':
                selected_pos = (selected_pos - 1) % len(supported_indices)
            elif key == b'P':
                selected_pos = (selected_pos + 1) % len(supported_indices)
        elif key == b'\r':
            name, _ = MODES[selected]
            return name.lower()
        elif key in [b'\x1b', b'q', b'Q']:
            return None
def option_selector(title, options):
    selected = 0
    while True:
        clear()
        print(sep(60))
        print(f" {CYAN}{title}{RESET}")
        print(sep(60))
        print()
        for i, option in enumerate(options):
            prefix = "➤ " if i == selected else "  "
            color = CYAN if i == selected else WHITE
            print(f"{prefix}{color}{option}{RESET}")
        menu_footer("go back")
        key = msvcrt.getch()
        if key == b'\xe0':
            key = msvcrt.getch()
            if key == b'H':
                selected = (selected - 1) % len(options)
            elif key == b'P':
                selected = (selected + 1) % len(options)
        elif key == b'\r':
            return options[selected].lower()
        elif key == b'\x1b':
            return None
def value_choice_selector(title, options, current=None, recommended=None, width=70, on_select=None):
    selected = 0
    saved_value = current
    values = [option[1] for option in options]
    if saved_value in values:
        selected = values.index(saved_value)
    while True:
        clear()
        print(sep(width))
        print(f" {CYAN}{title}{RESET}")
        print(sep(width))
        print()
        for i, option in enumerate(options):
            label, value = option
            prefix = "➤ " if i == selected else "  "
            if i == selected:
                color = CYAN
            elif value == saved_value:
                color = SOFT_CYAN
            else:
                color = WHITE
            recommended_tag = f" {GREEN}(Recommended){RESET}" if recommended is not None and value == recommended else ""
            print(f"{prefix}{color}{label}{RESET}{recommended_tag}")
        menu_footer("go back")
        key = msvcrt.getch()
        if key == b'\xe0':
            key = msvcrt.getch()
            if key == b'H':
                selected = (selected - 1) % len(options)
            elif key == b'P':
                selected = (selected + 1) % len(options)
        elif key == b'\r':
            saved_value = values[selected]
            if on_select:
                on_select(saved_value)
        elif key == b'\x1b':
            return saved_value
def number_selector(title, values, current=None, recommended=None, width=70, on_select=None):
    selected = 0
    saved_value = current
    string_values = [str(v) for v in values]
    if saved_value is not None:
        current_text = str(saved_value)
        if current_text in string_values:
            selected = string_values.index(current_text)
    while True:
        clear()
        print(sep(width))
        print(f" {CYAN}{title}{RESET}")
        print(sep(width))
        print()
        for i, value in enumerate(string_values):
            prefix = "➤ " if i == selected else "  "
            if i == selected:
                color = CYAN
            elif str(saved_value) == value:
                color = SOFT_CYAN
            else:
                color = WHITE
            recommended_tag = f" {GREEN}(Recommended){RESET}" if recommended is not None and str(recommended) == value else ""
            print(f"{prefix}{color}{value}{RESET}{recommended_tag}")
        menu_footer("go back")
        key = msvcrt.getch()
        if key == b'\xe0':
            key = msvcrt.getch()
            if key == b'H':
                selected = (selected - 1) % len(string_values)
            elif key == b'P':
                selected = (selected + 1) % len(string_values)
        elif key == b'\r':
            saved_value = values[selected]
            if on_select:
                on_select(saved_value)
        elif key == b'\x1b':
            return saved_value
def themed_choice_selector(title, options, note=None, width=70):
    selected = 0
    while True:
        clear()
        print(sep(width))
        print(f" {CYAN}{title}{RESET}")
        print(sep(width))
        print()
        for i, option in enumerate(options):
            prefix = "➤ " if i == selected else "  "
            color = CYAN if i == selected else WHITE
            label = color_gui_brackets(option[0], color)
            print(f"{prefix}{color}{label}{RESET}")
        if note:
            print(f"\n{YELLOW}{note}{RESET}")
        menu_footer("return to menu")
        key = msvcrt.getch()
        if key == b'\xe0':
            key = msvcrt.getch()
            if key == b'H':
                selected = (selected - 1) % len(options)
            elif key == b'P':
                selected = (selected + 1) % len(options)
        elif key == b'\r':
            return options[selected][1]
        elif key == b'\x1b':
            return "menu"
def import_error_screen(title, message):
    clear()
    print(sep(70))
    print(f" {RED}{title}{RESET}")
    print(sep(70))
    print(f"\n{RED}{message}{RESET}")
    pause_footer("return to menu")
    while True:
        key = msvcrt.getch()
        if key in [b'\r', b'\x1b']:
            return
def unsupported_mode_screen():
    import_error_screen("UNSUPPORTED MODE", "Unsupported mode detected")
def screen_header(title, width=70):
    clear()
    print(sep(width))
    print(f" {CYAN}{title}{RESET}")
    print(sep(width))
def section_header(title):
    print(f"\n{BLUE}[ {title} ]{RESET}")
def themed_input(label, default=None):
    prefix = str(label)
    if not prefix.startswith(" "):
        prefix = " " + prefix
    if default is not None:
        return input(f"{CYAN}{prefix} {GRAY}[{default}]{RESET}: ").strip()
    return input(f"{CYAN}{prefix}{RESET}: ").strip()
def themed_number_error(message):
    print(f"{RED}{message}{RESET}")
def load_last_config():
    paths = [CONFIG_PATH]
    for legacy_path in LEGACY_CONFIG_PATHS:
        if legacy_path not in paths:
            paths.append(legacy_path)
    for path in paths:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            continue
    return {}
def configure_console():
    if os.name != "nt":
        return
    try:
        kernel32 = ctypes.windll.kernel32
        std_input_handle = -10
        handle = kernel32.GetStdHandle(std_input_handle)
        mode = ctypes.c_uint()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return
        enable_quick_edit_mode = 0x0040
        enable_insert_mode = 0x0020
        enable_extended_flags = 0x0080
        new_mode = mode.value | enable_extended_flags
        new_mode &= ~enable_quick_edit_mode
        new_mode &= ~enable_insert_mode
        kernel32.SetConsoleMode(handle, new_mode)
    except Exception:
        pass
def save_last_config(data):
    try:
        if not isinstance(data, dict):
            data = {}
        os.makedirs(CONFIG_DIR, exist_ok=True)
        existing = load_last_config()
        if not isinstance(existing, dict):
            existing = {}
        merged = dict(existing)
        merged.update(data)
        clean = {
            key: merged[key]
            for key in CONFIG_KEYS
            if key in merged
        }
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(clean, f, indent=2)
    except Exception:
        pass
def validate_rawaccel_path(path):
    if not path:
        return False
    folder = os.path.abspath(path)
    return (
        os.path.isdir(folder)
        and os.path.isfile(os.path.join(folder, "settings.json"))
    )
def get_saved_rawaccel_path(config=None):
    data = config if isinstance(config, dict) else load_last_config()
    path = str(data.get("rawaccel_path", "")).strip()
    return path if validate_rawaccel_path(path) else None
def clean_invalid_rawaccel_path():
    cleaned = normalize_config_values(load_last_config())
    original_path = str(cleaned.get("rawaccel_path", "")).strip()
    normalized_path = os.path.abspath(original_path) if original_path else ""
    changed = False
    if original_path:
        if validate_rawaccel_path(normalized_path):
            if normalized_path != original_path:
                cleaned["rawaccel_path"] = normalized_path
                changed = True
        else:
            cleaned["rawaccel_path"] = ""
            changed = True
    if changed:
        save_last_config(cleaned)
    return cleaned
def get_rawaccel_settings_path(config=None):
    folder = get_saved_rawaccel_path(config)
    if not folder:
        return None
    return os.path.join(folder, "settings.json")
def get_output_points(config=None):
    data = config if isinstance(config, dict) else load_last_config()
    return nearest_allowed_int(data.get("point_count", RECOMMENDED_POINTS), POINT_OPTIONS, RECOMMENDED_POINTS)
def get_output_precision(config=None):
    data = config if isinstance(config, dict) else load_last_config()
    return nearest_allowed_int(data.get("precision", RECOMMENDED_PRECISION), PRECISION_OPTIONS, RECOMMENDED_PRECISION)
def get_output_reduction(config=None):
    data = config if isinstance(config, dict) else load_last_config()
    value = str(data.get("point_reduction_mode", RECOMMENDED_REDUCTION)).strip().lower()
    return value if value in REDUCTION_OPTIONS else RECOMMENDED_REDUCTION
def output_settings_note(config=None):
    return None
def pick_rawaccel_folder():
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(title="Select RawAccel folder")
        root.destroy()
        return path or None
    except Exception:
        return None
def settings_success_screen(title, message, path=None):
    clear()
    print(sep(70))
    print(f" {GREEN}{title}{RESET}")
    print(sep(70))
    print(f"\n{GREEN}{message}{RESET}")
    if path:
        print(f"{BLUE}Path:{RESET} {path}")
    pause_footer("return to menu")
    while True:
        key = msvcrt.getch()
        if key in [b'\r', b'\x1b']:
            return
def advanced_settings_options(config):
    rawaccel_path = get_saved_rawaccel_path(config)
    rawaccel_display = rawaccel_path if rawaccel_path else "Not set"
    return [
        (f"Set RawAccel Path [{rawaccel_display}]", "set_rawaccel_path"),
        (f"Set Points [{get_output_points(config)}]", "set_points"),
        (f"Set Precision [{get_output_precision(config)}]", "set_precision"),
        (f"Set Point Reduction Mode [{get_output_reduction(config)}]", "set_point_reduction"),
    ]
def advanced_settings_menu():
    while True:
        last = clean_invalid_rawaccel_path()
        choice = themed_choice_selector(
            "ADVANCED SETTINGS",
            advanced_settings_options(last),
            note=output_settings_note(last),
            width=70
        )
        if choice == "menu":
            return
        if choice == "set_rawaccel_path":
            folder = pick_rawaccel_folder()
            if not folder:
                continue
            if not validate_rawaccel_path(folder):
                import_error_screen("INVALID RAWACCEL PATH", "Folder must contain RawAccel")
                continue
            last["rawaccel_path"] = os.path.abspath(folder)
            save_last_config(last)
            continue
        if choice == "set_points":
            def save_points(value):
                data = clean_invalid_rawaccel_path()
                data["point_count"] = value
                save_last_config(data)
            number_selector(
                "SET POINTS",
                POINT_OPTIONS,
                current=get_output_points(last),
                recommended=RECOMMENDED_POINTS,
                width=70,
                on_select=save_points
            )
            continue
        if choice == "set_precision":
            def save_precision(value):
                data = clean_invalid_rawaccel_path()
                data["precision"] = value
                save_last_config(data)
            number_selector(
                "SET PRECISION",
                PRECISION_OPTIONS,
                current=get_output_precision(last),
                recommended=RECOMMENDED_PRECISION,
                width=70,
                on_select=save_precision
            )
            continue
        if choice == "set_point_reduction":
            def save_reduction(value):
                data = clean_invalid_rawaccel_path()
                data["point_reduction_mode"] = value
                save_last_config(data)
            value_choice_selector(
                "POINT REDUCTION MODE",
                [("Off", "off"), ("Safe", "safe"), ("Aggressive", "aggressive")],
                current=get_output_reduction(last),
                recommended=RECOMMENDED_REDUCTION,
                width=70,
                on_select=save_reduction
            )
def normalize_cc4_filename(name):
    base = (name or "").strip()
    if not base:
        base = "profile"
    lower = base.lower()
    if lower.endswith(".json"):
        base = base[:-5]
    if lower.endswith(".cc4"):
        base = base[:-4]
    base = base.strip() or "profile"
    return f"{base}.cc4"
def get_customcurve_folder_path():
    return os.path.join(os.getenv("APPDATA"), "CustomCurve")
def get_customcurve_profiles_path():
    return os.path.join(get_customcurve_folder_path(), "profiles.json")
def make_app_profile(profile):
    app_profile = dict(profile)
    app_profile.pop("Original", None)
    app_profile["IsNew"] = False
    app_profile.setdefault("RotationMode", "Both")
    app_profile.setdefault("RotationHorizontal", 0)
    app_profile.setdefault("RotationVertical", 0)
    app_profile.setdefault("AngleSnappingMode", "Legacy")
    app_profile.setdefault("AngleSnappingHorizontal", 0)
    app_profile.setdefault("AngleSnappingVertical", 0)
    app_profile.setdefault("InputSpeedMetric", "Euclidean")
    app_profile.setdefault("InputSmoothingTimeMs", 0)
    app_profile.setdefault("HandAccelScaleOn", "Acceleration")
    app_profile.setdefault("HandAccelDetectionSmoothing", "Normal")
    app_profile.setdefault("HandAccelScale", 0)
    app_profile.setdefault("HandAccelLimit", 2)
    app_profile.setdefault("BiasMode", 0)
    app_profile.setdefault("BiasCurve", {"Points": ["0|0|0.5", "90|1|0.5"]})
    app_profile.setdefault("OutputScalingDimension", 0)
    app_profile.setdefault("OutputScalingDimensionShape", 0)
    app_profile.setdefault("OutputSmoothingTimeMs", 0)
    app_profile.setdefault("InvertVertical", False)
    app_profile.setdefault("MousePollingRate", "Auto")
    app_profile.setdefault("UseMouseDpi", False)
    app_profile.setdefault("MouseDpi", 800)
    app_profile.setdefault("NormalizeOutput", False)
    return app_profile
def read_customcurve_profiles():
    path = get_customcurve_profiles_path()
    folder = os.path.dirname(path)
    if not os.path.isdir(folder):
        raise FileNotFoundError("CustomCurve folder was not found")
    if not os.path.exists(path):
        return path, {"Profiles": []}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("profiles.json is invalid")
    profiles = data.get("Profiles", [])
    if not isinstance(profiles, list):
        raise ValueError("profiles.json is invalid")
    data["Profiles"] = profiles
    return path, data
def load_profiles_directly(profiles):
    path, data = read_customcurve_profiles()
    current_profiles = data["Profiles"]
    if len(current_profiles) + len(profiles) > 10:
        return False, path, len(current_profiles)
    for profile in profiles:
        current_profiles.append(make_app_profile(profile))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return True, path, len(current_profiles)
def check_customcurve_profile_capacity(incoming_count):
    path, data = read_customcurve_profiles()
    current_count = len(data["Profiles"])
    return current_count + incoming_count <= 10, path, current_count
def is_customcurve_running():
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq CustomCurve.exe"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return "customcurve.exe" in result.stdout.lower()
    except Exception:
        return False
def get_customcurve_exe_path():
    if os.name != "nt":
        return None
    commands = [
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "(Get-CimInstance Win32_Process -Filter \"name='CustomCurve.exe'\" | Select-Object -First 1 -ExpandProperty ExecutablePath)"
        ],
        [
            "wmic",
            "process",
            "where",
            "name='CustomCurve.exe'",
            "get",
            "ExecutablePath",
            "/value"
        ]
    ]
    for command in commands:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            output = result.stdout.strip()
            if not output:
                continue
            if "ExecutablePath=" in output:
                for line in output.splitlines():
                    line = line.strip()
                    if line.lower().startswith("executablepath="):
                        path = line.split("=", 1)[1].strip()
                        if path and os.path.exists(path):
                            return path
            else:
                for line in output.splitlines():
                    path = line.strip().strip('"')
                    if path and path.lower().endswith("customcurve.exe") and os.path.exists(path):
                        return path
        except Exception:
            pass
    return None
def open_customcurve(exe_path):
    if not exe_path or not os.path.exists(exe_path):
        return False
    try:
        subprocess.Popen(
            [exe_path],
            cwd=os.path.dirname(exe_path),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
        return True
    except Exception:
        return False
def wait_until_customcurve_closed_screen():
    clear()
    print(sep(70))
    print(f" {YELLOW}WAITING FOR CUSTOMCURVE TO CLOSE{RESET}")
    print(sep(70))
    print(f"\n{YELLOW}CustomCurve.exe is still running.{RESET}")
    print(f"{GRAY}The profile will not be loaded until the process is fully closed.{RESET}")
    print(f"\n{CYAN}Checking process status...{RESET}")
    dots = 0
    while is_customcurve_running():
        dots = (dots + 1) % 4
        print(f"\r{CYAN}Waiting for CustomCurve.exe to close{'.' * dots}{' ' * (3 - dots)}{RESET}", end="", flush=True)
        time.sleep(0.5)
    print(f"\r{GREEN}CustomCurve.exe is closed. Continuing...{RESET}       ")
    time.sleep(0.6)
def reopened_customcurve_screen(exe_path, opened):
    clear()
    print(sep(70))
    print(f" {GREEN}CUSTOMCURVE UPDATED{RESET}")
    print(sep(70))
    print(f"\n{GREEN}✓ Profile data loaded successfully.{RESET}")
    if opened:
        print(f"{GREEN}✓ CustomCurve was reopened automatically.{RESET}")
        print(f"{BLUE}App:{RESET} {exe_path}")
    else:
        print(f"{YELLOW}CustomCurve was updated, but it could not be reopened automatically.{RESET}")
        if exe_path:
            print(f"{BLUE}App:{RESET} {exe_path}")
    pause_footer("return to menu")
    while True:
        key = msvcrt.getch()
        if key in [b'\r', b'\x1b']:
            return
def close_customcurve_process():
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(
            ["taskkill", "/IM", "CustomCurve.exe", "/F"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return result.returncode == 0
    except Exception:
        return False
def customcurve_running_screen():
    return themed_choice_selector(
        "CUSTOMCURVE IS STILL RUNNING",
        [
            ("Try again", "retry"),
            ("Close, try again, and open", "close_retry"),
            ("Save it as a file instead", "file"),
        ],
        note="CustomCurve must be closed before writing to profiles.json.",
        width=70
    )
def wait_for_customcurve_closed_or_fallback(generator_profiles):
    while is_customcurve_running():
        choice = customcurve_running_screen()
        if choice == "retry":
            continue
        if choice == "close_retry":
            exe_path = get_customcurve_exe_path()
            close_customcurve_process()
            wait_until_customcurve_closed_screen()
            return "closed_open_after", exe_path
        if choice == "file":
            result = save_profiles_as_files(generator_profiles)
            if result[0] == "cancelled":
                continue
            if result[0] > 0:
                save_file_success_screen(result[0], result[1])
                return "file", result
            return "destination", None
        return "destination", None
    return "closed", None
def profiles_full_screen(current_count, incoming_count):
    note = f"CustomCurve can only have 10 profiles. Current: {current_count} | Trying to add: {incoming_count}"
    return themed_choice_selector(
        "CUSTOMCURVE PROFILES FULL",
        [
            ("Save it as a file instead", "file"),
            ("Try again after deleting a profile", "retry"),
        ],
        note=note,
        width=70
    )
def output_destination_selector():
    return themed_choice_selector(
        "OUTPUT DESTINATION",
        [
            ("Save it as a file", "file"),
            ("Load it directly in the app", "app"),
        ],
        note="Note: Make sure CustomCurve is closed for directly loaded profiles to appear.",
        width=70
    )
def direct_load_success_screen(path, count):
    clear()
    print(sep(70))
    print(f" {GREEN}LOADED DIRECTLY IN CUSTOMCURVE{RESET}")
    print(sep(70))
    print(f"\n{GREEN}✓ Loaded {count} profile(s) directly in the app.{RESET}")
    print(f"{BLUE}Path:{RESET} {path}")
    pause_footer("return to menu")
    while True:
        key = msvcrt.getch()
        if key in [b'\r', b'\x1b']:
            return
def save_file_success_screen(saved_count, first_filename):
    clear()
    print(sep(70))
    print(f" {GREEN}SAVED AS FILE{RESET}")
    print(sep(70))
    print(f"\n{GREEN}✓ Saved {saved_count} file(s).{RESET}")
    if first_filename:
        print(f"{BLUE}Location:{RESET} {first_filename}")
    pause_footer("return to menu")
    while True:
        key = msvcrt.getch()
        if key in [b'\r', b'\x1b']:
            return
def direct_load_error_screen(title, message):
    return themed_choice_selector(
        title,
        [
            ("Save it as a file instead", "file"),
            ("Return to menu", "menu"),
        ],
        note=message,
        width=70
    )
def customcurve_installed_check():
    folder = get_customcurve_folder_path()
    if not os.path.isdir(folder):
        return False
    try:
        return any(os.scandir(folder))
    except Exception:
        return False
def customcurve_not_installed_screen():
    clear()
    print(sep(70))
    print(f" {RED}CUSTOMCURVE NOT FOUND{RESET}")
    print(sep(70))
    print(f"\n{RED}CustomCurve was not found or the folder is empty.{RESET}")
    print(f"{BLUE}Path:{RESET} {get_customcurve_folder_path()}")
    pause_footer("close")
    while True:
        key = msvcrt.getch()
        if key in [b'\r', b'\x1b']:
            return
def save_profiles_as_files(generator_profiles):
    if len(generator_profiles) == 1:
        generator, profile, default_name = generator_profiles[0]
        path = pick_output_file(default_name)
        if not path:
            return "cancelled", None
        try:
            generator.save_profile(profile, path)
            return 1, path
        except PermissionError:
            import_error_screen("SAVE PERMISSION ERROR", "Permission was denied while saving the file")
            return 0, None
        except OSError:
            import_error_screen("SAVE ERROR", "The file could not be saved to that location")
            return 0, None
        except Exception:
            import_error_screen("SAVE ERROR", "An unexpected error happened while saving the file")
            return 0, None
    folder = pick_output_directory()
    if not folder:
        return "cancelled", None
    used_names = set()
    saved_count = 0
    first_filename = None
    for generator, profile, default_name in generator_profiles:
        base_filename = normalize_cc4_filename(default_name)
        name_root = base_filename[:-4]
        candidate_name = base_filename
        idx = 2
        while candidate_name.lower() in used_names or os.path.exists(os.path.join(folder, candidate_name)):
            candidate_name = normalize_cc4_filename(f"{name_root}_{idx}")
            idx += 1
        used_names.add(candidate_name.lower())
        candidate = os.path.join(folder, candidate_name)
        try:
            generator.save_profile(profile, candidate)
        except PermissionError:
            import_error_screen("SAVE PERMISSION ERROR", "Permission was denied while saving one of the files")
            return saved_count, first_filename
        except OSError:
            import_error_screen("SAVE ERROR", "One of the files could not be saved to that location")
            return saved_count, first_filename
        except Exception:
            import_error_screen("SAVE ERROR", "An unexpected error happened while saving one of the files")
            return saved_count, first_filename
        if first_filename is None:
            first_filename = candidate
        saved_count += 1
    return saved_count, first_filename
def finish_generated_output(generator_profiles):
    profiles = [profile for _, profile, _ in generator_profiles]
    while True:
        destination = output_destination_selector()
        if destination == "menu":
            return "menu", None
        if destination == "file":
            result = save_profiles_as_files(generator_profiles)
            if result[0] == "cancelled":
                continue
            if result[0] > 0:
                save_file_success_screen(result[0], result[1])
                return "file", result
            return "menu", None
        if destination == "app":
            try:
                capacity_ok, path, current_count = check_customcurve_profile_capacity(len(profiles))
            except FileNotFoundError:
                choice = direct_load_error_screen(
                    "CUSTOMCURVE FOLDER NOT FOUND",
                    "CustomCurve folder was not found. Save it as a file instead, or open CustomCurve once and try again."
                )
                if choice == "file":
                    result = save_profiles_as_files(generator_profiles)
                    if result[0] == "cancelled":
                        continue
                    if result[0] > 0:
                        save_file_success_screen(result[0], result[1])
                        return "file", result
                return "menu", None
            except json.JSONDecodeError:
                choice = direct_load_error_screen(
                    "PROFILES JSON ERROR",
                    "CustomCurve profiles.json is not valid JSON. Save it as a file instead."
                )
                if choice == "file":
                    result = save_profiles_as_files(generator_profiles)
                    if result[0] == "cancelled":
                        continue
                    if result[0] > 0:
                        save_file_success_screen(result[0], result[1])
                        return "file", result
                return "menu", None
            except ValueError:
                choice = direct_load_error_screen(
                    "PROFILES JSON ERROR",
                    "CustomCurve profiles.json has incorrect contents. Save it as a file instead."
                )
                if choice == "file":
                    result = save_profiles_as_files(generator_profiles)
                    if result[0] == "cancelled":
                        continue
                    if result[0] > 0:
                        save_file_success_screen(result[0], result[1])
                        return "file", result
                return "menu", None
            except OSError:
                choice = direct_load_error_screen(
                    "LOAD ERROR",
                    "CustomCurve profiles.json could not be read. Save it as a file instead."
                )
                if choice == "file":
                    result = save_profiles_as_files(generator_profiles)
                    if result[0] == "cancelled":
                        continue
                    if result[0] > 0:
                        save_file_success_screen(result[0], result[1])
                        return "file", result
                return "menu", None
            except Exception:
                choice = direct_load_error_screen(
                    "LOAD ERROR",
                    "An unexpected error happened while checking CustomCurve profiles. Save it as a file instead."
                )
                if choice == "file":
                    result = save_profiles_as_files(generator_profiles)
                    if result[0] == "cancelled":
                        continue
                    if result[0] > 0:
                        save_file_success_screen(result[0], result[1])
                        return "file", result
                return "menu", None
            if not capacity_ok:
                choice = profiles_full_screen(current_count, len(profiles))
                if choice == "file":
                    result = save_profiles_as_files(generator_profiles)
                    if result[0] > 0:
                        save_file_success_screen(result[0], result[1])
                        return "file", result
                    return "menu", None
                if choice == "retry":
                    continue
                return "menu", None
            close_status, close_result = wait_for_customcurve_closed_or_fallback(generator_profiles)
            reopen_after_load = close_status == "closed_open_after"
            reopen_path = close_result if reopen_after_load else None
            if close_status == "destination":
                continue
            if close_status in ["file", "menu"]:
                return close_status, close_result
            try:
                ok, path, current_count = load_profiles_directly(profiles)
            except PermissionError:
                choice = direct_load_error_screen(
                    "LOAD PERMISSION ERROR",
                    "Permission was denied while writing to CustomCurve profiles.json. Save it as a file instead."
                )
                if choice == "file":
                    result = save_profiles_as_files(generator_profiles)
                    if result[0] == "cancelled":
                        continue
                    if result[0] > 0:
                        save_file_success_screen(result[0], result[1])
                        return "file", result
                return "menu", None
            except OSError:
                choice = direct_load_error_screen(
                    "LOAD ERROR",
                    "CustomCurve profiles.json could not be written. Save it as a file instead."
                )
                if choice == "file":
                    result = save_profiles_as_files(generator_profiles)
                    if result[0] == "cancelled":
                        continue
                    if result[0] > 0:
                        save_file_success_screen(result[0], result[1])
                        return "file", result
                return "menu", None
            except Exception:
                choice = direct_load_error_screen(
                    "LOAD ERROR",
                    "An unexpected error happened while loading directly into the app. Save it as a file instead."
                )
                if choice == "file":
                    result = save_profiles_as_files(generator_profiles)
                    if result[0] == "cancelled":
                        continue
                    if result[0] > 0:
                        save_file_success_screen(result[0], result[1])
                        return "file", result
                return "menu", None
            if ok:
                if reopen_after_load:
                    opened = open_customcurve(reopen_path)
                    reopened_customcurve_screen(reopen_path, opened)
                else:
                    direct_load_success_screen(path, len(profiles))
                return "app", path
            choice = profiles_full_screen(current_count, len(profiles))
            if choice == "file":
                result = save_profiles_as_files(generator_profiles)
                if result[0] > 0:
                    save_file_success_screen(result[0], result[1])
                    return "file", result
                return "menu", None
            if choice == "retry":
                continue
            return "menu", None
def safe_int(value, fallback, minimum=None, maximum=None):
    try:
        out = int(value)
    except Exception:
        out = int(fallback)
    if minimum is not None and out < minimum:
        out = minimum
    if maximum is not None and out > maximum:
        out = maximum
    return out
def safe_float(value, fallback=0.0, minimum=0.0, maximum=None):
    try:
        out = float(value)
    except Exception:
        out = float(fallback)
    if minimum is not None and out < minimum:
        out = minimum
    if maximum is not None and out > maximum:
        out = maximum
    return out
ARG_LIMITS = {
    "motivity": (1.0, None),
    "smooth": (0.0, 1.0),
    "sync_speed": (1e-6, None),
    "midpoint": (1e-6, None),
    "scale": (1e-12, None),
    "exponent_power": (1e-12, None),
    "growth_rate": (0.0, None),
    "gamma": (0.0, None),
    "input_offset": (0.0, None),
    "output_offset": (0.0, None),
    "acceleration": (0.0, None),
    "decay_rate": (0.0, None),
    "limit": (0.0, None),
    "exponent": (0.0, None),
    "cap_x": (0.0, None),
    "cap_y": (0.0, None),
}
def get_arg_limits(key):
    return ARG_LIMITS.get(key, (0.0, None))
def parse_bool(value, fallback=False):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ["true", "1", "yes", "y", "on"]:
            return True
        if v in ["false", "0", "no", "n", "off"]:
            return False
    return bool(fallback)
def get_profile_accel_params(profile_obj):
    if not isinstance(profile_obj, dict):
        return None
    for key in [
        "Whole or horizontal accel parameters",
        "Whole accel parameters",
        "Horizontal accel parameters",
    ]:
        params = profile_obj.get(key)
        if isinstance(params, dict):
            return params
    return None
def nearest_allowed_int(value, options, fallback):
    try:
        value = int(value)
    except Exception:
        value = int(fallback)
    return min(options, key=lambda option: (abs(option - value), option))
def normalize_config_values(data):
    if not isinstance(data, dict):
        data = {}
    cleaned = {}
    cleaned["point_count"] = nearest_allowed_int(
        data.get("point_count", RECOMMENDED_POINTS),
        POINT_OPTIONS,
        RECOMMENDED_POINTS
    )
    cleaned["precision"] = nearest_allowed_int(
        data.get("precision", RECOMMENDED_PRECISION),
        PRECISION_OPTIONS,
        RECOMMENDED_PRECISION
    )
    reduction = str(data.get("point_reduction_mode", RECOMMENDED_REDUCTION)).strip().lower()
    cleaned["point_reduction_mode"] = reduction if reduction in REDUCTION_OPTIONS else RECOMMENDED_REDUCTION
    cleaned["rawaccel_path"] = str(data.get("rawaccel_path", "")).strip()
    return cleaned
def pick_output_directory():
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(title="Select folder to save CC4 profile file(s)")
        root.destroy()
        return path or None
    except Exception:
        return None
def pick_output_file(default_name):
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.asksaveasfilename(
            title="Save CC4 profile",
            defaultextension=".cc4",
            initialfile=normalize_cc4_filename(default_name),
            filetypes=[("CC4 files", "*.cc4"), ("JSON files", "*.json"), ("All files", "*.*")]
        )
        root.destroy()
        return path or None
    except Exception:
        return None
def pick_settings_file():
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(
            title="Select RawAccel settings.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        root.destroy()
        return path or None
    except Exception:
        return None
def map_rawaccel_mode(mode_value):
    mode = str(mode_value or "").strip().lower()
    mapping = {
        "classic": "classic/linear",
        "jump": "jump",
        "natural": "natural",
        "synchronous": "synchronous",
        "motivity": "motivity (1.6.1)",
        "power": "power",
        "lut": "lut",
        "lookup": "lut",
        "lookuptable": "lut",
        "noaccel": "noaccel"
    }
    return mapping.get(mode, mode)
def map_rawaccel_cap_mode(cap_mode_value):
    cap = str(cap_mode_value or "").strip().lower()
    mapping = {
        "output": "out",
        "input": "in",
        "in_out": "io",
        "both": "io",
        "out": "out",
        "in": "in",
        "io": "io"
    }
    return mapping.get(cap, "out")
def parse_lookup_points(raw_points):
    if isinstance(raw_points, str):
        raw_points = [raw_points]
    points = []
    if not isinstance(raw_points, list):
        return points
    def parse_num(v):
        try:
            return float(v)
        except Exception:
            return None
    for item in raw_points:
        if isinstance(item, dict):
            x = parse_num(item.get("x"))
            y = parse_num(item.get("y"))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            x = parse_num(item[0])
            y = parse_num(item[1])
        elif isinstance(item, str):
            text = item.strip()
            if not text:
                continue
            if ";" in text and "," in text:
                pairs = [p.strip() for p in text.split(";") if p.strip()]
                for pair in pairs:
                    parts = [p.strip() for p in pair.split(",")]
                    if len(parts) < 2:
                        continue
                    x_pair = parse_num(parts[0])
                    y_pair = parse_num(parts[1])
                    if x_pair is None or y_pair is None or x_pair < 0.0:
                        continue
                    points.append((float(x_pair), float(y_pair)))
                continue
            chunks = text.replace(",", "|").replace(":", "|").split("|")
            if len(chunks) < 2:
                continue
            x = parse_num(chunks[0])
            y = parse_num(chunks[1])
        else:
            continue
        if x is None or y is None:
            continue
        if x < 0.0:
            continue
        points.append((float(x), float(y)))
    points.sort(key=lambda p: p[0])
    dedup = []
    for x, y in points:
        if dedup and abs(dedup[-1][0] - x) <= 1e-12:
            dedup[-1] = (x, y)
        else:
            dedup.append((x, y))
    return dedup
def extract_lookup_points(params):
    if not isinstance(params, dict):
        return []
    for key in ("Lookup table", "lookupTable", "lookup", "LookUpTable", "points", "Points"):
        parsed = parse_lookup_points(params.get(key))
        if parsed:
            return parsed
    raw_data = params.get("data")
    if isinstance(raw_data, list) and len(raw_data) >= 2:
        if isinstance(raw_data[0], (dict, list, tuple, str)):
            parsed = parse_lookup_points(raw_data)
            if parsed:
                return parsed
        numeric = []
        for value in raw_data:
            try:
                numeric.append(float(value))
            except Exception:
                numeric = []
                break
        if len(numeric) >= 2:
            if len(numeric) % 2 != 0:
                numeric = numeric[:-1]
            points = [(numeric[i], numeric[i + 1]) for i in range(0, len(numeric), 2)]
            return parse_lookup_points(points)
    return []
def build_args_from_rawaccel_params(mode, cap_mode, params):
    args = rawaccel_default_args(mode, cap_mode)
    cap_data = params.get("Cap / Jump", {}) if isinstance(params.get("Cap / Jump", {}), dict) else {}
    args["input_offset"] = safe_float(params.get("inputOffset"), args.get("input_offset", 0.0), *get_arg_limits("input_offset"))
    args["output_offset"] = safe_float(params.get("outputOffset"), args.get("output_offset", 0.0), *get_arg_limits("output_offset"))
    args["acceleration"] = safe_float(params.get("acceleration"), args.get("acceleration", 0.005), *get_arg_limits("acceleration"))
    args["decay_rate"] = safe_float(params.get("decayRate"), args.get("decay_rate", 0.1), *get_arg_limits("decay_rate"))
    args["gamma"] = safe_float(params.get("gamma"), args.get("gamma", 1.0), *get_arg_limits("gamma"))
    args["growth_rate"] = safe_float(params.get("growthRate"), args.get("growth_rate", args.get("gamma", 1.0)), *get_arg_limits("growth_rate"))
    args["motivity"] = safe_float(params.get("motivity"), args.get("motivity", 1.5), *get_arg_limits("motivity"))
    args["exponent"] = safe_float(params.get("exponentClassic"), args.get("exponent", 2.0), *get_arg_limits("exponent"))
    args["scale"] = safe_float(params.get("scale"), args.get("scale", 1.0), *get_arg_limits("scale"))
    args["exponent_power"] = safe_float(params.get("exponentPower"), args.get("exponent_power", 0.05), *get_arg_limits("exponent_power"))
    args["limit"] = safe_float(params.get("limit"), args.get("limit", 1.5), *get_arg_limits("limit"))
    args["sync_speed"] = safe_float(params.get("syncSpeed"), args.get("sync_speed", 5.0), *get_arg_limits("sync_speed"))
    args["midpoint"] = safe_float(params.get("midpoint"), args.get("midpoint", args.get("sync_speed", 5.0)), *get_arg_limits("midpoint"))
    args["smooth"] = safe_float(params.get("smooth"), args.get("smooth", 0.5), *get_arg_limits("smooth"))
    args["cap_x"] = safe_float(cap_data.get("x"), args.get("cap_x", 15.0), *get_arg_limits("cap_x"))
    args["cap_y"] = safe_float(cap_data.get("y"), args.get("cap_y", 1.5), *get_arg_limits("cap_y"))
    if mode == "lut":
        gain_key = params.get("Gain / Velocity", params.get("Gain/Velocity", args.get("lut_velocity", True)))
        args["lut_velocity"] = parse_bool(gain_key, args.get("lut_velocity", True))
        args["lookup_points"] = extract_lookup_points(params)
    return args
def sanitize_curve_args(args):
    cleaned = {}
    for key, value in args.items():
        if key == "lookup_points":
            cleaned[key] = parse_lookup_points(value)
            continue
        if key == "lut_velocity":
            cleaned[key] = bool(value)
            continue
        min_value, max_value = get_arg_limits(key)
        cleaned[key] = safe_float(value, 0.0, min_value, max_value)
    return cleaned
def rawaccel_default_args(mode, cap_mode):
    if mode == "natural":
        return {
            "input_offset": 0.0,
            "decay_rate": 0.1,
            "limit": 1.5
        }
    if mode == "jump":
        return {
            "input_offset": 0.0,
            "cap_x": 15.0,
            "cap_y": 1.5,
            "smooth": 0.5
        }
    if mode == "synchronous":
        return {
            "input_offset": 0.0,
            "gamma": 1.0,
            "motivity": 1.5,
            "sync_speed": 5.0,
            "smooth": 0.5
        }
    if mode == "motivity (1.6.1)":
        return {
            "growth_rate": 1.0,
            "motivity": 1.5,
            "midpoint": 5.0
        }
    if mode == "lut":
        return {
            "lut_velocity": True,
            "lookup_points": [
                (0.01, 1.0),
                (5.0, 1.0),
                (15.0, 1.0)
            ]
        }
    if mode == "power":
        args = {
            "output_offset": 0.0,
            "scale": 1.0,
            "exponent_power": 0.05,
            "cap_x": 0.0,
            "cap_y": 0.0
        }
        if cap_mode == "out":
            args["cap_y"] = 1.5
        elif cap_mode == "in":
            args["cap_x"] = 15.0
        else:
            args["cap_x"] = 15.0
            args["cap_y"] = 1.5
        return args
    args = {
        "input_offset": 0.0,
        "acceleration": 0.005,
        "exponent": 2.0,
        "cap_x": 0.0,
        "cap_y": 0.0
    }
    if cap_mode == "out":
        args["cap_y"] = 1.5
    elif cap_mode == "in":
        args["cap_x"] = 15.0
    else:
        args["cap_x"] = 15.0
        args["cap_y"] = 1.5
    return args
class NaturalCurveBase:
    def __init__(self, input_offset, decay_rate, limit):
        self.offset = Fraction(input_offset).limit_denominator(10000)
        self.decay_rate = Fraction(decay_rate).limit_denominator(10000)
        self.limit_frac = Fraction(limit).limit_denominator(10000)
        self.limit = float(self.limit_frac) - 1
        self._is_flat_limit = abs(self.limit) <= 1e-10
        self.accel = float(self.decay_rate) / abs(self.limit) if not self._is_flat_limit else 0.0
class NaturalCurveLegacy(NaturalCurveBase):
    def __call__(self, x):
        offset_float = float(self.offset)
        if x <= offset_float:
            return 1.0
        if self._is_flat_limit:
            return 1.0
        offset_x = offset_float - x
        decay = math.exp(self.accel * offset_x)
        return self.limit * (1 - (offset_float - decay * offset_x) / x) + 1
class NaturalCurveGain(NaturalCurveBase):
    def __init__(self, input_offset, decay_rate, limit):
        super().__init__(input_offset, decay_rate, limit)
        self.constant = -self.limit / self.accel if not self._is_flat_limit else 0.0
    def __call__(self, x):
        offset_float = float(self.offset)
        if x <= offset_float:
            return 1.0
        if self._is_flat_limit:
            return 1.0
        offset_x = offset_float - x
        decay = math.exp(self.accel * offset_x)
        output = self.limit * (decay / self.accel - offset_x) + self.constant
        return output / x + 1
class JumpCurveBase:
    SMOOTH_SCALE = 2 * math.pi
    def __init__(self, cap_x, cap_y, smooth):
        self.step_x = float(Fraction(cap_x).limit_denominator(10000))
        self.step_y = float(Fraction(cap_y).limit_denominator(10000)) - 1.0
        smooth = float(Fraction(smooth).limit_denominator(10000))
        rate_inverse = smooth * self.step_x
        self.smooth_rate = 0.0 if rate_inverse < 1.0 else self.SMOOTH_SCALE / rate_inverse
    def is_smooth(self):
        return self.smooth_rate != 0.0
    def decay(self, x):
        return math.exp(self.smooth_rate * (self.step_x - x))
    def smooth_value(self, x):
        return self.step_y / (1.0 + self.decay(x))
    def smooth_antideriv(self, x):
        if not self.is_smooth():
            return 0.0
        return self.step_y * (x + math.log(1.0 + self.decay(x)) / self.smooth_rate)
class JumpCurveLegacy(JumpCurveBase):
    def __call__(self, x):
        if self.is_smooth():
            return self.smooth_value(x) + 1.0
        if x < self.step_x:
            return 1.0
        return 1.0 + self.step_y
class JumpCurveGain(JumpCurveBase):
    def __init__(self, cap_x, cap_y, smooth):
        super().__init__(cap_x, cap_y, smooth)
        self.C = -self.smooth_antideriv(0.0)
    def __call__(self, x):
        if x <= 0.0:
            return 1.0
        if self.is_smooth():
            return 1.0 + (self.smooth_antideriv(x) + self.C) / x
        if x < self.step_x:
            return 1.0
        return 1.0 + self.step_y * (x - self.step_x) / x
class ClassicCurveBase:
    def __init__(self, input_offset, acceleration, exponent):
        self.offset = float(Fraction(input_offset).limit_denominator(10000))
        self.acceleration = float(Fraction(acceleration).limit_denominator(10000))
        self.exponent = float(Fraction(exponent).limit_denominator(10000))
    def base_fn(self, x, accel_raised):
        return accel_raised * math.pow(x - self.offset, self.exponent) / x
    def base_accel(self, x, y):
        return math.pow(
            x * y * math.pow(x - self.offset, -self.exponent),
            1 / (self.exponent - 1)
        )
class ClassicCurveLegacy(ClassicCurveBase):
    def __init__(self, input_offset, acceleration, exponent, cap_mode, cap_x, cap_y):
        super().__init__(input_offset, acceleration, exponent)
        self.cap = float("inf")
        self.sign = 1.0
        self.accel_raised = math.pow(self.acceleration, self.exponent - 1)
        cap_mode = cap_mode.lower()
        if cap_mode == "io":
            self.cap = cap_y - 1.0
            if self.cap < 0:
                self.cap = -self.cap
                self.sign = -self.sign
            if cap_x > self.offset and self.cap > 0:
                a = self.base_accel(cap_x, self.cap)
                self.accel_raised = math.pow(a, self.exponent - 1)
        elif cap_mode == "in":
            if cap_x > 0:
                self.cap = self.base_fn(cap_x, self.accel_raised)
        else:
            if cap_y > 0:
                self.cap = cap_y - 1.0
                if self.cap < 0:
                    self.cap = -self.cap
                    self.sign = -self.sign
    def __call__(self, x):
        if x <= self.offset:
            return 1.0
        return self.sign * min(self.base_fn(x, self.accel_raised), self.cap) + 1.0
class ClassicCurveGain(ClassicCurveBase):
    def __init__(self, input_offset, acceleration, exponent, cap_mode, cap_x, cap_y):
        super().__init__(input_offset, acceleration, exponent)
        self.cap_x = float("inf")
        self.cap_y = float("inf")
        self.constant = 0.0
        self.sign = 1.0
        self.accel_raised = math.pow(self.acceleration, self.exponent - 1)
        cap_mode = cap_mode.lower()
        if cap_mode == "io":
            self.cap_x = cap_x
            self.cap_y = cap_y - 1.0
            if self.cap_y < 0:
                self.cap_y = -self.cap_y
                self.sign = -self.sign
            if self.cap_x > self.offset and self.cap_y > 0:
                a = self.gain_accel(self.cap_x, self.cap_y, self.exponent, self.offset)
                self.accel_raised = math.pow(a, self.exponent - 1)
                self.constant = (self.base_fn(self.cap_x, self.accel_raised) - self.cap_y) * self.cap_x
        elif cap_mode == "in":
            if cap_x > 0:
                self.cap_x = cap_x
                self.cap_y = self.gain(self.cap_x, self.acceleration, self.exponent, self.offset)
                self.constant = (self.base_fn(self.cap_x, self.accel_raised) - self.cap_y) * self.cap_x
        else:
            if cap_y > 0:
                self.cap_y = cap_y - 1.0
                if self.cap_y == 0:
                    self.cap_x = 0.0
                else:
                    if self.cap_y < 0:
                        self.cap_y = -self.cap_y
                        self.sign = -self.sign
                    self.cap_x = self.gain_inverse(
                        self.cap_y,
                        self.acceleration,
                        self.exponent,
                        self.offset
                    )
                    self.constant = (self.base_fn(self.cap_x, self.accel_raised) - self.cap_y) * self.cap_x
    def __call__(self, x):
        if x <= self.offset:
            return 1.0
        if x < self.cap_x:
            output = self.base_fn(x, self.accel_raised)
        else:
            output = self.constant / x + self.cap_y
        return self.sign * output + 1.0
    @staticmethod
    def gain(x, accel, power, offset):
        return power * math.pow(accel * (x - offset), power - 1)
    @staticmethod
    def gain_inverse(y, accel, power, offset):
        return (accel * offset + math.pow(y / power, 1 / (power - 1))) / accel
    @staticmethod
    def gain_accel(x, y, power, offset):
        return -math.pow(y / power, 1 / (power - 1)) / (offset - x)
class SynchronousCurveLegacy:
    def __init__(self, gamma, motivity, sync_speed, smooth):
        self.motivity = max(float(Fraction(motivity).limit_denominator(10000)), 1e-12)
        self.log_motivity = math.log(self.motivity)
        self.gamma = float(Fraction(gamma).limit_denominator(10000))
        self.gamma_const = self.gamma / self.log_motivity if abs(self.log_motivity) > 1e-12 else 0.0
        self.sync_speed = max(float(Fraction(sync_speed).limit_denominator(10000)), 1e-12)
        self.log_syncspeed = math.log(self.sync_speed)
        smooth = max(float(Fraction(smooth).limit_denominator(10000)), 0.0)
        self.sharpness = 16.0 if smooth == 0 else 0.5 / smooth
        self.sharpness_recip = 1.0 / self.sharpness
        self.use_linear_clamp = self.sharpness >= 16.0
        self.minimum_sens = 1.0 / self.motivity
        self.maximum_sens = self.motivity
    def __call__(self, x):
        if x <= 0.0:
            return self.minimum_sens
        if self.use_linear_clamp:
            log_space = self.gamma_const * (math.log(x) - self.log_syncspeed)
            if log_space < -1.0:
                return self.minimum_sens
            if log_space > 1.0:
                return self.maximum_sens
            return math.exp(log_space * self.log_motivity)
        if x == self.sync_speed:
            return 1.0
        log_diff = math.log(x) - self.log_syncspeed
        if log_diff > 0:
            log_space = self.gamma_const * log_diff
            exponent = math.pow(math.tanh(math.pow(log_space, self.sharpness)), self.sharpness_recip)
            return math.exp(exponent * self.log_motivity)
        log_space = -self.gamma_const * log_diff
        exponent = -math.pow(math.tanh(math.pow(log_space, self.sharpness)), self.sharpness_recip)
        return math.exp(exponent * self.log_motivity)
class SynchronousCurveGain:
    RANGE_START = -3
    RANGE_STOP = 9
    RANGE_NUM = 8
    def __init__(self, gamma, motivity, sync_speed, smooth):
        self.velocity = True
        self.range_start = self.RANGE_START
        self.range_stop = self.RANGE_STOP
        self.range_num = self.RANGE_NUM
        self.x_start = math.ldexp(1.0, self.range_start)
        self.data = []
        sig = SynchronousCurveLegacy(gamma, motivity, sync_speed, smooth)
        sum_area = 0.0
        a = 0.0
        partitions = 2
        def sigmoid_sum(b):
            nonlocal a, sum_area
            interval = (b - a) / partitions
            for i in range(1, partitions + 1):
                sum_area += sig(a + i * interval) * interval
            a = b
            return sum_area
        for x in self._range_values():
            self.data.append(sigmoid_sum(x))
    def _range_values(self):
        for e in range(0, self.range_stop - self.range_start):
            exp_scale = math.ldexp(1.0, e + self.range_start) / self.range_num
            for i in range(self.range_num):
                yield (i + self.range_num) * exp_scale
        yield math.ldexp(1.0, self.range_stop)
    @staticmethod
    def _lerp(a, b, t):
        x = a + t * (b - a)
        if (t > 1.0) == (a < b):
            return max(x, b)
        return min(x, b)
    @staticmethod
    def _ilogb(x):
        if x <= 0.0:
            return -1024
        m, e = math.frexp(x)
        if m == 0.0:
            return -1024
        return e - 1
    def __call__(self, x):
        if x <= 0.0:
            return self.data[0] / self.x_start
        e = min(self._ilogb(x), self.range_stop - 1)
        if e >= self.range_start:
            idx_int_log_part = e - self.range_start
            idx_frac_lin_part = math.ldexp(x, -e) - 1.0
            idx_f = self.range_num * (idx_int_log_part + idx_frac_lin_part)
            idx = min(int(idx_f), len(self.data) - 2)
            if idx < len(self.data) - 1:
                t = idx_f - idx
                y = self._lerp(self.data[idx], self.data[idx + 1], t)
                return y / x
        return self.data[0] / self.x_start
class MotivityCurveLegacy:
    def __init__(self, growth_rate, motivity, midpoint):
        self.accel = math.exp(float(Fraction(growth_rate).limit_denominator(10000)))
        self.motivity = max(float(Fraction(motivity).limit_denominator(10000)), 1e-12)
        self.midpoint = max(float(Fraction(midpoint).limit_denominator(10000)), 1e-12)
        self.log_midpoint = math.log(self.midpoint)
        self.motivity_term = 2.0 * math.log(self.motivity)
        self.constant = -self.motivity_term / 2.0
        self.minimum_sens = 1.0 / self.motivity
    def __call__(self, x):
        if x <= 0.0:
            return self.minimum_sens
        denom = math.exp(self.accel * (self.log_midpoint - math.log(x))) + 1.0
        return math.exp(self.motivity_term / denom + self.constant)
class MotivityCurveGain:
    RANGE_START = -3
    RANGE_STOP = 9
    RANGE_NUM = 8
    def __init__(self, growth_rate, motivity, midpoint):
        self.range_start = self.RANGE_START
        self.range_stop = self.RANGE_STOP
        self.range_num = self.RANGE_NUM
        self.x_start = math.ldexp(1.0, self.range_start)
        self.data = []
        sig = MotivityCurveLegacy(growth_rate, motivity, midpoint)
        sum_area = 0.0
        a = 0.0
        partitions = 2
        def sigmoid_sum(b):
            nonlocal a, sum_area
            interval = (b - a) / partitions
            for i in range(1, partitions + 1):
                sum_area += sig(a + i * interval) * interval
            a = b
            return sum_area
        for x in self._range_values():
            self.data.append(sigmoid_sum(x))
    def _range_values(self):
        for e in range(0, self.range_stop - self.range_start):
            exp_scale = math.ldexp(1.0, e + self.range_start) / self.range_num
            for i in range(self.range_num):
                yield (i + self.range_num) * exp_scale
        yield math.ldexp(1.0, self.range_stop)
    @staticmethod
    def _lerp(a, b, t):
        x = a + t * (b - a)
        if (t > 1.0) == (a < b):
            return max(x, b)
        return min(x, b)
    @staticmethod
    def _ilogb(x):
        if x <= 0.0:
            return -1024
        m, e = math.frexp(x)
        if m == 0.0:
            return -1024
        return e - 1
    def __call__(self, x):
        if x <= 0.0:
            return self.data[0] / self.x_start
        e = min(self._ilogb(x), self.range_stop - 1)
        if e >= self.range_start:
            idx_int_log_part = e - self.range_start
            idx_frac_lin_part = math.ldexp(x, -e) - 1.0
            idx_f = self.range_num * (idx_int_log_part + idx_frac_lin_part)
            idx = min(int(idx_f), len(self.data) - 2)
            if idx < len(self.data) - 1:
                t = idx_f - idx
                y = self._lerp(self.data[idx], self.data[idx + 1], t)
                return y / x
        return self.data[0] / self.x_start
class LookupCurve:
    CAPACITY = 257
    def __init__(self, points, velocity):
        parsed = parse_lookup_points(points)
        if len(parsed) < 2:
            parsed = [(0.01, 1.0), (15.0, 1.0)]
        self.points = parsed
        self.velocity = bool(velocity)
    @staticmethod
    def _lerp(a, b, t):
        x = a + t * (b - a)
        if (t > 1.0) == (a < b):
            return max(x, b)
        return min(x, b)
    def __call__(self, x):
        if x <= 0.0:
            return 0.0
        size = len(self.points)
        lo = 0
        hi = size - 2
        if size >= 2 and hi < self.CAPACITY - 1:
            while lo <= hi:
                mid = (lo + hi) // 2
                px, py = self.points[mid]
                if x < px:
                    hi = mid - 1
                elif x > px:
                    lo = mid + 1
                else:
                    y = py
                    return (y / x) if self.velocity else y
            if lo > 0 and lo < size:
                ax, ay = self.points[lo - 1]
                bx, by = self.points[lo]
                if abs(bx - ax) <= 1e-12:
                    y = by
                else:
                    t = (x - ax) / (bx - ax)
                    y = self._lerp(ay, by, t)
                return (y / x) if self.velocity else y
        y = self.points[0][1]
        return (y / max(self.points[0][0], 1e-12)) if self.velocity else y
class PowerCurveBase:
    def __init__(self, output_offset, scale, exponent_power, cap_mode, cap_x, cap_y, gain_curve):
        self.power = max(float(Fraction(exponent_power).limit_denominator(10000)), 1e-12)
        self.output_offset = float(Fraction(output_offset).limit_denominator(10000))
        self.scale = float(Fraction(scale).limit_denominator(10000))
        self.offset_x = 0.0
        self.offset_y = self.output_offset
        self.constant = 0.0
        self.cap_mode = cap_mode.lower()
        self.gain_curve = bool(gain_curve)
        self.cap_x = float(Fraction(cap_x).limit_denominator(10000))
        self.cap_y = float(Fraction(cap_y).limit_denominator(10000))
        self._setup_parameters()
    @staticmethod
    def gain(input_val, power, scale):
        return (power + 1.0) * math.pow(input_val * scale, power)
    @staticmethod
    def gain_inverse(gain, power, scale):
        return math.pow(gain / (power + 1.0), 1.0 / power) / scale
    @staticmethod
    def scale_from_gain_point(input_val, gain, power):
        return math.pow(gain / (power + 1.0), 1.0 / power) / input_val
    @staticmethod
    def scale_from_output_point(input_val, output, power, constant):
        return math.pow(output - constant / input_val, 1.0 / power) / input_val
    @staticmethod
    def integration_constant(input_val, gain, output):
        return (output - gain) * input_val
    @staticmethod
    def ieee_divide(numerator, denominator):
        if denominator != 0:
            return numerator / denominator
        if numerator == 0:
            return float("nan")
        return math.copysign(float("inf"), numerator)
    def _setup_parameters(self):
        if self.cap_mode != "io":
            self.scale = self.scale
        elif self.gain_curve:
            self.scale = self.scale_from_gain_point(self.cap_x, self.cap_y, self.power)
        else:
            self.offset_x = 0.0
            self.offset_y = 0.0
            self.constant = 0.0
            self.scale = self.scale_from_output_point(
                self.cap_x,
                self.cap_y,
                self.power,
                self.constant
            )
            return
        self.offset_x = self.gain_inverse(self.output_offset, self.power, self.scale)
        self.offset_y = self.output_offset
        self.constant = self.offset_x * self.offset_y * self.power / (self.power + 1.0)
    def base_fn(self, x):
        if x <= self.offset_x:
            return self.offset_y
        return math.pow(self.scale * x, self.power) + self.constant / x
class PowerCurveLegacy(PowerCurveBase):
    def __init__(self, output_offset, scale, exponent_power, cap_mode, cap_x, cap_y):
        super().__init__(output_offset, scale, exponent_power, cap_mode, cap_x, cap_y, gain_curve=False)
        self.cap = float("inf")
        if self.cap_mode == "io":
            self.cap = self.cap_y
        elif self.cap_mode == "in":
            if self.cap_x > 0:
                self.cap = self.base_fn(self.cap_x)
        else:
            if self.cap_y > 0:
                self.cap = self.cap_y
    def __call__(self, x):
        return min(self.base_fn(x), self.cap)
class PowerCurveGain(PowerCurveBase):
    def __init__(self, output_offset, scale, exponent_power, cap_mode, cap_x, cap_y):
        super().__init__(output_offset, scale, exponent_power, cap_mode, cap_x, cap_y, gain_curve=True)
        self.cap_x_eff = float("inf")
        self.cap_y_eff = float("inf")
        self.constant_b = 0.0
        if self.cap_mode == "io":
            self.cap_x_eff = self.cap_x
            self.cap_y_eff = self.cap_y
        elif self.cap_mode == "in":
            if self.cap_x > 0:
                if self.cap_x <= self.offset_x:
                    self.cap_x_eff = 0.0
                    self.cap_y_eff = self.offset_y
                    self.constant_b = 0.0
                    return
                self.cap_x_eff = self.cap_x
                self.cap_y_eff = self.gain(self.cap_x, self.power, self.scale)
        else:
            if self.cap_y > 0:
                self.cap_x_eff = self.gain_inverse(self.cap_y, self.power, self.scale)
                self.cap_y_eff = self.cap_y
        self.constant_b = self.integration_constant(self.cap_x_eff, self.cap_y_eff, self.base_fn(self.cap_x_eff))
    def __call__(self, x):
        if x < self.cap_x_eff:
            out = self.base_fn(x)
        else:
            out = self.cap_y_eff + self.ieee_divide(self.constant_b, x)
        return out
class CurveGenerator:
    def __init__(self, mode_name="natural", curve_type="legacy", cap_mode="out", point_reduction_mode="off"):
        self.mode_name = mode_name.lower()
        self.curve_type = curve_type.lower()
        self.cap_mode = cap_mode.lower()
        self.point_reduction_mode = (point_reduction_mode or "off").lower()
        if self.curve_type not in ["legacy", "gain"]:
            raise ValueError("curve_type must be 'legacy' or 'gain'")
    def _build_curve(self, args):
        if self.mode_name == "natural":
            return NaturalCurveLegacy(args["input_offset"], args["decay_rate"], args["limit"]) \
                if self.curve_type == "legacy" \
                else NaturalCurveGain(args["input_offset"], args["decay_rate"], args["limit"])
        if self.mode_name == "jump":
            return JumpCurveLegacy(args["cap_x"], args["cap_y"], args["smooth"]) \
                if self.curve_type == "legacy" \
                else JumpCurveGain(args["cap_x"], args["cap_y"], args["smooth"])
        if self.mode_name == "synchronous":
            return SynchronousCurveLegacy(args["gamma"], args["motivity"], args["sync_speed"], args["smooth"]) \
                if self.curve_type == "legacy" \
                else SynchronousCurveGain(args["gamma"], args["motivity"], args["sync_speed"], args["smooth"])
        if self.mode_name == "motivity (1.6.1)":
            return MotivityCurveLegacy(args["growth_rate"], args["motivity"], args["midpoint"]) \
                if self.curve_type == "legacy" \
                else MotivityCurveGain(args["growth_rate"], args["motivity"], args["midpoint"])
        if self.mode_name == "lut":
            return LookupCurve(args.get("lookup_points", []), velocity=bool(args.get("lut_velocity", True)))
        if self.mode_name == "classic/linear":
            return ClassicCurveLegacy(
                args["input_offset"], args["acceleration"], args["exponent"],
                self.cap_mode, args["cap_x"], args["cap_y"]
            ) if self.curve_type == "legacy" else ClassicCurveGain(
                args["input_offset"], args["acceleration"], args["exponent"],
                self.cap_mode, args["cap_x"], args["cap_y"]
            )
        if self.mode_name == "power":
            return PowerCurveLegacy(
                args["output_offset"], args["scale"], args["exponent_power"],
                self.cap_mode, args["cap_x"], args["cap_y"]
            ) if self.curve_type == "legacy" else PowerCurveGain(
                args["output_offset"], args["scale"], args["exponent_power"],
                self.cap_mode, args["cap_x"], args["cap_y"]
            )
        raise ValueError(f"Unsupported mode: {self.mode_name}")
    def _classic_gain_cap_breakpoint(self, args):
        if self.mode_name != "classic/linear" or self.curve_type != "gain":
            return None
        offset = args["input_offset"]
        accel = args["acceleration"]
        exponent = args["exponent"]
        cap_x = args.get("cap_x", 0.0)
        cap_y = args.get("cap_y", 0.0)
        if self.cap_mode in ["in", "io"]:
            return cap_x if cap_x > offset else None
        if cap_y > 0 and accel > 0 and exponent != 1:
            cap_y_adj = cap_y - 1.0
            if abs(cap_y_adj) <= 1e-12:
                return 0.0
            cap_y_abs = abs(cap_y_adj)
            return (accel * offset + math.pow(cap_y_abs / exponent, 1 / (exponent - 1))) / accel
        return None
    def _power_gain_cap_breakpoint(self, args):
        if self.mode_name != "power" or self.curve_type != "gain":
            return None
        cap_x = args.get("cap_x", 0.0)
        cap_y = args.get("cap_y", 0.0)
        p = max(float(args.get("exponent_power", 0.05)), 1e-12)
        s = max(float(args.get("scale", 1.0)), 1e-12)
        if self.cap_mode in ["in", "io"]:
            return cap_x if cap_x > 0 else None
        if cap_y > 0:
            return math.pow(cap_y / (p + 1.0), 1.0 / p) / s
        return None
    def _power_offset_breakpoint(self, args):
        if self.mode_name != "power":
            return None
        cap_x = float(args.get("cap_x", 0.0))
        cap_y = float(args.get("cap_y", 0.0))
        output_offset = float(args.get("output_offset", 0.0))
        p = max(float(args.get("exponent_power", 0.05)), 1e-12)
        s = float(args.get("scale", 1.0))
        if self.cap_mode == "io" and self.curve_type == "legacy":
            return 0.0
        if self.cap_mode == "io" and self.curve_type == "gain":
            if cap_x > 0:
                s = PowerCurveBase.scale_from_gain_point(cap_x, cap_y, p)

        if output_offset <= 0:
            return 0.0
        return math.pow(output_offset / (p + 1.0), 1.0 / p) / s
    def _special_breakpoint(self, args):
        classic_bp = self._classic_gain_cap_breakpoint(args)
        if classic_bp is not None:
            return classic_bp
        return self._power_gain_cap_breakpoint(args)
    def _breakpoint_aware_x_values(self, point_count, max_input, breakpoint):
        if point_count <= 1:
            return [max_input]
        if breakpoint is None or breakpoint <= 0 or breakpoint >= max_input:
            step = max_input / (point_count - 1)
            return [i * step for i in range(point_count - 1)] + [max_input]
        pre_count = max(3, int(point_count * 0.46))
        post_count = max(3, point_count - pre_count)
        pre_step = breakpoint / (pre_count - 1)
        pre_x = [i * pre_step for i in range(pre_count)]
        span = max_input - breakpoint
        post_x = []
        for i in range(1, post_count + 1):
            t = i / post_count
            post_x.append(breakpoint + span * (math.log10(1.0 + 9.0 * t)))
        x_values = sorted(set(min(max(x, 0.0), max_input) for x in (pre_x + post_x)))
        while len(x_values) < point_count:
            x_values.append(max_input)
        return x_values[:point_count]
    def _power_x_values(self, args, point_count, max_input, cap_breakpoint):
        if point_count <= 1:
            return [max_input]
        base_x = self._breakpoint_aware_x_values(point_count, max_input, cap_breakpoint)
        offset_bp = self._power_offset_breakpoint(args)
        early_count = max(20, int(point_count * 0.40))
        early_focus = max(
            1.0,
            min(
                max_input,
                max(
                    max_input * 0.20,
                    (offset_bp or 0.0) * 3.0,
                    (cap_breakpoint or 0.0) * 0.35
                )
            )
        )
        early_x = [
            early_focus * ((i / max(1, early_count - 1)) ** 2.8)
            for i in range(early_count)
        ]
        x_values = sorted(
            set(
                min(max(x, 0.0), max_input)
                for x in (base_x + early_x + [offset_bp or 0.0, max_input])
            )
        )
        return x_values
    def _jump_x_values(self, args, point_count, max_input):
        step_x = max(0.0, float(args.get("cap_x", 15.0)))
        smooth = max(0.0, min(1.0, float(args.get("smooth", 0.5))))
        rate_inverse = smooth * step_x
        smooth_rate = 0.0 if rate_inverse < 1.0 else (2.0 * math.pi / rate_inverse)
        if point_count <= 1:
            return [max_input]
        if smooth_rate == 0.0:
            knee_width = max(0.25, step_x * 0.02)
        else:
            knee_width = max(0.25, 3.0 / smooth_rate)
        left = max(0.0, step_x - knee_width)
        right = min(max_input, step_x + knee_width)
        pre_count = max(16, int(point_count * 0.28))
        knee_count = max(28, int(point_count * 0.50))
        post_count = max(16, point_count - pre_count - knee_count)
        pre_x = [left * (i / max(1, pre_count - 1)) for i in range(pre_count)]
        knee_x = [left + (right - left) * (i / max(1, knee_count - 1)) for i in range(knee_count)]
        post_x = [right + (max_input - right) * (i / max(1, post_count - 1)) for i in range(post_count)]
        x_values = sorted(set(min(max(x, 0.0), max_input) for x in (pre_x + knee_x + post_x + [step_x, max_input])))
        if not x_values:
            return [0.0, max_input]
        if len(x_values) >= point_count:
            return x_values[:point_count]
        filled = []
        last_idx = len(x_values) - 1
        for i in range(point_count):
            pos = (i / max(1, point_count - 1)) * last_idx
            lo = int(math.floor(pos))
            hi = min(last_idx, lo + 1)
            t = pos - lo
            x = x_values[lo] * (1 - t) + x_values[hi] * t
            if not filled or x > filled[-1]:
                filled.append(x)
        while len(filled) < point_count:
            filled.append(max_input)
        return filled[:point_count]
    def _synchronous_x_values(self, args, point_count, max_input):
        if point_count <= 1:
            return [max_input]
        sync_speed = max(float(args.get("sync_speed", 5.0)), 1e-6)
        x_min = max(1e-4, sync_speed / 1000.0)
        x_max = max(max_input, x_min * 2.0)
        log_min = math.log(x_min)
        log_max = math.log(x_max)
        xs = []
        for i in range(point_count - 2):
            t = i / max(1, point_count - 3)
            x = math.exp(log_min + t * (log_max - log_min))
            xs.append(min(max(x, 0.0), max_input))
        xs.append(min(sync_speed, max_input))
        xs.append(max_input)
        xs = sorted(xs)
        xs[0] = 0.0
        xs[-1] = max_input
        return xs
    def _motivity_x_values(self, args, point_count, max_input):
        if point_count <= 1:
            return [max_input]
        midpoint = max(float(args.get("midpoint", 5.0)), 1e-6)
        x_min = max(1e-4, midpoint / 1000.0)
        x_max = max(max_input, x_min * 2.0)
        log_min = math.log(x_min)
        log_max = math.log(x_max)
        xs = []
        for i in range(point_count - 2):
            t = i / max(1, point_count - 3)
            x = math.exp(log_min + t * (log_max - log_min))
            xs.append(min(max(x, 0.0), max_input))
        xs.append(min(midpoint, max_input))
        xs.append(max_input)
        xs = sorted(xs)
        xs[0] = 0.0
        xs[-1] = max_input
        return xs
    def _remove_flat_runs(self, curve, x_values, y_tolerance=0.000001, protected=None, precision=6):
        return sorted(set(float(x) for x in x_values))
    def _collapse_flat_runs_in_output(self, points):
        if len(points) <= 2:
            return points
        collapsed = []
        run = [points[0]]
        def y_of(point):
            parts = str(point).split("|")
            return parts[1] if len(parts) > 1 else ""
        run_y = y_of(points[0])
        for point in points[1:]:
            y = y_of(point)
            if y == run_y:
                run.append(point)
            else:
                collapsed.append(run[0])
                if len(run) > 1:
                    collapsed.append(run[-1])
                run = [point]
                run_y = y
        collapsed.append(run[0])
        if len(run) > 1:
            collapsed.append(run[-1])
        return collapsed
    def _remove_same_direction_runs(
        self,
        curve,
        x_values,
        protected=None,
        preserve_below_x=0.0,
        slope_rel_tolerance=0.0002,
        slope_abs_tolerance=1e-9,
        max_midpoint_error=0.00005
    ):
        protected = set(round(float(x), 10) for x in (protected or []))
        x_values = sorted(set(float(x) for x in x_values))
        if len(x_values) <= 2:
            return x_values
        y_cache = {}
        def y_of(x):
            rx = round(float(x), 12)
            if rx not in y_cache:
                y_cache[rx] = curve(float(x))
            return y_cache[rx]
        def slope(a, b):
            dx = b - a
            if abs(dx) <= 1e-12:
                return 0.0
            return (y_of(b) - y_of(a)) / dx
        def direction(s):
            if s > slope_abs_tolerance:
                return 1
            if s < -slope_abs_tolerance:
                return -1
            return 0
        reduced = [x_values[0], x_values[1]]
        for x in x_values[2:]:
            a = reduced[-2]
            b = reduced[-1]
            c = x
            b_protected = round(float(b), 10) in protected
            b_preserved = b <= max(float(preserve_below_x), 0.0)
            s1 = slope(a, b)
            s2 = slope(b, c)
            d1 = direction(s1)
            d2 = direction(s2)
            close_slopes = abs(s2 - s1) <= max(
                slope_abs_tolerance,
                slope_rel_tolerance * max(abs(s1), abs(s2), 1.0)
            )
            same_direction = d1 == d2
            both_flat = d1 == 0 and d2 == 0
            y_a = y_of(a)
            y_b = y_of(b)
            y_c = y_of(c)
            t = 0.0 if abs(c - a) <= 1e-12 else (b - a) / (c - a)
            y_interp = y_a + (y_c - y_a) * t
            mid_err = abs(y_b - y_interp)
            allowed_err = max(max_midpoint_error, 0.00005 * max(abs(y_b), 1.0))
            near_collinear = mid_err <= allowed_err
            if not b_protected and not b_preserved and near_collinear and ((same_direction and close_slopes) or both_flat):
                reduced[-1] = c
            else:
                reduced.append(c)
        return reduced
    def _natural_x_values(self, args, point_count, max_input):
        offset = max(0.0, float(args.get("input_offset", 0.0)))
        if point_count <= 1:
            return [max_input]
        xs = []
        for i in range(point_count):
            t = i / max(1, point_count - 1)
            x = max_input * (t ** 2.25)
            xs.append(x)
        xs.extend([0.0, offset, max_input])
        return sorted(set(min(max(x, 0.0), max_input) for x in xs))
    def generate_points(self, args, point_count=50, max_input=100, precision=6):
        curve = self._build_curve(args)
        points = []
        max_input = max(float(max_input), 0.0)
        if self.mode_name == "lut":
            lut_points = parse_lookup_points(args.get("lookup_points", []))
            if lut_points:
                velocity = bool(args.get("lut_velocity", True))
                if not velocity:
                    for x, y in lut_points:
                        x_str = f"{float(x):.{precision}f}".rstrip('0').rstrip('.')
                        y_str = f"{float(y):.{precision}f}".rstrip('0').rstrip('.')
                        points.append(f"{x_str}|{y_str}|{POINT_TENSION}")
                    return points
                sampled_x = []
                for idx in range(len(lut_points) - 1):
                    ax, _ = lut_points[idx]
                    bx, _ = lut_points[idx + 1]
                    if bx <= ax:
                        continue
                    sampled_x.append(float(ax))
                    segment_ratio = max(bx / max(ax, 1e-9), 1.0)
                    samples_per_segment = min(64, max(12, int(12 + math.log10(segment_ratio + 1.0) * 22)))
                    for i in range(1, samples_per_segment):
                        t = i / samples_per_segment
                        t_bias = t * t
                        x = ax + (bx - ax) * t_bias
                        sampled_x.append(float(x))
                sampled_x.append(float(lut_points[-1][0]))
                sampled_x = sorted(set(sampled_x))
                for x in sampled_x:
                    y = curve(x)
                    x_str = f"{x:.{precision}f}".rstrip('0').rstrip('.')
                    y_str = f"{y:.{precision}f}".rstrip('0').rstrip('.')
                    points.append(f"{x_str}|{y_str}|{POINT_TENSION}")
                return points
        x_values = []
        cap_breakpoint = self._special_breakpoint(args)
        if self.mode_name == "jump":
            x_values = self._jump_x_values(args, point_count, max_input)
        elif self.mode_name == "synchronous":
            x_values = self._synchronous_x_values(args, point_count, max_input)
        elif self.mode_name == "motivity (1.6.1)":
            x_values = self._motivity_x_values(args, point_count, max_input)
        elif self.mode_name == "natural":
            x_values = self._natural_x_values(args, point_count, max_input)
        elif self.mode_name == "power":
            x_values = self._power_x_values(args, point_count, max_input, cap_breakpoint)
        else:
            x_values = self._breakpoint_aware_x_values(point_count, max_input, cap_breakpoint)
        protected = {0.0, max_input}
        if self.mode_name in ["classic/linear", "natural"]:
            protected.add(float(args.get("input_offset", 0.0)))
        if self.mode_name == "power":
            protected.add(float(self._power_offset_breakpoint(args) or 0.0))
        if self.mode_name == "jump":
            protected.add(float(args.get("cap_x", 15.0)))
        if self.mode_name == "synchronous":
            protected.add(float(args.get("sync_speed", 5.0)))
        if self.mode_name == "motivity (1.6.1)":
            protected.add(float(args.get("midpoint", 5.0)))
        if cap_breakpoint is not None:
            protected.add(float(cap_breakpoint))
        x_values = self._remove_flat_runs(
            curve,
            x_values,
            y_tolerance=0.000001,
            protected=protected,
            precision=precision
        )
        preserve_below_x = 0.0
        if self.mode_name == "power":
            preserve_below_x = max_input * 0.25
        if self.point_reduction_mode == "safe" and self.mode_name == "classic/linear":
            x_values = self._remove_same_direction_runs(
                curve,
                x_values,
                protected=protected,
                preserve_below_x=preserve_below_x
            )
        elif self.point_reduction_mode == "aggressive":
            x_values = self._remove_same_direction_runs(
                curve,
                x_values,
                protected=protected,
                preserve_below_x=preserve_below_x,
                slope_rel_tolerance=0.001,
                max_midpoint_error=0.00015
            )
        if self.mode_name == "power" and x_values:
            x_values = [x for x in x_values if x > 1e-12]
            if not x_values:
                x_values = [max_input]
        for x in x_values:
            y = curve(x)
            x_str = f"{x:.{precision}f}".rstrip('0').rstrip('.')
            y_str = f"{y:.{precision}f}".rstrip('0').rstrip('.')
            points.append(f"{x_str}|{y_str}|{POINT_TENSION}")
        return self._collapse_flat_runs_in_output(points)
    def estimate_right_slope(self, args, max_input):
        curve = self._build_curve(args)
        x = max(float(max_input), 0.0)
        h = max(1e-6, x * 1e-4)
        x0 = max(0.0, x - h)
        if abs(x - x0) <= 1e-12:
            return 0.0
        slope = (curve(x) - curve(x0)) / (x - x0)
        if abs(slope) < 1e-9:
            return 0.0
        return slope
    def sample_values(self, args, max_input, precision=6):
        curve = self._build_curve(args)
        max_input = max(float(max_input), 0.0)
        xs = [0.0, max_input * 0.25, max_input * 0.5, max_input * 0.75, max_input]
        out = []
        for x in xs:
            y = curve(x)
            x_str = f"{x:.{precision}f}".rstrip("0").rstrip(".")
            y_str = f"{y:.{precision}f}".rstrip("0").rstrip(".")
            out.append((x_str, y_str))
        return out
    def create_profile(
        self,
        profile_name,
        args,
        point_count=50,
        max_input=100,
        precision=6,
        right_slope_mode="Linear",
        custom_right_slope=0.0
    ):
        points = self.generate_points(
            args=args,
            point_count=point_count,
            max_input=max_input,
            precision=precision
        )
        profile_id = str(uuid.uuid4())
        allow_non_zero_left = self.mode_name in ["power", "lut"]
        left_slope_mode = "Flat" if self.mode_name in ["power", "lut"] else "Linear"
        base_profile = {
            "Id": profile_id,
            "Name": profile_name,
            "Description": None,
            "EditingVerticalCurve": False,
            "XCurve": {
                "AllowNonZeroLeftPoint": allow_non_zero_left,
                "LeftSlopeMode": left_slope_mode,
                "CustomLeftSlope": 0,
                "RightSlopeMode": right_slope_mode,
                "CustomRightSlope": custom_right_slope,
                "Points": points
            },
            "RotationMode": "Both",
            "RotationHorizontal": 0,
            "RotationVertical": 0,
            "AngleSnappingMode": "Legacy",
            "AngleSnappingHorizontal": 0,
            "AngleSnappingVertical": 0,
            "InputSpeedMetric": "Euclidean",
            "InputSmoothingTimeMs": 0,
            "HandAccelScaleOn": "Acceleration",
            "HandAccelDetectionSmoothing": "Normal",
            "HandAccelScale": 0,
            "HandAccelLimit": 2,
            "BiasMode": 0,
            "BiasCurve": {
                "Points": [
                    "0|0|0.5",
                    "90|1|0.5"
                ]
            },
            "OutputScalingDimension": 0,
            "OutputScalingDimensionShape": 0,
            "OutputSmoothingTimeMs": 0,
            "InvertVertical": False,
            "MousePollingRate": "Auto",
            "UseMouseDpi": False,
            "MouseDpi": 800,
            "NormalizeOutput": False,
            "IsNew": False
        }
        return {
            "Id": profile_id,
            "Name": profile_name,
            "Original": base_profile.copy(),
            **base_profile,
            "IsNew": True
        }
    def save_profile(self, profile, filename):
        with open(filename, 'w') as f:
            json.dump(profile, f, indent=2)
        print(f"\n{GREEN}✓ Profile saved to {filename}{RESET}")
def parse_input(label, default):
    while True:
        value = themed_input(label, default)
        if not value:
            value = default
        try:
            parsed = float(Fraction(value)) if "/" in str(value) else float(value)
            if parsed < 0:
                themed_number_error(" Negative values are not allowed.")
                continue
            return parsed
        except Exception:
            themed_number_error(" Invalid input. Enter a non-negative number.")
def parse_int_input(prompt, default, minimum=None, maximum=None):
    while True:
        raw = themed_input(prompt, default)
        if not raw:
            value = int(default)
        else:
            try:
                value = int(raw)
            except Exception:
                themed_number_error("Invalid input. Enter a whole number.")
                continue
        if minimum is not None and value < minimum:
            themed_number_error(f"Value must be >= {minimum}.")
            continue
        if maximum is not None and value > maximum:
            themed_number_error(f"Value must be <= {maximum}.")
            continue
        return value
def estimate_default_max_input(mode, curve_type, cap_mode, args):
    def bounded_tail_cover(cap_x, constant_term, reference_level):
        cap_x = max(float(cap_x), 1e-9)
        reference_level = max(float(reference_level), 1e-9)
        constant_term = abs(float(constant_term))
        rel_eps = 0.01
        x_rel = constant_term / (reference_level * rel_eps)
        lower = cap_x * 2.0
        upper = min(cap_x * 6.0, 600.0)
        return max(lower, min(max(x_rel, lower), upper))
    offset = args.get("input_offset", 0.0)
    base = max(30.0, offset * 20.0)
    if mode == "natural":
        decay = args.get("decay_rate", 0.1)
        base_range = 120.0 + (float(decay) * 400.0)
        offset_boost = float(offset) * 20.0
        max_input = base_range + offset_boost
        return max(base, max(200.0, max_input))
    if mode == "jump":
        cap_x = args.get("cap_x", 15.0)
        return max(base, cap_x * 6.0, 200.0)
    if mode == "synchronous":
        sync_speed = args.get("sync_speed", 5.0)
        return max(base, sync_speed * 20.0, 200.0)
    if mode == "motivity (1.6.1)":
        midpoint = args.get("midpoint", 5.0)
        return max(base, midpoint * 20.0, 200.0)
    if mode == "lut":
        points = parse_lookup_points(args.get("lookup_points", []))
        if points:
            return max(base, points[-1][0] * 2.0, 200.0)
        return max(base, 200.0)
    if mode == "classic/linear":
        cap_x = args.get("cap_x", 0.0)
        if cap_x <= 0:
            cap_x = 15.0
        if cap_mode in ["in", "io"] and cap_x > 0:
            return max(base, cap_x * 2.0, 200.0)
        if cap_mode == "out" and curve_type == "gain":
            accel = args.get("acceleration", 0.0)
            exponent = args.get("exponent", 2.0)
            cap_y = args.get("cap_y", 0.0) - 1.0
            if accel > 0 and exponent != 1 and abs(cap_y) > 1e-12:
                cap_y_abs = abs(cap_y)
                cap_x = (accel * offset + math.pow(cap_y_abs / exponent, 1 / (exponent - 1))) / accel
                accel_raised = math.pow(accel, exponent - 1.0)
                base_at_cap = accel_raised * math.pow(max(cap_x - offset, 1e-12), exponent) / max(cap_x, 1e-12)
                constant = (base_at_cap - cap_y_abs) * cap_x
                tail_cover = bounded_tail_cover(cap_x, constant, cap_y_abs)
                return max(base, cap_x * 2.0, tail_cover, 200.0)
        return max(base, 200.0)
    if mode == "power":
        output_offset = max(float(args.get("output_offset", 0.0)), 0.0)
        cap_x = args.get("cap_x", 0.0)
        cap_y = args.get("cap_y", 0.0)
        scale = float(args.get("scale", 1.0))
        exponent_power = max(float(args.get("exponent_power", 0.05)), 1e-12)

        if cap_mode == "io":
            if curve_type == "legacy":
                output_offset = 0.0
            elif curve_type == "gain" and cap_x > 0:
                scale = PowerCurveBase.scale_from_gain_point(cap_x, cap_y, exponent_power)

        offset_x = math.pow(output_offset / (exponent_power + 1.0), 1.0 / exponent_power) / scale if output_offset > 0 else 0.0
        power_base = max(120.0, offset_x * 2.5)
        if cap_mode in ["in", "io"] and cap_x > 0:
            return min(max(power_base, cap_x * 2.5, 200.0), 1000.0)
        if cap_mode == "out" and curve_type == "gain" and cap_y > 0:
            cap_x = math.pow(cap_y / (exponent_power + 1.0), 1.0 / exponent_power) / scale
            base_at_cap = math.pow(scale * cap_x, exponent_power)
            constant_b = (base_at_cap - cap_y) * cap_x
            tail_cover = bounded_tail_cover(cap_x, constant_b, cap_y)
            return min(max(power_base, cap_x * 2.5, tail_cover, 200.0), 1000.0)
        return min(max(power_base, 200.0), 1000.0)
    return base
def format_setup_value(value):
    if isinstance(value, list):
        return str(len(value))
    if isinstance(value, float):
        return f"{value:.8f}".rstrip("0").rstrip(".")
    return str(value)
def curve_setup_selector(title, options, note=None, width=70):
    selected = 0
    while True:
        clear()
        print(sep(width))
        print(f" {CYAN}{title}{RESET}")
        print(sep(width))
        print()
        for i, option in enumerate(options):
            label, value = option
            prefix = "➤ " if i == selected else "  "
            if value == "generate":
                print()
                color = GREEN if i != selected else CYAN
            else:
                color = CYAN if i == selected else WHITE
            label_colored = color_gui_brackets(label, color)
            print(f"{prefix}{color}{label_colored}{RESET}")
        if note:
            print(f"\n{YELLOW}{note}{RESET}")
        print(f"\n{GRAY}Use ↑ ↓ to move | ENTER to edit/select | ESC to return to menu{RESET}")
        key = msvcrt.getch()
        if key == b'\xe0':
            key = msvcrt.getch()
            if key == b'H':
                selected = (selected - 1) % len(options)
            elif key == b'P':
                selected = (selected + 1) % len(options)
        elif key == b'\r':
            return options[selected][1]
        elif key == b'\x1b':
            return "menu"
def text_input_screen(title, label, current):
    screen_header(title, 70)
    print()
    value = themed_input(label, current)
    return value if value else current
def float_input_screen(title, label, current, minimum=0.0, maximum=None):
    while True:
        screen_header(title, 70)
        print()
        value = themed_input(label, current)
        if not value:
            return current
        try:
            parsed = float(Fraction(value)) if "/" in value else float(value)
            if minimum is not None and parsed < minimum:
                themed_number_error(f" Value must be >= {minimum:g}.")
                input(f"\n{GRAY}Use ENTER to try again{RESET}")
                continue
            if maximum is not None and parsed > maximum:
                themed_number_error(f" Value must be <= {maximum:g}.")
                input(f"\n{GRAY}Use ENTER to try again{RESET}")
                continue
            return parsed
        except Exception:
            themed_number_error(" Invalid input. Enter a valid number (examples: 1.5, 2, 1/3).")
            input(f"\n{GRAY}Use ENTER to try again{RESET}")
def setup_curve_options(mode, profile_name, curve_type, cap_mode, args):
    options = [
        (f"Profile Name [{profile_name}]", "profile_name"),
    ]
    if mode != "lut":
        options.append((f"Mode Type [{curve_type.title()}]", "curve_type"))
    if mode in ["classic/linear", "power"]:
        cap_labels = {"out": "Output", "in": "Input", "io": "Both"}
        options.append((f"Cap Mode [{cap_labels.get(cap_mode, cap_mode)}]", "cap_mode"))
    if mode == "classic/linear":
        if cap_mode != "io":
            options.append((f"Acceleration [{format_setup_value(args['acceleration'])}]", "acceleration"))
        if cap_mode in ["in", "io"]:
            options.append((f"Cap Input [{format_setup_value(args['cap_x'])}]", "cap_x"))
        if cap_mode in ["out", "io"]:
            options.append((f"Cap Output [{format_setup_value(args['cap_y'])}]", "cap_y"))
        options.extend([
            (f"Input Offset [{format_setup_value(args['input_offset'])}]", "input_offset"),
            (f"Power / Exponent [{format_setup_value(args['exponent'])}]", "exponent"),
        ])
    elif mode == "jump":
        options.extend([
            (f"Smooth [{format_setup_value(args['smooth'])}]", "smooth"),
            (f"Input [{format_setup_value(args['cap_x'])}]", "cap_x"),
            (f"Output [{format_setup_value(args['cap_y'])}]", "cap_y"),
        ])
    elif mode == "natural":
        options.extend([
            (f"Decay Rate [{format_setup_value(args['decay_rate'])}]", "decay_rate"),
            (f"Input Offset [{format_setup_value(args['input_offset'])}]", "input_offset"),
            (f"Limit [{format_setup_value(args['limit'])}]", "limit"),
        ])
    elif mode == "synchronous":
        options.extend([
            (f"Gamma [{format_setup_value(args['gamma'])}]", "gamma"),
            (f"Smooth [{format_setup_value(args['smooth'])}]", "smooth"),
            (f"Motivity [{format_setup_value(args['motivity'])}]", "motivity"),
            (f"Sync Speed [{format_setup_value(args['sync_speed'])}]", "sync_speed"),
        ])
    elif mode == "motivity (1.6.1)":
        options.extend([
            (f"Growth Rate [{format_setup_value(args['growth_rate'])}]", "growth_rate"),
            (f"Motivity [{format_setup_value(args['motivity'])}]", "motivity"),
            (f"Midpoint [{format_setup_value(args['midpoint'])}]", "midpoint"),
        ])
    elif mode == "lut":
        points = parse_lookup_points(args.get("lookup_points", []))
        lut_mode = "Velocity" if bool(args.get("lut_velocity", True)) else "Sensitivity"
        options.append((f"Lookup Mode [{lut_mode}]", "lut_mode"))
        options.append((f"Lookup Points [{len(points)}]", "lookup_points"))
    elif mode == "power":
        if cap_mode != "io":
            options.append((f"Scale [{format_setup_value(args['scale'])}]", "scale"))
        if cap_mode in ["in", "io"]:
            options.append((f"Cap Input [{format_setup_value(args['cap_x'])}]", "cap_x"))
        if cap_mode in ["out", "io"]:
            options.append((f"Cap Output [{format_setup_value(args['cap_y'])}]", "cap_y"))
        options.extend([
            (f"Exponent [{format_setup_value(args['exponent_power'])}]", "exponent_power"),
            (f"Output Offset [{format_setup_value(args['output_offset'])}]", "output_offset"),
        ])
    options.append(("Generate", "generate"))
    return options
def run_curve_setup_menu(mode, last):
    profile_name = str(last.get("profile_name", "New Profile"))
    curve_type = str(last.get("curve_type", "gain")).lower()
    if curve_type not in ["legacy", "gain"]:
        curve_type = "gain"
    if mode == "lut":
        curve_type = "legacy"
    cap_mode = str(last.get("cap_mode", "out")).lower()
    if cap_mode not in ["out", "in", "io"]:
        cap_mode = "out"
    args = rawaccel_default_args(mode, cap_mode)
    last_args = last.get("args", {}) if isinstance(last.get("args"), dict) else {}
    for key in list(args.keys()):
        if key in last_args:
            try:
                if key == "lookup_points":
                    args[key] = parse_lookup_points(last_args[key])
                elif key == "lut_velocity":
                    args[key] = bool(last_args[key])
                else:
                    min_value, max_value = get_arg_limits(key)
                    args[key] = safe_float(last_args[key], args[key], min_value, max_value)
            except Exception:
                pass
    while True:
        choice = curve_setup_selector(
            f"{mode.upper()} CURVE CONFIGURATION",
            setup_curve_options(mode, profile_name, curve_type, cap_mode, args),
            note="Edit values, then select Generate."
        )
        if choice == "menu":
            return None
        if choice == "generate":
            return profile_name, curve_type, cap_mode, args
        if choice == "profile_name":
            profile_name = text_input_screen("PROFILE NAME", "Name", profile_name)
            continue
        if choice == "curve_type":
            if mode == "lut":
                continue
            picked = value_choice_selector(
                "MODE TYPE",
                [("Legacy", "legacy"), ("Gain", "gain")],
                current=curve_type,
                width=70
            )
            if picked:
                curve_type = picked
            continue
        if choice == "lut_mode":
            picked = value_choice_selector(
                "LOOKUP MODE",
                [("Sensitivity", "sensitivity"), ("Velocity", "velocity")],
                current="velocity" if bool(args.get("lut_velocity", True)) else "sensitivity",
                width=70
            )
            if picked:
                args["lut_velocity"] = (picked == "velocity")
            continue
        if choice == "cap_mode":
            picked = value_choice_selector(
                "CAP MODE",
                [("Output", "out"), ("Input", "in"), ("Both", "io")],
                current=cap_mode,
                width=70
            )
            if picked:
                old_args = dict(args)
                cap_mode = picked
                args = rawaccel_default_args(mode, cap_mode)
                for key, value in old_args.items():
                    if key in args:
                        args[key] = value
                if mode == "classic/linear" and cap_mode == "io":
                    args["acceleration"] = 0.0
                if mode == "power" and cap_mode == "io":
                    args["scale"] = float(args.get("scale", 1.0))
            continue
        if choice == "lookup_points":
            current_points = parse_lookup_points(args.get("lookup_points", []))
            screen_header("LOOKUP POINTS", 70)
            print()
            print(f"{BLUE}Format:{RESET} x,y;x,y;x,y;")
            print(f"{GRAY}Example:{RESET} 1.505035,0.85549892;4.375,3.30972978;13.51,15.17478447;140,354.7026875;")
            print(f"{GRAY}Current points:{RESET} {len(current_points)}")
            default_points = "".join(f"{x},{y};" for x, y in current_points)
            raw = themed_input("Points", default_points)
            parsed = parse_lookup_points(raw)
            if len(parsed) < 2:
                themed_number_error(" Need at least two valid x,y pairs.")
                input(f"\n{GRAY}Use ENTER to continue{RESET}")
                continue
            args["lookup_points"] = parsed
            continue
        if choice in args:
            labels = {
                "acceleration": "Acceleration",
                "cap_x": "Cap Input",
                "cap_y": "Cap Output",
                "input_offset": "Input Offset",
                "exponent": "Power / Exponent",
                "smooth": "Smooth",
                "decay_rate": "Decay Rate",
                "limit": "Limit",
                "gamma": "Gamma",
                "growth_rate": "Growth Rate",
                "motivity": "Motivity",
                "sync_speed": "Sync Speed",
                "midpoint": "Midpoint",
                "scale": "Scale",
                "exponent_power": "Exponent",
                "output_offset": "Output Offset",
            }
            label = labels.get(choice, choice)
            minimum, maximum = get_arg_limits(choice)
            value = float_input_screen(label.upper(), label, args[choice], minimum=minimum, maximum=maximum)
            args[choice] = value
            continue
def run_imported_curve_setup_menu(mode, profile_name, curve_type, cap_mode, args):
    temp_last = {
        "profile_name": profile_name,
        "curve_type": curve_type,
        "cap_mode": cap_mode,
        "args": args
    }
    return run_curve_setup_menu(mode, temp_last)
def main():
    configure_console()
    os.system("title RAWACCEL → CC4 CONVERTER")
    clean_invalid_rawaccel_path()
    if not customcurve_installed_check():
        customcurve_not_installed_screen()
        return
    while True:
        last = load_last_config()
        mode = mode_selector()
        if mode is None:
            return
        if mode == "advanced settings":
            advanced_settings_menu()
            continue
        if mode == "import from settings.json":
            settings_path = get_rawaccel_settings_path(last)
            if not settings_path:
                settings_path = pick_settings_file()
            if not settings_path:
                continue
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    raw_settings = json.load(f)
            except json.JSONDecodeError:
                import_error_screen("INVALID JSON FILE", "The selected file is not valid JSON")
                continue
            except Exception:
                import_error_screen("FILE LOAD ERROR", "The selected file could not be opened")
                continue
            if not isinstance(raw_settings, dict):
                import_error_screen("INCORRECT CONTENTS", "The selected file does not contain valid RawAccel settings")
                continue
            profiles = raw_settings.get("profiles", [])
            if not isinstance(profiles, list) or not profiles:
                import_error_screen("PROFILES NOT FOUND", "No profiles were found in settings.json")
                continue
            invalid_contents_found = False
            unsupported_mode_found = False
            for profile_obj in profiles:
                if not isinstance(profile_obj, dict):
                    invalid_contents_found = True
                    break
                accel_params = get_profile_accel_params(profile_obj)
                if not isinstance(accel_params, dict):
                    invalid_contents_found = True
                    break
                mapped_mode = map_rawaccel_mode(accel_params.get("mode", "noaccel"))
                if mapped_mode in ["noaccel"] or mapped_mode not in ["classic/linear", "jump", "natural", "synchronous", "motivity (1.6.1)", "power", "lut"]:
                    unsupported_mode_found = True
                    break
                if mapped_mode == "lut":
                    lut_points = extract_lookup_points(accel_params)
                    if len(lut_points) < 2:
                        invalid_contents_found = True
                        break
            if invalid_contents_found:
                import_error_screen("INCORRECT CONTENTS", "The selected settings.json has missing or incorrect profile data")
                continue
            if unsupported_mode_found:
                unsupported_mode_screen()
                continue
            import_profile_name = str(last.get("profile_name", "Imported Profile"))
            point_count = get_output_points(last)
            point_reduction_mode = get_output_reduction(last)
            precision = get_output_precision(last)
            clear()
            print(sep(70))
            print(f" {CYAN}IMPORTING RAWACCEL SETTINGS{RESET}")
            print(sep(70))
            print(f"\n{BLUE}Source:{RESET} {settings_path}")
            print(f"{BLUE}Profiles found:{RESET} {len(profiles)}")
            print(f"\n{YELLOW}Generating CC4 profile files...{RESET}\n")
            saved_count = 0
            skipped_count = 0
            generated_profiles = []
            import_failed = False
            for profile_obj in profiles:
                try:
                    raw_profile_name = str(profile_obj.get("name", "profile")).strip() or "profile"
                    accel_params = get_profile_accel_params(profile_obj) or {}
                    mapped_mode = map_rawaccel_mode(accel_params.get("mode", "noaccel"))
                    gain_key = accel_params.get("Gain / Velocity", accel_params.get("Gain/Velocity", True))
                    curve_type = "gain" if parse_bool(gain_key, True) else "legacy"
                    cap_mode = map_rawaccel_cap_mode(accel_params.get("Cap mode", "output"))
                    args = sanitize_curve_args(build_args_from_rawaccel_params(mapped_mode, cap_mode, accel_params))
                    if mapped_mode == "lut":
                        args["lut_velocity"] = parse_bool(gain_key, args.get("lut_velocity", True))
                        curve_type = "legacy"
                    if len(profiles) == 1:
                        output_profile_name = import_profile_name
                    else:
                        output_profile_name = f"{import_profile_name} - {raw_profile_name}"
                    setup_result = run_imported_curve_setup_menu(
                        mapped_mode,
                        output_profile_name,
                        curve_type,
                        cap_mode,
                        args
                    )
                    if setup_result is None:
                        import_failed = True
                        break
                    output_profile_name, curve_type, cap_mode, args = setup_result
                    args = sanitize_curve_args(args)
                    max_input = estimate_default_max_input(mapped_mode, curve_type, cap_mode, args)
                    generator = CurveGenerator(
                        mode_name=mapped_mode,
                        curve_type=curve_type,
                        cap_mode=cap_mode,
                        point_reduction_mode=point_reduction_mode
                    )
                    custom_right_slope = generator.estimate_right_slope(args, max_input)
                    profile = generator.create_profile(
                        output_profile_name,
                        args,
                        point_count=point_count,
                        max_input=max_input,
                        precision=precision,
                        right_slope_mode="Custom",
                        custom_right_slope=custom_right_slope
                    )
                    generated_profiles.append((generator, profile, output_profile_name))
                    print(f"{GREEN} ✓ {raw_profile_name}: generated profile data{RESET}")
                    saved_count += 1
                except Exception:
                    import_failed = True
                    break
            if import_failed:
                continue
            print(f"\n{GREEN}GENERATION COMPLETE{RESET}")
            print(f"{GREEN}Generated: {saved_count}{RESET} | {YELLOW}Skipped: {skipped_count}{RESET}")
            result_type, result_value = finish_generated_output(generated_profiles)
            if result_type == "menu":
                continue
            if result_type == "file":
                saved_files, first_filename = result_value
            save_last_config({
                "profile_name": import_profile_name,
                "mode": "import from settings.json",
                "curve_type": str(last.get("curve_type", "gain")),
                "cap_mode": str(last.get("cap_mode", "out")),
                "args": last.get("args", {}),
                "point_count": get_output_points(last),
                "point_reduction_mode": get_output_reduction(last),
                "precision": get_output_precision(last),
                "filename": str(last.get("filename", "profile.cc4")),
                "rawaccel_path": str(last.get("rawaccel_path", ""))
            })
            continue
        mode = map_rawaccel_mode(mode)
        if mode not in ["natural", "classic/linear", "jump", "synchronous", "motivity (1.6.1)", "power", "lut"]:
            continue
        setup_result = run_curve_setup_menu(mode, last)
        if setup_result is None:
            continue
        profile_name, curve_type, cap_mode, args = setup_result
        args = sanitize_curve_args(args)
        point_count = get_output_points(last)
        point_reduction_mode = get_output_reduction(last)
        precision = get_output_precision(last)
        max_input = estimate_default_max_input(mode, curve_type, cap_mode, args)
        screen_header("GENERATING CURVE", 70)
        print(f"\n{BLUE}Auto Max Input:{RESET} {max_input:.6f}".rstrip("0").rstrip("."))
        print(f"{YELLOW}Building CC4 curve profile...{RESET}")
        generator = CurveGenerator(
            mode_name=mode,
            curve_type=curve_type,
            cap_mode=cap_mode,
            point_reduction_mode=point_reduction_mode
        )
        custom_right_slope = generator.estimate_right_slope(args, max_input)
        profile = generator.create_profile(
            profile_name,
            args,
            point_count=point_count,
            max_input=max_input,
            precision=precision,
            right_slope_mode="Custom",
            custom_right_slope=custom_right_slope
        )
        print(f"\n{GREEN}Generated {len(profile['XCurve']['Points'])} points{RESET}\n")
        for p in profile['XCurve']['Points'][:10]:
            print(f" {WHITE}{p}{RESET}")
        samples = generator.sample_values(args, max_input, precision=precision)
        print(f"\n{BLUE}Reference samples (x -> y):{RESET}")
        for x_str, y_str in samples:
            print(f" {CYAN}{x_str}{RESET} -> {GREEN}{y_str}{RESET}")
        result_type, result_value = finish_generated_output([(generator, profile, profile_name)])
        if result_type == "app":
            print(f"\n{GREEN}✓ Loaded directly in CustomCurve.{RESET}")
            print(f"{BLUE}Path:{RESET} {result_value}")
            filename = str(last.get("filename", "profile.cc4"))
        elif result_type == "file":
            saved_files, first_filename = result_value
            filename = first_filename or normalize_cc4_filename(profile_name)
            print(f"\n{GREEN}✓ Saved {saved_files} file(s).{RESET}")
        else:
            filename = str(last.get("filename", "profile.cc4"))
            continue
        save_last_config({
            "profile_name": profile_name,
            "mode": mode,
            "curve_type": curve_type,
            "cap_mode": cap_mode,
            "args": args,
            "point_count": point_count,
            "point_reduction_mode": point_reduction_mode,
            "precision": precision,
            "filename": filename
        })
        continue
if __name__ == "__main__":
    main()
