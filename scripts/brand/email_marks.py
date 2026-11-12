"""Draw the Spark mark as PNGs for email (BLD-125). Mail apps drop SVG, so emails show a hosted PNG.

Geometry is the small cut from docs/BRAND.md §4 (below 32 px tall): zeros r 32 with stroke 24, the spark polygon
34,236 141,23.5 175,44.5, no ember; a Spark-orange spark with ink zeros for the paper header (DEC-101), and white
zeros for mail apps in dark mode. Drawn eight times larger and scaled down for clean edges. The white mark is on a
transparent background; the ink mark sits on its own paper ground, so a mail app that darkens the page without
telling the email (Gmail) still shows it, on a small paper tile (BLD-A170).

    services/worker/.venv/bin/python scripts/brand/email_marks.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[2] / "apps" / "web" / "public" / "brand"
SPARK = (255, 91, 20, 255)
WHITE = (255, 255, 255, 255)
INK = (17, 17, 17, 255)  # #111111, OFFER's ink (DEC-101)
PAPER = (243, 243, 241, 255)  # #F3F3F1, OFFER's paper
CLEAR = (0, 0, 0, 0)
SS = 8  # supersampling


def draw(
    width: int, zeros: tuple[int, int, int, int] = WHITE, ground: tuple[int, int, int, int] = CLEAR
) -> Image.Image:
    height = round(width * 240 / 200)
    k = width * SS / 200  # pixels per mark unit at the supersampled size
    img = Image.new("RGBA", (width * SS, height * SS), ground)
    d = ImageDraw.Draw(img)
    r, stroke = 32, 24
    for cx, cy in ((52, 58), (148, 184)):
        outer, inner = r + stroke / 2, r - stroke / 2
        d.ellipse([(cx - outer) * k, (cy - outer) * k, (cx + outer) * k, (cy + outer) * k], fill=zeros)
        d.ellipse([(cx - inner) * k, (cy - inner) * k, (cx + inner) * k, (cy + inner) * k], fill=ground)
    d.polygon([(34 * k, 236 * k), (141 * k, 23.5 * k), (175 * k, 44.5 * k)], fill=SPARK)
    return img.resize((width, height), Image.Resampling.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, zeros, ground in (("white", WHITE, CLEAR), ("ink", INK, PAPER)):
        draw(22, zeros, ground).save(OUT / f"email-mark-{name}.png", optimize=True)
        draw(44, zeros, ground).save(OUT / f"email-mark-{name}@2x.png", optimize=True)
        print("wrote", OUT / f"email-mark-{name}.png", OUT / f"email-mark-{name}@2x.png")


if __name__ == "__main__":
    main()
