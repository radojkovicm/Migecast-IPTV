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


class _FakeMedia:
    def add_option(self, _option):
        pass

    def release(self):
        pass


class _FakeInstance:
    def media_new(self, _url):
        return _FakeMedia()


class _FakeMediaPlayer:
    def __init__(self):
        self.plays = 0
        self.stops = 0

    def set_media(self, _media):
        pass

    def play(self):
        self.plays += 1

    def stop(self):
        self.stops += 1

    def is_playing(self):
        return False


def _fake_player():
    from core.video_player import VideoPlayer
    player = VideoPlayer(reconnect_attempts=3)
    player.instance = _FakeInstance()
    player._media_player = _FakeMediaPlayer()
    return player


def _cleanup(player):
    player._media_player = None
    player.instance = None
    player.cleanup()


def test_stream_without_picture_gives_up_after_deadline(qapp):
    from core.video_player import CONNECT_TIMEOUT_MS
    assert 10000 <= CONNECT_TIMEOUT_MS <= 15000
    player = _fake_player()
    player.connect_timer.setInterval(300)
    states = []
    player.state_changed.connect(states.append)
    assert player.play("http://stream.invalid/busy")
    assert pump_until(qapp, lambda: "timeout" in states, timeout=2.0)
    assert player.current_url is None and player._media_player.stops == 1
    _cleanup(player)


def test_reconnects_count_towards_the_same_deadline(qapp):
    player = _fake_player()
    player.connect_timer.setInterval(400)
    states = []
    player.state_changed.connect(states.append)
    player.play("http://stream.invalid/busy")
    player._on_vlc_event("error")  # first reconnect after 1 s, after the deadline
    assert pump_until(qapp, lambda: "timeout" in states, timeout=2.0)
    pump_until(qapp, lambda: False, timeout=1.3)
    assert player._media_player.plays == 1  # no reconnect after giving up
    assert states == ["reconnecting", "timeout"]
    _cleanup(player)


def test_picture_stops_the_deadline(qapp):
    player = _fake_player()
    player.connect_timer.setInterval(200)
    states = []
    player.state_changed.connect(states.append)
    player.play("http://stream.invalid/ok")
    player._on_vlc_event("playing")
    pump_until(qapp, lambda: False, timeout=0.4)
    assert states == ["playing"] and player.current_url
    _cleanup(player)
