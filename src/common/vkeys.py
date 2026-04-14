"""A module for simulating low-level keyboard and mouse key presses.

Uses Interception driver for kernel-level input injection.
"""

from src.common.decorators import run_if_enabled

# Interception 驱动初始化
_INTERCEPTION_AVAILABLE = False
_interception_driver = None

try:
    from src.common.interception_input import get_interception
    _interception_driver = get_interception()
    _INTERCEPTION_AVAILABLE = _interception_driver.is_available
    if not _INTERCEPTION_AVAILABLE:
        print(f"[!] Interception 不可用: {_interception_driver.error_message}")
except Exception as e:
    print(f"[!] 初始化 Interception 失败 ({e})")

# https://docs.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes?redirectedfrom=MSDN
# Do not add 'alt' to KEY_MAP: it does not register in MapleStory when sent via SendInput.
KEY_MAP = {
    'left': 0x25,   # Arrow keys
    'up': 0x26,
    'right': 0x27,
    'down': 0x28,

    'backspace': 0x08,      # Special keys
    'tab': 0x09,
    'enter': 0x0D,
    'shift': 0x10,
    'ctrl': 0x11,
    'caps lock': 0x14,
    'esc': 0x1B,
    'space': 0x20,
    'page up': 0x21,
    'page down': 0x22,
    'end': 0x23,
    'home': 0x24,
    'insert': 0x2D,
    'delete': 0x2E,

    '0': 0x30,      # Numbers
    '1': 0x31,
    '2': 0x32,
    '3': 0x33,
    '4': 0x34,
    '5': 0x35,
    '6': 0x36,
    '7': 0x37,
    '8': 0x38,
    '9': 0x39,

    'a': 0x41,      # Letters
    'b': 0x42,
    'c': 0x43,
    'd': 0x44,
    'e': 0x45,
    'f': 0x46,
    'g': 0x47,
    'h': 0x48,
    'i': 0x49,
    'j': 0x4A,
    'k': 0x4B,
    'l': 0x4C,
    'm': 0x4D,
    'n': 0x4E,
    'o': 0x4F,
    'p': 0x50,
    'q': 0x51,
    'r': 0x52,
    's': 0x53,
    't': 0x54,
    'u': 0x55,
    'v': 0x56,
    'w': 0x57,
    'x': 0x58,
    'y': 0x59,
    'z': 0x5A,

    'f1': 0x70,     # Functional keys
    'f2': 0x71,
    'f3': 0x72,
    'f4': 0x73,
    'f5': 0x74,
    'f6': 0x75,
    'f7': 0x76,
    'f8': 0x77,
    'f9': 0x78,
    'f10': 0x79,
    'f11': 0x7A,
    'f12': 0x7B,
    'num lock': 0x90,
    'scroll lock': 0x91,

    ';': 0xBA,      # Special characters
    '=': 0xBB,
    ',': 0xBC,
    '-': 0xBD,
    '.': 0xBE,
    '/': 0xBF,
    '`': 0xC0,
    '[': 0xDB,
    '\\': 0xDC,
    ']': 0xDD,
    "'": 0xDE
}


#################################
#           Functions           #
#################################
@run_if_enabled
def key_down(key):
    """
    Simulates a key-down action via Interception driver.
    Can be cancelled by Bot.toggle_enabled.

    :param key:     The key to press.
    :return:        None
    """
    key = key.lower()
    if key not in KEY_MAP:
        print(f"Invalid keyboard input: '{key}'.")
        return

    vk_code = KEY_MAP[key]
    if _INTERCEPTION_AVAILABLE:
        _interception_driver.key_down(key, vk_code)
    else:
        print(f"[!] Interception not available, cannot press '{key}'")


def key_up(key):
    """
    Simulates a key-up action via Interception driver.
    Cannot be cancelled by Bot.toggle_enabled.

    :param key:     The key to release.
    :return:        None
    """
    key = key.lower()
    if key not in KEY_MAP:
        print(f"Invalid keyboard input: '{key}'.")
        return

    vk_code = KEY_MAP[key]
    if _INTERCEPTION_AVAILABLE:
        _interception_driver.key_up(key, vk_code)


@run_if_enabled
def press(key, n, down_time=0.05, up_time=0.1):
    """
    Presses KEY N times via Interception driver.

    :param key:         The keyboard input to press.
    :param n:           Number of times to press KEY.
    :param down_time:   Duration of down-press (in seconds).
    :param up_time:     Duration of release (in seconds).
    :return:            None
    """
    if _INTERCEPTION_AVAILABLE:
        _interception_driver.press(key, n, down_time, up_time)


@run_if_enabled
def click(position, button='left'):
    """
    Simulate a mouse click with BUTTON at POSITION via Interception driver.
    :param position:    The (x, y) position at which to click.
    :param button:      Either the left or right mouse button.
    :return:            None
    """

    if button not in ['left', 'right']:
        print(f"'{button}' is not a valid mouse button.")
        return

    if _INTERCEPTION_AVAILABLE:
        _interception_driver.click(position, button)
