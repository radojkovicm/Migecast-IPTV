"""MigeCast IPTV entry point.

Startup order is optimised for a visible window as early as possible:
Qt is imported, the window is shown, and only then the database, playlist
cache and images are loaded in background threads. libVLC is loaded on the
first playback.
"""
import sys

from utils import startup_profiler  # first: records process start time

startup_profiler.mark("python_started")

import argparse  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="MigeCast")
    parser.add_argument("--smoke-test", action="store_true",
                        help="start, load the saved list, write the startup report and quit")
    parser.add_argument("--startup-report", help="write startup timings (JSON) to this file")
    parser.add_argument("--debug", action="store_true", help="verbose log")
    parser.add_argument("--windowed", action="store_true", help="do not start in full screen")
    parser.add_argument("--check-vlc", metavar="FILE",
                        help="load the bundled libVLC, write a JSON report to FILE and exit")
    args, _unknown = parser.parse_known_args(argv)
    return args


def check_vlc(report_file: str) -> int:
    """Used by the installer tests: proves libVLC loads from the program folder."""
    import json
    from core.video_player import load_vlc
    report = {"loaded": False}
    vlc = load_vlc()
    if vlc:
        report["loaded"] = True
        report["libvlc_version"] = vlc.libvlc_get_version().decode("utf-8", "replace")
        report["lib_path"] = os.environ.get("PYTHON_VLC_LIB_PATH", "")
        report["plugin_path"] = os.environ.get("PYTHON_VLC_MODULE_PATH", "")
        instance = vlc.Instance("--quiet --no-video-title-show")
        report["instance_ok"] = instance is not None
        if instance is not None:
            instance.release()
    with open(report_file, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    return 0 if report.get("instance_ok") else 3


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.startup_report:
        os.environ["MIGECAST_STARTUP_REPORT"] = args.startup_report

    if args.check_vlc:
        return check_vlc(args.check_vlc)

    from utils import paths
    from utils.log_setup import setup_logging
    paths.ensure_user_dirs()
    setup_logging(paths.logs_dir(), debug=args.debug)
    logger = logging.getLogger("migecast")
    from version import __build_date__, __version__
    logger.info("MigeCast %s (build %s) starting", __version__, __build_date__)

    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont, QIcon
    from PyQt6.QtWidgets import QApplication
    startup_profiler.mark("qt_imported")

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("MigeCast IPTV")
    app.setOrganizationName("MigeCast")
    app.setFont(QFont("Segoe UI", 12))
    icon_path = paths.resource_path("migecast.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MigeCast.IPTV")
        except Exception:
            pass
    startup_profiler.mark("qapplication_created")

    from utils import themes
    from utils.config import Config
    theme = Config().get("appearance", "theme", "dark")
    themes.set_current(theme)
    app.setStyleSheet(themes.generate_stylesheet(theme))

    from ui.main_window import MainWindow
    window = MainWindow(smoke_test=args.smoke_test)
    if args.windowed or args.smoke_test:
        window.resize(1400, 860)
        window.show()
    else:
        window.showFullScreen()
    app.processEvents()
    startup_profiler.mark("window_shown")

    from PyQt6.QtCore import QTimer
    QTimer.singleShot(0, window.start)
    exit_code = app.exec()
    logger.info("Exit code %s", exit_code)
    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # last resort: log and show a readable message
        logging.getLogger("migecast").exception("Fatal error")
        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, "MigeCast IPTV",
                                 "Program je naišao na grešku i mora da se zatvori.\n"
                                 "Detalji su upisani u log fajl u folderu sa podacima.")
        except Exception:
            pass
        sys.exit(1)
