"""A module for simulating low-level keyboard and mouse key presses."""

import ctypes
import time
import win32con
import win32api
from src.common.decorators import run_if_enabled
from ctypes import wintypes
from random import random

# 配置输入模式：'default' | 'raw' | 'enhanced'
INPUT_MODE = 'enhanced'  # 修改此处以切换输入模式

# Raw Input 模块（如果启用 raw 或 enhanced 模式）
if INPUT_MODE in ['raw', 'enhanced']:
    try:
        from src.common.raw_input import (
            key_down_raw, key_up_raw,
            key_down_enhanced, key_up_enhanced,
            press_enhanced
        )
        RAW_INPUT_AVAILABLE = True
    except ImportError:
        RAW_INPUT_AVAILABLE = False
        print("警告: raw_input 模块未找到，使用默认输入模式")
else:
    RAW_INPUT_AVAILABLE = False


user32 = ctypes.WinDLL('user32', use_last_error=True)

# 默认模式下的 SendInput 频率控制
_last_sendinput_time_default = 0.0
_MIN_SENDINPUT_INTERVAL_DEFAULT = 0.01  # 默认模式最小间隔

def _rate_limit_sendinput_default():
    """限制 SendInput 调用频率，防止句柄泄漏"""
    global _last_sendinput_time_default
    current_time = time.time()
    time_since_last = current_time - _last_sendinput_time_default
    if time_since_last < _MIN_SENDINPUT_INTERVAL_DEFAULT:
        time.sleep(_MIN_SENDINPUT_INTERVAL_DEFAULT - time_since_last)
    _last_sendinput_time_default = time.time()


INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

MAPVK_VK_TO_VSC = 0

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
#     C Struct Definitions      #
#################################
wintypes.ULONG_PTR = wintypes.WPARAM


class KeyboardInput(ctypes.Structure):
    _fields_ = (('wVk', wintypes.WORD),
                ('wScan', wintypes.WORD),
                ('dwFlags', wintypes.DWORD),
                ('time', wintypes.DWORD),
                ('dwExtraInfo', wintypes.ULONG_PTR))

    def __init__(self, *args, **kwargs):
        super(KeyboardInput, self).__init__(*args, **kwargs)
        if not self.dwFlags & KEYEVENTF_UNICODE:
            self.wScan = user32.MapVirtualKeyExW(self.wVk, MAPVK_VK_TO_VSC, 0)


class MouseInput(ctypes.Structure):
    _fields_ = (('dx', wintypes.LONG),
                ('dy', wintypes.LONG),
                ('mouseData', wintypes.DWORD),
                ('dwFlags', wintypes.DWORD),
                ('time', wintypes.DWORD),
                ('dwExtraInfo', wintypes.ULONG_PTR))


class HardwareInput(ctypes.Structure):
    _fields_ = (('uMsg', wintypes.DWORD),
                ('wParamL', wintypes.WORD),
                ('wParamH', wintypes.WORD))


class Input(ctypes.Structure):
    class _Input(ctypes.Union):
        _fields_ = (('ki', KeyboardInput),
                    ('mi', MouseInput),
                    ('hi', HardwareInput))

    _anonymous_ = ('_input',)
    _fields_ = (('type', wintypes.DWORD),
                ('_input', _Input))


LPINPUT = ctypes.POINTER(Input)


def err_check(result, _, args):
    if result == 0:
        raise ctypes.WinError(ctypes.get_last_error())
    else:
        return args


user32.SendInput.errcheck = err_check
user32.SendInput.argtypes = (wintypes.UINT, LPINPUT, ctypes.c_int)


#################################
#           Functions           #
#################################
@run_if_enabled
def key_down(key):
    """
    Simulates a key-down action. Can be cancelled by Bot.toggle_enabled.
    根据 INPUT_MODE 配置使用不同的输入方法：
    - 'default': 标准虚拟键码（可被检测）
    - 'raw': 扫描码（较难检测）
    - 'enhanced': 增强扫描码+时间戳+随机化（最难检测）
    
    :param key:     The key to press.
    :return:        None
    """

    key = key.lower()
    if key not in KEY_MAP.keys():
        print(f"Invalid keyboard input: '{key}'.")
    else:
        # 检查是否需要打印按键信息
        import src.common.config as config
        print_press_msg = False
        if hasattr(config.bot, 'command_book') and hasattr(config.bot.command_book, 'module'):
            module = config.bot.command_book.module
            print_press_msg = getattr(module, 'PRINT_PRESS_MSG', False)
        
        vk_code = KEY_MAP[key]
        
        # 根据 INPUT_MODE 选择输入方法
        if INPUT_MODE == 'enhanced' and RAW_INPUT_AVAILABLE:
            # 增强模式：扫描码 + 时间戳 + 高级随机化
            key_down_enhanced(key, vk_code)
        elif INPUT_MODE == 'raw' and RAW_INPUT_AVAILABLE:
            # Raw 模式：使用扫描码
            key_down_raw(key, vk_code)
        else:
            # 默认模式：标准虚拟键码
            time.sleep(0.005 + 0.01 * random())
            
            if print_press_msg:
                print(f"Key down: '{key}'")

            x = Input(type=INPUT_KEYBOARD, ki=KeyboardInput(wVk=vk_code))
            _rate_limit_sendinput_default()  # 限制频率
            user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))

            time.sleep(0.005 + 0.01 * random())


def key_up(key):
    """
    Simulates a key-up action. Cannot be cancelled by Bot.toggle_enabled.
    This is to ensure no keys are left in the 'down' state when the program pauses.
    根据 INPUT_MODE 配置使用不同的输入方法。
    
    :param key:     The key to press.
    :return:        None
    """

    key = key.lower()
    if key not in KEY_MAP.keys():
        print(f"Invalid keyboard input: '{key}'.")
    else:
        # 检查是否需要打印按键信息
        import src.common.config as config
        print_press_msg = False
        if hasattr(config.bot, 'command_book') and hasattr(config.bot.command_book, 'module'):
            module = config.bot.command_book.module
            print_press_msg = getattr(module, 'PRINT_PRESS_MSG', False)
        
        vk_code = KEY_MAP[key]
        
        # 根据 INPUT_MODE 选择输入方法
        if INPUT_MODE == 'enhanced' and RAW_INPUT_AVAILABLE:
            # 增强模式
            key_up_enhanced(key, vk_code)
        elif INPUT_MODE == 'raw' and RAW_INPUT_AVAILABLE:
            # Raw 模式
            key_up_raw(key, vk_code)
        else:
            # 默认模式
            time.sleep(0.005 + 0.01 * random())
            
            if print_press_msg:
                print(f"Key up: '{key}'")

            x = Input(type=INPUT_KEYBOARD, ki=KeyboardInput(wVk=vk_code, dwFlags=KEYEVENTF_KEYUP))
            _rate_limit_sendinput_default()  # 限制频率
            user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))

            time.sleep(0.005 + 0.01 * random())


@run_if_enabled
def press(key, n, down_time=0.05, up_time=0.1):
    """
    Presses KEY N times, holding it for DOWN_TIME seconds, and releasing for UP_TIME seconds.
    根据 INPUT_MODE 配置使用不同的输入方法。
    
    :param key:         The keyboard input to press.
    :param n:           Number of times to press KEY.
    :param down_time:   Duration of down-press (in seconds).
    :param up_time:     Duration of release (in seconds).
    :return:            None
    """

    # 检查是否需要打印按键信息
    import src.common.config as config
    print_press_msg = False
    if hasattr(config.bot, 'command_book') and hasattr(config.bot.command_book, 'module'):
        module = config.bot.command_book.module
        print_press_msg = getattr(module, 'PRINT_PRESS_MSG', False)
    
    # 根据 INPUT_MODE 选择输入方法
    if INPUT_MODE == 'enhanced' and RAW_INPUT_AVAILABLE:
        # 增强模式：使用 press_enhanced（已包含随机化）
        vk_code = KEY_MAP.get(key.lower(), 0)
        if vk_code:
            for _ in range(n):
                press_enhanced(key, vk_code, down_time, up_time)
    else:
        # 默认或 Raw 模式
        for _ in range(n):
            key_down(key)
            time.sleep(down_time * (0.8 + 0.4 * random()))
            key_up(key)
            time.sleep(up_time * (0.8 + 0.4 * random()))
    
    if print_press_msg:
        print(f"Pressed '{key}' {n} times")


@run_if_enabled
def click(position, button='left'):
    """
    Simulate a mouse click with BUTTON at POSITION.
    :param position:    The (x, y) position at which to click.
    :param button:      Either the left or right mouse button.
    :return:            None
    """

    if button not in ['left', 'right']:
        print(f"'{button}' is not a valid mouse button.")
    else:
        # 随机延迟
        time.sleep(0.005 + 0.01 * random())
        
        if button == 'left':
            down_event = win32con.MOUSEEVENTF_LEFTDOWN
            up_event = win32con.MOUSEEVENTF_LEFTUP
        else:
            down_event = win32con.MOUSEEVENTF_RIGHTDOWN
            up_event = win32con.MOUSEEVENTF_RIGHTUP
        
        # 鼠标移动到位置时添加随机偏移
        offset_x = int((random() - 0.5) * 3)
        offset_y = int((random() - 0.5) * 3)
        target_position = (position[0] + offset_x, position[1] + offset_y)
        win32api.SetCursorPos(target_position)
        
        # 随机延迟
        time.sleep(0.005 + 0.01 * random())
        
        win32api.mouse_event(down_event, target_position[0], target_position[1], 0, 0)
        
        # 随机延迟
        time.sleep(0.005 + 0.01 * random())
        
        win32api.mouse_event(up_event, target_position[0], target_position[1], 0, 0)
        
        # 随机延迟
        time.sleep(0.005 + 0.01 * random())
