"""Regression tests for responsive first playback."""

import time


def pump_until(qapp, predicate, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end and not predicate():
        qapp.processEvents()
        time.sleep(0.01)
    return predicate()


def test_media_player_property_never_initializes_synchronously(qapp, monkeypatch):
    from core.video_player import VideoPlayer

    player = VideoPlayer()
    called = []
    monkeypatch.setattr(player, "ensure_initialized", lambda: called.append(True) or True)

    assert player.media_player is None
    assert called == []
    player.cleanup()


def test_vlc_initialization_runs_off_gui_thread(qapp, monkeypatch):
    from core.video_player import VideoPlayer

    player = VideoPlayer()
    finished = []

    def slow_initialization():
        time.sleep(0.25)
        player._media_player = object()
        return True

    monkeypatch.setattr(player, "ensure_initialized", slow_initialization)
    player.initialization_finished.connect(finished.append)

    started = time.perf_counter()
    assert player.initialize_async() is False
    assert time.perf_counter() - started < 0.1
    assert pump_until(qapp, lambda: bool(finished))
    assert finished == [True]

    # Avoid asking the synthetic object to run libVLC cleanup methods.
    player._media_player = None
    player.cleanup()
