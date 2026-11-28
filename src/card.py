"""TrueCFB result card: a 1200 x 675 image for X, drawn from one game_impact result.

Layout (designed 27 Nov 2026, docs/BRAND.md "Result card"):
  scoreboard band   visitor left, home right: logo, name, record, score; FINAL and the date between
  Matchup Rating    the two Team Ratings as a sum, "55.2 + 65.6 = 120.8", and its percentile
  Game Rating       the two Game Ratings (higher blue, lower orange), a split bar, and each team's sum
                    in rule order: win or loss + opponent + margin + venue (+ postseason, limit)
  Team Rating       before, change chip, -> after
  TrueCFB rank      before -> after, with a change chip
Section labels sit in the center column; the visitor's numbers are flush left, the home team's flush
right. Colors and type are the design system's: up blue / down orange (never red or green), field
green band, Barlow Condensed for display, IBM Plex Sans for text, one decimal on ratings, a real minus.

Logos: assets/logos/<slug>.png when present (slug as the site's team pages); otherwise a plain
monogram circle. The card is drawn only from the result dict, so the same result always gives the
same image. A result saved before 27 Nov 2026 (no "parts") is drawn without the sums and percentiles.
Usage: card.py <impact.json> <out_dir>   (one PNG per game in the file)
"""
import json
import os
import re
import sys
import unicodedata
from datetime import date

from PIL import Image, ImageDraw, ImageFont

S = 2                                   # drawn at 2x, then scaled down, so shapes are smooth
W, H = 1200, 675
BG, PANEL, CHIP, LINE = "#f3f5f2", "#ffffff", "#e9eeea", "#d9dfd9"
INK, MUTED, ACCENT, ON_ACCENT, ON_MUTED = "#17201b", "#5d6b63", "#1f6b45", "#ffffff", "#cfe3d7"
UP, DOWN = "#1d5fa8", "#b0561a"
UP_TINT, DOWN_TINT = "#e3ecf7", "#f6e9df"
LOST = "#8fb5a0"                        # the loser's score: white at 55% on the band
MONO_FILL, MONO_RING = "#e6ebe7", "#aab6ad"
MINUS = "−"
TAGLINE = "Unbiased, Deterministic, Open Source Rankings"   # used by cfp_card.py
HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "..", "assets", "fonts")
LOGO_DIR = os.path.join(HERE, "..", "assets", "logos")
_fonts = {}


def font(kind, weight, size):
    name = {"display": "barlow-condensed", "body": "ibm-plex-sans"}[kind]
    key = (name, weight, size)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(os.path.join(FONT_DIR, f"{name}-latin-{weight}-normal.ttf"), int(size * S))
    return _fonts[key]


def slug(team):
    """Same as build_pages.slug: 'Texas A&M' -> 'texas-am'."""
    s = "".join(c for c in unicodedata.normalize("NFKD", team) if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"['&]", "", s)).strip("-")


def num(x, nd=1):
    """One decimal (or nd), with a real minus sign."""
    return f"{x:.{nd}f}".replace("-", MINUS)


def compact(x):
    """A rule's exact value: 6, 3, 5.25, 0.5."""
    s = f"{abs(x):.2f}".rstrip("0").rstrip(".")
    return s or "0"


def ordinal(n):
    n = min(max(int(n), 1), 99)           # a percentile reads 1st to 99th
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


class Card:
    def __init__(self):
        self.img = Image.new("RGB", (W * S, H * S), BG)
        self.d = ImageDraw.Draw(self.img)

    # --- primitives, all in 1x coordinates ---
    def text(self, xy, s, f, fill, anchor="la"):
        self.d.text((xy[0] * S, xy[1] * S), s, font=f, fill=fill, anchor=anchor)

    def width(self, s, f):
        return self.d.textlength(s, font=f) / S

    def rect(self, box, fill, radius=0):
        b = [v * S for v in box]
        if radius:
            self.d.rounded_rectangle(b, radius=radius * S, fill=fill)
        else:
            self.d.rectangle(b, fill=fill)

    def hline(self, y, x0=48, x1=W - 48, color=LINE, w=2):
        self.rect((x0, y - w / 2, x1, y + w / 2), color)

    def arrow(self, x, y, color=MUTED, w=34):
        """A right arrow drawn as shapes (the fonts' Latin subset has no arrow). y = center. Returns its right edge."""
        self.rect((x, y - 2, x + w - 8, y + 2), color)
        self.d.polygon([((x + w) * S, y * S), ((x + w - 12) * S, (y - 9) * S), ((x + w - 12) * S, (y + 9) * S)], fill=color)
        return x + w

    def triangle(self, x, y, up, color, size=13):
        """An up or down triangle centered at x, y."""
        h = size * 0.85
        pts = [(x, y - h / 2), (x - size / 2, y + h / 2), (x + size / 2, y + h / 2)] if up else \
              [(x, y + h / 2), (x - size / 2, y - h / 2), (x + size / 2, y - h / 2)]
        self.d.polygon([(a * S, b * S) for a, b in pts], fill=color)

    def chip(self, x, y, label, up, size=26, tri=False, align="l"):
        """A change chip: the signed change in a pill, centered on y. align 'l' starts at x, 'r' ends at x.
        up: True / False / None (no change). Returns (left, right)."""
        f = font("body", 600, size)
        color, fill = (UP, UP_TINT) if up else (DOWN, DOWN_TINT) if up is False else (MUTED, CHIP)
        tw = self.width(label, f) + (size * 0.75 if tri else 0)
        pad = size * 0.55
        w, h = tw + 2 * pad, size * 1.45
        x0 = x if align == "l" else x - w
        self.rect((x0, y - h / 2, x0 + w, y + h / 2), fill, radius=h / 2)
        tx = x0 + pad
        if tri:
            self.triangle(tx + size * 0.3, y, up, color, size * 0.55)
            tx += size * 0.75
        self.text((tx, y), label, f, color, "lm")
        return x0, x0 + w

    def label(self, x, y, lines, size=17):
        """A section label in the center column: uppercase by style, except the name TrueCFB."""
        f = font("body", 600, size)
        for i, ln in enumerate(lines):
            s = ln if ln == "TrueCFB" else ln.upper()
            self.text((x, y + (i - (len(lines) - 1) / 2) * size * 1.35), s, f, MUTED, "mm")

    def logo(self, team, cx, cy, d, on_band):
        p = os.path.join(LOGO_DIR, slug(team) + ".png")
        r = d / 2
        if os.path.exists(p):
            if on_band:   # a white disc keeps dark logos readable on the green band
                self.d.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], fill="#ffffff")
                inner = d * 0.74
            else:
                inner = d
            im = Image.open(p).convert("RGBA")
            im.thumbnail((int(inner * S), int(inner * S)), Image.LANCZOS)
            self.img.paste(im, (int(cx * S - im.width / 2), int(cy * S - im.height / 2)), im)
            return
        fill, ring, ink = ("#3c7f5b", "#a5c8b5", "#e8f1ec") if on_band else (MONO_FILL, MONO_RING, MUTED)
        self.d.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], fill=fill, outline=ring, width=max(2, int(d / 28)) * S)
        words = [w for w in re.split(r"[\s\-]+", team) if w]
        mono = (words[0][:4] if len(words) == 1 else "".join(w[0] for w in words[:3])).upper()
        self.text((cx, cy), mono, font("display", 700, d * 0.3), ink, "mm")

    def save_png(self):
        return self.img.resize((W, H), Image.LANCZOS)


# --- the card ---

def kicker(res):
    dt = date.fromisoformat(res["day"])
    top = "FINAL" + (" (OT)" if res["overtime"] else "")
    return top, f"{dt.strftime('%b').upper()} {dt.day}"


def band(c, res, away, home):
    c.rect((0, 0, W, 140), ACCENT)
    mid_top, mid_day = kicker(res)
    f_mid = font("body", 600, 20)
    mid_w = max(c.width(mid_top, f_mid), c.width(mid_day, f_mid))
    c.text((W / 2, 56), mid_top, f_mid, ON_MUTED, "mm")
    c.text((W / 2, 84), mid_day, f_mid, ON_MUTED, "mm")
    f_pts = font("display", 700, 100)
    gap = mid_w / 2 + 30
    for s, side in ((away, "l"), (home, "r")):
        lost = not s["won"]
        x_logo = 48 + 42 if side == "l" else W - 48 - 42
        c.logo(s["team"], x_logo, 70, 84, True)
        rec = f"{s['record'][0]}–{s['record'][1]}" if s.get("record") else ("FCS" if not s["fbs"] else "")
        name_max = W / 2 - gap - c.width(str(s["points"]), f_pts) - 28 - (48 + 84 + 22)
        f_name = font("display", 700, 54)
        size = 54
        while c.width(s["team"], f_name) > name_max and size > 32:
            size -= 2; f_name = font("display", 700, size)
        if side == "l":
            c.text((48 + 84 + 22, 64), s["team"], f_name, ON_ACCENT, "ls")
            c.text((48 + 84 + 22, 96), rec, font("body", 500, 22), ON_MUTED, "ls")
            c.text((W / 2 - gap, 72), str(s["points"]), f_pts, LOST if lost else ON_ACCENT, "rm")
        else:
            c.text((W - 48 - 84 - 22, 64), s["team"], f_name, ON_ACCENT, "rs")
            c.text((W - 48 - 84 - 22, 96), rec, font("body", 500, 22), ON_MUTED, "rs")
            c.text((W / 2 + gap, 72), str(s["points"]), f_pts, LOST if lost else ON_ACCENT, "lm")


def team_rating(s):
    return float(s["rating_after"]) if s["fbs"] else 25.0


def matchup(c, res, away, home):
    """Row 1: Team Rating + Team Rating (+ postseason) = Matchup Rating, centered."""
    c.label(W / 2, 156, ["Matchup Rating"])
    ra, rh = round(team_rating(away), 1), round(team_rating(home), 1)
    fbs = away if away["fbs"] else home
    post = 2 * fbs.get("post_both", 0.0) + fbs.get("post_win", 0.0)
    total = ra + rh + post
    f_n, f_op, f_tot, f_pc = font("body", 600, 40), font("body", 400, 40), font("display", 700, 60), font("body", 500, 22)
    items = [("logo", away["team"]), ("n", num(ra)), ("op", "+"), ("logo", home["team"]), ("n", num(rh))]
    if post:
        items += [("op", "+"), ("n", compact(post)), ("small", "postseason")]
    items += [("op", "="), ("tot", num(total))]
    pct = res.get("matchup_pct")
    if pct is not None:
        items.append(("pc", f"{ordinal(pct)} percentile"))
    widths = {"logo": lambda v: 46, "n": lambda v: c.width(v, f_n), "op": lambda v: c.width(v, f_op) + 8,
              "tot": lambda v: c.width(v, f_tot), "pc": lambda v: c.width(v, f_pc) + 8, "small": lambda v: c.width(v, f_pc)}
    gap = 14
    total_w = sum(widths[k](v) for k, v in items) + gap * (len(items) - 1)
    x, y = W / 2 - total_w / 2, 202
    for k, v in items:
        w = widths[k](v)
        if k == "logo":
            c.logo(v, x + 23, y, 46, False)
        elif k == "n":
            c.text((x, y), v, f_n, INK, "lm")
        elif k == "op":
            c.text((x + w / 2, y), v, f_op, MUTED, "mm")
        elif k == "tot":
            c.text((x, y + 2), v, f_tot, INK, "lm")
        else:
            c.text((x + (8 if k == "pc" else 0), y + 3), v, f_pc, MUTED, "lm")
        x += w + gap


def part_terms(s):
    """A Game Rating's parts, in rule order, as (sign, value text, word)."""
    p = s["parts"]
    terms = [("", compact(p["result"]), "win" if s["won"] else "loss"),
             ("+" if p["strength"] >= 0 else MINUS, num(abs(p["strength"])), "opponent"),
             ("+" if p["margin"] >= 0 else MINUS, compact(p["margin"]), "margin"),
             ("+" if p["venue"] >= 0 else MINUS, compact(p["venue"]), "venue")]
    if abs(p.get("limit", 0)) >= 0.05:
        terms.append(("+" if p["limit"] > 0 else MINUS, num(abs(p["limit"])), "limit"))
    if p.get("post"):
        terms.append(("+", compact(p["post"]), "postseason"))
    return terms


SUM_ROOM = (W - 96 - 200) / 2 - 8     # each team's half, beside the center label


def sum_line(c, terms, x, y, align):
    """One team's Game Rating sum, each number over its word. Shrinks to fit its half of the card
    (a playoff game can have six parts)."""
    for size in (28, 26, 24, 22, 20):
        f_n, f_w, f_op = font("body", 600, size), font("body", 500, max(14, size * 4 // 7)), font("body", 400, size)
        pad = size * 6 // 7
        cols = []
        for sign, v, word in terms:
            if sign:
                cols.append(("op", sign, c.width(sign, f_op) + pad))
            cols.append(("t", (v, word), max(c.width(v, f_n), c.width(word, f_w))))
        total = sum(w for _, _, w in cols)
        if total <= SUM_ROOM:
            break
    cx = x if align == "l" else x - total
    for k, v, w in cols:
        if k == "op":
            c.text((cx + w / 2, y), v, f_op, MUTED, "mm")
        else:
            c.text((cx + w / 2, y), v[0], f_n, INK, "mm")
            c.text((cx + w / 2, y + size * 0.93), v[1], f_w, MUTED, "mm")
        cx += w


def game_ratings(c, res, away, home):
    y = 292
    f_n, f_pc = font("display", 700, 80), font("body", 500, 18)
    gr = [s.get("game_rating") if s["fbs"] else None for s in (away, home)]
    hi = max(g for g in gr if g is not None) if any(g is not None for g in gr) else None
    edges = []
    for s, g, side in ((away, gr[0], "l"), (home, gr[1], "r")):
        if g is None:
            text, color, cap = "FCS", MUTED, "not rated"
        else:
            text = num(g)
            both = all(v is not None for v in gr) and gr[0] != gr[1]
            color = (UP if g == hi else DOWN) if both else INK
            pct = s.get("game_rating_pct")
            cap = f"{ordinal(pct)} pct" if pct is not None else ""
        w = c.width(text, f_n)
        if side == "l":
            c.text((48, y + 28), text, f_n, color, "ls")
            if cap:
                c.text((48 + w + 10, y + 28), cap, f_pc, MUTED, "ls")
            edges.append(48 + max(w + 10 + c.width(cap, f_pc), 190))
        else:
            c.text((W - 48, y + 28), text, f_n, color, "rs")
            if cap:
                c.text((W - 48 - w - 10, y + 28), cap, f_pc, MUTED, "rs")
            edges.append(W - 48 - max(w + 10 + c.width(cap, f_pc), 190))
    x0, x1 = edges[0] + 28, edges[1] - 28
    if all(v is not None for v in gr) and x1 > x0:
        split = x0 + (x1 - x0) * gr[0] / (gr[0] + gr[1])
        ca = (UP if gr[0] > gr[1] else DOWN) if gr[0] != gr[1] else MUTED
        ch = (UP if gr[1] > gr[0] else DOWN) if gr[0] != gr[1] else MUTED
        c.rect((x0, y - 11, x1, y + 11), ch, radius=11)          # home's share, rounded at the right end
        c.rect((x0, y - 11, split + 11, y + 11), ca, radius=11)  # visitor's share, rounded at the left end
        c.rect((split, y - 11, split + 12, y + 11), ch)          # a straight edge where the two meet
    yb = 360
    c.label(W / 2, yb + 10, ["Game", "Rating"])
    for s, side in ((away, "l"), (home, "r")):
        if s["fbs"] and s.get("parts"):
            sum_line(c, part_terms(s), 48 if side == "l" else W - 48, yb, side)


def team_ratings(c, away, home):
    y = 456
    c.label(W / 2, y, ["Team", "Rating"])
    f_was, f_now = font("body", 400, 38), font("body", 600, 38)
    for s, side in ((away, "l"), (home, "r")):
        if not s["fbs"]:
            f = font("body", 500, 24)
            c.text((48 if side == "l" else W - 48, y), "Not rated (counts as a 25)", f, MUTED, "lm" if side == "l" else "rm")
            continue
        b, a = round(s["rating_before"], 1), round(s["rating_after"], 1)
        ch = round(a - b, 1)          # the change as shown, so before + change = after on the card
        ch_txt = ("+" if ch > 0 else MINUS if ch < 0 else "") + num(abs(ch)) if ch else "="
        up = True if ch > 0 else False if ch < 0 else None
        f_chip = font("body", 600, 26)
        chip_w = c.width(ch_txt, f_chip) + 2 * 26 * 0.55
        widths = [c.width(num(b), f_was), 16 + chip_w, 14 + 34 + 14, c.width(num(a), f_now)]
        x = 48 if side == "l" else W - 48 - sum(widths)
        c.text((x, y), num(b), f_was, MUTED, "lm"); x += widths[0] + 16
        c.chip(x, y, ch_txt, up); x += chip_w + 14
        x = c.arrow(x, y) + 14
        c.text((x, y), num(a), f_now, INK, "lm")


def ranks(c, away, home):
    y = 558
    c.label(W / 2, y, ["TrueCFB", "Rank"])
    f_was, f_now = font("display", 600, 50), font("display", 700, 92)
    for s, side in ((away, "l"), (home, "r")):
        if not s["fbs"]:
            continue
        b, a = s["rank_before"], s["rank_after"]
        moved = b - a
        up = True if moved > 0 else False if moved < 0 else None
        color = UP if up else DOWN if up is False else INK
        lab = str(abs(moved)) if moved else "="
        f_chip = font("body", 600, 28)
        chip_w = c.width(lab, f_chip) + 2 * 28 * 0.55 + (28 * 0.75 if moved else 0)
        widths = [c.width(f"#{b}", f_was), 12 + 34 + 14, c.width(f"#{a}", f_now), 18 + chip_w]
        x = 48 if side == "l" else W - 48 - sum(widths)
        c.text((x, y), f"#{b}", f_was, MUTED, "lm"); x += widths[0] + 12
        x = c.arrow(x, y) + 14
        c.text((x, y + 3), f"#{a}", f_now, color, "lm"); x += widths[2] + 18
        c.chip(x, y, lab, up, size=28, tri=bool(moved))


def footer(c):
    c.hline(615)
    fy = 645
    wf = font("display", 700, 30)
    c.text((48, fy), "True", wf, INK, "lm")
    c.text((48 + c.width("True", wf), fy), "CFB", wf, ACCENT, "lm")
    c.text((W - 48, fy), "truecfb.com", font("body", 600, 22), INK, "rm")


def sides(res):
    """(visitor, home); at a neutral site the listed away team stays on the left."""
    t = res["teams"]
    home = next((s for s in t if s.get("site") == "home"), t[0])
    away = next(s for s in t if s is not home)
    return away, home


def render(res):
    c = Card()
    away, home = sides(res)
    band(c, res, away, home)
    matchup(c, res, away, home)
    c.hline(240)
    game_ratings(c, res, away, home)
    c.hline(412)
    team_ratings(c, away, home)
    c.hline(500)
    ranks(c, away, home)
    footer(c)
    return c.save_png()


def main():
    results, out = json.load(open(sys.argv[1])), sys.argv[2]
    os.makedirs(out, exist_ok=True)
    for res in results:
        p = os.path.join(out, f"{res['game_id']}.png")
        render(res).save(p, optimize=True)
        print(p)


if __name__ == "__main__":
    sys.path.insert(0, HERE)
    main()
