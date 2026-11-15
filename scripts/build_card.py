"""Build the terminal-style profile card: card.svg.

Layout and idea inspired by Andrew Grant's profile README
(https://github.com/Andrew6rant/Andrew6rant), credited in README.md.

Run:  python scripts/build_card.py
Uses only the Python standard library, so the GitHub Action needs no installs.
Live numbers come from public GitHub pages/APIs; if a fetch fails, the last
good numbers in assets/stats.json are reused.
"""
from __future__ import annotations

import html
import json
import os
import random
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PERSONAL = "khushbawal"
WORK = "khushbawalhyperprint"

# ---- the card's text (facts from shared/master-profile.json) -------------
INFO = [
    ("title", "khush@bawal"),
    ("rule", ""),
    ("kv", "Role", "Lead Software Developer @ HyperPrint"),
    ("kv", "Location", "Lee's Summit, MO  |  Remote / KC / Dubai"),
    ("kv", "Education", "B.S. Computer Science (AI), NC State '25"),
    ("gap", ""),
    ("kv", "Languages.Code", "TypeScript, Python, Java, C#, SQL"),
    ("kv", "Frameworks", "React, Next.js, Node.js, .NET 8"),
    ("kv", "Cloud", "AWS (ECS, Lambda, DynamoDB), Azure, GCP"),
    ("kv", "AI.ML", "GenAI image pipelines, XGBoost, TF"),
    ("kv", "DevOps", "Docker, GitHub Actions, Playwright"),
    ("gap", ""),
    ("kv", "Previously", "Noregon, Wiley, Nissan"),
    ("gap", ""),
    ("head", "Contact"),
    ("kv", "LinkedIn", "in/khush-bawal"),
    ("kv", "GitHub", "@khushbawal"),
    ("gap", ""),
    ("head", "GitHub Stats"),
    ("stat", "Public.Repos", "{repos}"),
    ("stat", "Contributions", "{personal_contrib}  (personal, last year)"),
    ("stat", "Work.Contrib", "{work_contrib}  (work account, last year)"),
]

WIDTH_CHARS = 56  # width of the info panel in characters

THEMES = {
    "dark": dict(bg="#161b22", fg="#c9d1d9", key="#ffa657", val="#a5d6ff",
                 dim="#8b949e", rain="#3fb950", head="#7ee787"),
    "light": dict(bg="#f6f8fa", fg="#24292f", key="#953800", val="#0a3069",
                  dim="#57606a", rain="#1a7f37", head="#116329"),
}

FONT = 13          # px
CW = 8.1           # character width in px (a little wide, so nothing overflows)
LH = 15            # line height in px
PAD = 24


# ---- live numbers --------------------------------------------------------
def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "profile-card-builder"})
    token = os.environ.get("GITHUB_TOKEN")
    if token and "api.github.com" in url:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8")


def _contributions(user: str) -> int:
    page = _get(f"https://github.com/users/{user}/contributions")
    m = re.search(r"([\d,]+)\s+contributions?\s+in the last year", page)
    if not m:
        raise ValueError("count not found")
    return int(m.group(1).replace(",", ""))


def fetch_stats() -> dict:
    cache = ROOT / "assets/stats.json"
    stats = json.loads(cache.read_text()) if cache.exists() else {}
    try:
        repos = json.loads(_get(f"https://api.github.com/users/{PERSONAL}/repos?per_page=100&type=owner"))
        stats["repos"] = len([r for r in repos if not r["fork"]])
        stats["stars"] = sum(r["stargazers_count"] for r in repos)
    except Exception as e:  # keep last good numbers
        print("repo fetch failed:", e)
    for key, user in (("personal_contrib", PERSONAL), ("work_contrib", WORK)):
        try:
            stats[key] = _contributions(user)
        except Exception as e:
            print(f"{user} contributions fetch failed:", e)
    cache.write_text(json.dumps(stats, indent=2) + "\n")
    return stats


# ---- SVG -----------------------------------------------------------------
def _esc(s: str) -> str:
    return html.escape(s, quote=False)


P_FONT = 9          # portrait font size, px
P_CW = 5.4          # portrait character width, px
P_LH = 9.6          # portrait line height, px


def portrait_svg(grid: list, x0: float, y0: float) -> str:
    """Each column of the portrait falls into place like Matrix rain.

    Every character carries a brightness level (class b1..b9) so the face
    has light and shadow, not just denser or lighter letters.
    """
    rng = random.Random(7)  # fixed seed: same animation every build
    rows, cols = len(grid), len(grid[0])
    drop = y0 + rows * P_LH + 40
    out = []
    for c in range(cols):
        cells = [(r, grid[r][c]) for r in range(rows) if grid[r][c][0] != " "]
        if not cells:
            continue
        delay = rng.uniform(0, 1.8)
        dur = rng.uniform(1.0, 1.8)
        x = f"{x0 + c * P_CW:.1f}"
        spans = "".join(
            f'<tspan x="{x}" y="{y0 + r * P_LH:.1f}" class="b{lvl}">{_esc(ch)}</tspan>'
            for r, (ch, lvl) in cells
        )
        out.append(
            f'<text class="col" style="animation-delay:{delay:.2f}s;animation-duration:{dur:.2f}s;'
            f'--drop:-{drop:.0f}px">{spans}</text>'
        )
    return "\n".join(out)


def visible_info(stats: dict) -> list:
    # Hide the personal count while it is 0 (its contributions are private).
    return [i for i in INFO if not (i[0] == "stat" and "{personal_contrib}" in i[2] and not stats.get("personal_contrib"))]


def info_svg(stats: dict, x0: float, y0: float) -> str:
    out = []
    info = visible_info(stats)
    for i, item in enumerate(info):
        kind = item[0]
        y = y0 + i * LH
        delay = 2.2 + i * 0.07
        attrs = f'x="{x0}" y="{y}" style="animation-delay:{delay:.2f}s"'
        if kind == "title":
            out.append(f'<text {attrs} class="line"><tspan class="key">{_esc(item[1])}</tspan></text>')
        elif kind == "rule":
            out.append(f'<text {attrs} class="line dim">{"-" * WIDTH_CHARS}</text>')
        elif kind == "head":
            label = f"- {item[1]} "
            out.append(f'<text {attrs} class="line"><tspan class="head">{_esc(label)}</tspan>'
                       f'<tspan class="dim">{"-" * (WIDTH_CHARS - len(label))}</tspan></text>')
        elif kind in ("kv", "stat"):
            key, val = item[1], item[2].format(**{k: f"{v:,}" for k, v in stats.items()})
            dots = " " + "." * max(2, WIDTH_CHARS - len(key) - len(val) - 4) + " "
            out.append(f'<text {attrs} class="line"><tspan class="dim">. </tspan><tspan class="key">{_esc(key)}</tspan>'
                       f'<tspan class="dim">:{dots}</tspan><tspan class="val">{_esc(val)}</tspan></text>')
    # blinking cursor under the last line
    y = y0 + len(info) * LH + LH
    out.append(f'<text x="{x0}" y="{y}" class="line" style="animation-delay:{2.2 + len(info) * 0.07:.2f}s">'
               f'<tspan class="key">khush@bawal</tspan><tspan class="dim">:~$ </tspan>'
               f'<tspan class="cursor">_</tspan></text>')
    return "\n".join(out)


def build(theme: str, stats: dict, grid: list) -> str:
    t = THEMES[theme]
    pw = len(grid[0]) * P_CW
    ix = PAD + pw + 30
    w = ix + WIDTH_CHARS * CW + PAD + 16
    ph = len(grid) * P_LH
    ih = (len(visible_info(stats)) + 2) * LH
    h = PAD * 2 + max(ph, ih)
    iy = PAD + LH + max(0, (ph - ih) / 2)  # center the info panel next to the portrait
    levels = "\n".join(
        f"    .b{i} {{ fill-opacity: {0.18 if i == 1 else 0.3 + 0.7 * (i - 2) / 7:.2f}; }}" for i in range(1, 10)
    )
    style = f"""
    text {{ font-family: ui-monospace, SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
            font-size: {FONT}px; fill: {t['fg']}; white-space: pre; }}
    .col {{ font-size: {P_FONT}px; animation-name: fall; animation-timing-function: cubic-bezier(.2,.7,.3,1);
            animation-fill-mode: both; }}
{levels}
    .key {{ fill: {t['key']}; }} .val {{ fill: {t['val']}; }} .dim {{ fill: {t['dim']}; }}
    .head {{ fill: {t['head']}; }}
    @keyframes fall {{
      0%   {{ transform: translateY(var(--drop)); fill: {t['rain']}; }}
      70%  {{ fill: {t['rain']}; }}
      100% {{ transform: translateY(0); fill: {t['fg']}; }}
    }}
    .line {{ opacity: 0; animation: show .01s linear forwards; }}
    @keyframes show {{ to {{ opacity: 1; }} }}
    .cursor {{ fill: {t['fg']}; animation: blink 1s steps(1) infinite; }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}
    @media (prefers-reduced-motion: reduce) {{
      .col, .line, .cursor {{ animation: none; opacity: 1; transform: none; }}
    }}
    """
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" '
        f'viewBox="0 0 {w:.0f} {h:.0f}" role="img" aria-label="Khush Bawal - ASCII portrait and profile card">\n'
        f"<style>{style}</style>\n"
        f'<clipPath id="card"><rect width="{w:.0f}" height="{h:.0f}" rx="12"/></clipPath>\n'
        f'<g clip-path="url(#card)">\n'
        f'<rect width="{w:.0f}" height="{h:.0f}" fill="{t["bg"]}"/>\n'
        f"{portrait_svg(grid, PAD, PAD + P_LH)}\n"
        f"{info_svg(stats, ix, iy)}\n"
        f"</g>\n</svg>\n"
    )


def main() -> None:
    grid = json.loads((ROOT / "assets/portrait.json").read_text(encoding="utf-8"))
    stats = fetch_stats()
    # One dark card for everyone: the portrait is drawn for a dark background
    # and also reads well on GitHub's light theme.
    (ROOT / "card.svg").write_text(build("dark", stats, grid), encoding="utf-8")
    print("built card.svg with", stats)


if __name__ == "__main__":
    main()
