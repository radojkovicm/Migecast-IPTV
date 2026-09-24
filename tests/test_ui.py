"""Startup, navigation, series screen and playback flow (Qt offscreen, no VLC)."""
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from core.database import Database
from core.m3u import parse_m3u_text
from tools.demo_data import demo_m3u


def pump(qapp, seconds=0.3):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        qapp.processEvents()
        time.sleep(0.01)


def wait_loaded(qapp, window, timeout=15):
    end = time.monotonic() + timeout
    while time.monotonic() < end and not window._loaded_once:
        qapp.processEvents()
        time.sleep(0.01)
    assert window._loaded_once


@pytest.fixture
def demo_db():
    parsed = parse_m3u_text(demo_m3u(channels=50, movies=200, series=8, max_episodes=120))
    db = Database()
    playlist_id = db.save_playlist("Demo", "M3U", url="http://list.demo.invalid/x.m3u")
    db.replace_cached_playlist(playlist_id, parsed.channels, parsed.vod_items, parsed.series_items)
    Database.reset_instance()
    return parsed


@pytest.fixture
def window(qapp):
    from ui.main_window import MainWindow
    win = MainWindow()
    win.resize(1400, 900)
    win.show()
    yield win
    win.close()
    pump(qapp, 0.1)


def test_first_run_opens_settings_without_blocking(qapp):
    import core.video_player as vp
    from ui.main_window import SETTINGS, MainWindow
    start = time.perf_counter()
    win = MainWindow()
    win.show()
    qapp.processEvents()
    assert time.perf_counter() - start < 3.0
    win.start()
    wait_loaded(qapp, win)
    assert win.stack.currentIndex() == SETTINGS
    assert win.settings_page.welcome.isVisible()
    assert vp._vlc_module is None, "VLC must not be loaded at startup"
    win.close()


def test_startup_with_saved_list(qapp, demo_db, window):
    from ui.main_window import HOME, SERIES, VOD
    window.start()
    wait_loaded(qapp, window)
    assert window.stack.currentIndex() == HOME
    assert "(50)" in window.tv_btn.text()
    window.open_section(VOD)
    assert window.stack.currentIndex() == VOD
    assert window.vod_page.model.rowCount() == 200
    window.vod_page.search.setText("Film 12")
    window.vod_page.apply_filter()
    items = window.vod_page.model.items
    assert items and all("film" in i.title.lower() and "12" in i.title for i in items)
    window.go_back()
    assert window.stack.currentIndex() == HOME
    window.open_section(SERIES)
    assert window.series_page.model.rowCount() > 0


def test_series_screen_and_autoplay_flow(qapp, demo_db, window):
    from ui.main_window import SERIES_DETAIL
    window.start()
    wait_loaded(qapp, window)
    groups = window.series_page.groups
    episodes = groups["Duga Demo Serija"]
    window.open_series(("Duga Demo Serija", episodes))
    page = window.series_detail
    assert window.stack.currentIndex() == SERIES_DETAIL
    assert len(page._season_keys) == 5
    assert page.model.rowCount() == 24
    assert page.model.rows[0].code == "S01E01"
    assert page.continue_btn.text().endswith("S01E01")

    # Switch season, then search across seasons and sort.
    page.season_list.setCurrentRow(2)
    assert page.model.rows[0].code == "S03E01"
    assert Database().get_series_state("Duga Demo Serija")["season"] == "3"
    page.search.setText("S02E1")
    assert {r.code for r in page.model.rows} >= {"S02E10", "S02E19"}
    page.search.clear()
    page._toggle_sort()
    assert page.model.rows[0].code == "S03E24"
    page._toggle_sort()

    # Play S03E05 -> state remembered, autoplay goes to S03E06, end of season -> S04E01
    target = next(e for e in episodes if e.season == "3" and e.episode == "5")
    window.play_episode(target, page.ordered, 0)
    assert window.series_queue[window.series_index].stream_id == target.stream_id
    assert Database().get_series_state("Duga Demo Serija")["episode_id"] == target.stream_id
    window.play_next_episode()
    assert (window.series_queue[window.series_index].season,
            window.series_queue[window.series_index].episode) == ("3", "6")
    last_of_season = next(e for e in episodes if e.season == "3" and e.episode == "24")
    window.play_episode(last_of_season, page.ordered, 0)
    window.play_next_episode()
    assert (window.series_queue[window.series_index].season,
            window.series_queue[window.series_index].episode) == ("4", "1")

    # Progress -> "Nastavi" on the exact episode and position; returning shows the same season.
    current = window.series_queue[window.series_index]
    Database().update_watch_progress(current.stream_id, "series", current.name, 754, 2600)
    window.on_playback_exited()
    assert "S04E01" in page.continue_btn.text() and "12:34" in page.continue_btn.text()
    assert page.current_season == "4"
    row = next(r for r in page.model.rows if r.episode.stream_id == current.stream_id)
    assert row.resumable and row.is_last

    # Finished episode -> watched; continue offers the next one.
    window.on_playback_finished("series")
    Database().update_watch_progress(current.stream_id, "series", current.name, 2600, 2600)
    page.refresh()
    assert "sledeću: S04E02" in page.continue_btn.text()
    page._on_action("watched", next(r for r in page.model.rows if r.episode.stream_id == current.stream_id))
    assert current.stream_id not in Database().get_watched_series_ids()


def test_movie_detail_resume_and_favorite(qapp, demo_db, window):
    from ui.main_window import VOD_DETAIL
    window.start()
    wait_loaded(qapp, window)
    vod = demo_db.vod_items[5]
    Database().update_watch_progress(vod.stream_id, "vod", vod.name, 125, 5000)
    window.open_vod(vod)
    page = window.vod_detail
    assert window.stack.currentIndex() == VOD_DETAIL
    assert page.resume_btn.isVisible() and "2:05" in page.resume_btn.text()
    page._toggle_favorite()
    assert Database().is_vod_favorite(vod.stream_id)
    played = []
    page.play_requested.connect(lambda item, pos: played.append(pos))
    page._resume()
    assert played == [125]


def test_settings_detects_xtream_link(qapp, window):
    from ui.main_window import SETTINGS
    window.start()
    wait_loaded(qapp, window)
    assert window.stack.currentIndex() == SETTINGS
    requested = []
    window.settings_page.load_requested.disconnect()
    window.settings_page.load_requested.connect(lambda source, name: requested.append((source, name)))
    window.settings_page.url_input.setText("http://srv.demo.invalid:8080/get.php?username=a&password=b&type=m3u")
    assert "Xtream" in window.settings_page.url_hint.text()
    window.settings_page._submit()
    source, name = requested[0]
    assert source["type"] == "Xtream" and source["server"] == "http://srv.demo.invalid:8080"
    window.settings_page.url_input.setText("ne-valja")
    window.settings_page._submit()
    assert len(requested) == 1 and window.settings_page.error.isVisible()


def test_load_file_from_settings_and_cancel(qapp, window, fixtures_dir):
    from ui.main_window import HOME
    window.start()
    wait_loaded(qapp, window)
    window.load_playlist({"type": "M3U", "url": str(fixtures_dir / "sample.m3u")}, "Uzorak")
    end = time.monotonic() + 10
    while time.monotonic() < end and window.parsed is None:
        qapp.processEvents()
        time.sleep(0.01)
    assert window.parsed is not None and window.stack.currentIndex() == HOME
    assert not window.overlay.isVisible()
    # Reload a list that survives a restart
    Database.reset_instance()
    assert Database().get_last_playlist()["name"] == "Uzorak"
    # Cancel a (slow) load: the cancel is immediate and the old list stays.
    class Slow(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            time.sleep(4)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"#EXTM3U\n#EXTINF:-1,X\nhttp://a.invalid/1.ts\n")

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Slow)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    window.load_playlist({"type": "M3U", "url": f"http://127.0.0.1:{httpd.server_address[1]}/slow.m3u"}, "Spora")
    pump(qapp, 0.2)
    started = time.monotonic()
    window.cancel_loading()
    pump(qapp, 0.2)
    assert time.monotonic() - started < 1.0, "cancel must be immediate"
    assert not window.overlay.isVisible()
    pump(qapp, 4.5)  # the late result of the abandoned worker must be ignored
    assert window.parsed.total == 10
    assert Database().get_last_playlist()["name"] == "Uzorak"
    httpd.shutdown()
