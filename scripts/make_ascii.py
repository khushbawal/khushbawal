"""Turn assets/portrait.jpg into assets/portrait.json (ASCII art with shading).

Run once (or whenever the photo changes):  python scripts/make_ascii.py
Writes a grid of [character, brightness 0-9]; build_card.py draws each
character with that brightness, so the face gets real light and shadow.
Also writes assets/portrait_preview.png to eyeball the result.
"""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
COLS = 92                          # width of the portrait in characters
CHAR_ASPECT = 0.5                  # monospace chars are about twice as tall as wide
CROP = (0.16, 0.13, 0.98, 0.86)    # left, top, right, bottom (fractions of the photo)
BG_RANGE = (14, 34)                # the studio backdrop's grey
# Characters ordered by how much ink they use (light to heavy).
RAMP = " .`:-=+*cxoaeszun#%MW&8B@"


def flood_background(raw: Image.Image, cols: int, rows: int) -> list[list[bool]]:
    """Backdrop = backdrop-grey cells connected to the photo's edge."""
    grey = [[BG_RANGE[0] <= raw.getpixel((x, y)) <= BG_RANGE[1] for x in range(cols)] for y in range(rows)]
    bg = [[False] * cols for _ in range(rows)]
    stack = [(x, y) for y in range(rows) for x in range(cols)
             if (x in (0, cols - 1) or y in (0, rows - 1)) and grey[y][x]]
    while stack:
        x, y = stack.pop()
        if bg[y][x]:
            continue
        bg[y][x] = True
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < cols and 0 <= ny < rows and grey[ny][nx] and not bg[ny][nx]:
                stack.append((nx, ny))
    return bg


def main() -> None:
    img = Image.open(ROOT / "assets/portrait.jpg").convert("L")
    w, h = img.size
    img = img.crop((int(CROP[0] * w), int(CROP[1] * h), int(CROP[2] * w), int(CROP[3] * h)))
    rows = round(COLS * img.height / img.width * CHAR_ASPECT)

    raw = img.resize((COLS, rows), Image.BOX)
    bg = flood_background(raw, COLS, rows)

    # Sharpen features (eyes, brows, beard edge), then stretch contrast
    # using only the person, not the backdrop.
    sharp = img.filter(ImageFilter.UnsharpMask(radius=6, percent=180, threshold=2)).resize((COLS, rows), Image.BOX)
    person = sorted(sharp.getpixel((x, y)) for y in range(rows) for x in range(COLS) if not bg[y][x])
    lo, hi = person[len(person) // 50], person[-len(person) // 100]

    grid = []
    for y in range(rows):
        row = []
        for x in range(COLS):
            if bg[y][x]:
                row.append([" ", 0])
                continue
            v = min(1.0, max(0.0, (sharp.getpixel((x, y)) - lo) / (hi - lo))) ** 0.85
            if v < 0.06:
                # hair and suit: dim texture so the silhouette stays visible
                row.append([":" if (x + 2 * y) % 4 == 0 else ".", 1])
                continue
            ch = RAMP[1 + min(len(RAMP) - 2, int(v * (len(RAMP) - 1)))]
            row.append([ch, 2 + min(7, int(v * 8))])
        grid.append(row)
    (ROOT / "assets/portrait.json").write_text(json.dumps(grid, separators=(",", ":")), encoding="utf-8")

    # Preview PNG (final frame, dark theme)
    font = ImageFont.truetype("consola.ttf", 10)
    cw, ch = 5.5, 10
    im = Image.new("RGB", (int(cw * COLS) + 20, ch * rows + 20), (22, 27, 34))
    d = ImageDraw.Draw(im)
    for y, row in enumerate(grid):
        for x, (c, lvl) in enumerate(row):
            if c != " ":
                a = 0.16 if lvl == 1 else 0.25 + 0.75 * (lvl - 2) / 7
                col = tuple(int(22 + (201 - 22) * a + (b - 201) * 0) for b in (201, 209, 217))
                col = tuple(int(bgc + (fg - bgc) * a) for bgc, fg in zip((22, 27, 34), (201, 209, 217)))
                d.text((10 + x * cw, 10 + y * ch), c, fill=col, font=font)
    im.save(ROOT / "assets/portrait_preview.png")
    print(f"{COLS}x{rows} grid written")


if __name__ == "__main__":
    main()
