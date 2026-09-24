import pytest

from core.m3u import (NotAPlaylist, classify, detect_xtream_url, episode_code, group_series,
                      is_legacy_hash_id, legacy_series_name, parse_episode_info, parse_m3u_text,
                      sort_episodes, url_id)


def load(fixtures_dir):
    return parse_m3u_text((fixtures_dir / "sample.m3u").read_text(encoding="utf-8"))


def test_parse_counts_and_types(fixtures_dir):
    result = load(fixtures_dir)
    assert [c.name for c in result.channels] == ["Demo Kanal 1", "Demo Kanal 1 HD", "Sport Klub S1"]
    assert [v.name for v in result.vod_items] == ["Demo Film (2020)", "Stari Film.mp4"]
    assert len(result.series_items) == 5


def test_attributes_with_commas_in_quotes(fixtures_dir):
    channel = load(fixtures_dir).channels[0]
    assert channel.category == "Informativni, Srbija"
    assert channel.logo == "http://img.example.invalid/demo1.png"
    assert channel.channel_id == "demo1.rs"
    assert channel.epg_id == "demo1.rs"


def test_duplicate_tvg_id_gets_unique_id(fixtures_dir):
    channels = load(fixtures_dir).channels
    assert channels[0].channel_id != channels[1].channel_id
    assert channels[1].channel_id == url_id(channels[1].url)


def test_empty_logo_is_none(fixtures_dir):
    assert load(fixtures_dir).channels[2].logo is None


def test_stable_ids_across_parses(fixtures_dir):
    first = load(fixtures_dir)
    second = load(fixtures_dir)
    assert [v.stream_id for v in first.vod_items] == [v.stream_id for v in second.vod_items]
    assert all(v.stream_id.startswith("u") and len(v.stream_id) == 17 for v in first.vod_items)


def test_series_fields(fixtures_dir):
    series = load(fixtures_dir).series_items
    first = series[0]
    assert (first.series_name, first.season, first.episode) == ("Demo Serija", "1", "1")
    assert (series[1].season, series[1].episode) == ("1", "2")
    assert (series[3].series_name, series[3].season, series[3].episode) == ("Druga Serija", "1", "5")
    assert (series[4].series_name, series[4].season, series[4].episode) == ("Bez Sezone", None, "7")


def test_group_and_sort(fixtures_dir):
    groups = group_series(load(fixtures_dir).series_items)
    assert list(groups) == ["Demo Serija", "Druga Serija", "Bez Sezone"]
    ordered = sort_episodes(list(reversed(groups["Demo Serija"])))
    assert [episode_code(e.season, e.episode) for e in ordered] == ["S01E01", "S01E02", "S02E01"]


@pytest.mark.parametrize("title,expected", [
    ("Show S01E03", ("Show", 1, 3)),
    ("Show s1e3", ("Show", 1, 3)),
    ("Show - S01 E03 - Title", ("Show", 1, 3)),
    ("Show.S01.E03.1080p", ("Show", 1, 3)),
    ("Show 2x11", ("Show", 2, 11)),
    ("Show Sezona 3 Epizoda 12", ("Show", 3, 12)),
    ("Show Season 1 Episode 2", ("Show", 1, 2)),
    ("RS| Moja Serija S10E100", ("RS| Moja Serija", 10, 100)),
    ("Show E07", ("Show", None, 7)),
])
def test_parse_episode_info(title, expected):
    info = parse_episode_info(title)
    assert (info.series_name, info.season, info.episode) == expected


def test_parse_episode_info_none():
    assert parse_episode_info("Demo Film (2020)") is None
    assert parse_episode_info("") is None


def test_episode_code():
    assert episode_code("1", "3") == "S01E03"
    assert episode_code(None, 7) == "E07"
    assert episode_code(None, None) == ""


@pytest.mark.parametrize("name,group,url,kind", [
    ("CNN", "News", "http://h/live/u/p/1.ts", "tv"),
    ("Film", "Anything", "http://h/movie/u/p/1.mkv", "movie"),
    ("Ep", "Anything", "http://h/series/u/p/1.mkv", "series"),
    ("Sport Klub S1", "Sport", "http://h/stream/1.ts", "tv"),
    ("Show S01E01", "Misc", "http://h/x.mp4", "series"),
    ("Movie", "FILMOVI", "http://h/x", "movie"),
    ("Clip", "Misc", "http://h/clip.mp4", "movie"),
    ("RTS 1", "Srbija", "http://h/rts1", "tv"),
])
def test_classify(name, group, url, kind):
    assert classify(name, group, url) == kind


def test_detect_xtream_url():
    account = detect_xtream_url("http://example.invalid:8080/get.php?username=demo&password=secret&type=m3u_plus&output=ts")
    assert account.server == "http://example.invalid:8080"
    assert (account.username, account.password) == ("demo", "secret")
    assert detect_xtream_url("https://example.invalid/sub/player_api.php?username=a&password=b").server == "https://example.invalid/sub"
    assert detect_xtream_url("http://example.invalid/list.m3u") is None
    assert detect_xtream_url("http://example.invalid/get.php?username=a") is None
    assert detect_xtream_url("not a url") is None


def test_not_a_playlist():
    with pytest.raises(NotAPlaylist):
        parse_m3u_text("<html><body>404</body></html>")


def test_empty_and_plain_url_list():
    assert parse_m3u_text("#EXTM3U\n").total == 0
    plain = parse_m3u_text("http://h/a.ts\nhttp://h/b.ts\n")
    assert plain.total == 2


def test_crlf_and_bom():
    text = "﻿#EXTM3U\r\n#EXTINF:-1 group-title=\"News\",One\r\nhttp://h/1.ts\r\n"
    result = parse_m3u_text(text)
    assert [c.name for c in result.channels] == ["One"]


def test_large_playlist_is_fast():
    import time
    lines = ["#EXTM3U"]
    for i in range(60000):
        group = ("Serije" if i % 3 == 0 else "Filmovi" if i % 3 == 1 else "TV")
        name = f"Serija {i // 30} S01E{i % 30 + 1:02d}" if i % 3 == 0 else f"Naziv {i}"
        lines.append(f'#EXTINF:-1 tvg-logo="http://img/{i}.png" group-title="{group}",{name}')
        lines.append(f"http://h/{i}.ts")
    start = time.perf_counter()
    result = parse_m3u_text("\n".join(lines))
    assert result.total == 60000
    assert time.perf_counter() - start < 10


def test_legacy_helpers():
    assert legacy_series_name("Demo Serija S01E01 Naslov") == "Demo Serija"
    assert is_legacy_hash_id("-4199219117042205212")
    assert is_legacy_hash_id("1679849040774549068")
    assert not is_legacy_hash_id("12345")
    assert not is_legacy_hash_id("demo1.rs")
