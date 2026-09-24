import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Every test gets its own empty %LOCALAPPDATA%\\MigeCast."""
    monkeypatch.setenv("MIGECAST_DATA_DIR", str(tmp_path / "userdata"))
    from utils import paths
    monkeypatch.setattr(paths, "legacy_data_dirs", lambda: [])  # never import a developer's real data
    from core.database import Database
    Database.reset_instance()
    yield tmp_path / "userdata"
    Database.reset_instance()


@pytest.fixture
def fixtures_dir():
    return ROOT / "tests" / "fixtures"


@pytest.fixture(scope="session")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


_slot_errors = []


def _record_slot_error(exc_type, exc, tb):
    import traceback
    _slot_errors.append("".join(traceback.format_exception(exc_type, exc, tb)))


@pytest.fixture(autouse=True)
def no_errors_in_qt_slots():
    """PyQt6 would abort the test process on an exception in a slot; record
    it instead and fail the test that caused it, with the full traceback."""
    previous = sys.excepthook
    sys.excepthook = _record_slot_error
    _slot_errors.clear()
    yield
    sys.excepthook = previous
    if _slot_errors:
        pytest.fail("Exception in a Qt slot:\n" + "\n".join(_slot_errors))
