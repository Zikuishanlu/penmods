"""Qt application entry point: loads the QML shell and wires the C backend."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle

from . import __version__, winfx, winfx_region
from .bridge import Backend
from .paths import qml_dir


def _grab(window) -> QImage | None:
    """Grab the QML window: QQuickWindow::grabWindow first, QScreen as fallback."""
    try:
        image = QQuickWindow.grabWindow(window)
        if isinstance(image, QImage):
            return image
    except Exception:  # noqa: BLE001 - fall through to the screen grab
        pass
    screen = window.screen()
    if screen is None:
        return None
    pixmap = screen.grabWindow(window.winId())
    return pixmap.toImage() if pixmap is not None else None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="penmods-manager", add_help=True)
    parser.add_argument("--screenshot", metavar="PNG", help="渲染主界面到 PNG 后退出（开发自检）")
    parser.add_argument("--screenshot-delay", type=int, default=1500, help="截图前的等待毫秒数")
    parser.add_argument("--page", type=int, default=0, help="启动时显示的页面序号（开发自检）")
    parser.add_argument("--serial", default="", help="预置已连接的设备序列号（开发自检）")
    parser.add_argument("--ssh-target", default="", metavar="USER@HOST[:PORT]",
                        help="启动前先用密钥连上 SSH 并预置为当前连接（开发自检）")
    parser.add_argument("--version", action="version", version=f"PenMods Manager {__version__}")
    parser.add_argument("--ui-size", default="", help=argparse.SUPPRESS)
    parser.add_argument("--ui-pos", default="", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    parser = _build_parser()
    args, qt_argv = parser.parse_known_args(argv[1:])

    # Controls-style: our glass panels restyle every control, which only the
    # non-native styles allow.
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication([argv[0], *qt_argv])
    app.setApplicationName("PenMods Manager")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("PenMods")

    engine = QQmlApplicationEngine()
    backend = Backend()
    engine.rootContext().setContextProperty("backend", backend)

    if args.ssh_target:
        target, _, port = args.ssh_target.partition(":")
        user, _, host = target.partition("@")
        result = backend.ssh_connect_blocking(host, user or "root", port or "22")
        print(f"[penmanager] ssh preflight: ok={result.get('ok')} {result.get('error', '')}")
        if result.get("ok"):
            args.serial = "ssh:" + result["target"]

    qml_main = qml_dir() / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_main)))
    roots = engine.rootObjects()
    if not roots:
        print(f"[penmanager] QML 加载失败: {qml_main}", file=sys.stderr)
        return 2

    window = roots[0]
    if args.ui_size:
        try:
            w, h = (int(v) for v in args.ui_size.lower().split("x"))
            window.resize(w, h)
        except (ValueError, TypeError):
            pass
    if args.ui_pos:
        try:
            x, y = (int(v) for v in args.ui_pos.split(","))
            window.setPosition(x, y)
        except (ValueError, TypeError):
            pass
    if args.page:
        window.setProperty("pageIndex", int(args.page))
    if args.serial:
        window.setProperty("activeSerial", str(args.serial))
    try:
        flags = winfx.apply(int(window.winId()))
        print(f"[penmanager] windows chrome: {flags}")
    except Exception as exc:  # noqa: BLE001 - cosmetic only
        print(f"[penmanager] windows chrome skipped: {exc}")

    # Windows 10 has no DWM rounded corners: clip the window ourselves.
    region_state = {"w": 0, "h": 0}

    def refresh_region() -> None:
        try:
            ratio = float(window.devicePixelRatio())
            w = int(round(window.width() * ratio))
            h = int(round(window.height() * ratio))
            r = int(round(14 * ratio))
        except Exception:  # noqa: BLE001 - cosmetic only
            return
        if (w, h) == (region_state["w"], region_state["h"]):
            return
        if winfx_region.apply_round_region(int(window.winId()), w, h, r):
            region_state["w"], region_state["h"] = w, h

    region_timer = QTimer()
    region_timer.setInterval(300)
    region_timer.timeout.connect(refresh_region)
    refresh_region()
    region_timer.start()

    if args.screenshot:
        target = Path(args.screenshot).resolve()

        def shoot() -> None:
            image = _grab(window)
            if image is None or image.isNull():
                print("[penmanager] 截图失败：窗口抓取返回空图像", file=sys.stderr)
                app.exit(3)
                return
            target.parent.mkdir(parents=True, exist_ok=True)
            if not image.save(str(target)):
                print(f"[penmanager] 截图保存失败: {target}", file=sys.stderr)
                app.exit(4)
                return
            print(f"[penmanager] screenshot: {target} ({image.width()}x{image.height()})")
            app.quit()

        QTimer.singleShot(max(200, args.screenshot_delay), shoot)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
