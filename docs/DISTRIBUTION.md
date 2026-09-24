# Distribution decisions

## Packaging options compared

| | One-file PyInstaller EXE | One-folder ZIP | **Inno Setup installer (chosen)** |
|---|---|---|---|
| Files the user downloads | 1 | 1 ZIP, then a folder | **1** |
| Start time | slow: unpacks ~150 MB to `%TEMP%` on *every* start | fast | **fast (files installed once)** |
| Antivirus false positives | frequent (self-extracting Python EXE) | rare | **rare** |
| User must understand folders / `_internal` | no | **yes** | no |
| Desktop + Start menu shortcuts, uninstall entry | no | no | **yes** |
| Upgrade keeping data | manual | manual | **automatic** |
| Admin rights | no | no | **no (per-user install)** |

Inno Setup was chosen over NSIS/WiX because it is pre-installed on GitHub's
Windows runners, produces a single self-contained EXE with LZMA2 compression,
supports per-user installation without UAC (`PrivilegesRequired=lowest`) and is
widely used, so it is well known to antivirus vendors.

## Runtime contents of the installer

- Python 3.11 runtime and all Python packages (PyInstaller one-folder build).
- Qt 6 DLLs and plugins (`platforms/qwindows.dll`, image formats).
- libVLC 3.0.21 (`libvlc.dll`, `libvlccore.dll`, all plugins, pre-generated
  `plugins.dat`) in `_internal\vlc`, loaded via `PYTHON_VLC_LIB_PATH`; an
  installed VLC is neither needed nor used.
- Microsoft C/C++ runtime: `vcruntime140.dll`, `vcruntime140_1.dll` (Python)
  and `msvcp140*.dll` (shipped with PyQt6-Qt6) are deployed app-local, which
  Microsoft permits for the Visual C++ Redistributable files. libVLC is built
  with MinGW and needs no MSVC runtime. `tools/verify_bundle.py` fails the build
  if one of them is missing.

## Hosting

- The installer (~70–90 MB) is published as a **GitHub Release asset** (tag
  `v*`). The repository must be **public** for anonymous downloads; release
  assets of private repositories require a GitHub login.
- The download page (`site/`) is static and can be hosted on Vercel
  (project root directory: `site`). It only reads `release.json`; the installer
  itself is not deployed to Vercel, so Vercel file-size and bandwidth limits of
  the chosen plan do not apply to the binary. Check the current Vercel plan
  limits before serving large files from Vercel directly.
- The download button stays disabled until `site/release.json` points to a
  published, CI-tested installer (`tools/update_site_release.py`).

## SmartScreen and code signing

The installer is currently **unsigned**. Windows SmartScreen therefore shows
"Windows protected your PC" for new downloads until the file gains reputation;
users must click *More info → Run anyway* (documented on the download page).

To remove the warning, sign both `MigeCast.exe` and the installer:

1. Obtain a code-signing certificate: an OV or EV certificate from a public CA
   (EV/OV certificates are now issued on hardware tokens or cloud HSMs), or a
   cloud signing service such as Azure Trusted Signing (check the current
   eligibility rules), or SignPath's free program for open-source projects.
2. Sign the PyInstaller output before running ISCC:
   `signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /a dist\MigeCast\MigeCast.exe`
3. Build the installer with signing enabled:
   `ISCC /DSIGN=1 "/Ssigntool=signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /a $f" installer\MigeCast.iss`
   (`SignedUninstaller=yes` is already set under `#ifdef SIGN`).
4. Store certificate material only as GitHub Actions secrets / in the signing
   service, never in the repository.

Even signed files from a new publisher may show SmartScreen warnings until
reputation builds up; EV certificates no longer bypass this automatically.

## Antivirus

CI scans the installer and the one-folder build with Microsoft Defender
(`MpCmdRun -Scan -ScanType 3`) and stores the result in the test reports.
UPX compression is disabled on purpose because UPX-packed Python programs are
a common source of false positives. Before a public release it is recommended
to also upload the installer to VirusTotal manually and to report false
positives to the vendors.
