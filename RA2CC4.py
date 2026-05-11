import json
import ast
import math
import heapq
import uuid
import os
import msvcrt
import ctypes
import subprocess
import time
import tkinter as tk
import textwrap
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
MAX_FLOAT = 1e300
MAX_EXPONENT = 700.0
MIN_EXPONENT = -745.0
RAWACCEL_POSITIVE_EPSILON = 1e-12
RAWACCEL_MOTIVITY_MIN = 1.0 + RAWACCEL_POSITIVE_EPSILON
RAWACCEL_CLASSIC_EXPONENT_MIN = 1.0 + RAWACCEL_POSITIVE_EPSILON
RAWACCEL_LUT_POINTS_CAPACITY = 257
def safe_exp(value):
    value = float(value)
    if value >= MAX_EXPONENT:
        return MAX_FLOAT
    if value <= MIN_EXPONENT:
        return 0.0
    return math.exp(value)
def safe_pow(base, exponent, fallback=MAX_FLOAT):
    try:
        value = math.pow(float(base), float(exponent))
    except (OverflowError, ValueError, ZeroDivisionError):
        return fallback
    if not math.isfinite(value):
        return fallback
    return value
def finite_value(value, fallback=0.0):
    try:
        value = float(value)
    except Exception:
        return fallback
    return value if math.isfinite(value) else fallback
def safe_divide(numerator, denominator, fallback=MAX_FLOAT):
    try:
        denominator = float(denominator)
        numerator = float(numerator)
    except Exception:
        return fallback
    if abs(denominator) <= 1e-300:
        if abs(numerator) <= 1e-300:
            return 0.0
        return math.copysign(fallback, numerator)
    value = numerator / denominator
    if not math.isfinite(value):
        return math.copysign(fallback, value if value else numerator)
    return max(-fallback, min(fallback, value))
ALLOWED_NUMERIC_CONSTANTS = {
    "e": math.e,
    "pi": math.pi,
    "tau": math.tau,
}
ALLOWED_NUMERIC_FUNCTIONS = {
    "abs": abs,
    "min": min,
    "max": max,
}
for _math_name in [
    "acos",
    "asin",
    "atan",
    "atan2",
    "ceil",
    "copysign",
    "cos",
    "cosh",
    "degrees",
    "exp",
    "fabs",
    "floor",
    "fmod",
    "hypot",
    "log",
    "log10",
    "log2",
    "pow",
    "radians",
    "remainder",
    "sin",
    "sinh",
    "sqrt",
    "tan",
    "tanh",
    "trunc",
]:
    if hasattr(math, _math_name):
        ALLOWED_NUMERIC_FUNCTIONS[_math_name] = getattr(math, _math_name)
if hasattr(math, "cbrt"):
    ALLOWED_NUMERIC_FUNCTIONS["cbrt"] = math.cbrt
def coerce_expression_number(value):
    try:
        out = float(value)
    except Exception as exc:
        raise ValueError("Expression did not produce a number.") from exc
    if not math.isfinite(out) or abs(out) > MAX_FLOAT:
        raise ValueError("Expression result is not finite.")
    return out
def resolve_expression_function(node):
    if isinstance(node, ast.Name) and node.id in ALLOWED_NUMERIC_FUNCTIONS:
        return ALLOWED_NUMERIC_FUNCTIONS[node.id]
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "math"
        and node.attr in ALLOWED_NUMERIC_FUNCTIONS
    ):
        return ALLOWED_NUMERIC_FUNCTIONS[node.attr]
    raise ValueError("Unsupported function.")
def eval_numeric_expression_node(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError("Only numeric constants are allowed.")
        return coerce_expression_number(node.value)
    if isinstance(node, ast.UnaryOp):
        operand = eval_numeric_expression_node(node.operand)
        if isinstance(node.op, ast.UAdd):
            return operand
        if isinstance(node.op, ast.USub):
            return coerce_expression_number(-operand)
        raise ValueError("Unsupported unary operator.")
    if isinstance(node, ast.BinOp):
        left = eval_numeric_expression_node(node.left)
        right = eval_numeric_expression_node(node.right)
        try:
            if isinstance(node.op, ast.Add):
                result = left + right
            elif isinstance(node.op, ast.Sub):
                result = left - right
            elif isinstance(node.op, ast.Mult):
                result = left * right
            elif isinstance(node.op, ast.Div):
                result = left / right
            elif isinstance(node.op, ast.Pow):
                result = left ** right
            else:
                raise ValueError("Unsupported arithmetic operator.")
        except (OverflowError, ValueError, ZeroDivisionError) as exc:
            raise ValueError("Invalid arithmetic expression.") from exc
        return coerce_expression_number(result)
    if isinstance(node, ast.Name):
        if node.id in ALLOWED_NUMERIC_CONSTANTS:
            return ALLOWED_NUMERIC_CONSTANTS[node.id]
        raise ValueError("Unsupported name.")
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "math"
        and node.attr in ALLOWED_NUMERIC_CONSTANTS
    ):
        return ALLOWED_NUMERIC_CONSTANTS[node.attr]
    if isinstance(node, ast.Call):
        if node.keywords:
            raise ValueError("Keyword arguments are not supported.")
        function = resolve_expression_function(node.func)
        args = [eval_numeric_expression_node(arg) for arg in node.args]
        try:
            return coerce_expression_number(function(*args))
        except (OverflowError, TypeError, ValueError, ZeroDivisionError) as exc:
            raise ValueError("Invalid function call.") from exc
    raise ValueError("Unsupported expression.")
def parse_numeric_expression(value):
    if isinstance(value, bool):
        raise ValueError("Boolean values are not numbers.")
    if isinstance(value, (int, float, Fraction)):
        return coerce_expression_number(value)
    text = str(value).strip()
    if not text:
        raise ValueError("Empty number.")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise ValueError("Invalid number expression.") from exc
    if sum(1 for _ in ast.walk(tree)) > 80:
        raise ValueError("Expression is too complex.")
    return eval_numeric_expression_node(tree.body)
def sep(width=60):
    return f"{GRAY}{'=' * width}{RESET}"
def color_gui_brackets(text, active_color=RESET):
    return str(text).replace("[", f"{GRAY}[").replace("]", f"]{active_color}")
def menu_footer(esc_text="go back"):
    print(f"\n{GRAY}Use UP/DOWN to move | ENTER to select | ESC to {esc_text}{RESET}")
def main_menu_footer():
    print(f"\n{GRAY}Use UP/DOWN to move | ENTER to select | Q or ESC to quit{RESET}")
def pause_footer(action="return to menu"):
    print(f"\n{GRAY}Use ENTER or ESC to {action}{RESET}")
POINT_TENSION = "0.5"
CONFIG_KEYS = (
    "profile_name",
    "mode",
    "curve_type",
    "cap_mode",
    "args",
    "filename",
    "rawaccel_path",
    "customcurve_path",
    "point_count",
    "precision",
    "point_reduction_mode",
    "smooth_transitions",
)
APPDATA_DIR = os.getenv("APPDATA")
if APPDATA_DIR:
    CONFIG_DIR = os.path.join(APPDATA_DIR, "CurveGen")
else:
    CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
LEGACY_CONFIG_PATHS = [
    os.path.join(os.getcwd(), "config.json"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"),
]
POINT_OPTIONS = [32, 64, 96, 128, 160, 192, 256, 320, 384, 512, 640, 768, 1024, 2048, 4096]
PRECISION_OPTIONS = list(range(1, 11))
REDUCTION_OPTIONS = ["optimal", "normal", "aggressive"]
SMOOTH_TRANSITION_OPTIONS = ["off", "on"]
SMOOTH_TRANSITION_STRENGTHS = {
    "off": 0.0,
    "on": 1.0,
}
RECOMMENDED_POINTS = 128
RECOMMENDED_PRECISION = 6
RECOMMENDED_REDUCTION = "optimal"
RECOMMENDED_SMOOTH_TRANSITIONS = "off"
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
def menu_pointer(active):
    return "➤ " if active else "  "
def print_detail_line(label, value, color=BLUE, width=70):
    label = str(label)
    value = str(value)
    value_width = max(24, width - len(label) - 5)
    chunks = textwrap.wrap(value, width=value_width, break_long_words=False, break_on_hyphens=False) or [""]
    print(f" {color}{label}:{RESET} {chunks[0]}")
    indent = " " * (len(label) + 3)
    for chunk in chunks[1:]:
        print(f"{indent}{chunk}")
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
        prefix = menu_pointer(i == selected)
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
            prefix = menu_pointer(i == selected)
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
            prefix = menu_pointer(i == selected)
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
            prefix = menu_pointer(i == selected)
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
def detail_action_screen(title, lines=None, options=None, title_color=CYAN, width=70, esc_text="return to menu"):
    lines = lines or []
    options = options or [("Return to menu", "menu")]
    selected = 0
    while True:
        clear()
        print(sep(width))
        print(f" {title_color}{title}{RESET}")
        print(sep(width))
        if lines:
            print()
            for line in lines:
                if isinstance(line, tuple) and len(line) >= 2:
                    label, value = line[0], line[1]
                    color = line[2] if len(line) >= 3 else BLUE
                    print_detail_line(label, value, color=color, width=width)
                else:
                    print(f" {line}")
        print()
        for i, option in enumerate(options):
            label, value = option
            prefix = menu_pointer(i == selected)
            color = CYAN if i == selected else WHITE
            print(f"{prefix}{color}{label}{RESET}")
        menu_footer(esc_text)
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
    detail_action_screen(
        title,
        [("Problem", message, RED)],
        [("Return to menu", "menu")],
        title_color=RED
    )
def unsupported_mode_screen():
    import_error_screen("UNSUPPORTED MODE", "Unsupported mode detected")
def screen_header(title, width=70):
    clear()
    print(sep(width))
    print(f" {CYAN}{title}{RESET}")
    print(sep(width))
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
        merged = normalize_config_values(merged)
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
    customcurve_path = str(cleaned.get("customcurve_path", "")).strip()
    normalized_customcurve_path = os.path.abspath(customcurve_path) if customcurve_path else ""
    changed = False
    if original_path:
        if validate_rawaccel_path(normalized_path):
            if normalized_path != original_path:
                cleaned["rawaccel_path"] = normalized_path
                changed = True
        else:
            cleaned["rawaccel_path"] = ""
            changed = True
    if customcurve_path:
        if validate_customcurve_path(normalized_customcurve_path):
            if normalized_customcurve_path != customcurve_path:
                cleaned["customcurve_path"] = normalized_customcurve_path
                changed = True
        else:
            cleaned["customcurve_path"] = ""
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
    if value == "safe":
        value = "normal"
    return value if value in REDUCTION_OPTIONS else RECOMMENDED_REDUCTION
def format_reduction_label(value):
    value = str(value or "").strip().lower()
    return value[:1].upper() + value[1:] if value else ""
def normalize_smooth_transition_mode(value):
    if isinstance(value, bool):
        return "on" if value else "off"
    if isinstance(value, (int, float)):
        return "on" if value != 0 else "off"
    text = str(value or "").strip().lower()
    if text in ["true", "yes", "y", "on", "1", "natural", "strong"]:
        return "on"
    if text in ["false", "no", "n", "0"]:
        return "off"
    return text if text in SMOOTH_TRANSITION_OPTIONS else RECOMMENDED_SMOOTH_TRANSITIONS
def get_smooth_transition_mode(config=None):
    data = config if isinstance(config, dict) else load_last_config()
    return normalize_smooth_transition_mode(data.get("smooth_transitions", RECOMMENDED_SMOOTH_TRANSITIONS))
def get_smooth_transitions(config=None):
    return get_smooth_transition_mode(config) != "off"
def get_smooth_transition_strength(config=None):
    return SMOOTH_TRANSITION_STRENGTHS.get(get_smooth_transition_mode(config), 0.0)
def format_smooth_transition_label(value):
    mode = normalize_smooth_transition_mode(value)
    return mode[:1].upper() + mode[1:] if mode else "Off"
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
def validate_customcurve_path(path):
    if not path:
        return False
    file_path = os.path.abspath(path)
    return (
        os.path.isfile(file_path)
        and os.path.basename(file_path).lower() == "customcurve.exe"
    )
def get_customcurve_exe_from_folder(folder):
    if not folder:
        return None
    exe_path = os.path.join(os.path.abspath(folder), "CustomCurve.exe")
    return exe_path if validate_customcurve_path(exe_path) else None
def resolve_customcurve_exe_path(path):
    if validate_customcurve_path(path):
        return os.path.abspath(path)
    if path and os.path.isdir(path):
        return get_customcurve_exe_from_folder(path)
    return None
def get_saved_customcurve_path(config=None):
    data = config if isinstance(config, dict) else load_last_config()
    path = str(data.get("customcurve_path", "")).strip()
    return resolve_customcurve_exe_path(path)
def get_saved_customcurve_folder(config=None):
    exe_path = get_saved_customcurve_path(config)
    return os.path.dirname(exe_path) if exe_path else None
def pick_customcurve_folder():
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(title="Select CustomCurve folder")
        root.destroy()
        return path or None
    except Exception:
        return None
def advanced_settings_options(config):
    rawaccel_path = get_saved_rawaccel_path(config)
    rawaccel_display = rawaccel_path if rawaccel_path else "Not set"
    customcurve_folder = get_saved_customcurve_folder(config)
    customcurve_display = customcurve_folder if customcurve_folder else "Not set"
    return [
        (f"Set RawAccel Path [{rawaccel_display}]", "set_rawaccel_path"),
        (f"Set CustomCurve Path [{customcurve_display}]", "set_customcurve_path"),
        (f"Set Points [{get_output_points(config)}]", "set_points"),
        (f"Set Precision [{get_output_precision(config)}]", "set_precision"),
        (f"Set Point Reduction Mode [{format_reduction_label(get_output_reduction(config))}]", "set_point_reduction"),
        (f"Smooth Transitions [{format_smooth_transition_label(get_smooth_transition_mode(config))}]", "set_smooth_transitions"),
    ]
def advanced_settings_menu():
    while True:
        last = clean_invalid_rawaccel_path()
        choice = themed_choice_selector(
            "ADVANCED SETTINGS",
            advanced_settings_options(last),
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
        if choice == "set_customcurve_path":
            folder = pick_customcurve_folder()
            if not folder:
                continue
            exe_path = get_customcurve_exe_from_folder(folder)
            if not exe_path:
                import_error_screen("INVALID CUSTOMCURVE PATH", "Selected folder must contain CustomCurve.exe.")
                continue
            last["customcurve_path"] = os.path.abspath(exe_path)
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
                [("Optimal", "optimal"), ("Normal", "normal"), ("Aggressive", "aggressive")],
                current=get_output_reduction(last),
                recommended=RECOMMENDED_REDUCTION,
                width=70,
                on_select=save_reduction
            )
            continue
        if choice == "set_smooth_transitions":
            def save_smooth_transitions(value):
                data = clean_invalid_rawaccel_path()
                data["smooth_transitions"] = value
                save_last_config(data)
            value_choice_selector(
                "SMOOTH TRANSITIONS",
                [("Off", "off"), ("On", "on")],
                current=get_smooth_transition_mode(last),
                recommended="off",
                width=70,
                on_select=save_smooth_transitions
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
    print(f"\n{GREEN}[OK] Profile data loaded successfully.{RESET}")
    if opened:
        print(f"{GREEN}[OK] CustomCurve was reopened automatically.{RESET}")
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
            exe_path = get_customcurve_exe_path() or get_saved_customcurve_path(clean_invalid_rawaccel_path())
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
def direct_load_success_screen(path, count, exe_path=None):
    lines = [
        ("Status", f"Loaded {count} profile(s) into CustomCurve profiles.json.", GREEN),
        ("Profiles", path, BLUE),
    ]
    options = [("Return to menu", "menu")]
    if exe_path:
        lines.append(("App", exe_path, BLUE))
        options.insert(0, ("Start CustomCurve", "start"))
    while True:
        choice = detail_action_screen(
            "LOADED DIRECTLY IN CUSTOMCURVE",
            lines,
            options,
            title_color=GREEN
        )
        if choice == "start":
            opened = open_customcurve(exe_path)
            lines = [
                ("Status", "CustomCurve was started." if opened else "CustomCurve could not be started.", GREEN if opened else YELLOW),
                ("Profiles", path, BLUE),
                ("App", exe_path, BLUE),
            ]
            options = [("Return to menu", "menu")]
            continue
        return
def save_file_success_screen(saved_count, first_filename):
    lines = [("Status", f"Saved {saved_count} file(s).", GREEN)]
    if first_filename:
        lines.append(("Location", first_filename, BLUE))
    detail_action_screen(
        "SAVED AS FILE",
        lines,
        [("Return to menu", "menu")],
        title_color=GREEN
    )
def direct_load_error_screen(title, message):
    return detail_action_screen(
        title,
        [("Problem", message, RED)],
        [
            ("Save it as a file instead", "file"),
            ("Return to menu", "menu"),
        ],
        title_color=RED,
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
    detail_action_screen(
        "CUSTOMCURVE NOT FOUND",
        [
            ("Problem", "CustomCurve was not found or the app data folder is empty.", RED),
            ("Expected folder", get_customcurve_folder_path(), BLUE),
        ],
        [("Close", "menu")],
        title_color=RED,
        esc_text="close"
    )
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
                    launch_path = get_saved_customcurve_path(clean_invalid_rawaccel_path())
                    direct_load_success_screen(path, len(profiles), launch_path)
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
def safe_float(value, fallback=0.0, minimum=0.0, maximum=None):
    try:
        out = parse_numeric_expression(value)
    except Exception:
        out = float(fallback)
    if minimum is not None and out < minimum:
        out = minimum
    if maximum is not None and out > maximum:
        out = maximum
    return out
ARG_LIMITS = {
    "motivity": (RAWACCEL_MOTIVITY_MIN, None),
    "smooth": (0.0, 1.0),
    "sync_speed": (RAWACCEL_POSITIVE_EPSILON, None),
    "midpoint": (1e-6, None),
    "scale": (RAWACCEL_POSITIVE_EPSILON, None),
    "exponent_power": (RAWACCEL_POSITIVE_EPSILON, None),
    "growth_rate": (RAWACCEL_POSITIVE_EPSILON, None),
    "gamma": (RAWACCEL_POSITIVE_EPSILON, None),
    "input_offset": (0.0, None),
    "output_offset": (0.0, None),
    "acceleration": (RAWACCEL_POSITIVE_EPSILON, None),
    "decay_rate": (RAWACCEL_POSITIVE_EPSILON, None),
    "limit": (RAWACCEL_POSITIVE_EPSILON, None),
    "exponent": (RAWACCEL_CLASSIC_EXPONENT_MIN, None),
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
def sanitize_stored_args(args):
    if not isinstance(args, dict):
        return {}
    cleaned = {}
    for key, value in args.items():
        if key == "lookup_points":
            cleaned[key] = parse_lookup_points(value)
        elif key == "lut_velocity":
            cleaned[key] = parse_bool(value, True)
        elif key in ARG_LIMITS:
            min_value, max_value = get_arg_limits(key)
            cleaned[key] = safe_float(value, 0.0, min_value, max_value)
    return cleaned
def normalize_config_values(data):
    if not isinstance(data, dict):
        data = {}
    cleaned = {}
    if "profile_name" in data:
        cleaned["profile_name"] = str(data.get("profile_name") or "New Profile")
    if "mode" in data:
        mode = str(data.get("mode", "")).strip().lower()
        if mode == "import from settings.json":
            cleaned["mode"] = mode
        else:
            mapped_mode = map_rawaccel_mode(mode)
            if mapped_mode in ["natural", "classic/linear", "jump", "synchronous", "motivity (1.6.1)", "power", "lut"]:
                cleaned["mode"] = mapped_mode
    if "curve_type" in data:
        curve_type = str(data.get("curve_type", "gain")).strip().lower()
        if curve_type in ["legacy", "gain"]:
            cleaned["curve_type"] = curve_type
    if "cap_mode" in data:
        cap_mode = str(data.get("cap_mode", "out")).strip().lower()
        if cap_mode in ["out", "in", "io"]:
            cleaned["cap_mode"] = cap_mode
    if "args" in data:
        cleaned["args"] = sanitize_stored_args(data.get("args"))
    if "filename" in data:
        cleaned["filename"] = str(data.get("filename") or "profile.cc4")
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
    if reduction == "safe":
        reduction = "normal"
    cleaned["point_reduction_mode"] = reduction if reduction in REDUCTION_OPTIONS else RECOMMENDED_REDUCTION
    cleaned["smooth_transitions"] = normalize_smooth_transition_mode(data.get("smooth_transitions", RECOMMENDED_SMOOTH_TRANSITIONS))
    cleaned["rawaccel_path"] = str(data.get("rawaccel_path", "")).strip()
    customcurve_path = str(data.get("customcurve_path", "")).strip()
    cleaned["customcurve_path"] = resolve_customcurve_exe_path(customcurve_path) or ""
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
            return parse_numeric_expression(v)
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
    return dedup[:RAWACCEL_LUT_POINTS_CAPACITY]
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
        self.offset = float(input_offset)
        self.decay_rate = float(decay_rate)
        self.limit = float(limit) - 1
        self._is_flat_limit = abs(self.limit) <= 1e-10 or abs(self.decay_rate) <= 1e-12
        self.accel = self.decay_rate / abs(self.limit) if not self._is_flat_limit else 0.0
    def flat_segments(self):
        if self._is_flat_limit:
            return [(0.0, float("inf"), 1.0)]
        return [(0.0, self.offset, 1.0)] if self.offset > 0.0 else []
class NaturalCurveLegacy(NaturalCurveBase):
    def __call__(self, x):
        if x <= self.offset:
            return 1.0
        if self._is_flat_limit:
            return 1.0
        offset_x = self.offset - x
        decay = safe_exp(self.accel * offset_x)
        return self.limit * (1 - (self.offset - decay * offset_x) / x) + 1
class NaturalCurveGain(NaturalCurveBase):
    def __init__(self, input_offset, decay_rate, limit):
        super().__init__(input_offset, decay_rate, limit)
        self.constant = -self.limit / self.accel if not self._is_flat_limit else 0.0
    def __call__(self, x):
        if x <= self.offset:
            return 1.0
        if self._is_flat_limit:
            return 1.0
        offset_x = self.offset - x
        decay = safe_exp(self.accel * offset_x)
        output = self.limit * (decay / self.accel - offset_x) + self.constant
        return output / x + 1
class JumpCurveBase:
    SMOOTH_SCALE = 2 * math.pi
    def __init__(self, cap_x, cap_y, smooth):
        self.step_x = float(cap_x)
        self.step_y = float(cap_y) - 1.0
        smooth = float(smooth)
        rate_inverse = smooth * self.step_x
        self.smooth_rate = 0.0 if rate_inverse < 1.0 else self.SMOOTH_SCALE / rate_inverse
    def is_smooth(self):
        return self.smooth_rate != 0.0
    def flat_segments(self):
        if self.is_smooth() or self.step_x <= 0.0:
            return []
        return [(0.0, self.step_x, 1.0)]
    def decay(self, x):
        return safe_exp(self.smooth_rate * (self.step_x - x))
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
        self.offset = float(input_offset)
        self.acceleration = float(acceleration)
        self.exponent = max(float(exponent), RAWACCEL_CLASSIC_EXPONENT_MIN)
    def flat_segments(self):
        return [(0.0, self.offset, 1.0)] if self.offset > 0.0 else []
    def base_fn(self, x, accel_raised):
        return accel_raised * safe_pow(x - self.offset, self.exponent) / x
    def base_accel(self, x, y):
        return safe_pow(
            x * y * safe_pow(x - self.offset, -self.exponent),
            1 / (self.exponent - 1)
        )
class ClassicCurveLegacy(ClassicCurveBase):
    def __init__(self, input_offset, acceleration, exponent, cap_mode, cap_x, cap_y):
        super().__init__(input_offset, acceleration, exponent)
        self.cap = float("inf")
        self.sign = 1.0
        self.accel_raised = safe_pow(self.acceleration, self.exponent - 1)
        cap_mode = cap_mode.lower()
        if cap_mode == "io":
            self.cap = cap_y - 1.0
            if self.cap < 0:
                self.cap = -self.cap
                self.sign = -self.sign
            if cap_x > self.offset and self.cap > 0:
                a = self.base_accel(cap_x, self.cap)
                self.accel_raised = safe_pow(a, self.exponent - 1)
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
        self.accel_raised = safe_pow(self.acceleration, self.exponent - 1)
        cap_mode = cap_mode.lower()
        if cap_mode == "io":
            self.cap_x = cap_x
            self.cap_y = cap_y - 1.0
            if self.cap_y < 0:
                self.cap_y = -self.cap_y
                self.sign = -self.sign
            if self.cap_x > self.offset and self.cap_y > 0:
                a = self.gain_accel(self.cap_x, self.cap_y, self.exponent, self.offset)
                self.accel_raised = safe_pow(a, self.exponent - 1)
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
        if accel <= 0:
            return 0.0
        return power * safe_pow(accel * (x - offset), power - 1)
    @staticmethod
    def gain_inverse(y, accel, power, offset):
        if accel <= 0:
            return float("inf")
        return (accel * offset + safe_pow(y / power, 1 / (power - 1))) / accel
    @staticmethod
    def gain_accel(x, y, power, offset):
        if abs(offset - x) <= 1e-12:
            return 0.0
        return -safe_pow(y / power, 1 / (power - 1)) / (offset - x)
class SynchronousCurveLegacy:
    def __init__(self, gamma, motivity, sync_speed, smooth):
        self.motivity = max(float(Fraction(motivity).limit_denominator(10000)), RAWACCEL_MOTIVITY_MIN)
        self.log_motivity = math.log(self.motivity)
        self.gamma = max(float(Fraction(gamma).limit_denominator(10000)), RAWACCEL_POSITIVE_EPSILON)
        self.gamma_const = self.gamma / self.log_motivity
        self.sync_speed = max(float(Fraction(sync_speed).limit_denominator(10000)), RAWACCEL_POSITIVE_EPSILON)
        self.log_syncspeed = math.log(self.sync_speed)
        smooth = max(float(Fraction(smooth).limit_denominator(10000)), 0.0)
        self.sharpness = 16.0 if smooth == 0 else 0.5 / smooth
        self.sharpness_recip = 1.0 / self.sharpness
        self.use_linear_clamp = self.sharpness >= 16.0
        self.minimum_sens = 1.0 / self.motivity
        self.maximum_sens = self.motivity
        if self.use_linear_clamp and abs(self.gamma_const) > 1e-12:
            clamp_factor = safe_exp(1.0 / self.gamma_const)
            self.lower_clamp_x = self.sync_speed / clamp_factor
            self.upper_clamp_x = self.sync_speed * clamp_factor
        else:
            self.lower_clamp_x = None
            self.upper_clamp_x = None
    def flat_segments(self):
        if not self.use_linear_clamp or self.lower_clamp_x is None:
            return []
        return [
            (0.0, self.lower_clamp_x, self.minimum_sens),
            (self.upper_clamp_x, float("inf"), self.maximum_sens)
        ]
    def __call__(self, x):
        if x <= 0.0:
            return self.minimum_sens
        if self.use_linear_clamp:
            log_space = self.gamma_const * (math.log(x) - self.log_syncspeed)
            if log_space < -1.0:
                return self.minimum_sens
            if log_space > 1.0:
                return self.maximum_sens
            return safe_exp(log_space * self.log_motivity)
        if x == self.sync_speed:
            return 1.0
        log_diff = math.log(x) - self.log_syncspeed
        if log_diff > 0:
            log_space = self.gamma_const * log_diff
            shaped = safe_pow(log_space, self.sharpness)
            tanh_value = 1.0 if shaped >= MAX_FLOAT else math.tanh(shaped)
            exponent = safe_pow(tanh_value, self.sharpness_recip)
            return safe_exp(exponent * self.log_motivity)
        log_space = -self.gamma_const * log_diff
        shaped = safe_pow(log_space, self.sharpness)
        tanh_value = 1.0 if shaped >= MAX_FLOAT else math.tanh(shaped)
        exponent = -safe_pow(tanh_value, self.sharpness_recip)
        return safe_exp(exponent * self.log_motivity)
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
        self.minimum_sens = sig.minimum_sens
        self.lower_clamp_x = sig.lower_clamp_x
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
        if self.lower_clamp_x is not None and x <= self.lower_clamp_x:
            return self.minimum_sens
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
    def flat_segments(self):
        if self.lower_clamp_x is None:
            return []
        return [(0.0, self.lower_clamp_x, self.minimum_sens)]
class MotivityCurveLegacy:
    def __init__(self, growth_rate, motivity, midpoint):
        self.accel = min(safe_exp(float(growth_rate)), 1e12)
        self.motivity = max(float(motivity), RAWACCEL_MOTIVITY_MIN)
        self.midpoint = max(float(midpoint), RAWACCEL_POSITIVE_EPSILON)
        self.log_midpoint = math.log(self.midpoint)
        self.motivity_term = 2.0 * math.log(self.motivity)
        self.constant = -self.motivity_term / 2.0
        self.minimum_sens = 1.0 / self.motivity
    def __call__(self, x):
        if x <= 0.0:
            return self.minimum_sens
        exponent = self.accel * (self.log_midpoint - math.log(x))
        if exponent >= 60.0:
            return self.minimum_sens
        if exponent <= -60.0:
            return self.motivity
        denom = safe_exp(exponent) + 1.0
        return safe_exp(self.motivity_term / denom + self.constant)
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
    CAPACITY = RAWACCEL_LUT_POINTS_CAPACITY
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
        self.power = max(float(exponent_power), RAWACCEL_POSITIVE_EPSILON)
        self.output_offset = float(output_offset)
        self.scale = float(scale)
        self.offset_x = 0.0
        self.offset_y = self.output_offset
        self.constant = 0.0
        self.cap_mode = cap_mode.lower()
        self.gain_curve = bool(gain_curve)
        self.cap_x = float(cap_x)
        self.cap_y = float(cap_y)
        self._setup_parameters()
    def flat_segments(self):
        return [(0.0, self.offset_x, self.offset_y)] if self.offset_x > 0.0 else []
    @staticmethod
    def gain(input_val, power, scale):
        return (power + 1.0) * safe_pow(input_val * scale, power)
    @staticmethod
    def gain_inverse(gain, power, scale):
        return safe_divide(safe_pow(gain / (power + 1.0), 1.0 / power), scale)
    @staticmethod
    def scale_from_gain_point(input_val, gain, power):
        if input_val <= 0:
            return 1.0
        return safe_divide(safe_pow(gain / (power + 1.0), 1.0 / power), input_val)
    @staticmethod
    def scale_from_output_point(input_val, output, power, constant):
        if input_val <= 0:
            return 1.0
        return safe_divide(safe_pow(output - constant / input_val, 1.0 / power), input_val)
    @staticmethod
    def integration_constant(input_val, gain, output):
        return (output - gain) * input_val
    @staticmethod
    def ieee_divide(numerator, denominator):
        return safe_divide(numerator, denominator)
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
        return safe_pow(self.scale * x, self.power) + self.constant / x
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
        if x <= 0.0 and self.cap_x_eff <= 0.0:
            return self.cap_y_eff
        if x < self.cap_x_eff:
            out = self.base_fn(x)
        else:
            out = self.cap_y_eff + self.ieee_divide(self.constant_b, x)
        return out
class TransitionSmoothedCurve:
    def __init__(self, curve, transitions):
        self.curve = curve
        self.transitions = sorted(transitions, key=lambda transition: transition["left"])

    def __call__(self, x):
        x = float(x)
        for transition in self.transitions:
            left = transition["left"]
            right = transition["right"]
            if x < left:
                break
            if x > right:
                continue
            tol = max((right - left) * 1e-12, 1e-12)
            if x <= left + tol or x >= right - tol:
                return self.curve(x)
            if "center" in transition:
                center = transition["center"]
                if abs(x - center) <= tol:
                    return transition["center_y"]
                if x < center:
                    return self._hermite(
                        x,
                        left,
                        center,
                        transition["left_y"],
                        transition["center_y"],
                        transition["left_slope"],
                        transition["center_slope"]
                    )
                return self._hermite(
                    x,
                    center,
                    right,
                    transition["center_y"],
                    transition["right_y"],
                    transition["center_slope"],
                    transition["right_slope"]
                )
            return self._hermite(
                x,
                left,
                right,
                transition["left_y"],
                transition["right_y"],
                transition["left_slope"],
                transition["right_slope"]
            )
        return self.curve(x)

    @staticmethod
    def _hermite(x, left, right, left_y, right_y, left_slope, right_slope):
        dx = right - left
        if dx <= 0.0:
            return left_y
        t = (x - left) / dx
        t2 = t * t
        t3 = t2 * t
        h00 = 2.0 * t3 - 3.0 * t2 + 1.0
        h10 = t3 - 2.0 * t2 + t
        h01 = -2.0 * t3 + 3.0 * t2
        h11 = t3 - t2
        return (
            h00 * left_y
            + h10 * dx * left_slope
            + h01 * right_y
            + h11 * dx * right_slope
        )

    def flat_segments(self):
        if not hasattr(self.curve, "flat_segments"):
            return []
        try:
            return self.curve.flat_segments()
        except Exception:
            return []

    def transition_anchors(self):
        anchors = []
        for transition in self.transitions:
            left = transition["left"]
            right = transition["right"]
            width = right - left
            if width <= 0.0:
                continue
            if "center" in transition:
                center = transition["center"]
                left_width = center - left
                right_width = right - center
                anchors.extend([left, center, right])
                if left_width > 0.0:
                    anchors.extend([
                        left + left_width * 0.45,
                        left + left_width * 0.75,
                    ])
                if right_width > 0.0:
                    anchors.extend([
                        center + right_width * 0.25,
                        center + right_width * 0.60,
                    ])
                continue
            anchors.extend([left, left + width * 0.35, left + width * 0.70, right])
        return anchors
class CurveGenerator:
    def __init__(
        self,
        mode_name="natural",
        curve_type="legacy",
        cap_mode="out",
        point_reduction_mode="optimal",
        smooth_transition_strength=0.0
    ):
        self.mode_name = mode_name.lower()
        self.curve_type = curve_type.lower()
        self.cap_mode = cap_mode.lower()
        self.point_reduction_mode = (point_reduction_mode or "off").lower()
        self.smooth_transition_strength = max(0.0, finite_value(smooth_transition_strength, 0.0))
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
        exponent = max(float(args["exponent"]), 1e-12)
        cap_x = args.get("cap_x", 0.0)
        cap_y = args.get("cap_y", 0.0)
        if self.cap_mode in ["in", "io"]:
            return cap_x if cap_x > offset else None
        if cap_y > 0 and accel > 0 and exponent != 1:
            cap_y_adj = cap_y - 1.0
            if abs(cap_y_adj) <= 1e-12:
                return 0.0
            cap_y_abs = abs(cap_y_adj)
            return (accel * offset + safe_pow(cap_y_abs / exponent, 1 / (exponent - 1))) / accel
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
            return safe_divide(safe_pow(cap_y / (p + 1.0), 1.0 / p), s)
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
        return safe_divide(safe_pow(output_offset / (p + 1.0), 1.0 / p), s)
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
    def _adaptive_anchors(self, args, max_input):
        anchors = {0.0, float(max_input)}
        def add(value):
            try:
                v = float(value)
                if math.isfinite(v) and 0.0 <= v <= max_input:
                    anchors.add(v)
            except Exception:
                pass
        if self.mode_name in ["classic/linear", "natural"]:
            add(args.get("input_offset", 0.0))
        if self.mode_name == "jump":
            cap_x = float(args.get("cap_x", 15.0))
            add(cap_x)
            if cap_x > 0:
                add(cap_x * 0.5)
                add(cap_x * 0.9)
                add(cap_x * 1.1)
                add(cap_x * 1.5)
        if self.mode_name == "synchronous":
            sync_speed = float(args.get("sync_speed", 5.0))
            add(sync_speed)
            if sync_speed > 0:
                add(sync_speed * 0.25)
                add(sync_speed * 0.5)
                add(sync_speed * 2.0)
                add(sync_speed * 4.0)
        if self.mode_name == "motivity (1.6.1)":
            midpoint = float(args.get("midpoint", 5.0))
            add(midpoint)
            if midpoint > 0:
                add(midpoint * 0.25)
                add(midpoint * 0.5)
                add(midpoint * 2.0)
                add(midpoint * 4.0)
        if self.mode_name == "power":
            add(self._power_offset_breakpoint(args) or 0.0)
        cap_breakpoint = self._special_breakpoint(args)
        if cap_breakpoint is not None:
            add(cap_breakpoint)
            add(float(cap_breakpoint) * 0.98)
            add(float(cap_breakpoint) * 1.02)
        return sorted(anchors)

    def _flat_segments_for_transition_smoothing(self, curve, max_input, precision=6):
        flat_segments = self._exact_flat_segments(curve, max_input)
        for segment in self._rounded_flat_segments(curve, max_input, precision=precision):
            if not any(
                abs(segment[0] - existing[0]) <= 1e-10 and abs(segment[1] - existing[1]) <= 1e-10
                for existing in flat_segments
            ):
                flat_segments.append(segment)
        min_length = max(float(max_input) * 1e-5, 1e-5)
        filtered_segments = []
        for start_x, end_x, y in flat_segments:
            start_x = float(start_x)
            end_x = float(end_x)
            if math.isfinite(end_x):
                if end_x <= start_x or end_x - start_x < min_length:
                    continue
            filtered_segments.append((start_x, end_x, y))
        return filtered_segments

    def _transition_hard_anchors(self, args, max_input, flat_segments=None):
        anchors = {0.0, float(max_input)}
        def add(value):
            try:
                value = float(value)
            except Exception:
                return
            if math.isfinite(value) and 0.0 <= value <= max_input:
                anchors.add(value)
        if self.mode_name in ["classic/linear", "natural"]:
            add(args.get("input_offset", 0.0))
        if self.mode_name == "jump":
            add(args.get("cap_x", 15.0))
        if self.mode_name == "synchronous":
            add(args.get("sync_speed", 5.0))
        if self.mode_name == "motivity (1.6.1)":
            add(args.get("midpoint", 5.0))
        if self.mode_name == "power":
            add(self._power_offset_breakpoint(args) or 0.0)
        cap_breakpoint = self._special_breakpoint(args)
        if cap_breakpoint is not None:
            add(cap_breakpoint)
        if self.mode_name == "lut":
            for x, _ in parse_lookup_points(args.get("lookup_points", [])):
                add(x)
        for start_x, end_x, _ in flat_segments or []:
            add(start_x)
            add(end_x)
        return sorted(anchors)

    def _transition_smoothing_y_scale(self, curve, max_input, protected=None):
        samples = {0.0, float(max_input)}
        for i in range(65):
            t = i / 64.0
            samples.add(max_input * t)
            samples.add(max_input * (t ** 2.0))
        for x in protected or []:
            try:
                x = float(x)
                if math.isfinite(x) and 0.0 <= x <= max_input:
                    samples.add(x)
            except Exception:
                pass
        values = []
        for x in sorted(samples):
            try:
                y = float(curve(x))
            except Exception:
                continue
            if math.isfinite(y):
                values.append(y)
        if not values:
            return 1.0
        return max(max(values) - min(values), max(abs(y) for y in values), 1.0)

    def _estimate_curve_slope(self, curve, x, max_input, side="right", lower_bound=0.0, upper_bound=None):
        x = float(x)
        max_input = max(float(max_input), 0.0)
        lower_bound = max(float(lower_bound), 0.0)
        upper_bound = max_input if upper_bound is None else min(float(upper_bound), max_input)
        h = max(max_input * 1e-5, abs(x) * 1e-5, 1e-6)

        if side == "left":
            x0 = max(lower_bound, x - h)
            x1 = x
        elif side == "central":
            x0 = max(lower_bound, x - h)
            x1 = min(upper_bound, x + h)
        else:
            x0 = x
            x1 = min(upper_bound, x + h)
            if x1 <= x0:
                x0 = max(lower_bound, x - h)
                x1 = x

        if x1 <= x0:
            return 0.0
        try:
            slope = (float(curve(x1)) - float(curve(x0))) / (x1 - x0)
        except Exception:
            return 0.0
        return slope if math.isfinite(slope) else 0.0

    def _build_flat_exit_transition(
        self,
        curve,
        boundary,
        max_input,
        protected,
        y_scale,
        precision=6,
        strength=1.0
    ):
        boundary = max(0.0, min(float(boundary), float(max_input)))
        if boundary >= max_input:
            return None

        protected_right = [
            float(x)
            for x in protected
            if math.isfinite(float(x)) and float(x) > boundary + max(max_input * 1e-9, 1e-9)
        ]
        hard_right = min(protected_right) if protected_right else float(max_input)
        available = hard_right - boundary
        min_width = max(max_input * 1e-5, 1e-5)
        if available <= min_width * 4.0:
            return None

        strength = max(0.0, min(float(strength), 4.0))
        local_scale = max(abs(boundary), max_input * 0.02, 1.0)
        target_width = max(max_input * 0.004, local_scale * 0.08) * strength
        width = min(available * 0.55, max(target_width, min_width * 4.0))
        if width <= min_width:
            return None

        left = boundary
        right = boundary + width
        try:
            left_y = float(curve(left))
            right_y = float(curve(right))
        except Exception:
            return None
        if not math.isfinite(left_y) or not math.isfinite(right_y):
            return None

        y_epsilon = max(10.0 ** -(int(precision) + 1), y_scale * 1e-7, 1e-10)
        if right_y <= left_y + y_epsilon:
            return None

        probe_dx = max(min(width * 0.03, available * 0.03), max_input * 1e-7, 1e-7)
        probe_x = min(right, boundary + probe_dx)
        try:
            probe_y = float(curve(probe_x))
        except Exception:
            return None
        if not math.isfinite(probe_y):
            return None
        if probe_y - left_y > max((right_y - left_y) * 0.60, y_scale * 0.08):
            return None

        linear_start = min(right, boundary + probe_dx)
        if right - linear_start > min_width:
            try:
                if self._safe_is_linear_segment(curve, linear_start, right, precision=precision):
                    return None
            except Exception:
                pass

        secant = (right_y - left_y) / width
        if secant <= 0.0:
            return None

        right_slope = self._estimate_curve_slope(
            curve,
            right,
            max_input,
            side="right",
            lower_bound=left,
            upper_bound=hard_right
        )
        if right_slope <= 0.0:
            right_slope = self._estimate_curve_slope(
                curve,
                right,
                max_input,
                side="left",
                lower_bound=left,
                upper_bound=hard_right
            )
        if right_slope <= secant * 0.10:
            return None

        return {
            "left": left,
            "right": right,
            "left_y": left_y,
            "right_y": right_y,
            "left_slope": 0.0,
            "right_slope": max(0.0, min(right_slope, secant * 3.0)),
        }

    def _transition_candidate_points(self, args, max_input, flat_segments):
        candidates = set(self._transition_hard_anchors(args, max_input, flat_segments))
        return sorted(
            float(x)
            for x in candidates
            if math.isfinite(float(x)) and 0.0 < float(x) < max_input
        )

    @staticmethod
    def _clamp_monotone_slope(slope, secant):
        slope = finite_value(slope, 0.0)
        secant = finite_value(secant, 0.0)
        if abs(secant) <= 1e-15:
            return 0.0
        if secant > 0.0:
            return max(0.0, min(slope, secant * 3.0))
        return min(0.0, max(slope, secant * 3.0))

    @staticmethod
    def _pchip_join_slope(left_dx, right_dx, left_secant, right_secant):
        if left_dx <= 0.0 or right_dx <= 0.0:
            return 0.0
        if left_secant <= 0.0 or right_secant <= 0.0:
            return 0.0
        w1 = 2.0 * right_dx + left_dx
        w2 = right_dx + 2.0 * left_dx
        denom = (w1 / right_secant) + (w2 / left_secant)
        if denom <= 0.0:
            return 0.0
        return (w1 + w2) / denom

    def _build_slope_knee_transition(
        self,
        curve,
        center,
        max_input,
        protected,
        y_scale,
        precision=6,
        strength=1.0
    ):
        center = float(center)
        max_input = max(float(max_input), 0.0)
        if center <= 0.0 or center >= max_input:
            return None

        gap = max(max_input * 1e-9, 1e-9)
        left_protected = [
            float(x)
            for x in protected
            if math.isfinite(float(x)) and float(x) < center - gap
        ]
        right_protected = [
            float(x)
            for x in protected
            if math.isfinite(float(x)) and float(x) > center + gap
        ]
        hard_left = max(left_protected) if left_protected else 0.0
        hard_right = min(right_protected) if right_protected else max_input
        left_available = center - hard_left
        right_available = hard_right - center
        min_width = max(max_input * 1e-5, 1e-5)
        if left_available <= min_width * 4.0 or right_available <= min_width * 4.0:
            return None

        strength = max(0.0, min(float(strength), 4.0))
        local_scale = max(abs(center), max_input * 0.02, 1.0)
        target_width = max(max_input * 0.004, local_scale * 0.06) * strength
        left_width = min(left_available * 0.45, max(target_width, min_width * 3.0))
        right_width = min(right_available * 0.45, max(target_width, min_width * 3.0))
        if left_width <= min_width or right_width <= min_width:
            return None

        left = center - left_width
        right = center + right_width
        try:
            left_y = float(curve(left))
            center_y = float(curve(center))
            right_y = float(curve(right))
        except Exception:
            return None
        if not all(math.isfinite(y) for y in (left_y, center_y, right_y)):
            return None
        y_epsilon = max(10.0 ** -(int(precision) + 1), y_scale * 1e-7, 1e-10)
        if center_y <= left_y + y_epsilon or right_y <= center_y + y_epsilon:
            return None

        left_secant = (center_y - left_y) / (center - left)
        right_secant = (right_y - center_y) / (right - center)
        if left_secant <= 0.0 or right_secant <= 0.0:
            return None

        left_near = self._estimate_curve_slope(
            curve,
            center,
            max_input,
            side="left",
            lower_bound=hard_left,
            upper_bound=hard_right
        )
        right_near = self._estimate_curve_slope(
            curve,
            center,
            max_input,
            side="right",
            lower_bound=hard_left,
            upper_bound=hard_right
        )
        if right_near <= 0.0 or right_near <= left_near:
            return None
        slope_scale = max(abs(right_near), abs(left_near), y_scale / max(max_input, 1.0), 1e-12)
        if right_near - left_near < slope_scale * 0.18:
            return None
        if right_secant <= left_secant * 1.08 and right_near <= left_near * 1.25:
            return None

        left_slope = self._estimate_curve_slope(
            curve,
            left,
            max_input,
            side="central",
            lower_bound=hard_left,
            upper_bound=center
        )
        right_slope = self._estimate_curve_slope(
            curve,
            right,
            max_input,
            side="central",
            lower_bound=center,
            upper_bound=hard_right
        )
        center_slope = self._pchip_join_slope(
            center - left,
            right - center,
            left_secant,
            right_secant
        )
        center_slope = min(center_slope, left_secant * 3.0, right_secant * 3.0)

        return {
            "left": left,
            "center": center,
            "right": right,
            "left_y": left_y,
            "center_y": center_y,
            "right_y": right_y,
            "left_slope": self._clamp_monotone_slope(left_slope, left_secant),
            "center_slope": max(0.0, center_slope),
            "right_slope": self._clamp_monotone_slope(right_slope, right_secant),
        }

    @staticmethod
    def _transition_overlaps(existing_transitions, candidate):
        left = candidate["left"]
        right = candidate["right"]
        for transition in existing_transitions:
            if left < transition["right"] and right > transition["left"]:
                return True
        return False

    def _apply_transition_smoothing(self, curve, args, max_input, precision=6):
        strength = max(0.0, finite_value(self.smooth_transition_strength, 0.0))
        if strength <= 0.0 or max_input <= 0.0:
            return curve

        flat_segments = self._flat_segments_for_transition_smoothing(curve, max_input, precision=precision)
        protected = set(self._transition_hard_anchors(args, max_input, flat_segments))
        flat_tail_start = self._safe_find_flat_tail_start(curve, max_input, precision=precision)
        if flat_tail_start is not None:
            protected.add(float(flat_tail_start))

        y_scale = self._transition_smoothing_y_scale(curve, max_input, protected=protected)
        transitions = []
        flat_boundaries = set()
        for start_x, end_x, _ in sorted(flat_segments, key=lambda segment: (segment[0], segment[1])):
            try:
                start_x = float(start_x)
                end_x = float(end_x)
            except Exception:
                continue
            flat_boundaries.add(round(start_x, 10))
            if math.isfinite(end_x):
                flat_boundaries.add(round(end_x, 10))
            if not math.isfinite(end_x) or end_x <= start_x or end_x >= max_input:
                continue
            transition = self._build_flat_exit_transition(
                curve,
                end_x,
                max_input,
                protected,
                y_scale,
                precision=precision,
                strength=strength
            )
            if transition is None:
                continue
            if self._transition_overlaps(transitions, transition):
                continue
            transitions.append(transition)

        for center in self._transition_candidate_points(args, max_input, flat_segments):
            if round(float(center), 10) in flat_boundaries:
                continue
            transition = self._build_slope_knee_transition(
                curve,
                center,
                max_input,
                protected,
                y_scale,
                precision=precision,
                strength=strength
            )
            if transition is None:
                continue
            if self._transition_overlaps(transitions, transition):
                continue
            transitions.append(transition)

        if not transitions:
            return curve
        return TransitionSmoothedCurve(curve, transitions)

    def _transition_smoothing_anchors(self, curve):
        if not hasattr(curve, "transition_anchors"):
            return []
        try:
            return [
                float(x)
                for x in curve.transition_anchors()
                if math.isfinite(float(x))
            ]
        except Exception:
            return []

    def _adaptive_effective_max_input(self, curve, max_input, precision=6):
        max_input = max(float(max_input), 0.0)
        if max_input <= 0:
            return max_input
        precision = int(precision)
        y_tolerance = max((10.0 ** -max(precision, 1)) * 1.5, 1e-8)
        xs = []
        count = 96
        for i in range(count):
            t = i / max(1, count - 1)
            x = max_input * (t ** 2.0)
            xs.append(x)
        xs = sorted(set([0.0, max_input] + xs))
        ys = [round(float(curve(x)), precision) for x in xs]
        last_change = 0
        for i in range(1, len(xs)):
            if abs(ys[i] - ys[i - 1]) > y_tolerance:
                last_change = i
        if last_change >= len(xs) - 4:
            return max_input
        candidate = xs[min(len(xs) - 1, last_change + 2)]
        return max(candidate, max_input * 0.05)

    def _adaptive_x_values(self, curve, args, point_count, max_input, precision=6, protected=None):
        max_input = max(float(max_input), 0.0)
        point_count = max(2, int(point_count))
        if max_input <= 0:
            return [0.0]
        precision = int(precision)
        anchors = set(self._adaptive_anchors(args, max_input))
        anchors.update(self._transition_smoothing_anchors(curve))
        if protected:
            for x in protected:
                try:
                    v = float(x)
                    if math.isfinite(v) and 0.0 <= v <= max_input:
                        anchors.add(v)
                except Exception:
                    pass
        effective_max = self._adaptive_effective_max_input(curve, max_input, precision)
        anchors.add(effective_max)
        if effective_max < max_input:
            step = max((max_input - effective_max) / max(point_count, 2), max_input * 1e-6)
            anchors.add(min(max_input, effective_max + step))
            anchors.add(max_input)
        dense_seed = []
        seed_count = max(48, min(512, point_count * 4))
        for i in range(seed_count):
            t = i / max(1, seed_count - 1)
            x = effective_max * (t ** 2.15)
            dense_seed.append(x)
        anchors.update(dense_seed)
        anchors = sorted(set(min(max(float(x), 0.0), max_input) for x in anchors))
        y_values = [float(curve(x)) for x in anchors]
        y_min = min(y_values)
        y_max = max(y_values)
        y_scale = max(y_max - y_min, max(abs(y) for y in y_values), 1.0)
        max_error = max((10.0 ** -max(precision, 1)) * 0.75, y_scale * 0.000015)
        min_dx = max_input / max(4096, point_count * 32)
        result = set()
        result.add(0.0)
        result.add(max_input)
        for x in self._adaptive_anchors(args, max_input):
            result.add(x)
        for x in self._transition_smoothing_anchors(curve):
            result.add(x)
        if protected:
            for x in protected:
                try:
                    result.add(float(x))
                except Exception:
                    pass
        def y_at(x):
            return float(curve(float(x)))
        def split_segment(x0, x1, depth=0):
            if x1 <= x0:
                result.add(x0)
                result.add(x1)
                return
            y0 = y_at(x0)
            y1 = y_at(x1)
            mid = (x0 + x1) * 0.5
            ym = y_at(mid)
            line_y = y0 + (y1 - y0) * ((mid - x0) / (x1 - x0))
            error = abs(ym - line_y)
            if depth >= 18 or (x1 - x0) <= min_dx or error <= max_error:
                result.add(x0)
                result.add(x1)
                return
            split_segment(x0, mid, depth + 1)
            split_segment(mid, x1, depth + 1)
        ordered = sorted(set([0.0, max_input, effective_max] + anchors))
        for left, right in zip(ordered, ordered[1:]):
            split_segment(left, right)
        result = sorted(set(min(max(float(x), 0.0), max_input) for x in result))
        return result
    def _safe_flat_epsilon(self, precision=6):
        precision = int(precision)
        return max((10.0 ** -max(precision, 1)) * 1.5, 1e-8)

    def _safe_find_flat_end(self, curve, start_x, end_x, precision=6):
        start_x = float(start_x)
        end_x = float(end_x)
        if end_x <= start_x:
            return start_x
        precision = int(precision)
        epsilon = self._safe_flat_epsilon(precision)
        start_y = round(float(curve(start_x)), precision)
        lo = start_x
        hi = end_x
        for _ in range(48):
            mid = (lo + hi) * 0.5
            mid_y = round(float(curve(mid)), precision)
            if abs(mid_y - start_y) <= epsilon:
                lo = mid
            else:
                hi = mid
        return lo

    def _safe_protect_flat_boundaries(self, curve, x_values, precision=6, protected=None):
        x_values = sorted(set(float(x) for x in x_values))
        if len(x_values) <= 1:
            return x_values
        output = set(x_values)
        min_x = x_values[0]
        max_x = x_values[-1]
        if protected:
            for x in protected:
                try:
                    x = float(x)
                    if math.isfinite(x) and min_x <= x <= max_x:
                        output.add(x)
                except Exception:
                    pass
        precision = int(precision)
        epsilon = self._safe_flat_epsilon(precision)
        y_values = [round(float(curve(x)), precision) for x in x_values]
        for i in range(len(x_values) - 1):
            y0 = y_values[i]
            y1 = y_values[i + 1]
            prev_flat = i > 0 and abs(y_values[i] - y_values[i - 1]) <= epsilon
            leaving_flat = prev_flat and abs(y1 - y0) > epsilon
            if leaving_flat:
                boundary = self._safe_find_flat_end(curve, x_values[i], x_values[i + 1], precision=precision)
                output.add(x_values[i - 1])
                output.add(x_values[i])
                output.add(boundary)
                output.add(x_values[i + 1])
        return sorted(set(float(x) for x in output))

    def _safe_effective_end_x(self, curve, max_input, precision=6):
        max_input = max(float(max_input), 0.0)
        if max_input <= 0:
            return 0.0
        precision = int(precision)
        epsilon = self._safe_flat_epsilon(precision)
        sample_count = 256
        xs = []
        for i in range(sample_count):
            t = i / max(1, sample_count - 1)
            xs.append(max_input * t)
            xs.append(max_input * (t ** 2.0))
            xs.append(max_input * (t ** 3.0))
        xs = sorted(set(min(max(x, 0.0), max_input) for x in xs))
        ys = [round(float(curve(x)), precision) for x in xs]
        last_change = 0
        for i in range(1, len(xs)):
            if abs(ys[i] - ys[i - 1]) > epsilon:
                last_change = i
        if last_change >= len(xs) - 3:
            return max_input
        end_index = min(len(xs) - 1, last_change + 2)
        return max(xs[end_index], max_input * 0.02)

    def _safe_find_flat_tail_start(self, curve, max_input, precision=6):
        max_input = max(float(max_input), 0.0)
        if max_input <= 0:
            return None
        precision = int(precision)
        epsilon = max(10.0 ** -(precision + 3), 1e-10)
        end_y = float(curve(max_input))
        sample_count = 1024
        xs = [max_input * (i / max(1, sample_count - 1)) for i in range(sample_count)]
        ys = [float(curve(x)) for x in xs]
        first_tail_index = None
        tail_is_flat = True
        for i in range(len(xs) - 1, -1, -1):
            if abs(ys[i] - end_y) <= epsilon and tail_is_flat:
                first_tail_index = i
                continue
            tail_is_flat = False
            if first_tail_index is not None:
                break
        if first_tail_index is None or first_tail_index == 0:
            return None
        lo = xs[first_tail_index - 1]
        hi = xs[first_tail_index]
        for _ in range(64):
            mid = (lo + hi) * 0.5
            if abs(float(curve(mid)) - end_y) <= epsilon:
                hi = mid
            else:
                lo = mid
        if hi >= max_input or hi <= 0.0:
            return None
        return hi

    def _exact_flat_segments(self, curve, max_input):
        max_input = max(float(max_input), 0.0)
        segments = []
        raw_segments = []
        if hasattr(curve, "flat_segments"):
            try:
                raw_segments = curve.flat_segments()
            except Exception:
                raw_segments = []
        for start_x, end_x, y in raw_segments:
            try:
                start_x = max(float(start_x), 0.0)
                end_x = float(end_x)
                y = float(y)
            except Exception:
                continue
            if not math.isfinite(y) or start_x >= max_input:
                continue
            if not math.isfinite(end_x):
                end_x = max_input
            end_x = min(max(end_x, 0.0), max_input)
            if end_x > start_x:
                segments.append((start_x, end_x, y))
        return segments

    def _format_y_key(self, y, precision=6):
        return f"{float(y):.{int(precision)}f}"

    def _safe_find_rounded_flat_head_end(self, curve, max_input, precision=6):
        max_input = max(float(max_input), 0.0)
        if max_input <= 0:
            return None
        precision = int(precision)
        base_key = self._format_y_key(curve(0.0), precision)
        samples = {0.0, max_input}
        sample_count = 2048
        for i in range(1, sample_count):
            t = i / sample_count
            samples.add(max_input * t)
            samples.add(max_input * (t ** 2.0))
            samples.add(max_input * (t ** 3.0))
        last_same = 0.0
        first_different = None
        for x in sorted(samples):
            if x <= 0.0:
                continue
            if self._format_y_key(curve(x), precision) == base_key:
                last_same = float(x)
                continue
            first_different = float(x)
            break
        if first_different is None:
            return max_input
        if last_same <= 0.0 and first_different <= max_input * 1e-6:
            return None
        lo = last_same
        hi = first_different
        for _ in range(64):
            mid = (lo + hi) * 0.5
            if self._format_y_key(curve(mid), precision) == base_key:
                lo = mid
            else:
                hi = mid
        if lo <= 0.0:
            return None
        return lo

    def _rounded_flat_segments(self, curve, max_input, precision=6):
        head_end = self._safe_find_rounded_flat_head_end(curve, max_input, precision=precision)
        if head_end is None or head_end <= 0.0:
            return []
        return [(0.0, head_end, float(self._format_y_key(curve(0.0), precision)))]

    def _remove_near_exact_flat_boundary_points(self, curve, x_values, flat_segments, precision=6):
        if not flat_segments:
            return sorted(set(float(x) for x in x_values))
        precision = int(precision)
        epsilon = max(self._safe_flat_epsilon(precision) * 2.0, 10.0 ** -max(precision, 1) * 2.5)
        keep = set()
        flat_endpoints = set()
        for start_x, end_x, _ in flat_segments:
            flat_endpoints.add(round(float(start_x), 10))
            flat_endpoints.add(round(float(end_x), 10))
        for x in sorted(set(float(v) for v in x_values)):
            rx = round(float(x), 10)
            if rx in flat_endpoints:
                keep.add(float(x))
                continue
            remove = False
            y = float(curve(x))
            for start_x, end_x, flat_y in flat_segments:
                if start_x < x < end_x:
                    remove = True
                    break
                if x > end_x and abs(y - flat_y) <= epsilon:
                    remove = True
                    break
                if x < start_x and abs(y - flat_y) <= epsilon:
                    remove = True
                    break
            if not remove:
                keep.add(float(x))
        return sorted(keep)

    def _safe_is_linear_segment(self, curve, x0, x1, precision=6):
        x0 = float(x0)
        x1 = float(x1)
        if x1 <= x0:
            return False
        y0 = float(curve(x0))
        y1 = float(curve(x1))
        dx = x1 - x0
        tolerance = max((10.0 ** -(int(precision) + 2)), 1e-10)
        for t in (0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875):
            x = x0 + dx * t
            actual = float(curve(x))
            expected = y0 + (y1 - y0) * t
            if abs(actual - expected) > tolerance:
                return False
        return True

    def _safe_strict_linear_cleanup(self, curve, x_values, precision=6, protected=None, preserve_below_x=0.0):
        x_values = sorted(set(float(x) for x in x_values))
        if len(x_values) <= 2:
            return x_values
        protected_values = set(round(float(x), 10) for x in (protected or []))
        keep = set([x_values[0], x_values[-1]])
        for x in x_values:
            if round(float(x), 10) in protected_values or x <= preserve_below_x:
                keep.add(x)
        start_index = 0
        i = 1
        while i < len(x_values):
            start_x = x_values[start_index]
            end_x = x_values[i]
            if self._safe_is_linear_segment(curve, start_x, end_x, precision=precision):
                i += 1
                continue
            prev_index = max(start_index + 1, i - 1)
            keep.add(x_values[prev_index])
            start_index = prev_index
            i = start_index + 1
        keep.add(x_values[-1])
        return sorted(set(float(x) for x in keep))

    def _segment_is_edge(self, curve, x0, x1, precision=6):
        x0 = float(x0)
        x1 = float(x1)

        if x1 <= x0:
            return False

        y0 = float(curve(x0))
        y1 = float(curve(x1))
        precision = int(precision)

        if round(y0, precision) == round(y1, precision):
            return True

        dx = x1 - x0

        if abs(dx) <= 1e-12:
            return False

        tolerance = max(10.0 ** -(precision + 2), 1e-12)

        checks = (
            0.125,
            0.25,
            0.375,
            0.5,
            0.625,
            0.75,
            0.875
        )

        for t in checks:
            x = x0 + dx * t
            actual = float(curve(x))
            expected = y0 + (y1 - y0) * t

            if actual != expected and abs(actual - expected) > tolerance:
                return False

        return True


    def _format_curve_points_with_edges(self, curve, x_values, precision=6):
        points = []
        x_values = sorted(set(float(x) for x in x_values))

        for index, x in enumerate(x_values):
            y = curve(x)
            x_str = f"{x:.{precision}f}".rstrip('0').rstrip('.')
            y_str = f"{y:.{precision}f}".rstrip('0').rstrip('.')
            marker = ""

            if index > 0:
                prev_x = x_values[index - 1]
                if self._segment_is_edge(curve, prev_x, x, precision=precision):
                    marker = "|e"

            points.append(f"{x_str}|{y_str}|{POINT_TENSION}{marker}")

        return points

    def _collapse_flat_runs_in_output(self, points):
        if len(points) <= 2:
            return points

        output = []
        i = 0

        def parse_y(point):
            try:
                return float(str(point).split("|")[1])
            except Exception:
                return None

        while i < len(points):
            y0 = parse_y(points[i])
            if y0 is None:
                output.append(points[i])
                i += 1
                continue

            run_start = i
            run_end = i

            while run_end + 1 < len(points):
                yn = parse_y(points[run_end + 1])
                if yn is None or abs(yn - y0) > 1e-12:
                    break
                run_end += 1

            output.append(points[run_start])
            if run_end > run_start:
                output.append(points[run_end])

            i = run_end + 1

        deduped = []
        for point in output:
            if not deduped or deduped[-1] != point:
                deduped.append(point)

        return deduped

    def _simplify_sampled_curve(
        self,
        dense_x,
        dense_y,
        protected=None,
        max_error=0.00008,
        max_span_ratio=0.12
    ):
        if len(dense_x) <= 2:
            return dense_x
        x_domain = max(dense_x[-1] - dense_x[0], 1e-9)
        protected_x = set(round(float(x), 10) for x in (protected or []))
        keep = {0, len(dense_x) - 1}
        for i, x in enumerate(dense_x):
            if round(float(x), 10) in protected_x:
                keep.add(i)
        stack = [(0, len(dense_x) - 1)]
        while stack:
            left, right = stack.pop()
            if right - left <= 1:
                continue
            protected_inside = [i for i in range(left + 1, right) if i in keep]
            if protected_inside:
                mid_target = (left + right) / 2.0
                mid = min(protected_inside, key=lambda i: abs(i - mid_target))
                stack.append((left, mid))
                stack.append((mid, right))
                continue
            x_left = dense_x[left]
            x_right = dense_x[right]
            y_left = dense_y[left]
            y_right = dense_y[right]
            dx = x_right - x_left
            if abs(dx) <= 1e-12:
                continue
            max_err = -1.0
            split_idx = None
            for i in range(left + 1, right):
                t = (dense_x[i] - x_left) / dx
                y_interp = y_left + (y_right - y_left) * t
                err = abs(dense_y[i] - y_interp)
                if err > max_err:
                    max_err = err
                    split_idx = i
            span_too_large = (x_right - x_left) > max(float(max_span_ratio), 0.0) * x_domain
            if split_idx is not None and (max_err > max_error or span_too_large):
                keep.add(split_idx)
                stack.append((left, split_idx))
                stack.append((split_idx, right))
        return [dense_x[i] for i in sorted(keep)]
    def _resolve_mode_x_values(self, curve, x_values, point_count, precision, protected=None, preserve_below_x=0.0):
        mode = str(self.point_reduction_mode or "optimal").strip().lower()
        if mode == "safe":
            mode = "normal"
        if mode not in ["optimal", "normal", "aggressive"]:
            mode = "optimal"

        x_values = sorted(set(float(x) for x in x_values))
        x_values = self._safe_protect_flat_boundaries(curve, x_values, precision=precision, protected=protected)
        x_values = self._safe_strict_linear_cleanup(
            curve,
            x_values,
            precision=precision,
            protected=protected,
            preserve_below_x=preserve_below_x
        )

        if mode == "normal":
            max_points = max(8, int(round(int(point_count) * 0.75)))
        elif mode == "aggressive":
            max_points = max(6, int(round(int(point_count) * 0.55)))
        else:
            max_points = int(point_count)

        return self._enforce_point_limit(
            curve,
            x_values,
            max_points=max_points,
            protected=protected,
            preserve_below_x=preserve_below_x
        )

    def _best_priority_split(self, x_values, y_values, left, right):
        if right - left <= 1:
            return None
        x_left = x_values[left]
        x_right = x_values[right]
        y_left = y_values[left]
        y_right = y_values[right]
        dx = x_right - x_left
        if abs(dx) <= 1e-12:
            return None
        best_error = -1.0
        best_index = None
        for i in range(left + 1, right):
            t = (x_values[i] - x_left) / dx
            expected = y_left + (y_right - y_left) * t
            error = abs(y_values[i] - expected)
            if error > best_error:
                best_error = error
                best_index = i
        if best_index is None or best_error <= 1e-15:
            return None
        return best_error, x_right - x_left, best_index

    def _push_priority_segment(self, heap, x_values, y_values, left, right):
        split = self._best_priority_split(x_values, y_values, left, right)
        if split is None:
            return
        error, span, split_index = split
        heapq.heappush(heap, (-error, -span, left, right, split_index))

    def _enforce_point_limit(self, curve, x_values, max_points, protected=None, preserve_below_x=0.0):
        x_values = sorted(set(float(x) for x in x_values))
        max_points = max(2, int(max_points))
        if len(x_values) <= max_points:
            return x_values
        protected_values = set(round(float(x), 10) for x in (protected or []))
        hard_keep_indices = {0, len(x_values) - 1}
        for index, x in enumerate(x_values):
            rx = round(float(x), 10)
            if rx in protected_values:
                hard_keep_indices.add(index)
        if len(hard_keep_indices) >= max_points:
            return [x_values[i] for i in sorted(hard_keep_indices)]

        y_values = [float(curve(x)) for x in x_values]
        keep_indices = set(hard_keep_indices)
        heap = []
        ordered_keep = sorted(keep_indices)
        for left, right in zip(ordered_keep, ordered_keep[1:]):
            self._push_priority_segment(heap, x_values, y_values, left, right)

        while len(keep_indices) < max_points and heap:
            _, _, left, right, split_index = heapq.heappop(heap)
            if split_index in keep_indices or not (left < split_index < right):
                continue
            if any(left < index < right for index in keep_indices):
                continue
            keep_indices.add(split_index)
            self._push_priority_segment(heap, x_values, y_values, left, split_index)
            self._push_priority_segment(heap, x_values, y_values, split_index, right)

        return [x_values[i] for i in sorted(keep_indices)]
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
        original_max_input = max_input
        curve = self._apply_transition_smoothing(curve, args, original_max_input, precision=precision)
        effective_max_input = self._safe_effective_end_x(curve, max_input, precision=precision)
        max_input = max(effective_max_input, 0.0)
        if self.mode_name == "lut":
            lut_points = parse_lookup_points(args.get("lookup_points", []))
            if lut_points:
                velocity = bool(args.get("lut_velocity", True))
                if not velocity:
                    x_values = sorted(set(float(x) for x, _ in lut_points))
                    protected = set()
                    if x_values:
                        protected.update({x_values[0], x_values[-1]})
                    transition_anchors = self._transition_smoothing_anchors(curve)
                    protected.update(transition_anchors)
                    x_values = sorted(set(float(x) for x in x_values + transition_anchors))
                    x_values = self._resolve_mode_x_values(
                        curve,
                        x_values,
                        point_count=point_count,
                        precision=precision,
                        protected=protected
                    )
                    points = self._format_curve_points_with_edges(
                        curve,
                        x_values,
                        precision=precision
                    )
                    return self._collapse_flat_runs_in_output(points)
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
                protected = set(float(x) for x, _ in lut_points)
                if sampled_x:
                    protected.update({sampled_x[0], sampled_x[-1]})
                transition_anchors = self._transition_smoothing_anchors(curve)
                protected.update(transition_anchors)
                sampled_x = sorted(set(float(x) for x in sampled_x + transition_anchors))
                sampled_x = self._resolve_mode_x_values(
                    curve,
                    sampled_x,
                    point_count=point_count,
                    precision=precision,
                    protected=protected
                )
                points = self._format_curve_points_with_edges(
                    curve,
                    sampled_x,
                    precision=precision
                )
                return self._collapse_flat_runs_in_output(points)
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
        protected = {0.0, max_input, original_max_input}
        transition_anchors = self._transition_smoothing_anchors(curve)
        protected.update(transition_anchors)
        x_values = sorted(set(float(x) for x in x_values + transition_anchors))
        flat_segments = self._exact_flat_segments(curve, original_max_input)
        rounded_flat_segments = self._rounded_flat_segments(curve, original_max_input, precision=precision)
        for segment in rounded_flat_segments:
            if not any(
                abs(segment[0] - existing[0]) <= 1e-10 and abs(segment[1] - existing[1]) <= 1e-10
                for existing in flat_segments
            ):
                flat_segments.append(segment)
        for start_x, end_x, _ in flat_segments:
            protected.add(float(start_x))
            protected.add(float(end_x))
            if start_x <= max_input:
                x_values.append(float(start_x))
            if end_x <= max_input:
                x_values.append(float(end_x))
        flat_tail_start = self._safe_find_flat_tail_start(curve, original_max_input, precision=precision)
        if flat_tail_start is not None:
            protected.add(float(flat_tail_start))
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
        if flat_tail_start is not None and flat_tail_start <= max_input:
            x_values.append(float(flat_tail_start))
        adaptive_values = self._adaptive_x_values(
                curve,
                args,
                point_count=max(point_count, len(x_values)),
                max_input=max_input,
                precision=precision,
                protected=protected
            )
        x_values = sorted(set(float(x) for x in x_values + adaptive_values))
        x_values = self._remove_near_exact_flat_boundary_points(
                curve,
                x_values,
                flat_segments,
                precision=precision
            )
        x_values = sorted(set(float(x) for x in x_values))
        preserve_below_x = 0.0
        if self.mode_name == "power":
            preserve_below_x = max_input * 0.25
        x_values = self._resolve_mode_x_values(
            curve,
            x_values,
            point_count=point_count,
            precision=precision,
            protected=protected,
            preserve_below_x=preserve_below_x
        )
        x_values = self._remove_near_exact_flat_boundary_points(
            curve,
            x_values,
            flat_segments,
            precision=precision
        )
        if self.mode_name == "power" and x_values:
            exact_flat_endpoints = set()
            for start_x, end_x, _ in flat_segments:
                exact_flat_endpoints.add(round(float(start_x), 10))
                exact_flat_endpoints.add(round(float(end_x), 10))
            x_values = [
                x for x in x_values
                if x > 1e-12 or round(float(x), 10) in exact_flat_endpoints
            ]
            if not x_values:
                x_values = [max_input]
        if original_max_input > max_input:
            extra_values = [original_max_input]
            if flat_tail_start is not None:
                extra_values.append(flat_tail_start)
            for start_x, end_x, _ in flat_segments:
                extra_values.extend([start_x, end_x])
            x_values = sorted(set(float(x) for x in x_values + extra_values))
            x_values = self._remove_near_exact_flat_boundary_points(
                curve,
                x_values,
                flat_segments,
                precision=precision
            )
        points = self._format_curve_points_with_edges(
            curve,
            x_values,
            precision=precision
        )
        return self._collapse_flat_runs_in_output(points)
    def estimate_right_slope(self, args, max_input):
        curve = self._build_curve(args)
        x = max(float(max_input), 0.0)
        curve = self._apply_transition_smoothing(curve, args, x, precision=6)
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
        curve = self._apply_transition_smoothing(curve, args, max_input, precision=precision)
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
        print(f"\n{GREEN}[OK] Profile saved to {filename}{RESET}")
def estimate_heuristic_max_input(mode, curve_type, cap_mode, args):
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
            exponent = max(float(args.get("exponent", 2.0)), 1e-12)
            cap_y = args.get("cap_y", 0.0) - 1.0
            if accel > 0 and exponent != 1 and abs(cap_y) > 1e-12:
                cap_y_abs = abs(cap_y)
                cap_x = (accel * offset + safe_pow(cap_y_abs / exponent, 1 / (exponent - 1))) / accel
                accel_raised = safe_pow(accel, exponent - 1.0)
                base_at_cap = accel_raised * safe_pow(max(cap_x - offset, 1e-12), exponent) / max(cap_x, 1e-12)
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
        offset_x = safe_divide(safe_pow(output_offset / (exponent_power + 1.0), 1.0 / exponent_power), scale) if output_offset > 0 else 0.0
        power_base = max(120.0, offset_x * 2.5)
        if cap_mode in ["in", "io"] and cap_x > 0:
            return min(max(power_base, cap_x * 2.5, 200.0), 1000.0)
        if cap_mode == "out" and curve_type == "gain" and cap_y > 0:
            cap_x = safe_divide(safe_pow(cap_y / (exponent_power + 1.0), 1.0 / exponent_power), scale)
            base_at_cap = safe_pow(scale * cap_x, exponent_power)
            constant_b = (base_at_cap - cap_y) * cap_x
            tail_cover = bounded_tail_cover(cap_x, constant_b, cap_y)
            return min(max(power_base, cap_x * 2.5, tail_cover, 200.0), 1000.0)
        return min(max(power_base, 200.0), 1000.0)
    return base

def estimate_default_max_input(mode, curve_type, cap_mode, args):
    fallback = estimate_heuristic_max_input(mode, curve_type, cap_mode, args)
    try:
        generator = CurveGenerator(mode_name=mode, curve_type=curve_type, cap_mode=cap_mode)
        curve = generator._build_curve(args)
        anchors = {0.0}
        if mode in ["classic/linear", "natural"]:
            anchors.add(float(args.get("input_offset", 0.0)))
        if mode == "jump":
            anchors.add(float(args.get("cap_x", 15.0)))
        if mode == "synchronous":
            anchors.add(float(args.get("sync_speed", 5.0)))
        if mode == "motivity (1.6.1)":
            anchors.add(float(args.get("midpoint", 5.0)))
        if mode == "power":
            offset_bp = generator._power_offset_breakpoint(args)
            if offset_bp is not None:
                anchors.add(float(offset_bp))
        cap_breakpoint = generator._special_breakpoint(args)
        if cap_breakpoint is not None:
            anchors.add(float(cap_breakpoint))
        if mode == "lut":
            points = parse_lookup_points(args.get("lookup_points", []))
            anchors.update(float(x) for x, _ in points)

        anchors = {
            float(x)
            for x in anchors
            if math.isfinite(float(x)) and float(x) >= 0.0
        }
        anchor_max = max(anchors or {0.0})
        lower_bound = max(30.0, anchor_max * 1.12, fallback * 0.05)
        hard_max = min(max(fallback * 3.0, lower_bound * 3.0, 300.0), 5000.0)
        if mode == "lut" and anchor_max > 0:
            hard_max = min(max(anchor_max * 2.5, 200.0), 5000.0)

        sample_x = {0.0, lower_bound, fallback, hard_max}
        sample_x.update(anchors)
        linear_count = 180
        for i in range(linear_count):
            t = i / max(1, linear_count - 1)
            sample_x.add(hard_max * t)
            sample_x.add(hard_max * (t ** 2.0))
        log_start = max(1e-4, min(max(0.001, lower_bound / 1000.0), 1.0))
        log_stop = max(hard_max, log_start * 2.0)
        log_min = math.log(log_start)
        log_max = math.log(log_stop)
        for i in range(linear_count):
            t = i / max(1, linear_count - 1)
            sample_x.add(math.exp(log_min + (log_max - log_min) * t))

        samples = []
        for x in sorted(sample_x):
            x = min(max(float(x), 0.0), hard_max)
            if not math.isfinite(x):
                continue
            try:
                y = float(curve(x))
            except Exception:
                continue
            if math.isfinite(y):
                samples.append((x, y))
        if len(samples) < 8:
            return fallback

        y_values = [y for _, y in samples]
        y_min = min(y_values)
        y_max = max(y_values)
        y_scale = max(y_max - y_min, max(abs(y) for y in y_values), 1.0)
        tail_tolerance = max(y_scale * 0.012, 0.01)

        best = None
        for i, (x, y) in enumerate(samples):
            if x < lower_bound:
                continue
            future = [fy for _, fy in samples[i:]]
            if len(future) < 8:
                break
            future_range = max(future) - min(future)
            if future_range <= tail_tolerance:
                best = x
                break

        if best is None:
            effective = generator._adaptive_effective_max_input(curve, fallback, precision=6)
            if effective < fallback:
                best = effective
            else:
                best = fallback

        padded = best * 1.08 if best > 0 else fallback
        min_reasonable = max(30.0, anchor_max * 1.04)
        max_reasonable = max(fallback * 1.5, min_reasonable)
        if best < fallback:
            return max(min_reasonable, padded)
        return min(max(padded, min_reasonable), max_reasonable)
    except Exception:
        return fallback
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
            prefix = menu_pointer(i == selected)
            if value == "generate":
                print()
                color = GREEN if i != selected else CYAN
            else:
                color = CYAN if i == selected else WHITE
            label_colored = color_gui_brackets(label, color)
            print(f"{prefix}{color}{label_colored}{RESET}")
        if note:
            print(f"\n{YELLOW}{note}{RESET}")
        print(f"\n{GRAY}Use UP/DOWN to move | ENTER to edit/select | ESC to return to menu{RESET}")
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
            parsed = parse_numeric_expression(value)
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
            themed_number_error(" Invalid input. Enter a valid number (examples: 1.5, 2, 1/3, sqrt(1.5)).")
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
            smooth_transitions = get_smooth_transition_mode(last)
            smooth_transition_strength = get_smooth_transition_strength(last)
            clear()
            print(sep(70))
            print(f" {CYAN}IMPORTING RAWACCEL SETTINGS{RESET}")
            print(sep(70))
            print(f"\n{BLUE}Source:{RESET} {settings_path}")
            print(f"{BLUE}Profiles found:{RESET} {len(profiles)}")
            print(f"{BLUE}Output points:{RESET} {point_count}")
            print(f"{BLUE}Precision:{RESET} {precision}")
            print(f"{BLUE}Point reduction:{RESET} {format_reduction_label(point_reduction_mode)}")
            print(f"{BLUE}Smooth transitions:{RESET} {format_smooth_transition_label(smooth_transitions)}")
            print(f"\n{YELLOW}Building CustomCurve profile data...{RESET}\n")
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
                        point_reduction_mode=point_reduction_mode,
                        smooth_transition_strength=smooth_transition_strength
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
                    print(f"{GREEN} [OK] {raw_profile_name}: generated profile data{RESET}")
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
            filename = str(last.get("filename", "profile.cc4"))
            if result_type == "file":
                saved_files, first_filename = result_value
                filename = first_filename or filename
            save_last_config({
                "profile_name": import_profile_name,
                "mode": "import from settings.json",
                "point_count": point_count,
                "point_reduction_mode": point_reduction_mode,
                "precision": precision,
                "smooth_transitions": smooth_transitions,
                "filename": filename,
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
        smooth_transitions = get_smooth_transition_mode(last)
        smooth_transition_strength = get_smooth_transition_strength(last)
        max_input = estimate_default_max_input(mode, curve_type, cap_mode, args)
        screen_header("GENERATING CURVE", 70)
        print(f"\n{BLUE}Profile:{RESET} {profile_name}")
        print(f"{BLUE}Mode:{RESET} {mode}")
        print(f"{BLUE}Curve type:{RESET} {curve_type.title()}")
        print(f"{BLUE}Cap mode:{RESET} {cap_mode.upper()}")
        print(f"{BLUE}Output points:{RESET} {point_count}")
        print(f"{BLUE}Precision:{RESET} {precision}")
        print(f"{BLUE}Point reduction:{RESET} {format_reduction_label(point_reduction_mode)}")
        print(f"{BLUE}Smooth transitions:{RESET} {format_smooth_transition_label(smooth_transitions)}")
        print(f"{BLUE}Auto max input:{RESET} {max_input:.6f}".rstrip("0").rstrip("."))
        print(f"\n{YELLOW}Building CustomCurve profile data...{RESET}")
        generator = CurveGenerator(
            mode_name=mode,
            curve_type=curve_type,
            cap_mode=cap_mode,
            point_reduction_mode=point_reduction_mode,
            smooth_transition_strength=smooth_transition_strength
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
            filename = str(last.get("filename", "profile.cc4"))
        elif result_type == "file":
            saved_files, first_filename = result_value
            filename = first_filename or normalize_cc4_filename(profile_name)
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
            "smooth_transitions": smooth_transitions,
            "filename": filename
        })
        continue
if __name__ == "__main__":
    main()
