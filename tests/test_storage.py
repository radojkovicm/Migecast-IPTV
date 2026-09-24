"""Encryption, database migration, watch progress, series state, legacy import."""
import sqlite3
from pathlib import Path

from core.database import SCHEMA_VERSION, Database
from core.m3u import parse_m3u_text, url_id
from utils import paths
from utils.log_setup import redact
from utils.security import SecurityManager


def test_encrypt_roundtrip_and_key_persistence(isolated_data_dir):
    manager = SecurityManager()
    token = manager.encrypt_password("tajna")
    assert token != "tajna" and manager.is_encrypted(token)
    assert SecurityManager().decrypt_password(token) == "tajna"
    assert manager.decrypt_password("garbage") == ""
    key_file = paths.data_dir() / "secret.key"
    assert key_file.exists() and b"tajna" not in key_file.read_bytes()


def test_legacy_env_key_is_imported(isolated_data_dir):
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    paths.data_dir().mkdir(parents=True)
    (paths.data_dir() / ".env").write_text(f"ENCRYPTION_KEY='{key.decode()}'\n")
    token = Fernet(key).encrypt(b"old").decode()
    assert SecurityManager().decrypt_password(token) == "old"


def test_playlist_credentials_are_encrypted_at_rest(isolated_data_dir):
    db = Database()
    db.save_playlist("X", "Xtream", server="http://srv.invalid", username="user", password="pass123")
    db.save_playlist("U", "M3U", url="http://srv.invalid/get.m3u?token=abc")
    raw = paths.database_path().read_bytes()
    assert b"pass123" not in raw and b"token=abc" not in raw
    active = db.get_last_playlist()
    assert active["url"] == "http://srv.invalid/get.m3u?token=abc"
    playlists = {p.name: db.get_playlist(p.id) for p in db.get_all_playlists()}
    assert playlists["X"]["password"] == "pass123"


def _create_v1_database(path: Path, playlist_url: str, items):
    """Schema and content as written by MigeCast 1.x."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript("""
        CREATE TABLE favorite_channels (id INTEGER PRIMARY KEY, channel_id VARCHAR UNIQUE NOT NULL, name VARCHAR, added_at DATETIME);
        CREATE TABLE favorite_vod (id INTEGER PRIMARY KEY, stream_id VARCHAR UNIQUE NOT NULL, name VARCHAR, added_at DATETIME);
        CREATE TABLE favorite_series (id INTEGER PRIMARY KEY, series_id VARCHAR UNIQUE NOT NULL, name VARCHAR, added_at DATETIME);
        CREATE TABLE watched_vod (id INTEGER PRIMARY KEY, stream_id VARCHAR UNIQUE NOT NULL, name VARCHAR, watched_at DATETIME);
        CREATE TABLE watched_series (id INTEGER PRIMARY KEY, stream_id VARCHAR NOT NULL, series_id VARCHAR, name VARCHAR, season VARCHAR, episode VARCHAR, watched_at DATETIME);
        CREATE TABLE saved_playlists (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL, type VARCHAR, url VARCHAR, server VARCHAR, username VARCHAR, password VARCHAR, is_active BOOLEAN, added_at DATETIME, last_loaded DATETIME, last_refreshed DATETIME);
        CREATE TABLE cached_channels (id INTEGER PRIMARY KEY, channel_id VARCHAR NOT NULL, name VARCHAR, url VARCHAR, logo VARCHAR, category VARCHAR, playlist_id INTEGER NOT NULL);
        CREATE TABLE cached_vod (id INTEGER PRIMARY KEY, stream_id VARCHAR NOT NULL, name VARCHAR, url VARCHAR, cover VARCHAR, plot TEXT, rating VARCHAR, year VARCHAR, genre VARCHAR, duration VARCHAR, director VARCHAR, "cast" TEXT, category VARCHAR, playlist_id INTEGER NOT NULL);
        CREATE TABLE cached_series (id INTEGER PRIMARY KEY, stream_id VARCHAR NOT NULL, name VARCHAR, url VARCHAR, cover VARCHAR, plot TEXT, rating VARCHAR, year VARCHAR, genre VARCHAR, director VARCHAR, "cast" TEXT, category VARCHAR, season VARCHAR, episode VARCHAR, playlist_id INTEGER NOT NULL);
        CREATE TABLE watch_progress (id INTEGER PRIMARY KEY, stream_id VARCHAR UNIQUE NOT NULL, content_type VARCHAR NOT NULL, name VARCHAR, position_seconds INTEGER, duration_seconds INTEGER, last_watched DATETIME, completed BOOLEAN);
        CREATE TABLE tmdb_cache (id INTEGER PRIMARY KEY, stream_id VARCHAR UNIQUE NOT NULL, title VARCHAR, tmdb_id INTEGER, rating FLOAT, vote_count INTEGER, overview TEXT, genres VARCHAR, release_date VARCHAR, runtime INTEGER, director VARCHAR, "cast" TEXT, poster_path VARCHAR, backdrop_path VARCHAR, cached_at DATETIME);
    """)
    conn.execute("INSERT INTO saved_playlists (id, name, type, url, is_active) VALUES (1, 'Stara', 'M3U', ?, 1)", (playlist_url,))
    for legacy_id, name, url in items:
        conn.execute("INSERT INTO cached_vod (stream_id, name, url, category, playlist_id) VALUES (?, ?, ?, 'Filmovi', 1)",
                     (legacy_id, name, url))
    conn.execute("INSERT INTO cached_channels (channel_id, name, url, category, playlist_id) VALUES ('demo1.rs', 'K', 'http://h/live/1.ts', 'TV', 1)")
    first_id = items[0][0]
    conn.execute("INSERT INTO favorite_vod (stream_id, name) VALUES (?, 'f')", (first_id,))
    conn.execute("INSERT INTO watched_vod (stream_id, name) VALUES (?, 'f')", (first_id,))
    conn.execute("INSERT INTO watch_progress (stream_id, content_type, name, position_seconds, duration_seconds, completed) VALUES (?, 'vod', 'f', 600, 6000, 0)", (first_id,))
    conn.execute("INSERT INTO favorite_channels (channel_id, name) VALUES ('demo1.rs', 'K')")
    conn.execute("INSERT INTO favorite_series (series_id, name) VALUES ('Demo Serija', 'Demo Serija')")
    conn.commit()
    conn.close()


def test_migration_from_v1_rekeys_ids_and_keeps_user_data(isolated_data_dir):
    items = [("-4199219117042205212", "Film A", "http://h/movie/a.mkv"),
             ("1679849040774549068", "Film B", "http://h/movie/b.mkv")]
    _create_v1_database(paths.database_path(), "C:/lists/demo.m3u", items)

    db = Database()
    new_id = url_id("http://h/movie/a.mkv")
    assert db.get_all_vod_favorite_ids() == {new_id}
    assert db.get_all_watched_vod_ids() == {new_id}
    assert db.get_watch_progress(new_id).position_seconds == 600
    assert db.get_favorite_channel_ids() == {"demo1.rs"}
    assert db.get_all_series_favorite_ids() == {"Demo Serija"}

    playlist = db.get_last_playlist()
    channels, vod, series = db.load_cached_playlist(playlist["id"])
    assert {v.stream_id for v in vod} == {new_id, url_id("http://h/movie/b.mkv")}
    # After re-parsing the same file, IDs match the migrated ones.
    reparsed = parse_m3u_text('#EXTM3U\n#EXTINF:-1 group-title="Filmovi",Film A\nhttp://h/movie/a.mkv\n')
    assert reparsed.vod_items[0].stream_id == new_id

    backups = list(paths.backups_dir().glob("migecast-before-v*.db"))
    assert len(backups) == 1
    conn = sqlite3.connect(str(paths.database_path()))
    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    conn.close()


def test_migration_is_idempotent(isolated_data_dir):
    _create_v1_database(paths.database_path(), "x.m3u", [("-4199219117042205212", "A", "http://h/a.mkv")])
    Database()
    Database.reset_instance()
    Database()
    assert len(list(paths.backups_dir().glob("migecast-before-v*.db"))) == 1


def test_cache_roundtrip_and_refresh(fixtures_dir):
    db = Database()
    parsed = parse_m3u_text((fixtures_dir / "sample.m3u").read_text(encoding="utf-8"))
    playlist_id = db.save_playlist("Demo", "M3U", url=str(fixtures_dir / "sample.m3u"))
    assert db.replace_cached_playlist(playlist_id, parsed.channels, parsed.vod_items, parsed.series_items)
    channels, vod, series = db.load_cached_playlist(playlist_id)
    assert len(channels) == 3 and len(vod) == 2 and len(series) == 5
    assert series[0].series_name == "Demo Serija"
    # Refresh replaces instead of duplicating.
    db.replace_cached_playlist(playlist_id, parsed.channels, parsed.vod_items, parsed.series_items)
    assert len(db.load_cached_playlist(playlist_id)[0]) == 3
    assert db.get_last_playlist()["last_refreshed"] is not None


def test_watch_progress_and_continue_watching():
    db = Database()
    db.update_watch_progress("e1", "series", "Ep 1", 300, 3000)
    db.update_watch_progress("e2", "series", "Ep 2", 2950, 3000)
    db.update_watch_progress("m1", "vod", "Film", 600, 6000)
    assert db.get_progress_map(["e1", "e2"]) == {"e1": (300, 3000, False), "e2": (2950, 3000, True)}
    assert [p.stream_id for p in db.get_continue_watching(content_type="series")] == ["e1"]
    assert {p.stream_id for p in db.get_continue_watching()} == {"e1", "m1"}
    db.delete_watch_progress("e1")
    assert db.get_watch_progress("e1") is None


def test_series_state_and_watched():
    db = Database()
    assert db.get_series_state("Demo") is None
    db.set_series_state("Demo", season="2")
    db.set_series_state("Demo", episode_id="ep5")
    assert db.get_series_state("Demo") == {"season": "2", "episode_id": "ep5"}
    db.mark_series_watched("ep5", "Ep", "Demo", "2", "5")
    db.mark_series_watched("ep5", "Ep", "Demo", "2", "5")
    assert db.get_watched_series_ids(["ep5", "ep6"]) == {"ep5"}
    db.mark_series_unwatched("ep5")
    assert db.get_watched_series_ids() == set()


def test_series_favorite_rename():
    db = Database()
    db.add_series_favorite("Old Name")
    assert db.rename_series_favorites({"Old Name": "New Name"}) == 1
    assert db.get_all_series_favorite_ids() == {"New Name"}


def test_legacy_install_import(tmp_path, monkeypatch):
    from core import legacy_import
    old = tmp_path / "old_install" / "data"
    _create_v1_database(old / "migecast.db", "x.m3u", [("-4199219117042205212", "A", "http://h/a.mkv")])
    (old / "config.json").write_text('{"appearance": {"theme": "light"}}')
    monkeypatch.setattr(paths, "legacy_data_dirs", lambda: [old])
    assert legacy_import.import_legacy_install() == old
    assert (old / "migecast.db").exists(), "original must be kept"
    assert paths.database_path().exists()
    from utils.config import Config
    assert Config().get("appearance", "theme") == "light"
    assert legacy_import.import_legacy_install() is None  # only once


def test_log_redaction():
    line = redact("Playing http://line.example.invalid:80/abcuser/abcpass/123 and get.php?username=u1&password=p1 C:\\Users\\KATA\\list.m3u")
    assert "abcuser" not in line and "abcpass" not in line
    assert "u1" not in line and "p1" not in line
    assert "KATA" not in line
    assert "line.example.invalid:80" in line
