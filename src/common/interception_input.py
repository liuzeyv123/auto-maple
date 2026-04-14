"""Interception driver-level keyboard/mouse input simulation.

Uses local interception.dll for kernel-level input injection.
Based on official interception.h definitions.
"""

import os
import time
import ctypes
import threading
from ctypes import wintypes
from ctypes import CFUNCTYPE
from random import random

_DLL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'Interception', 'library', 'x64', 'interception.dll'
)

_dll = None
_ctx = None

# Constants from interception.h
INTERCEPTION_MAX_KEYBOARD = 10
INTERCEPTION_MAX_MOUSE = 10
INTERCEPTION_MAX_DEVICE = INTERCEPTION_MAX_KEYBOARD + INTERCEPTION_MAX_MOUSE

INTERCEPTION_KEY = lambda D: ((D) + 1)
INTERCEPTION_MOUSE = lambda D: (INTERCEPTION_MAX_KEYBOARD + (D) + 1)

INTERCEPTION_KEY_DOWN = 0x00
INTERCEPTION_KEY_UP = 0x01
INTERCEPTION_KEY_E0 = 0x02
INTERCEPTION_FILTER_KEY_NONE = 0x0000

INTERCEPTION_MOUSE_LEFT_BUTTON_DOWN = 0x001
INTERCEPTION_MOUSE_LEFT_BUTTON_UP = 0x002
INTERCEPTION_MOUSE_RIGHT_BUTTON_DOWN = 0x004
INTERCEPTION_MOUSE_RIGHT_BUTTON_UP = 0x008
INTERCEPTION_MOUSE_MOVE_ABSOLUTE = 0x001
INTERCEPTION_FILTER_MOUSE_NONE = 0x0000

# VK -> Set 1 ScanCode mapping (US keyboard layout)
# Reference: https://www.win.tue.nl/~aeb/linux/kbd/scancodes-1.html
VK_TO_SC = {
    # Letters (row by row)
    0x41: 0x1E,  # a
    0x42: 0x30,  # b
    0x43: 0x2E,  # c
    0x44: 0x20,  # d
    0x45: 0x12,  # e
    0x46: 0x21,  # f
    0x47: 0x22,  # g
    0x48: 0x23,  # h
    0x49: 0x17,  # i
    0x4A: 0x24,  # j
    0x4B: 0x25,  # k
    0x4C: 0x26,  # l
    0x4D: 0x32,  # m
    0x4E: 0x31,  # n
    0x4F: 0x18,  # o
    0x50: 0x19,  # p
    0x51: 0x10,  # q
    0x52: 0x13,  # r
    0x53: 0x1F,  # s
    0x54: 0x14,  # t
    0x55: 0x16,  # u
    0x56: 0x2F,  # v
    0x57: 0x11,  # w
    0x58: 0x2D,  # x
    0x59: 0x15,  # y
    0x5A: 0x2C,  # z

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

    # Arrow keys + Navigation (need E0 prefix)
    0x25: 0x4B,  # Left   (E0 prefix)
    0x26: 0x48,  # Up     (E0 prefix)
    0x27: 0x4D,  # Right  (E0 prefix)
    0x28: 0x50,  # Down   (E0 prefix)
    0x21: 0x49,  # PgUp   (E0 prefix)
    0x22: 0x51,  # PgDown (E0 prefix)
    0x23: 0x4F,  # End    (E0 prefix)
    0x24: 0x47,  # Home   (E0 prefix)
    0x2D: 0x52,  # Insert (E0 prefix)
    0x2E: 0x53,  # Delete (E0 prefix)

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

    # Special keys
    0x08: 0x0E,  # Backspace
    0x09: 0x0F,  # Tab
    0x0D: 0x1C,  # Enter
    0x10: 0x2A,  # LShift
    0x11: 0x1D,  # LCtrl
    0x14: 0x3A,  # CapsLock
    0x1B: 0x01,  # Esc
    0x20: 0x39,  # Space

    # Punctuation / Symbols
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

    # Numpad Enter (needs E0 prefix)
    0x36: 0x1C,

    # NumLock/ScrollLock (need E0 prefix)
    0x90: 0x45,  # NumLock
    0x91: 0x46,  # ScrollLock
}

_E0_KEYS = frozenset({
    0x25, 0x26, 0x27, 0x28,
    0x21, 0x22, 0x23, 0x24,
    0x2D, 0x2E, 0x36, 0x90, 0x91,
})


class InterceptionKeyStroke(ctypes.Structure):
    """Matches InterceptionKeyStroke from interception.h:
        unsigned short code, state;
        unsigned int information;
    """
    _fields_ = [
        ("code", wintypes.USHORT),
        ("state", wintypes.USHORT),
        ("information", wintypes.UINT),
    ]


class InterceptionMouseStroke(ctypes.Structure):
    """Matches InterceptionMouseStroke from interception.h:
        unsigned short state, flags;
        short rolling;
        int x, y;
        unsigned int information;
    """
    _fields_ = [
        ("state", wintypes.USHORT),
        ("flags", wintypes.USHORT),
        ("rolling", wintypes.SHORT),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("information", wintypes.UINT),
    ]


class InterceptionDriver:
    def __init__(self):
        self._kbd_dev = INTERCEPTION_KEY(0)
        self._ms_dev = INTERCEPTION_MOUSE(0)
        self._lock = threading.Lock()
        self._ok = False
        self._err = None
        self._init()

    @property
    def is_available(self):
        return self._ok

    @property
    def error_message(self):
        return self._err

    def _init(self):
        global _dll, _ctx
        if not os.path.exists(_DLL_PATH):
            self._err = f"DLL not found: {_DLL_PATH}"
            print(f"[!] {self._err}")
            return

        try:
            _dll = ctypes.WinDLL(_DLL_PATH)

            # Function prototypes matching interception.h exactly
            _dll.interception_create_context.restype = ctypes.c_void_p
            _dll.interception_create_context.argtypes = []

            _dll.interception_destroy_context.restype = None
            _dll.interception_destroy_context.argtypes = [ctypes.c_void_p]

            # void interception_set_filter(context, predicate, filter)
            # predicate is: int (*InterceptionPredicate)(InterceptionDevice device)
            _PredicateFunc = CFUNCTYPE(ctypes.c_int, ctypes.c_int)
            _dll.interception_set_filter.restype = None
            _dll.interception_set_filter.argtypes = [ctypes.c_void_p, _PredicateFunc, wintypes.USHORT]

            # int interception_send(context, device, stroke*, nstroke)
            # InterceptionStroke is char[sizeof(InterceptionMouseStroke)]
            _STROKE_SIZE = ctypes.sizeof(InterceptionMouseStroke)
            StrokeBuffer = ctypes.c_byte * _STROKE_SIZE
            _dll.interception_send.restype = ctypes.c_int
            _dll.interception_send.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(StrokeBuffer), wintypes.UINT]

            _dll.interception_is_keyboard.restype = ctypes.c_int
            _dll.interception_is_keyboard.argtypes = [ctypes.c_int]

            _dll.interception_is_mouse.restype = ctypes.c_int
            _dll.interception_is_mouse.argtypes = [ctypes.c_int]

            # Create context
            _ctx = _dll.interception_create_context()
            if not _ctx:
                self._err = "Cannot create context - run install-interception /install as admin"
                print(f"[!] {self._err}")
                return

            # No-op predicate function (always return 0 -> intercept nothing)
            @_PredicateFunc
            def _no_op_predicate(device):
                return 0

            # Set filters to intercept nothing (pass-through mode)
            _dll.interception_set_filter(_ctx, _no_op_predicate, INTERCEPTION_FILTER_KEY_NONE)
            _dll.interception_set_filter(_ctx, _no_op_predicate, INTERCEPTION_FILTER_MOUSE_NONE)

            self._ok = True
            print("[~] Interception driver OK")

        except Exception as e:
            self._err = f"Init failed: {e}"
            print(f"[!] {self._err}")

    def _make_stroke_buffer(self):
        """Create an empty stroke buffer."""
        _STROKE_SIZE = ctypes.sizeof(InterceptionMouseStroke)
        return (ctypes.c_byte * _STROKE_SIZE)()

    def _send_key(self, vk_code, state):
        with self._lock:
            if not self._ok or _dll is None or _ctx is None:
                return False
            try:
                sc = VK_TO_SC.get(vk_code, 0)
                if sc == 0:
                    return False
                st = state | (INTERCEPTION_KEY_E0 if vk_code in _E0_KEYS else 0)

                buf = self._make_stroke_buffer()
                ks = InterceptionKeyStroke.from_buffer(buf)
                ks.code = sc & 0xFF
                ks.state = st
                ks.information = 0

                _dll.interception_send(_ctx, self._kbd_dev, buf, 1)
                return True
            except Exception as e:
                print(f"[!] Send failed: {e}")
                return False

    def _rdelay(self, a=0.002, b=0.008):
        return a + (b - a) * random()

    def key_down(self, key_name, vk_code=None):
        if vk_code is None:
            from src.common.vkeys import KEY_MAP as _KM
            vk_code = _KM.get(key_name.lower(), 0)
            if not vk_code:
                print(f"[!] Invalid key: '{key_name}'")
                return False
        time.sleep(self._rdelay())
        ok = self._send_key(vk_code, INTERCEPTION_KEY_DOWN)
        time.sleep(self._rdelay())
        return ok

    def key_up(self, key_name, vk_code=None):
        if vk_code is None:
            from src.common.vkeys import KEY_MAP as _KM
            vk_code = _KM.get(key_name.lower(), 0)
            if not vk_code:
                return False
        time.sleep(self._rdelay())
        ok = self._send_key(vk_code, INTERCEPTION_KEY_UP)
        time.sleep(self._rdelay())
        return ok

    def press(self, key_name, n=1, down_time=0.05, up_time=0.1):
        from src.common.vkeys import KEY_MAP as _KM
        vk_code = _KM.get(key_name.lower(), 0)
        if not vk_code:
            print(f"[!] Invalid key: '{key_name}'")
            return
        for _ in range(n):
            self.key_down(key_name, vk_code)
            time.sleep(down_time * (0.7 + 0.6 * random()))
            self.key_up(key_name, vk_code)
            time.sleep(up_time * (0.7 + 0.6 * random()))

    def click(self, position, button='left'):
        with self._lock:
            if not self._ok or _dll is None or _ctx is None:
                return
            try:
                ox = int((random() - 0.5) * 3)
                oy = int((random() - 0.5) * 3)
                tx = position[0] + ox
                ty = position[1] + oy

                df = INTERCEPTION_MOUSE_LEFT_BUTTON_DOWN if button == 'left' else INTERCEPTION_MOUSE_RIGHT_BUTTON_DOWN
                uf = INTERCEPTION_MOUSE_LEFT_BUTTON_UP if button == 'left' else INTERCEPTION_MOUSE_RIGHT_BUTTON_UP

                buf = self._make_stroke_buffer()
                ms = InterceptionMouseStroke.from_buffer(buf)
                ms.x = tx
                ms.y = ty
                ms.state = df
                ms.flags = INTERCEPTION_MOUSE_MOVE_ABSOLUTE
                ms.rolling = 0
                ms.information = 0

                _dll.interception_send(_ctx, self._ms_dev, buf, 1)
                time.sleep(self._rdelay())

                ms.state = uf
                _dll.interception_send(_ctx, self._ms_dev, buf, 1)

            except Exception as e:
                print(f"[!] Click failed: {e}")

    def close(self):
        global _ctx
        try:
            if _ctx and _dll:
                _dll.interception_destroy_context(_ctx)
            _ctx = None
            self._ok = False
        except Exception as e:
            print(f"[!] Close error: {e}")


_global_driver = None


def get_interception():
    global _global_driver
    if _global_driver is None:
        _global_driver = InterceptionDriver()
    return _global_driver
