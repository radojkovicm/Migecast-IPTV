"""Synthetic demo playlist for tests, screenshots and manual QA.

Contains no real IPTV data: every host uses the reserved ``.invalid`` TLD.
"""
import random


def demo_m3u(channels: int = 300, movies: int = 1500, series: int = 40, max_episodes: int = 240,
             seed: int = 7, image_base: str = "http://img.demo.invalid") -> str:
    rng = random.Random(seed)
    lines = ["#EXTM3U"]
    groups = ["Informativni", "Sport", "Filmski kanali", "Dečiji", "Muzika", "Dokumentarni"]
    for i in range(channels):
        group = groups[i % len(groups)]
        lines.append(f'#EXTINF:-1 tvg-id="demo{i}.tv" tvg-logo="{image_base}/ch/{i}.png" '
                     f'group-title="{group}",Demo Kanal {i + 1}')
        lines.append(f"http://stream.demo.invalid/live/demo/demo/{1000 + i}.ts")
    genres = ["Filmovi | Akcija", "Filmovi | Komedija", "Filmovi | Drama", "Filmovi | Domaći"]
    for i in range(movies):
        year = 1970 + (i % 55)
        lines.append(f'#EXTINF:-1 tvg-logo="{image_base}/m/{i}.jpg" group-title="{rng.choice(genres)}",'
                     f"Demo Film {i + 1} ({year})")
        lines.append(f"http://stream.demo.invalid/movie/demo/demo/{5000 + i}.mkv")
    for s in range(series):
        episodes = max_episodes if s == 0 else rng.randint(4, 40)
        seasons = max(1, episodes // 24) if s == 0 else rng.randint(1, 4)
        name = f"Demo Serija {s + 1}" if s else "Duga Demo Serija"
        for e in range(episodes):
            season = e % seasons + 1 if s else e // 24 + 1
            number = e // seasons + 1 if s else e % 24 + 1
            lines.append(f'#EXTINF:-1 tvg-logo="{image_base}/s/{s}.jpg" group-title="Serije | Drame",'
                         f"{name} S{season:02d}E{number:02d}")
            lines.append(f"http://stream.demo.invalid/series/demo/demo/{90000 + s * 1000 + e}.mp4")
    lines.append('#EXTINF:-1 group-title="Serije",Serija Bez Sezone E01')
    lines.append("http://stream.demo.invalid/series/demo/demo/99001.mp4")
    lines.append('#EXTINF:-1 group-title="Serije",Serija Bez Sezone E02')
    lines.append("http://stream.demo.invalid/series/demo/demo/99002.mp4")
    return "\n".join(lines) + "\n"
