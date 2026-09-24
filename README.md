# MigeCast IPTV

A simple, fast IPTV player for Windows 10/11 (x64), designed for older users who
only use a mouse: three huge buttons (**TV**, **Filmovi**, **Serije**), large
text, clear **Nazad / Pusti / Nastavi / Favorit** buttons and no technical
settings. The user interface is in Serbian (Latin script).

MigeCast does not provide any channels. It plays the M3U/M3U8 playlist or
Xtream Codes account supplied by the user's IPTV provider.

## For users

1. Download `MigeCast-Setup-<version>.exe` (one file) from the download page / GitHub Releases.
2. Run it and follow the steps. No administrator rights are needed.
3. Start **MigeCast IPTV** from the desktop or the Start menu.
4. Open **Podešavanja**, paste the playlist link (or pick a file, or enter the Xtream server, user and password) and click **Učitaj listu**.

Nothing else has to be installed: Python, Qt, libVLC with all plugins and the
Microsoft C/C++ runtime DLLs are part of the installer.

## Features

- M3U/M3U8 from a file or URL, paste from clipboard, automatic detection of full Xtream `get.php` links, Xtream server/user/password form.
- Live TV list with favorites (★), next/previous channel, auto-reconnect when a stream drops.
- Movies and series as poster grids with search, categories, *Favoriti* and *Nastavi gledanje*.
- Series screen: seasons as large buttons, episodes as rows with `S01E03`, title, progress and *Pusti / Nastavi / Od početka / Odgledano*; episode search and sort; remembers the last season and episode; automatically plays the next episode (also across seasons); returns to the same series, season and episode after playback.
- Watch progress with resume for movies and episodes.
- Dark, light and high-contrast themes.

## Where user data is stored

| What | Location |
|---|---|
| Database (playlists, cache, favorites, progress, watched) | `%LOCALAPPDATA%\MigeCast\data\migecast.db` |
| Settings | `%LOCALAPPDATA%\MigeCast\data\config.json` |
| Encryption key (Xtream passwords, playlist URLs) | `%LOCALAPPDATA%\MigeCast\data\secret.key` (protected with Windows DPAPI) |
| Poster cache (max. 300 MB, oldest removed first) | `%LOCALAPPDATA%\MigeCast\cache\images` |
| Logs (rotating, credentials and stream URLs are redacted) | `%LOCALAPPDATA%\MigeCast\logs` |
| Automatic database backups before schema migrations | `%LOCALAPPDATA%\MigeCast\backups` |

The program folder (`%LOCALAPPDATA%\Programs\MigeCast`) contains only program
files. The folder can be opened from *Podešavanja → O programu*.

**Removing all data:** uninstall MigeCast, then delete `%LOCALAPPDATA%\MigeCast`.

### Upgrades

Installing a newer `MigeCast-Setup-*.exe` over an existing installation
replaces the program files and keeps everything in `%LOCALAPPDATA%\MigeCast`
(same `AppId` in the Inno Setup script). Uninstall + reinstall keeps the data too.

When the database schema changes, MigeCast first writes a backup to
`%LOCALAPPDATA%\MigeCast\backups` and then migrates in place (see
`core/database.py`, `migrate_schema`). Version 2.0 migration:

- adds new columns and the `series_state` table,
- re-keys items of M3U playlists that 1.x identified with Python's randomised
  `hash(url)` to a stable SHA-1 based ID and updates favorites, watched flags and
  watch progress accordingly.

Data of version 1.x (portable folder with `data\migecast.db` next to the
program) is copied automatically on first start if MigeCast is started from
that folder, or can be imported with *Podešavanja → Uvezi podatke iz stare
verzije*. Originals are never modified or deleted.

## Building the installer

The release build runs on GitHub Actions (`.github/workflows/windows-build.yml`)
on every push; a tag `v*` publishes a GitHub Release. Steps (reproducible
locally on Windows 10/11 x64 with Python 3.11 and Inno Setup 6):

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements-build.txt -r requirements-dev.txt
$env:QT_QPA_PLATFORM="offscreen"; python -m pytest -q; Remove-Item Env:QT_QPA_PLATFORM

# libVLC 3.0.21 (official VideoLAN build), checksum verified
Invoke-WebRequest https://download.videolan.org/pub/videolan/vlc/3.0.21/win64/vlc-3.0.21-win64.zip -OutFile vlc.zip
Invoke-WebRequest https://download.videolan.org/pub/videolan/vlc/3.0.21/win64/vlc-3.0.21-win64.zip.sha256 -OutFile vlc.zip.sha256
# compare (Get-FileHash vlc.zip).Hash with the value in vlc.zip.sha256
Expand-Archive vlc.zip vendor-tmp
New-Item -ItemType Directory vendor\vlc
Copy-Item vendor-tmp\vlc-3.0.21\libvlc.dll, vendor-tmp\vlc-3.0.21\libvlccore.dll vendor\vlc\
Copy-Item vendor-tmp\vlc-3.0.21\plugins vendor\vlc\ -Recurse
vendor-tmp\vlc-3.0.21\vlc-cache-gen.exe vendor\vlc\plugins

$version = python tools/stamp_version.py        # writes build date + commit
pyinstaller MigeCast.spec --noconfirm --clean    # -> dist\MigeCast (one-folder)
python tools/verify_bundle.py dist\MigeCast      # completeness + no private files
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" "/DAppVersion=$version" installer\MigeCast.iss
# -> installer\Output\MigeCast-Setup-<version>.exe
pwsh installer\test_installer.ps1 -Installer installer\Output\MigeCast-Setup-$version.exe
```

`tools/stamp_version.py` modifies `version.py`; do not commit that change.

### Checksum

```powershell
Get-FileHash installer\Output\MigeCast-Setup-2.0.0.exe -Algorithm SHA256
```

CI writes `MigeCast-Setup-<version>.exe.sha256` next to the installer and
attaches both to the GitHub Release. `tools/update_site_release.py` writes
`site/release.json` (version, size, date, SHA-256, final download URL) for the
download page.

## Why an installer and not a one-file EXE

See [docs/DISTRIBUTION.md](docs/DISTRIBUTION.md). In short: a PyInstaller
`--onefile` EXE must unpack ~150 MB (Qt + libVLC) into `%TEMP%` on every
start, which takes several seconds on older PCs and often triggers antivirus
heuristics. A plain one-folder ZIP requires users to keep the `_internal`
folder next to the EXE. An Inno Setup installer is one download, installs the
one-folder build once, and every later start is as fast as possible.

## Startup performance

Double-clicking shows a splash screen immediately: the PyInstaller bootloader
draws it before Python and Qt are loaded. The first start after installation
("cold") is dominated by Windows reading and virus-scanning the Qt DLLs once,
and the splash covers that time. Every later start ("warm") shows the main
window in well under a second on a normal PC.

The main window is shown with only the header and the home screen; the other
pages are built right after it is visible. The database, playlist cache and
images are loaded after that; those load in background threads while a large *Učitavam listu…*
message is shown. libVLC is loaded on the first playback. Every start logs a
profile (`[startup] ...` lines in the log). Measured in the development
container (Linux, offscreen Qt, 8,700-item real-world database copy):

| Phase | Time since process start |
|---|---|
| Qt imported | ~50 ms |
| Main window built | ~230 ms |
| Window visible | ~250 ms |
| Database opened (incl. migration on first run) | ~550 ms |
| Cached playlist shown | ~650 ms |

The Windows CI job measures the installed build (including the PyInstaller
bootloader) on every run, prints every phase, and fails if a warm start takes
longer than 3 s on average or a cold start longer than 10 s. The numbers are
also in the `installer-test-reports` artifact.

## Development

```bash
pip install -r requirements-dev.txt
QT_QPA_PLATFORM=offscreen python -m pytest -q     # 70 tests
python main.py --windowed                         # run from source (needs VLC installed or vendor/vlc)
python tools/screenshots.py shots dark            # render all pages with synthetic data
python tools/check_repo_secrets.py                # fail on committed private data
```

Tests use only synthetic data (`tests/fixtures`, `tools/demo_data.py`, hosts
under the reserved `.invalid` TLD) and an isolated data folder
(`MIGECAST_DATA_DIR`).

| Area | Tests |
|---|---|
| M3U/M3U8 parser, classification TV/movie/series, `S01E03` parsing, stable IDs, Xtream URL detection | `tests/test_m3u.py` |
| Loading from URL, timeouts, network errors, cancellation, Xtream API | `tests/test_network.py` |
| Encryption, credentials at rest, 1.x database migration, watch progress, series state, legacy import, log redaction | `tests/test_storage.py` |
| Image cache: worker threads, de-duplication, failures, disk LRU, GUI responsiveness | `tests/test_image_cache.py` |
| Startup, first run, navigation, series with many seasons, autoplay, resume, settings, cancel | `tests/test_ui.py` |
| Install, upgrade, uninstall, reinstall, bundled VLC, startup time | `installer/test_installer.ps1` (Windows CI) |

## Privacy and security

- No playlist, password, database, log or cache is part of the repository or the installer (`tools/check_repo_secrets.py`, `tools/verify_bundle.py`).
- Xtream passwords and remote playlist URLs are encrypted at rest; Xtream stream URLs are cached without credentials and built at playback time.
- Logs never contain stream URLs or credentials.
- No telemetry. Network access only to the user's IPTV provider and the image hosts referenced by the playlist.

## License

Third-party components: Qt 6 / PyQt6 (LGPLv3 / GPLv3), libVLC 3 (LGPLv2.1+;
the VLC license is included as `_internal/vlc/VLC-COPYING.txt`), SQLAlchemy
(MIT), requests (Apache-2.0), cryptography (Apache-2.0/BSD). Choose and add a
license for MigeCast itself before publishing the repository.
