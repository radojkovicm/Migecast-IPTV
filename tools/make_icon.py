"""Generate resources/migecast.ico (multi-size) and migecast.png with Qt."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QRectF, Qt  # noqa: E402
from PyQt6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPen  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def draw(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 256
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#1e7a36"))
    p.drawRoundedRect(QRectF(8 * s, 8 * s, 240 * s, 240 * s), 52 * s, 52 * s)
    p.setBrush(QColor("#ffffff"))
    p.drawRoundedRect(QRectF(40 * s, 72 * s, 176 * s, 124 * s), 18 * s, 18 * s)
    p.setBrush(QColor("#15171a"))
    p.drawRoundedRect(QRectF(54 * s, 86 * s, 148 * s, 96 * s), 10 * s, 10 * s)
    p.setBrush(QColor("#3fae5a"))
    tri = [(110, 106), (110, 162), (156, 134)]
    from PyQt6.QtCore import QPointF
    from PyQt6.QtGui import QPolygonF
    p.drawPolygon(QPolygonF([QPointF(x * s, y * s) for x, y in tri]))
    pen = QPen(QColor("#ffffff"), max(1.0, 12 * s))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawLine(QPointF(100 * s, 40 * s), QPointF(128 * s, 70 * s))
    p.drawLine(QPointF(156 * s, 40 * s), QPointF(128 * s, 70 * s))
    p.drawLine(QPointF(96 * s, 210 * s), QPointF(160 * s, 210 * s))
    p.end()
    return image


def main():
    app = QGuiApplication(sys.argv)  # noqa: F841
    out = ROOT / "resources"
    out.mkdir(exist_ok=True)
    draw(256).save(str(out / "migecast.png"))
    # Qt writes a single-size ICO; build a multi-size ICO by hand (PNG entries).
    import struct
    from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
    sizes = [16, 24, 32, 48, 64, 128, 256]
    blobs = []
    for size in sizes:
        data = QByteArray()
        buf = QBuffer(data)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        draw(size).save(buf, "PNG")
        blobs.append(bytes(data))
    header = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries, payload = b"", b""
    for size, blob in zip(sizes, blobs):
        dim = 0 if size == 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(blob), offset + len(payload))
        payload += blob
    (out / "migecast.ico").write_bytes(header + entries + payload)
    print("icon written")


if __name__ == "__main__":
    main()
