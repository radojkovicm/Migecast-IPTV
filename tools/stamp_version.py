"""Stamp build date/commit into version.py and write the Windows version
resource for PyInstaller (build/version_info.txt).

Prints the version so CI can pass it to Inno Setup.
Usage: python tools/stamp_version.py [--commit SHA]
"""
import argparse
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", default="")
    args = parser.parse_args()
    commit = args.commit[:10]
    if not commit:
        try:
            commit = subprocess.check_output(["git", "rev-parse", "--short=10", "HEAD"], cwd=ROOT, text=True).strip()
        except (OSError, subprocess.CalledProcessError):
            commit = "unknown"
    build_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    version_py = ROOT / "version.py"
    text = version_py.read_text(encoding="utf-8")
    version = re.search(r'__version__ = "([^"]+)"', text).group(1)
    text = re.sub(r'__build_date__ = "[^"]*"', f'__build_date__ = "{build_date}"', text)
    text = re.sub(r'__build_commit__ = "[^"]*"', f'__build_commit__ = "{commit}"', text)
    version_py.write_text(text, encoding="utf-8")

    parts = [int(p) for p in re.findall(r"\d+", version)[:3]] + [0]
    while len(parts) < 4:
        parts.insert(-1, 0)
    tup = ", ".join(str(p) for p in parts[:4])
    info = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(filevers=({tup}), prodvers=({tup}), mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'MigeCast'),
      StringStruct('FileDescription', 'MigeCast IPTV'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', 'MigeCast'),
      StringStruct('LegalCopyright', 'MigeCast contributors'),
      StringStruct('OriginalFilename', 'MigeCast.exe'),
      StringStruct('ProductName', 'MigeCast IPTV'),
      StringStruct('ProductVersion', '{version} ({commit}, {build_date})')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    out = ROOT / "build"
    out.mkdir(exist_ok=True)
    (out / "version_info.txt").write_text(info, encoding="utf-8")
    print(version)


if __name__ == "__main__":
    main()
