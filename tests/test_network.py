"""Loading from URL, timeouts, network errors, cancellation and Xtream API
against a local HTTP server with synthetic data."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

from core import net, xtream
from core.net import CancelToken, Cancelled, NetworkError
from core.playlist_service import PlaylistError, load_playlist, source_from_user_input

M3U = "#EXTM3U\n#EXTINF:-1 group-title=\"News\",Demo\nhttp://stream.invalid/1.ts\n"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="text/plain"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parts = urlsplit(self.path)
        query = {k: v[0] for k, v in parse_qs(parts.query).items()}
        if parts.path == "/list.m3u":
            return self._send(200, M3U)
        if parts.path == "/empty.m3u":
            return self._send(200, "#EXTM3U\n")
        if parts.path == "/html":
            return self._send(200, "<html>nope</html>", "text/html")
        if parts.path == "/missing":
            return self._send(404, "no")
        if parts.path == "/slow":
            time.sleep(3)
            return self._send(200, M3U)
        if parts.path == "/big":
            self.send_response(200)
            self.end_headers()
            try:
                for _ in range(400):
                    self.wfile.write(b"#EXTINF:-1,x\nhttp://a/b.ts\n" * 2000)
                    time.sleep(0.01)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return None
        if parts.path == "/player_api.php":
            if query.get("password") != "good":
                return self._send(200, json.dumps({"user_info": {"auth": 0}}), "application/json")
            action = query.get("action")
            payloads = {
                None: {"user_info": {"auth": 1, "status": "Active", "allowed_output_formats": ["m3u8", "ts"]}},
                "get_live_categories": [{"category_id": "1", "category_name": "Vesti"}],
                "get_live_streams": [{"stream_id": 11, "name": "Kanal", "category_id": "1", "stream_icon": ""}],
                "get_vod_categories": [{"category_id": "2", "category_name": "Akcija"}],
                "get_vod_streams": [{"stream_id": 22, "name": "Film", "category_id": "2", "container_extension": "mkv"}],
                "get_series_categories": [{"category_id": "3", "category_name": "Drame"}],
                "get_series": [{"series_id": 33, "name": "Serija", "category_id": "3", "cover": "http://img.invalid/c.jpg"}],
                "get_series_info": {"info": {"name": "Serija"}, "episodes": {
                    "1": [{"id": "331", "episode_num": 1, "season": 1, "title": "Serija S01E01 Pilot", "container_extension": "mp4"},
                          {"id": "332", "episode_num": 2, "season": 1, "title": "Serija S01E02", "container_extension": "mp4"}],
                    "2": [{"id": "341", "episode_num": 1, "season": 2, "title": "", "container_extension": "mkv"}]}},
            }
            return self._send(200, json.dumps(payloads.get(action, [])), "application/json")
        return self._send(404, "")


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_load_m3u_url(server):
    result = load_playlist({"type": "M3U", "url": server + "/list.m3u"})
    assert [c.name for c in result.channels] == ["Demo"]


def test_empty_list_error(server):
    with pytest.raises(PlaylistError, match="prazna"):
        load_playlist({"type": "M3U", "url": server + "/empty.m3u"})


def test_html_is_rejected(server):
    with pytest.raises(PlaylistError, match="nije IPTV"):
        load_playlist({"type": "M3U", "url": server + "/html"})


def test_404(server):
    with pytest.raises(PlaylistError, match="404"):
        load_playlist({"type": "M3U", "url": server + "/missing"})


def test_unreachable_server():
    with pytest.raises(PlaylistError, match="nije dostupan"):
        load_playlist({"type": "M3U", "url": "http://127.0.0.1:9/list.m3u"})


def test_timeout(server):
    with pytest.raises(NetworkError) as info:
        net.fetch_bytes(server + "/slow", retries=0, timeout=(2, 0.5))
    assert info.value.kind == "timeout"


def test_cancel_during_download(server):
    token = CancelToken()
    threading.Timer(0.3, token.cancel).start()
    start = time.monotonic()
    with pytest.raises(Cancelled):
        net.fetch_bytes(server + "/big", cancel=token)
    assert time.monotonic() - start < 3


def test_cancel_before_start():
    token = CancelToken()
    token.cancel()
    with pytest.raises(Cancelled):
        load_playlist({"type": "M3U", "url": "http://127.0.0.1:9/x"}, cancel=token)


def test_missing_file():
    with pytest.raises(PlaylistError, match="nije pronađen"):
        load_playlist({"type": "M3U", "url": "C:/definitely/missing/list.m3u"})


def test_local_file(fixtures_dir):
    result = load_playlist({"type": "M3U", "url": str(fixtures_dir / "sample.m3u")})
    assert result.total == 10


def test_source_from_user_input_detects_xtream():
    source = source_from_user_input("  http://host.invalid:80/get.php?username=u&password=p&type=m3u_plus ")
    assert source == {"type": "Xtream", "server": "http://host.invalid:80", "username": "u", "password": "p"}
    assert source_from_user_input("https://host.invalid/list.m3u") == {"type": "M3U", "url": "https://host.invalid/list.m3u"}
    with pytest.raises(PlaylistError):
        source_from_user_input("")
    with pytest.raises(PlaylistError):
        source_from_user_input("ftp:/broken://")


def test_xtream_account(server):
    result = load_playlist({"type": "Xtream", "server": server, "username": "demo", "password": "good"})
    assert result.channels[0].category == "Vesti"
    assert result.channels[0].url == "xtream:live/11.ts"
    assert result.vod_items[0].url == "xtream:movie/22.mkv"
    stub = result.series_items[0]
    assert stub.is_series_stub and stub.xtream_series_id == "33"
    episodes = xtream.fetch_series_episodes(server, "demo", "good", stub)
    assert [(e.season, e.episode) for e in episodes] == [("1", "1"), ("1", "2"), ("2", "1")]
    assert episodes[0].episode_title == "Pilot"
    assert xtream.resolve_url("xtream:series/331.mp4", server, "demo", "good") == f"{server}/series/demo/good/331.mp4"


def test_xtream_wrong_password(server):
    with pytest.raises(PlaylistError, match="Pogrešno"):
        load_playlist({"type": "Xtream", "server": server, "username": "demo", "password": "bad"})


def test_resolve_passthrough():
    assert xtream.resolve_url("http://a/b.ts", "s", "u", "p") == "http://a/b.ts"
