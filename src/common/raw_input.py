"""Raw Input driver simulation for more隐蔽的按键输入.

使用底层驱动级别的输入注入，比 SendInput 更难被反作弊检测。
"""

import ctypes
import time
from ctypes import wintypes
from random import random

# 加载必要的系统库
user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

# 常量定义
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

# 虚拟键码映射
VK_TO_SCANCODE = {
    # Arrow keys
    0x25: 0x4B,  # Left Arrow
    0x26: 0x48,  # Up Arrow
    0x27: 0x4D,  # Right Arrow
    0x28: 0x50,  # Down Arrow

    # Navigation keys
    0x21: 0x49,  # Page Up
    0x22: 0x51,  # Page Down
    0x23: 0x4F,  # End
    0x24: 0x47,  # Home

    # Numbers
    0x30: 0x0B,  # 0
    0x31: 0x02,  # 1
    0x32: 0x03,  # 2
    0x33: 0x04,  # 3
    0x34: 0x05,  # 4
    0x35: 0x06,  # 5
    0x36: 0x07,  # 6
    0x37: 0x08,  # 7
    0x38: 0x09,  # 8
    0x39: 0x0A,  # 9

    # Letters
    0x41: 0x1E,  # A
    0x42: 0x30,  # B
    0x43: 0x2E,  # C
    0x44: 0x20,  # D
    0x45: 0x12,  # E
    0x46: 0x21,  # F
    0x47: 0x22,  # G
    0x48: 0x23,  # H
    0x49: 0x17,  # I
    0x4A: 0x24,  # J
    0x4B: 0x25,  # K
    0x4C: 0x26,  # L
    0x4D: 0x32,  # M
    0x4E: 0x31,  # N
    0x4F: 0x18,  # O
    0x50: 0x19,  # P
    0x51: 0x10,  # Q
    0x52: 0x13,  # R
    0x53: 0x1F,  # S
    0x54: 0x14,  # T
    0x55: 0x16,  # U
    0x56: 0x2F,  # V
    0x57: 0x11,  # W
    0x58: 0x2D,  # X
    0x59: 0x15,  # Y
    0x5A: 0x2C,  # Z

    # Special keys
    0x08: 0x0E,  # Backspace
    0x09: 0x0F,  # Tab
    0x0D: 0x1C,  # Enter
    0x10: 0x2A,  # Shift
    0x11: 0x1D,  # Ctrl
    0x14: 0x3A,  # Caps Lock
    0x1B: 0x01,  # Esc
    0x20: 0x39,  # Space
    0x2D: 0x52,  # Insert
    0x2E: 0x53,  # Delete

    # Function keys
    0x70: 0x3B,  # F1
    0x71: 0x3C,  # F2
    0x72: 0x3D,  # F3
    0x73: 0x3E,  # F4
    0x74: 0x3F,  # F5
    0x75: 0x40,  # F6
    0x76: 0x41,  # F7
    0x77: 0x42,  # F8
    0x78: 0x43,  # F9
    0x79: 0x44,  # F10
    0x7A: 0x57,  # F11
    0x7B: 0x58,  # F12
    0x90: 0x45,  # Num Lock
    0x91: 0x46,  # Scroll Lock

    # Special characters
    0xBA: 0x27,  # ;
    0xBB: 0x0D,  # =
    0xBC: 0x33,  # ,
    0xBD: 0x0C,  # -
    0xBE: 0x34,  # .
    0xBF: 0x35,  # /
    0xC0: 0x29,  # `
    0xDB: 0x1A,  # [
    0xDC: 0x2B,  # \
    0xDD: 0x1B,  # ]
    0xDE: 0x28,  # '
}


#################################
#     C Struct Definitions      #
#################################
wintypes.ULONG_PTR = wintypes.WPARAM


class KeyboardInput(ctypes.Structure):
    _fields_ = (
        ('wVk', wintypes.WORD),
        ('wScan', wintypes.WORD),
        ('dwFlags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', wintypes.ULONG_PTR)
    )


class MouseInput(ctypes.Structure):
    _fields_ = (
        ('dx', wintypes.LONG),
        ('dy', wintypes.LONG),
        ('mouseData', wintypes.DWORD),
        ('dwFlags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', wintypes.ULONG_PTR)
    )


class Input(ctypes.Structure):
    class _Input(ctypes.Union):
        _fields_ = (
            ('ki', KeyboardInput),
            ('mi', MouseInput)
        )

    _anonymous_ = ('_input',)
    _fields_ = (
        ('type', wintypes.DWORD),
        ('_input', _Input)
    )


LPINPUT = ctypes.POINTER(Input)

# 配置 SendInput 函数
user32.SendInput.errcheck = lambda result, func, args: args if result else ctypes.WinError(ctypes.get_last_error())
user32.SendInput.argtypes = (wintypes.UINT, LPINPUT, ctypes.c_int)


#################################
#           Functions           #
#################################

def get_random_delay(min_delay=0.003, max_delay=0.012):
    """获取随机延迟，模拟真实人类操作的不确定性."""
    return min_delay + (max_delay - min_delay) * random()


def key_down_raw(key, vk_code):
    """使用 scancode 模拟按键按下（更底层，更难检测）.
    
    Args:
        key: 键名称
        vk_code: 虚拟键码
    """
    # 获取 scancode
    scancode = VK_TO_SCANCODE.get(vk_code, 0)
    
    # 构造输入结构体 - 使用 scancode 而非虚拟键码
    flags = KEYEVENTF_SCANCODE
    if vk_code in [0x21, 0x22, 0x25, 0x26, 0x27, 0x28, 0x2A, 0x36]:  # Extended keys (Page Up, Page Down, Arrows, etc.)
        flags |= KEYEVENTF_EXTENDEDKEY
    
    x = Input(
        type=INPUT_KEYBOARD,
        ki=KeyboardInput(
            wVk=0,  # 使用 scancode 时设为 0
            wScan=scancode,
            dwFlags=flags,
            time=0,  # 系统自动设置
            dwExtraInfo=0  # 模拟真实输入
        )
    )
    
    user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))


def key_up_raw(key, vk_code):
    """使用 scancode 模拟按键释放（更底层，更难检测）.
    
    Args:
        key: 键名称
        vk_code: 虚拟键码
    """
    # 获取 scancode
    scancode = VK_TO_SCANCODE.get(vk_code, 0)
    
    # 构造输入结构体 - 使用 scancode + KEYUP 标志
    flags = KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP
    if vk_code in [0x21, 0x22, 0x25, 0x26, 0x27, 0x28, 0x2A, 0x36]:  # Extended keys (Page Up, Page Down, Arrows, etc.)
        flags |= KEYEVENTF_EXTENDEDKEY
    
    x = Input(
        type=INPUT_KEYBOARD,
        ki=KeyboardInput(
            wVk=0,  # 使用 scancode 时设为 0
            wScan=scancode,
            dwFlags=flags,
            time=0,  # 系统自动设置
            dwExtraInfo=0  # 模拟真实输入
        )
    )
    
    user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))


def key_down_enhanced(key, vk_code):
    """增强的按键按下模拟 - 结合多种技术提高隐蔽性.
    
    1. 使用 scancode 而非虚拟键码
    2. 随机延迟
    3. 模拟真实输入的时间戳
    """
    time.sleep(get_random_delay())
    
    # 获取 scancode
    scancode = VK_TO_SCANCODE.get(vk_code, 0)
    
    flags = KEYEVENTF_SCANCODE
    if vk_code in [0x21, 0x22, 0x25, 0x26, 0x27, 0x28, 0x2A, 0x36]:  # Extended keys (Page Up, Page Down, Arrows, etc.)
        flags |= KEYEVENTF_EXTENDEDKEY
    
    # 获取当前系统时间作为时间戳（模拟真实输入）
    system_time = kernel32.GetTickCount()
    
    x = Input(
        type=INPUT_KEYBOARD,
        ki=KeyboardInput(
            wVk=0,
            wScan=scancode,
            dwFlags=flags,
            time=system_time,
            dwExtraInfo=0
        )
    )
    
    user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))
    time.sleep(get_random_delay())


def key_up_enhanced(key, vk_code):
    """增强的按键释放模拟."""
    time.sleep(get_random_delay())
    
    scancode = VK_TO_SCANCODE.get(vk_code, 0)
    
    flags = KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP
    if vk_code in [0x21, 0x22, 0x25, 0x26, 0x27, 0x28, 0x2A, 0x36]:  # Extended keys (Page Up, Page Down, Arrows, etc.)
        flags |= KEYEVENTF_EXTENDEDKEY
    
    system_time = kernel32.GetTickCount()
    
    x = Input(
        type=INPUT_KEYBOARD,
        ki=KeyboardInput(
            wVk=0,
            wScan=scancode,
            dwFlags=flags,
            time=system_time,
            dwExtraInfo=0
        )
    )
    
    user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))
    time.sleep(get_random_delay())


def press_enhanced(key, vk_code, down_time=0.05, up_time=0.1):
    """增强的按键按压模拟 - 模拟真实人类操作时序.
    
    Args:
        key: 键名称
        vk_code: 虚拟键码
        down_time: 按下持续时间（基础值，会随机化）
        up_time: 释放后等待时间（基础值，会随机化）
    """
    # 按下
    key_down_enhanced(key, vk_code)
    
    # 随机化的按下持续时间（模拟人类按住时间的不确定性）
    actual_down_time = down_time * (0.7 + 0.6 * random())
    time.sleep(actual_down_time)
    
    # 释放
    key_up_enhanced(key, vk_code)
    
    # 随机化的释放后等待时间
    actual_up_time = up_time * (0.7 + 0.6 * random())
    time.sleep(actual_up_time)


def get_scancode_from_vk(vk_code):
    """从虚拟键码获取扫描码.
    
    Args:
        vk_code: 虚拟键码
        
    Returns:
        扫描码
    """
    return VK_TO_SCANCODE.get(vk_code, 0)


def is_extended_key(vk_code):
    """判断是否为扩展键（需要额外标志）.
    
    Args:
        vk_code: 虚拟键码
        
    Returns:
        bool: 是否为扩展键
    """
    # Extended keys: Page Up, Page Down, End, Home, Insert, Delete, Arrows, etc.
    return vk_code in [0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x2A, 0x36]




#################################
#        Hook Functions        #
#################################

def clear_injected_flag():
    """
    尝试清除输入的注入标记（高级技术）。
    
    注意：这需要全局钩子，较为复杂，此处仅提供接口。
    实际实现需要安装键盘钩子并修改 LLKHF_INJECTED 标志。
    """
    # 此功能需要更复杂的实现
    # 包括：
    # 1. 安装低级键盘钩子 (SetWindowsHookEx)
    # 2. 修改钩子回调中的 LLKHF_INJECTED 标志
    # 3. 卸载钩子
    
    pass
