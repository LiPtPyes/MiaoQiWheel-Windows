"""轮盘毛玻璃背景：抓取屏幕局部 → 降采样模糊。

设计约束：
- 只在轮盘呼出时调用一次，结果交给 WheelFaceWidget 缓存，不在常驻期持有。
- 任何环节失败都返回 None，调用方降级为纯色玻璃，绝不因截图失败阻塞呼出。
- 环境变量 MQWHEEL_DISABLE_BACKDROP=1 可强制关闭（远程桌面/排查用）。
- 抓取走 GDI BitBlt 而非 Qt 的 grabWindow：前者能明确指定物理像素，
  在多屏不同 DPI 与负坐标（主屏左侧的显示器）下行为可预期。
"""

from __future__ import annotations

import os

BLUR_DOWNSCALE = 12  # 降采样倍率，越大越模糊
DISABLE_ENV = "MQWHEEL_DISABLE_BACKDROP"

SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000
BI_RGB = 0
DIB_RGB_COLORS = 0


def is_disabled() -> bool:
    return os.environ.get(DISABLE_ENV, "") == "1"


class _BitmapInfoHeader:
    """按需构造 BITMAPINFOHEADER，避免模块导入即依赖 ctypes 结构定义开销。"""

    @staticmethod
    def build(ctypes, wintypes, width: int, height: int):
        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", wintypes.DWORD),
                ("biWidth", ctypes.c_long),
                ("biHeight", ctypes.c_long),
                ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", ctypes.c_long),
                ("biYPelsPerMeter", ctypes.c_long),
                ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD),
            ]

        header = BITMAPINFOHEADER()
        header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        header.biWidth = width
        header.biHeight = -height  # 负值 = 自上而下，省一次翻转
        header.biPlanes = 1
        header.biBitCount = 32
        header.biCompression = BI_RGB
        return header


def grab_region(x: int, y: int, width: int, height: int):
    """抓取虚拟桌面上以物理像素计的区域，返回 QImage 或 None。

    x/y 可以是负数（主屏左侧的显示器），GDI 的桌面 DC 覆盖整个虚拟桌面。
    """
    if width <= 0 or height <= 0:
        return None

    try:
        import ctypes
        from ctypes import wintypes

        from PySide6 import QtGui

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

        user32.GetDC.argtypes = [wintypes.HWND]
        user32.GetDC.restype = wintypes.HDC
        user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        user32.ReleaseDC.restype = ctypes.c_int

        gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
        gdi32.CreateCompatibleDC.restype = wintypes.HDC
        gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
        gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
        gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
        gdi32.SelectObject.restype = wintypes.HGDIOBJ
        gdi32.BitBlt.argtypes = [
            wintypes.HDC,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HDC,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.DWORD,
        ]
        gdi32.BitBlt.restype = wintypes.BOOL
        gdi32.GetDIBits.argtypes = [
            wintypes.HDC,
            wintypes.HBITMAP,
            wintypes.UINT,
            wintypes.UINT,
            wintypes.LPVOID,
            wintypes.LPVOID,
            wintypes.UINT,
        ]
        gdi32.GetDIBits.restype = ctypes.c_int
        gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
        gdi32.DeleteObject.restype = wintypes.BOOL
        gdi32.DeleteDC.argtypes = [wintypes.HDC]
        gdi32.DeleteDC.restype = wintypes.BOOL

        screen_dc = user32.GetDC(None)
        if not screen_dc:
            return None
        try:
            memory_dc = gdi32.CreateCompatibleDC(screen_dc)
            if not memory_dc:
                return None
            try:
                bitmap = gdi32.CreateCompatibleBitmap(screen_dc, width, height)
                if not bitmap:
                    return None
                try:
                    gdi32.SelectObject(memory_dc, bitmap)
                    if not gdi32.BitBlt(
                        memory_dc, 0, 0, width, height, screen_dc, x, y, SRCCOPY | CAPTUREBLT
                    ):
                        return None

                    stride = width * 4
                    buffer = ctypes.create_string_buffer(stride * height)
                    header = _BitmapInfoHeader.build(ctypes, wintypes, width, height)
                    got = gdi32.GetDIBits(
                        memory_dc,
                        bitmap,
                        0,
                        height,
                        buffer,
                        ctypes.byref(header),
                        DIB_RGB_COLORS,
                    )
                    if got != height:
                        return None
                    image = QtGui.QImage(
                        buffer, width, height, stride, QtGui.QImage.Format.Format_RGB32
                    )
                    return image.copy()  # 脱离 ctypes 缓冲区
                finally:
                    gdi32.DeleteObject(bitmap)
            finally:
                gdi32.DeleteDC(memory_dc)
        finally:
            user32.ReleaseDC(None, screen_dc)
    except Exception:
        return None


def blur(image, downscale: int = BLUR_DOWNSCALE):
    """降采样再放大，得到廉价但足够均匀的高斯近似。"""
    from PySide6 import QtCore

    if image is None or image.isNull():
        return None
    width, height = image.width(), image.height()
    small_width = max(1, int(round(width / downscale)))
    small_height = max(1, int(round(height / downscale)))
    if small_width >= width or small_height >= height:
        return image
    smooth = QtCore.Qt.TransformationMode.SmoothTransformation
    ignore = QtCore.Qt.AspectRatioMode.IgnoreAspectRatio
    small = image.scaled(small_width, small_height, ignore, smooth)
    return small.scaled(width, height, ignore, smooth)


def capture(x: float, y: float, side: float, dpr: float = 1.0):
    """抓取逻辑坐标 (x, y, side, side) 的区域，返回已模糊、带 DPR 的 QPixmap。

    失败返回 None。dpr 为所在屏幕的设备像素比，用于按物理像素抓取后再
    还原成逻辑尺寸，避免高 DPI 下背景被拉伸模糊。
    """
    from PySide6 import QtGui

    if is_disabled() or side <= 0:
        return None
    ratio = dpr if dpr and dpr > 0 else 1.0
    physical = int(round(side * ratio))
    image = grab_region(
        int(round(x * ratio)), int(round(y * ratio)), physical, physical
    )
    if image is None or image.isNull():
        return None
    blurred = blur(image)
    if blurred is None:
        return None
    pixmap = QtGui.QPixmap.fromImage(blurred)
    if ratio != 1.0:
        pixmap.setDevicePixelRatio(ratio)
    return pixmap


__all__ = ["BLUR_DOWNSCALE", "blur", "capture", "grab_region", "is_disabled"]
