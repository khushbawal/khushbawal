"""Build card.svg (ASCII portrait + info panel) and contributions.svg.

Layout and idea inspired by Andrew Grant's profile README
(https://github.com/Andrew6rant/Andrew6rant), credited in README.md.

Run:  python scripts/build_card.py
Uses only the Python standard library, so the GitHub Action needs no installs.
Live numbers come from public GitHub pages/APIs; if a fetch fails, the last
good numbers in assets/stats.json are reused.

Animation: the card plays like a terminal running `neofetch` - the command
is typed, then the shaded ASCII portrait and info print top to bottom. A
little later the portrait winks, and the cursor keeps blinking.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import subprocess
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
    ("kv", "Location", "Lee's Summit, MO | Remote/KC/Dubai"),
    ("kv", "Education", "B.S. CS (AI), NC State '25"),
    ("gap", ""),
    ("kv", "Languages.Code", "TypeScript, Python, Java, C#, SQL"),
    ("kv", "Frameworks", "React, Next.js, Node.js, .NET 8"),
    ("kv", "Cloud", "AWS, Azure, GCP"),
    ("kv", "AI.ML", "GenAI image pipelines, XGBoost"),
    ("kv", "DevOps", "Docker, GitHub Actions, Playwright"),
    ("kv", "Previously", "Noregon, Wiley, Nissan"),
    ("gap", ""),
    ("head", "Contact"),
    ("kv", "LinkedIn", "in/khush-bawal"),
    ("kv", "GitHub", "@khushbawal"),
    ("gap", ""),
    ("head", "GitHub Stats"),
    ("kv", "Public.Repos", "{repos}"),
    ("kv", "Contrib.Personal", "{personal_contrib}"),
    ("kv", "Contrib.Work", "{work_contrib}"),
    ("kv", "Contrib.Total", "{total_contrib}  (last year)"),
]
PANEL_CHARS = 54  # width of the info panel in characters

C = dict(bg="#161b22", fg="#c9d1d9", key="#ffa657", val="#a5d6ff", dim="#8b949e",
         head="#7ee787", prompt="#7ee787")
FONT = 16     # px, one size for everything (readable when GitHub scales the card)
CW = 9.65     # character width in px for a 16px monospace font
LH = 19       # line height in px
PAD = 22

# Portrait: small shaded characters (each with its own brightness, b1..b9).
P_FONT, P_CW, P_LH = 8.6, 5.15, 9.3

# The eye that winks (his left eye, on the right of the picture), in grid cells.
WINK_ROWS, WINK_COLS = (19, 21), (32, 41)


# ---- fetching ------------------------------------------------------------
def _get(url: str) -> str:
    headers = {"User-Agent": "profile-card-builder"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8")
    except Exception:
        # Some machines have broken Python certificates; curl usually works.
        args = ["curl", "-sfL", "-A", headers["User-Agent"], url]
        return subprocess.run(args, capture_output=True, text=True, check=True, timeout=30).stdout


def _calendar(user: str) -> tuple[int, dict[str, int]]:
    """Yearly total and {date: count} from the public contribution graph."""
    page = _get(f"https://github.com/users/{user}/contributions")
    total = int(re.search(r"([\d,]+)\s+contributions?\s+in the last year", page).group(1).replace(",", ""))
    dates = dict(re.findall(r'data-date="([\d-]+)" id="([^"]+)"', page))
    dates = {cid: d for d, cid in dates.items()}
    days = {}
    for cid, text in re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)</tool-tip>', page):
        if cid in dates:
            m = re.match(r"(\d+) contribution", text)
            days[dates[cid]] = int(m.group(1)) if m else 0
    return total, days


def fetch_stats() -> dict:
    cache = ROOT / "assets/stats.json"
    stats = json.loads(cache.read_text()) if cache.exists() else {}
    try:
        repos = json.loads(_get(f"https://api.github.com/users/{PERSONAL}/repos?per_page=100&type=owner"))
        stats["repos"] = len([r for r in repos if not r["fork"]])
    except Exception as e:  # keep last good numbers
        print("repo fetch failed:", e)
    for key, user in (("personal", PERSONAL), ("work", WORK)):
        try:
            total, days = _calendar(user)
            stats[f"{key}_contrib"], stats[f"{key}_days"] = total, days
        except Exception as e:
            print(f"{user} contributions fetch failed:", e)
    stats["total_contrib"] = stats.get("personal_contrib", 0) + stats.get("work_contrib", 0)
    cache.write_text(json.dumps(stats, indent=1) + "\n")
    return stats


# ---- card.svg ------------------------------------------------------------
def _esc(s: str) -> str:
    return html.escape(s, quote=False)


def _line_delay(i: int) -> float:
    return 1.15 + i * 0.045  # output prints line by line after the command


def panel_line(item: tuple, stats: dict) -> str:
    kind = item[0]
    if kind == "title":
        return f'<tspan fill="{C["key"]}">{_esc(item[1])}</tspan>'
    if kind == "rule":
        return f'<tspan fill="{C["dim"]}">{"-" * PANEL_CHARS}</tspan>'
    if kind == "head":
        label = f"- {item[1]} "
        return (f'<tspan fill="{C["head"]}">{_esc(label)}</tspan>'
                f'<tspan fill="{C["dim"]}">{"-" * (PANEL_CHARS - len(label))}</tspan>')
    if kind == "kv":
        key = item[1]
        val = item[2].format(**{k: f"{v:,}" for k, v in stats.items() if isinstance(v, int)})
        dots = " " + "." * max(2, PANEL_CHARS - len(key) - len(val) - 5) + " "
        return (f'<tspan fill="{C["dim"]}">. </tspan><tspan fill="{C["key"]}">{_esc(key)}</tspan>'
                f'<tspan fill="{C["dim"]}">:{dots}</tspan><tspan fill="{C["val"]}">{_esc(val)}</tspan>')
    return ""


def _row_svg(cells: list, y: float, x0: float) -> str:
    spans = "".join(f'<tspan x="{x0 + c * P_CW:.1f}" class="b{lvl}">{_esc(ch)}</tspan>'
                    for c, (ch, lvl) in cells if ch != " ")
    return f'<text class="p" y="{y:.1f}">{spans}</text>' if spans else ""


def build_card(stats: dict, grid: list) -> str:
    cols, prow = len(grid[0]), len(grid)
    px = PAD
    ix = PAD + cols * P_CW + 2.5 * CW
    w = ix + PANEL_CHARS * CW + PAD
    top = PAD + LH                      # baseline of the command line
    out_y = top + LH * 1.4              # first output line
    ph = prow * P_LH
    ih = len(INFO) * LH
    iy = out_y + max(0, (ph - ih) / 2)  # info panel centred beside the portrait
    bottom = out_y + max(ph, ih)
    h = bottom + LH * 1.8 + PAD

    def delay(y: float) -> float:       # output prints top to bottom, like a terminal
        return 1.15 + (y - out_y) / LH * 0.05

    body = []
    # 1. the typed command
    line = (f'<text x="{px}" y="{top}"><tspan fill="{C["prompt"]}">khush@bawal</tspan>'
            f'<tspan fill="{C["dim"]}">:~$ </tspan>')
    for i, ch in enumerate("neofetch"):
        line += f'<tspan class="t" style="animation-delay:{0.35 + i * 0.07:.2f}s">{ch}</tspan>'
    body.append(line + "</text>")

    # 2. output: portrait rows and panel rows appear as the "print" sweeps down
    for r, row in enumerate(grid):
        y = out_y + r * P_LH
        svg = _row_svg(list(enumerate(row)), y, px)
        if svg:
            body.append(f'<g class="ln" style="animation-delay:{delay(y):.2f}s">{svg}</g>')
    for i, item in enumerate(INFO):
        if item[0] == "gap":
            continue
        y = iy + i * LH
        body.append(f'<text x="{ix:.0f}" y="{y:.0f}" class="ln" style="animation-delay:{delay(y):.2f}s">'
                    f"{panel_line(item, stats)}</text>")

    # 3. the wink: cover the eye, refill it with cheek texture and a closed lid
    (r0, r1), (c0, c1) = WINK_ROWS, WINK_COLS
    width = c1 - c0 + 1
    lid = " ." + "_" * (width - 4) + ". "
    parts = [f'<rect x="{px + c0 * P_CW - 0.5:.1f}" y="{out_y + (r0 - 1) * P_LH + 2.5:.1f}" '
             f'width="{width * P_CW + 1:.1f}" height="{(r1 - r0 + 1) * P_LH:.1f}" fill="{C["bg"]}"/>']
    mid = (r0 + r1) // 2
    for r in range(r0, r1 + 1):
        cells = [(c, [lid[c - c0], 2] if r == mid else grid[r + 4][c]) for c in range(c0, c1 + 1)]
        parts.append(_row_svg(cells, out_y + r * P_LH, px))
    end = delay(bottom) + 0.2
    body.append(f'<g class="wink">{"".join(parts)}</g>')

    # 4. the next prompt with a blinking cursor
    body.append(f'<text x="{px}" y="{bottom + LH * 1.1:.0f}" class="ln" style="animation-delay:{end:.2f}s">'
                f'<tspan fill="{C["prompt"]}">khush@bawal</tspan><tspan fill="{C["dim"]}">:~$ </tspan>'
                f'<tspan class="cursor">_</tspan></text>')

    levels = "\n".join(f"    .b{i} {{ fill-opacity: {0.18 if i == 1 else 0.3 + 0.7 * (i - 2) / 7:.2f}; }}"
                        for i in range(1, 10))
    style = f"""
    text {{ font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace;
            font-size: {FONT}px; fill: {C['fg']}; white-space: pre; }}
    .p {{ font-size: {P_FONT}px; }}
{levels}
    .t, .ln {{ opacity: 0; animation: show .01s linear forwards; }}
    @keyframes show {{ to {{ opacity: 1; }} }}
    .wink {{ opacity: 0; animation: wink 7s linear {end + 1.2:.1f}s infinite; }}
    @keyframes wink {{ 0%, 4% {{ opacity: 1; }} 4.5%, 100% {{ opacity: 0; }} }}
    .cursor {{ animation: blink 1s steps(1) infinite; }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}
    @media (prefers-reduced-motion: reduce) {{
      .t, .ln {{ animation: none; opacity: 1; }}
      .wink, .cursor {{ animation: none; }}
    }}
    """
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" viewBox="0 0 {w:.0f} {h:.0f}" '
        f'role="img" aria-label="Khush Bawal - ASCII portrait and profile card">\n'
        f"<style>{style}</style>\n"
        f'<rect width="{w:.0f}" height="{h:.0f}" rx="12" fill="{C["bg"]}"/>\n'
        + "\n".join(body) + "\n</svg>\n"
    )


# ---- contributions.svg ---------------------------------------------------
GREENS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]


def build_graph(stats: dict) -> str:
    """One GitHub-style graph adding up the personal and work accounts."""
    p, wk = stats.get("personal_days", {}), stats.get("work_days", {})
    days = sorted(set(p) | set(wk))
    if not days:
        return ""
    counts = {d: p.get(d, 0) + wk.get(d, 0) for d in days}
    nonzero = sorted(v for v in counts.values() if v)
    q = [nonzero[int(len(nonzero) * f)] for f in (0.25, 0.5, 0.75)] if nonzero else [1, 2, 3]

    def level(v: int) -> int:
        return 0 if v == 0 else 1 if v <= q[0] else 2 if v <= q[1] else 3 if v <= q[2] else 4

    cell, gap = 13, 3
    left, top = PAD + 30, PAD + 46
    start = dt.date.fromisoformat(days[0])
    rects, months, seen = [], [], set()
    for d in days:
        day = dt.date.fromisoformat(d)
        wkday = (day.isoweekday() % 7)  # Sunday = 0, like GitHub
        week = ((day - start).days + (start.isoweekday() % 7)) // 7
        x, y = left + week * (cell + gap), top + wkday * (cell + gap)
        v = counts[d]
        rects.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2.5" fill="{GREENS[level(v)]}">'
                     f'<title>{v} contribution{"s" if v != 1 else ""} on {day:%b %d, %Y}</title></rect>')
        key = (day.year, day.month)
        if day.day <= 7 and key not in seen and wkday == 0:
            seen.add(key)
            months.append(f'<text x="{x}" y="{top - 8}" class="s">{day:%b}</text>')
    weeks = ((dt.date.fromisoformat(days[-1]) - start).days + (start.isoweekday() % 7)) // 7 + 1
    w = left + weeks * (cell + gap) + PAD
    h = top + 7 * (cell + gap) + 40
    title = (f'<tspan fill="{C["fg"]}">{stats["total_contrib"]:,} contributions in the last year</tspan>'
             f'<tspan fill="{C["dim"]}">  personal {stats.get("personal_contrib", 0):,} + work @ HyperPrint '
             f'{stats.get("work_contrib", 0):,}</tspan>')
    labels = "".join(f'<text x="{PAD}" y="{top + i * (cell + gap) + 11}" class="s">{n}</text>'
                     for i, n in ((1, "Mon"), (3, "Wed"), (5, "Fri")))
    legend_x = w - PAD - 5 * (cell + gap) - 70
    legend = (f'<text x="{legend_x}" y="{h - 14}" class="s">Less</text>'
              + "".join(f'<rect x="{legend_x + 34 + i * (cell + gap)}" y="{h - 25}" width="{cell}" height="{cell}" '
                        f'rx="2.5" fill="{g}"/>' for i, g in enumerate(GREENS))
              + f'<text x="{legend_x + 34 + 5 * (cell + gap) + 4}" y="{h - 14}" class="s">More</text>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" '
        f'aria-label="{stats["total_contrib"]:,} contributions in the last year across personal and work accounts">\n'
        f"<style>text {{ font-family: -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 15px; }}"
        f" .s {{ font-size: 12px; fill: {C['dim']}; }}</style>\n"
        f'<rect width="{w}" height="{h}" rx="12" fill="{C["bg"]}"/>\n'
        f'<text x="{PAD}" y="{PAD + 12}">{title}</text>\n'
        f"{''.join(months)}{labels}\n{''.join(rects)}\n{legend}\n</svg>\n"
    )


def main() -> None:
    grid = json.loads((ROOT / "assets/portrait.json").read_text(encoding="utf-8"))
    stats = fetch_stats()
    (ROOT / "card.svg").write_text(build_card(stats, grid), encoding="utf-8")
    graph = build_graph(stats)
    if graph:
        (ROOT / "contributions.svg").write_text(graph, encoding="utf-8")
    print("built card.svg and contributions.svg:",
          {k: v for k, v in stats.items() if not k.endswith("_days")})


if __name__ == "__main__":
    main()
