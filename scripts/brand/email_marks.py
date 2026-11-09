"""Draw the Spark mark as PNGs for email (BLD-125). Mail apps drop SVG, so emails show a hosted PNG.

Geometry is the small cut from docs/BRAND.md §4 (below 32 px tall): zeros r 32 with stroke 24, the spark polygon
34,236 141,23.5 175,44.5, no ember; white zeros and a Spark-orange spark, for the Zed header band. Drawn eight
times larger and scaled down for clean edges, on a transparent background.

    services/worker/.venv/bin/python scripts/brand/email_marks.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[2] / "apps" / "web" / "public" / "brand"
SPARK = (255, 91, 20, 255)
WHITE = (255, 255, 255, 255)
SS = 8  # supersampling


def draw(width: int) -> Image.Image:
    height = round(width * 240 / 200)
    k = width * SS / 200  # pixels per mark unit at the supersampled size
    img = Image.new("RGBA", (width * SS, height * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r, stroke = 32, 24
    for cx, cy in ((52, 58), (148, 184)):
        outer, inner = r + stroke / 2, r - stroke / 2
        d.ellipse([(cx - outer) * k, (cy - outer) * k, (cx + outer) * k, (cy + outer) * k], fill=WHITE)
        d.ellipse([(cx - inner) * k, (cy - inner) * k, (cx + inner) * k, (cy + inner) * k], fill=(0, 0, 0, 0))
    d.polygon([(34 * k, 236 * k), (141 * k, 23.5 * k), (175 * k, 44.5 * k)], fill=SPARK)
    return img.resize((width, height), Image.Resampling.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    draw(20).save(OUT / "email-mark-white.png", optimize=True)
    draw(40).save(OUT / "email-mark-white@2x.png", optimize=True)
    print("wrote", OUT / "email-mark-white.png", OUT / "email-mark-white@2x.png")


if __name__ == "__main__":
    main()
