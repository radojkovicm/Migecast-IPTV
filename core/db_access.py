"""Lazy access to :class:`core.database.Database`.

UI modules import this instead of ``core.database`` so SQLAlchemy is not
imported on the GUI thread before the main window is visible.
"""


def Database():  # noqa: N802 - mirrors the class name on purpose
    from core.database import Database as _Database
    return _Database()
