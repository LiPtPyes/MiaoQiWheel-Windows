"""产出网站上的毛玻璃配图（website/assets/img/m5-glass.png）。

两种模式：

1. 默认 · 真机抓取 —— 呼出一次轮盘，抓下盘面背后的**真实桌面**模糊。
       .venv\\Scripts\\python.exe tools\\shot_glass.py [输出] [--show-desktop]
   走的是 app 运行时同一条路径：真的呼出、真的 GDI BitBlt 抓屏、真的降采样模糊。
   屏幕上会闪现轮盘约 1 秒。--show-desktop 会先按一次 Win+D 露出桌面（抓完还原），
   几乎总是需要 —— 触发脚本时人正在聊天/终端窗口里，那个窗口会盖住屏幕。
   ⚠ 底图就是抓取那一刻屏幕上显示的东西（含桌面壁纸）。放到公开页面前务必确认
     屏幕内容合适：私人照片、聊天窗口之类都不能用。

2. --gradient · 合成底图 —— 离屏渲染，底层用一张现生成的蓝紫渐变。
       .venv\\Scripts\\python.exe tools\\shot_glass.py website\\assets\\img\\m5-glass.png --gradient
   除了底图像素的来源，其余全是 app 的真实渲染：set_backdrop() → 盘面绘制 →
   那层 rgba(16,18,24,118) 的玻璃暗色。不碰屏幕，无隐私与版权顾虑。
   注意它属于「渲染图」而非「桌面截图」，配图文案不要写成"透出桌面"。

⚠ 不要拿 tools/smoke_m5.py 产出的 docs/m5-glass.png 当产品配图。那是像素断言的
   测试夹具：底图来自 synthetic_backdrop()，一张纯洋红测试图案，存在的唯一目的
   是让断言能检查"R 是否明显高于 G"。放上去就是一个莫名其妙的紫色轮盘。
   （docs/ 下的同名文件是自检产物，本脚本不碰它，只写 website/assets/img/。）
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

SIDE = 520  # 盘面逻辑边长，与 smoke_wheel / smoke_m5 一致
HOST_PAD = 40  # 四周留白，最终输出 (520+40*2)=600×600
HIGHLIGHT_INDEX = 1  # 高亮「区域截图」，与另外两张截图的选中态对齐
SETTLE_MS = 700  # 等入场动画（130ms）跑完再抓
DESKTOP_SETTLE_MS = 900  # Win+D 之后等最小化动画结束
HARD_TIMEOUT_MS = 6000  # 无论如何都要退出，别把轮盘留在屏幕上
GRADIENT_SIZE = 1040  # 渐变底图边长（留点余量，盘面实际只用 520）

if os.environ.get("MQWHEEL_OFFSCREEN", "1") == "1":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402

from mqwheel.models.action import default_actions  # noqa: E402
from mqwheel.models.settings import WheelSettings  # noqa: E402
from mqwheel.services import backdrop  # noqa: E402
from mqwheel.views.overlay import WheelFaceWidget  # noqa: E402

HOST_BG = QtGui.QColor(27, 29, 33)  # #1b1d21，与 m1 / m5 系列截图的宿主底色一致


def _ensure_app() -> QtWidgets.QApplication:
    """建好 QApplication。

    ⚠ 必须先建它再碰 QImage / QPixmap：没有应用实例时构造 QPixmap 会直接
    abort（Qt 的行为，不是 Python 异常），进程连一行输出都打不出来就没了 ——
    表现为退出码 127、stdout 全空。第一版把 _gradient_backdrop() 写在实参
    位置，正好踩中这个坑。
    """
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setFont(QtGui.QFont("Microsoft YaHei UI", 9))
    return app


def _gradient_backdrop(size: int = GRADIENT_SIZE) -> QtGui.QPixmap:
    """蓝紫渐变底图，模拟一张偏蓝紫的桌面壁纸。

    刻意做得偏亮偏饱和：毛玻璃会在底图之上再压一层 rgba(16,18,24,118)（约 46%
    的暗色），底图太暗的话透出来就成了一块灰 —— 这正是之前那张测试夹具观感差
    的原因之一。
    """
    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_RGB32)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

    # 斜向主渐变：左上深靛蓝 → 右下紫罗兰
    linear = QtGui.QLinearGradient(0.0, 0.0, float(size), float(size))
    linear.setColorAt(0.00, QtGui.QColor("#0e1640"))
    linear.setColorAt(0.42, QtGui.QColor("#26308f"))
    linear.setColorAt(0.74, QtGui.QColor("#5b34c8"))
    linear.setColorAt(1.00, QtGui.QColor("#8b4fd8"))
    painter.fillRect(0, 0, size, size, linear)

    # 左上再叠一团青色光斑，让盘面中心有层次而不是一片平涂
    glow = QtGui.QRadialGradient(size * 0.36, size * 0.32, size * 0.62)
    glow.setColorAt(0.0, QtGui.QColor(72, 168, 255, 120))
    glow.setColorAt(1.0, QtGui.QColor(72, 168, 255, 0))
    painter.fillRect(0, 0, size, size, glow)
    painter.end()

    # 走 app 真实的那套模糊，而不是另写一个
    blurred = backdrop.blur(image)
    return QtGui.QPixmap.fromImage(blurred or image)


def _render_offscreen(out: Path, backdrop_pixmap: QtGui.QPixmap) -> int:
    """离屏渲染盘面。除了底图来源，与运行时走的是同一套绘制。"""
    app = _ensure_app()

    host = QtWidgets.QWidget()
    host.setFixedSize(SIDE + HOST_PAD * 2, SIDE + HOST_PAD * 2)
    host.setStyleSheet(f"background-color: {HOST_BG.name()};")
    layout = QtWidgets.QVBoxLayout(host)
    layout.setContentsMargins(HOST_PAD, HOST_PAD, HOST_PAD, HOST_PAD)

    face = WheelFaceWidget(host)
    face.setFixedSize(SIDE, SIDE)
    face.set_actions(default_actions())
    face.set_selected_index(HIGHLIGHT_INDEX)
    face.set_backdrop(backdrop_pixmap)
    face.set_reveal(1.0)
    layout.addWidget(face)

    host.show()
    app.processEvents()
    canvas = host.grab()
    layout.removeWidget(face)
    face.setParent(None)
    host.close()

    out.parent.mkdir(parents=True, exist_ok=True)
    if not canvas.save(str(out)):
        print(f"保存失败：{out}")
        return 1
    _report(canvas, out)
    return 0


def _toggle_desktop() -> None:
    """模拟一次 Win+D。按两次即可往返（露出桌面 / 还原窗口）。"""
    import ctypes

    VK_LWIN, VK_D, KEYUP = 0x5B, 0x44, 0x0002
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    for vk, flags in ((VK_LWIN, 0), (VK_D, 0), (VK_D, KEYUP), (VK_LWIN, KEYUP)):
        user32.keybd_event(vk, 0, flags, 0)


def _report(canvas: QtGui.QPixmap, out: Path) -> None:
    """采样盘内一点，便于确认底图确实透出来了（纯色降级时该点会是中性灰）。"""
    image = canvas.toImage()
    probe = image.pixelColor(image.width() // 2, int(image.height() * 0.28))
    print(f"已保存 {out}  {canvas.width()}x{canvas.height()}")
    print(f"盘内采样 {(probe.red(), probe.green(), probe.blue())}（纯色降级时应为中性灰）")


def _capture_real(out: Path, show_desktop: bool) -> int:
    """真机抓取：走 WheelOverlayController 的完整呼出流程。"""
    from mqwheel.controllers.overlay_controller import WheelOverlayController

    app = _ensure_app()

    if backdrop.is_disabled():
        print("MQWHEEL_DISABLE_BACKDROP=1，毛玻璃被禁用，抓不到效果")
        return 1

    settings = WheelSettings()
    settings.appearance.blur_background = True
    settings.appearance.animate = True

    controller = WheelOverlayController(settings)
    state = {"done": False, "desktop_hidden": False, "code": 1}

    def finish(code: int) -> None:
        if state["done"]:
            return
        state["done"] = True
        state["code"] = code
        try:
            controller.hide()
        except Exception:  # 收尾失败也不能把轮盘留在屏幕上
            pass
        if state["desktop_hidden"]:
            # 只在自己按过 Win+D 时才按回去，否则会反过来把用户的桌面最小化。
            QtCore.QTimer.singleShot(250, lambda: (_toggle_desktop(), app.quit()))
        else:
            app.quit()

    def shoot() -> None:
        # 控制器没有暴露窗口访问器，这里直接取 —— 本脚本与控制器同仓库，
        # 走私有属性比再加一个只为截图存在的公开接口划算。
        window = controller._window
        if window is None:
            print("窗口未创建")
            finish(1)
            return

        face = window.face
        face.set_selected_index(HIGHLIGHT_INDEX)
        app.processEvents()

        # 抓 face 而不是抓屏幕：face 只画阴影 + 盘面，盘外是透明的，
        # 这样就不必去猜盘面半径、也不会把用户桌面的边角拍进来。
        shot = face.grab()
        if shot.isNull():
            print("抓取失败")
            finish(1)
            return

        # ⚠ face.grab() 返回的是**物理像素**：高 DPI 下宽度是逻辑边长的 dpr 倍
        # （实测 dpr=2 时给的是 1040×1040）。不按 dpr 折算直接贴图，画面就只
        # 占左上角 1/4 —— 第一版就是这么错的。
        ratio = shot.devicePixelRatio() or 1.0
        side = int(round(shot.width() / ratio))
        pad = int(round(side * HOST_PAD / SIDE))

        canvas = QtGui.QPixmap(side + pad * 2, side + pad * 2)
        canvas.fill(HOST_BG)
        painter = QtGui.QPainter(canvas)
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawPixmap(
            QtCore.QRectF(pad, pad, side, side), shot, QtCore.QRectF(shot.rect())
        )
        painter.end()

        out.parent.mkdir(parents=True, exist_ok=True)
        if not canvas.save(str(out)):
            print(f"保存失败：{out}")
            finish(1)
            return
        _report(canvas, out)
        finish(0)

    center = QtGui.QGuiApplication.primaryScreen().availableGeometry().center()
    delay = 0
    if show_desktop:
        _toggle_desktop()
        state["desktop_hidden"] = True
        delay = DESKTOP_SETTLE_MS  # 等最小化动画跑完再呼出，否则抓到的还是窗口
    QtCore.QTimer.singleShot(delay, lambda: controller.show(center))
    QtCore.QTimer.singleShot(delay + SETTLE_MS, shoot)
    QtCore.QTimer.singleShot(delay + HARD_TIMEOUT_MS, lambda: finish(1))
    app.exec()
    return state["code"]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="产出网站上的毛玻璃配图")
    parser.add_argument(
        "output",
        nargs="?",
        default=str(ROOT / "website" / "assets" / "img" / "m5-glass.png"),
    )
    parser.add_argument(
        "--gradient",
        action="store_true",
        help="离屏渲染 + 蓝紫渐变底图（不碰屏幕，无隐私顾虑，属渲染图而非截图）",
    )
    parser.add_argument(
        "--show-desktop",
        action="store_true",
        help="真机模式下先 Win+D 露出桌面，抓完再还原（会临时最小化所有窗口）",
    )
    args = parser.parse_args(argv[1:])
    out = Path(args.output)

    if args.gradient:
        # 必须在 QApplication 之前定下来，否则平台插件已经初始化完毕
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

    _ensure_app()

    if args.gradient:
        return _render_offscreen(out, _gradient_backdrop())
    return _capture_real(out, args.show_desktop)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
