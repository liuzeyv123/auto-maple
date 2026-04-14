"""一个用于跟踪游戏内有用信息的模块。

使用 PrintWindow(PW_RENDERFULLCONTENT) 进行窗口截图，
避免向 MapleStory 进程注入 GDI 句柄，解决句柄泄漏问题。
"""

import time
import gc
import cv2
import threading
import ctypes
import numpy as np
from src.common import config, utils
from ctypes import wintypes

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

# DPI 感知
user32.SetProcessDPIAware()

# GDI 常量
SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0
PW_RENDERFULLCONTENT = 2  # Windows 8.1+: DWM 直接返回合成缓存画面


# 小地图顶部到屏幕顶部的距离
MINIMAP_TOP_BORDER = 5

# 小地图其他三个边框的厚度
MINIMAP_BOTTOM_BORDER = 9

# 窗口模式下的像素偏移调整
WINDOWED_OFFSET_TOP = 36
WINDOWED_OFFSET_LEFT = 10

# 小地图的左上角和右下角
MM_TL_TEMPLATE = cv2.imread('assets/minimap_tl_template.png', 0)
MM_BR_TEMPLATE = cv2.imread('assets/minimap_br_template.png', 0)

MMT_HEIGHT = max(MM_TL_TEMPLATE.shape[0], MM_BR_TEMPLATE.shape[0])
MMT_WIDTH = max(MM_TL_TEMPLATE.shape[1], MM_BR_TEMPLATE.shape[1])

# 小地图上的玩家符号
PLAYER_TEMPLATE = cv2.imread('assets/player_template.png', 0)
PT_HEIGHT, PT_WIDTH = PLAYER_TEMPLATE.shape


class Capture:
    """
    一个跟踪玩家位置和各种游戏内事件的类。它不断更新
    config 模块，提供有关这些事件的信息。它还会注释并
    在弹出窗口中显示小地图。
    """

    def __init__(self):
        """初始化此 Capture 对象的主线程。"""

        config.capture = self

        self.frame = None
        self.minimap = {}
        self.minimap_ratio = 1
        self.minimap_sample = None
        self.window = {
            'left': 0,
            'top': 0,
            'width': 1366,
            'height': 768
        }
        # 缓存窗口句柄，避免重复调用 FindWindowW（句柄泄漏风险）
        self._window_handle = None

        # PrintWindow GDI 资源（只创建一次，永久复用，避免每帧分配/释放）
        self._window_dc = None      # MapleStory 窗口 DC (GetDC)
        self._mem_dc = None         # 内存 DC (CreateCompatibleDC)
        self._bitmap = None         # 兼容位图 (CreateCompatibleBitmap)
        self._old_bitmap = None     # 原始位图对象 (SelectObject 返回值，必须保存用于恢复)
        self._bmi = None            # BITMAPINFO 结构体 (GetDIBits 用)
        self._pixel_data = None     # 像素数据缓冲区 (ctypes.create_string_buffer)

        self.ready = False
        self.calibrated = False
        self.thread = threading.Thread(target=self._main)
        self.thread.daemon = True
        # 重用单个缓冲区进行屏幕截图，以避免每 ~1 毫秒分配 4+ MiB（ArrayMemoryError）。
        self._frame_buffer = None
        self._gc_counter = 0  # 周期性垃圾回收的计数器
        self._window_validated = False  # 窗口信息验证标志，避免重复 GetWindowRect 调用
        self._window_check_counter = 0  # 窗口句柄检查计数器，大幅降低检查频率
        self._needs_recalibration = True  # 首次启动需要校准

    def start(self):
        """启动此 Capture 的线程。"""

        print('\n[~] 启动视频捕获')
        self.thread.start()

    def _main(self):
        """持续监控玩家位置和游戏内事件。"""

        while True:
            try:
                # 使用缓存的窗口句柄，避免重复调用 FindWindowW（句柄泄漏风险）
                # 大幅降低句柄检查频率（每100秒检查一次，减少对游戏进程的API调用压力）
                self._window_check_counter += 1
                if self._window_check_counter >= 500:  # 500帧 = 100秒（5fps）
                    if not self._window_handle or not user32.IsWindow(self._window_handle):
                        print('[!] 重新查找 MapleStory 窗口...')
                        # 窗口变化时需要重建 GDI 资源
                        self._release_gdi_resources()
                        self._window_handle = user32.FindWindowW(None, 'MapleStory')
                        self._window_validated = False
                    self._window_check_counter = 0
                elif self._window_handle is None:
                    # 首次启动时需要获取句柄
                    self._window_handle = user32.FindWindowW(None, 'MapleStory')
                    self._window_check_counter = 0

                handle = self._window_handle
                if not handle:
                    print('[!] 未找到 MapleStory 窗口，等待中...')
                    time.sleep(5)
                    continue

                # 初始化/重建 GDI 资源（只在句柄变化或首次时执行）
                if self._window_dc is None:
                    if not self._init_gdi_resources(handle):
                        print('[!] GDI 资源初始化失败，重试中...')
                        time.sleep(2)
                        continue

                # 移除动态窗口矩形更新，只在句柄失效时更新（避免触发游戏内存泄漏）
                # 窗口位置信息通常不会在运行时频繁变化，只在游戏重启或窗口移动时需要更新
                # 通过检查句柄有效性来判断是否需要重新获取窗口信息
                if not self._window_validated:
                    rect = wintypes.RECT()
                    user32.GetWindowRect(handle, ctypes.pointer(rect))
                    rect = (rect.left, rect.top, rect.right, rect.bottom)
                    rect = tuple(max(0, x) for x in rect)
                    self.window['left'] = rect[0]
                    self.window['top'] = rect[1]
                    self.window['width'] = max(rect[2] - rect[0], MMT_WIDTH)
                    self.window['height'] = max(rect[3] - rect[1], MMT_HEIGHT)
                    self._window_validated = True
                    # 窗口尺寸变化后需要重建位图等资源
                    self._rebuild_bitmap_resources()

                # 通过找到小地图的左上角和右下角来校准
                if self._needs_recalibration or not self.calibrated:
                    # 重新获取窗口位置，确保窗口移动后能正确校准
                    rect = wintypes.RECT()
                    user32.GetWindowRect(handle, ctypes.pointer(rect))
                    rect = (rect.left, rect.top, rect.right, rect.bottom)
                    rect = tuple(max(0, x) for x in rect)
                    self.window['left'] = rect[0]
                    self.window['top'] = rect[1]
                    self.window['width'] = max(rect[2] - rect[0], MMT_WIDTH)
                    self.window['height'] = max(rect[3] - rect[1], MMT_HEIGHT)
                    self._window_validated = True
                    # 窗口尺寸变化后需要重建位图资源
                    self._rebuild_bitmap_resources()

                    try:
                        # 直接使用 PrintWindow 截图进行校准
                        self.frame = self.screenshot_window()
                        if self.frame is None:
                            continue
                        # 仅在帧的左上角 30% 搜索（小地图总是在那里）
                        h_frame, w_frame = self.frame.shape[:2]
                        temp_frame = self.frame[0 : int(h_frame * 0.3), 0 : int(w_frame * 0.3)]
                        tl, _ = utils.single_match(temp_frame, MM_TL_TEMPLATE)
                        _, br = utils.single_match(temp_frame, MM_BR_TEMPLATE)
                        mm_tl = (
                            tl[0] + MINIMAP_BOTTOM_BORDER,
                            tl[1] + MINIMAP_TOP_BORDER
                        )
                        mm_br = (
                            max(mm_tl[0] + PT_WIDTH, br[0] - MINIMAP_BOTTOM_BORDER),
                            max(mm_tl[1] + PT_HEIGHT, br[1] - MINIMAP_BOTTOM_BORDER)
                        )
                        self.minimap_ratio = (mm_br[0] - mm_tl[0]) / (mm_br[1] - mm_tl[1])
                        self.minimap_sample = self.frame[mm_tl[1]:mm_br[1], mm_tl[0]:mm_br[0]]
                        self.calibrated = True
                        self._needs_recalibration = False
                        print('[~] 小地图校准成功')
                    except Exception as e:
                        print(f'[!] 校准过程中出错: {e}')
                        time.sleep(2)
                        continue

                # 主截图循环（使用 PrintWindow，不创建/销毁任何 GDI 对象）
                while True:
                    if not self.calibrated:
                        break

                    try:
                        # 使用 PrintWindow 截图（GDI 资源全部复用，零分配）
                        self.frame = self.screenshot_window()
                        if self.frame is None:
                            continue

                        # 裁剪帧以仅显示小地图（复制以便 GUI 线程
                        # 不会持有对完整帧的引用并导致内存压力）。
                        minimap = self.frame[mm_tl[1]:mm_br[1], mm_tl[0]:mm_br[0]].copy()

                        # 确定玩家位置
                        player = utils.multi_match(minimap, PLAYER_TEMPLATE, threshold=0.8)
                        if player:
                            config.player_pos = utils.convert_to_relative(player[0], minimap)
                        else:
                            # 如果未找到玩家，保持最后位置但不更新
                            pass

                        # 打包显示信息以供 GUI 轮询
                        # 先获取旧的minimap引用，以便后续清理
                        old_minimap = self.minimap.get('minimap') if hasattr(self, 'minimap') else None
                        self.minimap = {
                            'minimap': minimap,
                            'rune_active': config.bot.rune_active,
                            'rune_pos': config.bot.rune_pos,
                            'path': config.path,
                            'player_pos': config.player_pos
                        }
                        # 显式释放旧的minimap引用，帮助GC
                        if old_minimap is not None:
                            del old_minimap

                        if not self.ready:
                            self.ready = True

                        # 每约50帧（50fps下约1秒）进行一次垃圾回收，以帮助
                        # 在系统压力下释放内存（减少"无法分配"错误）。
                        self._gc_counter += 1
                        if self._gc_counter >= 30:  # 更频繁的GC以减少内存占用
                            # 强制垃圾回收，确保内存及时释放
                            gc.collect()
                            # 显式调用gc.garbage来处理循环引用
                            if hasattr(gc, 'garbage') and gc.garbage:
                                print(f'[~] 捕获模块垃圾回收: 处理了 {len(gc.garbage)} 个循环引用对象')
                            self._gc_counter = 0

                        # ~20 fps 平衡流畅度和内存压力
                        time.sleep(0.05)
                    except Exception as e:
                        print(f'[!] 捕获循环中的错误: {e}')
                        # 暂停并尝试恢复
                        time.sleep(1)
                        # 必要时尝试重新校准
                        if not self.calibrated:
                            break
                        # 出错后释放帧缓冲区
                        if self._frame_buffer is not None:
                            self._frame_buffer = None
                            gc.collect()
            except Exception as e:
                print(f'[!] 捕获主循环中的严重错误: {e}')
                import traceback
                traceback.print_exc()
                # 暂停以允许恢复
                time.sleep(5)
                # 严重错误后强制进行垃圾回收并重建 GDI 资源
                if self._frame_buffer is not None:
                    self._frame_buffer = None
                self._release_gdi_resources()
                gc.collect()

    def get_minimap_from_frame(self, frame):
        """
        通过在整个帧中搜索 TL/BR 角来找到小地图（无 ROI）。
        当预裁剪的小地图可能错误时使用此方法（例如，用于自动例程解析）。
        将 BGRA（mss）转换为 BGR，以便匹配测试小地图查找器 / cv2.imread。
        :param frame: 完整的游戏窗口图像（例如 self.frame），BGR 或 BGRA
        :return: 小地图裁剪作为 numpy 数组，如果未找到则返回 None
        """
        if frame is None or frame.size == 0:
            return None
        # 标准化为 BGR，以便匹配与测试脚本相同（保存的帧加载为 BGR）
        if frame.ndim == 3 and frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        h, w = frame.shape[:2]
        if (MM_TL_TEMPLATE.shape[0] > h or MM_TL_TEMPLATE.shape[1] > w or
                MM_BR_TEMPLATE.shape[0] > h or MM_BR_TEMPLATE.shape[1] > w):
            return None
        tl, _ = utils.single_match(frame, MM_TL_TEMPLATE)
        _, br = utils.single_match(frame, MM_BR_TEMPLATE)
        mm_tl = (
            tl[0] + MINIMAP_BOTTOM_BORDER,
            tl[1] + MINIMAP_TOP_BORDER
        )
        mm_br = (
            max(mm_tl[0] + PT_WIDTH, br[0] - MINIMAP_BOTTOM_BORDER),
            max(mm_tl[1] + PT_HEIGHT, br[1] - MINIMAP_BOTTOM_BORDER)
        )
        # 边界检查，确保我们永远不会返回无效裁剪
        if mm_br[0] <= mm_tl[0] or mm_br[1] <= mm_tl[1]:
            return None
        if mm_tl[0] < 0 or mm_tl[1] < 0 or mm_br[0] > w or mm_br[1] > h:
            return None
        return frame[mm_tl[1]:mm_br[1], mm_tl[0]:mm_br[0]]

    # ------------------------------------------------------------------ #
    #  PrintWindow (PW_RENDERFULLCONTENT) 截图实现                       #
    #                                                                     #
    #  原理: DWM 直接将合成缓存画面写入我们提供的 DC，                  #
    #        不向 MapleStory 进程注入任何 GDI 句柄。                     #
    #  所有 GDI 资源只创建一次、永久复用。                               #
    # ------------------------------------------------------------------ #

    def _init_gdi_resources(self, hwnd):
        """
        初始化 PrintWindow 所需的 GDI 资源（只调用一次）。
        返回 True 表示成功，False 表示失败。
        
        资源生命周期:
          window_dc = GetDC(hwnd)              → 窗口设备上下文
          mem_dc    = CreateCompatibleDC(dc)   → 内存设备上下文（画布）
          bitmap    = CreateCompatibleBitmap() → 兼容位图（画纸）
          bmi       = BITMAPINFO               → 像素格式描述
          data      = create_string_buffer     → 像素数据缓冲区
        """
        try:
            # 1. 获取 MapleStory 窗口的 DC
            self._window_dc = user32.GetDC(hwnd)
            if not self._window_dc:
                print('[!] GetDC 失败')
                return False

            # 2. 创建兼容内存 DC
            self._mem_dc = gdi32.CreateCompatibleDC(self._window_dc)
            if not self._mem_dc:
                print('[!] CreateCompatibleDC 失败')
                user32.ReleaseDC(hwnd, self._window_dc)
                self._window_dc = None
                return False

            width = self.window['width']
            height = self.window['height']

            # 3. 创建兼容位图（用于接收 PrintWindow 的输出）
            self._bitmap = gdi32.CreateCompatibleBitmap(self._window_dc, width, height)
            if not self._bitmap:
                print('[!] CreateCompatibleBitmap 失败')
                gdi32.DeleteDC(self._mem_dc)
                user32.ReleaseDC(hwnd, self._window_dc)
                self._mem_dc = None
                self._window_dc = None
                return False

            # 4. 将位图选入内存 DC（SelectObject 返回旧的位图对象，必须保存）
            self._old_bitmap = gdi32.SelectObject(self._mem_dc, self._bitmap)

            # 5. 构建 BITMAPINFO 结构体（用于 GetDIBits 读取像素数据）
            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = (
                    ('biSize', wintypes.DWORD),
                    ('biWidth', ctypes.c_long),
                    ('biHeight', ctypes.c_long),   # 负数 = 从上到下 (top-down DIB)
                    ('biPlanes', wintypes.WORD),
                    ('biBitCount', wintypes.WORD),
                    ('biCompression', wintypes.DWORD),
                    ('biSizeImage', wintypes.DWORD),
                    ('biXPelsPerMeter', ctypes.c_long),
                    ('biYPelsPerMeter', ctypes.c_long),
                    ('biClrUsed', wintypes.DWORD),
                    ('biClrImportant', wintypes.DWORD),
                )

            class BITMAPINFO(ctypes.Structure):
                _fields_ = (
                    ('bmiHeader', BITMAPINFOHEADER),
                    ('bmiColors', wintypes.DWORD * 3),
                )

            self._bmi = BITMAPINFO()
            bmi_header = self._bmi.bmiHeader
            bmi_header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi_header.biWidth = width
            bmi_header.biHeight = -height  # top-down DIB
            bmi_header.biPlanes = 1
            bmi_header.biBitCount = 32  # BGRA (4 bytes per pixel)
            bmi_header.biCompression = 0  # BI_RGB (无压缩)
            bmi_header.biSizeImage = 0
            bmi_header.biClrUsed = 0
            bmi_header.biClrImportant = 0

            # 6. 分配像素数据缓冲区（与位图大小一致，永久复用）
            pixel_size = width * height * 4  # BGRA = 4 bytes/pixel
            self._pixel_data = ctypes.create_string_buffer(pixel_size)

            print(f'[~] GDI 资源初始化成功 (窗口大小: {width}x{height})')
            return True

        except Exception as e:
            print(f'[!] GDI 资源初始化异常: {e}')
            self._release_gdi_resources()
            return False

    def _rebuild_bitmap_resources(self):
        """
        当窗口尺寸变化时重建位图和像素缓冲区。
        保留 window_dc 和 mem_dc（只要窗口句柄不变就不需要重建）。
        """
        if self._mem_dc is None:
            return

        try:
            width = self.window['width']
            height = self.window['height']

            # 恢复旧位图（防止泄漏）
            if self._bitmap is not None:
                gdi32.SelectObject(self._mem_dc, self._old_bitmap)
                gdi32.DeleteObject(self._bitmap)
                self._bitmap = None
                self._old_bitmap = None

            # 创建新尺寸的位图
            self._bitmap = gdi32.CreateCompatibleBitmap(self._window_dc, width, height)
            if self._bitmap:
                self._old_bitmap = gdi32.SelectObject(self._mem_dc, self._bitmap)

                # 更新 BITMAPINFO 尺寸信息
                if self._bmi is not None:
                    self._bmi.bmiHeader.biWidth = width
                    self._bmi.bmiHeader.biHeight = -height

                # 重新分配像素缓冲区
                pixel_size = width * height * 4
                self._pixel_data = ctypes.create_string_buffer(pixel_size)

                # 重置 numpy 缓冲区（下次 screenshot_window 时会按新尺寸创建）
                self._frame_buffer = None

                print(f'[~] 位图资源已重建 ({width}x{height})')
        except Exception as e:
            print(f'[!] 重建位图资源失败: {e}')

    def _release_gdi_resources(self):
        """释放所有 GDI 资源（按相反顺序释放）。"""
        try:
            if self._pixel_data is not None:
                self._pixel_data = None
            if self._bmi is not None:
                self._bmi = None
            # 先恢复原始位图再删除
            if self._bitmap is not None and self._mem_dc is not None:
                gdi32.SelectObject(self._mem_dc, self._old_bitmap)
                gdi32.DeleteObject(self._bitmap)
                self._bitmap = None
                self._old_bitmap = None
            if self._mem_dc is not None:
                gdi32.DeleteDC(self._mem_dc)
                self._mem_dc = None
            if self._window_dc is not None and self._window_handle is not None:
                user32.ReleaseDC(self._window_handle, self._window_dc)
                self._window_dc = None
        except Exception as e:
            print(f'[!] 释放 GDI 资源时出错: {e}')

    def screenshot_window(self):
        """
        使用 PrintWindow(PW_RENDERFULLCONTENT) 对 MapleStory 窗口进行截图。

        核心流程（每帧调用，GDI 资源全部复用）:
          1. PrintWindow(hwnd, memdc, PW_RENDERFULLCONTENT=2)  ← DWM 写入我们的 DC
          2. GetDIBits(memdc, bitmap, data, bmi)              ← 读取像素到缓冲区
          3. 复制到 numpy 数组                                ← 返回给上层

        返回值: numpy.ndarray, shape=(H, W, 4), dtype=uint8 (BGRA 格式)
                 出错时返回 None
        """
        handle = self._window_handle
        try:
            width = self.window['width']
            height = self.window['height']
            need_shape = (height, width, 4)

            # 分配/复用 numpy 缓冲区
            if self._frame_buffer is None or self._frame_buffer.shape != need_shape:
                if self._frame_buffer is not None:
                    self._frame_buffer = None
                    gc.collect()
                self._frame_buffer = np.empty(need_shape, dtype=np.uint8)

            # 核心：PrintWindow 让 DWM 将合成缓存画面直接写入我们的内存 DC
            # PW_RENDERFULLCONTENT(2): 不经过目标进程窗口过程，由 DWM 层处理，
            # 不会向 MapleStory 注入任何 GDI 句柄
            result = user32.PrintWindow(handle, self._mem_dc, PW_RENDERFULLCONTENT)
            if not result:
                # PrintWindow 失败（窗口可能被遮挡或最小化），返回上一帧
                return self.frame

            # 从内存 DC 的位图中读取像素数据到预分配的缓冲区
            bits_copied = gdi32.GetDIBits(
                self._mem_dc,
                self._bitmap,
                0,
                height,
                self._pixel_data,
                self._bmi,
                DIB_RGB_COLORS
            )
            if bits_copied == 0 or bits_copied == -1:
                # GetDIBits 失败
                return self.frame

            # 将 ctypes 缓冲区的数据复制到 numpy 数组（避免 frombuffer 的只读问题）
            np.copyto(
                self._frame_buffer,
                np.frombuffer(self._pixel_data, dtype=np.uint8).reshape(need_shape)
            )

            # 强制刷新 GDI，确保资源及时回收
            gdi32.GdiFlush()

            return self._frame_buffer

        except Exception as e:
            print(f'[!] PrintWindow 截图错误: {e}')
            return None

    def screenshot(self, delay=1):
        """使用 PrintWindow 进行截图（保持向后兼容）"""
        return self.screenshot_window()