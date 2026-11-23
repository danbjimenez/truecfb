"""TrueCFB result card: a 1200 x 675 image for X, drawn from one game_impact result.

Brand (claude/truecfb-brand.md): light theme, field green header band, Barlow Condensed for display,
IBM Plex Sans for body, blue for up and orange for down (never red or green as a verdict), one decimal
on ratings, a real minus sign, no team logos or colors. The name is always written TrueCFB.

The card is drawn only from the result dict, so the same result always gives the same image.
Usage: card.py <impact.json> <out_dir>   (one PNG per game in the file)
"""
import json
import os
import sys
from datetime import date

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 675
BG, PANEL, CHIP, LINE = "#f3f5f2", "#ffffff", "#e9eeea", "#d9dfd9"
INK, MUTED, ACCENT, ON_ACCENT = "#17201b", "#5d6b63", "#1f6b45", "#ffffff"
UP, DOWN = "#1d5fa8", "#b0561a"
UP_BG, DOWN_BG = "#e3ecf7", "#f6e9df"
TAGLINE = "Unbiased, Deterministic, Open Source Rankings"
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "fonts")
_fonts = {}


def font(kind, weight, size):
    name = {"display": "barlow-condensed", "body": "ibm-plex-sans"}[kind]
    key = (name, weight, size)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(os.path.join(FONT_DIR, f"{name}-latin-{weight}-normal.ttf"), size)
    return _fonts[key]


def fit(d, text, kind, weight, size, max_w, min_size=18):
    """The largest font at or below `size` that fits `text` in `max_w`."""
    while size > min_size and d.textlength(text, font=font(kind, weight, size)) > max_w:
        size -= 2
    return font(kind, weight, size)


def num(x):
    """One decimal, with a real minus sign."""
    s = f"{x:.1f}"
    return s.replace("-", "−")


def signed(x):
    v = round(x, 1)
    return ("+" if v > 0 else "") + num(v) if v != 0 else "0.0"


def arrow(d, x, y, color, w=22):
    """A right arrow drawn as shapes (the brand fonts' Latin subset has no arrow glyph). y = center."""
    d.line([(x, y), (x + w - 6, y)], fill=color, width=3)
    d.polygon([(x + w, y), (x + w - 9, y - 7), (x + w - 9, y + 7)], fill=color)
    return x + w


def chip(d, x, y, text, up):
    f = font("body", 600, 22)
    tw = d.textlength(text, font=f)
    d.rounded_rectangle([x, y, x + tw + 20, y + 34], radius=999, fill=UP_BG if up else DOWN_BG)
    d.text((x + 10, y + 17), text, font=f, fill=UP if up else DOWN, anchor="lm")
    return x + tw + 20


def label(d, xy, text, fill=MUTED, size=17, anchor="la"):
    d.text(xy, text.upper(), font=font("body", 600, size), fill=fill, anchor=anchor)


def team_panel(d, x, y, w, h, s, opp_pts):
    d.rounded_rectangle([x, y, x + w, y + h], radius=10, fill=PANEL, outline=LINE)
    pad = 28
    result = f"{'W' if s['won'] else 'L'} {s['points']}–{opp_pts}"
    rf = font("body", 500, 24)
    rw = d.textlength(result, font=rf)
    d.text((x + w - pad, y + 30), result, font=rf, fill=MUTED, anchor="ra")
    d.text((x + pad, y + 22), s["team"], font=fit(d, s["team"], "display", 600, 44, w - 2 * pad - rw - 20), fill=INK)
    if not s["fbs"]:
        d.text((x + pad, y + 100), "FCS", font=font("display", 700, 80), fill=MUTED)
        d.text((x + pad, y + 195), "Not rated. Counts as a 25 for its opponent.", font=font("body", 400, 22), fill=MUTED)
        return
    d.text((x + pad, y + 70), num(s["game_rating"]), font=font("display", 700, 96), fill=INK)
    label(d, (x + pad + 4, y + 176), "Game Rating")
    # Team Rating, before -> after, with the change
    ry = y + 222
    label(d, (x + pad, ry), "Team Rating", anchor="lm")
    vx = x + pad + 150
    f = font("body", 500, 24)
    d.text((vx, ry), num(s["rating_before"]), font=f, fill=MUTED, anchor="lm")
    vx += d.textlength(num(s["rating_before"]), font=f) + 10
    vx = arrow(d, vx, ry, MUTED) + 10
    d.text((vx, ry), num(s["rating_after"]), font=font("body", 600, 24), fill=INK, anchor="lm")
    vx += d.textlength(num(s["rating_after"]), font=font("body", 600, 24)) + 14
    if round(s["change"], 1) != 0:
        chip(d, vx, ry - 17, signed(s["change"]), s["change"] > 0)
    # Rank
    ky = ry + 44
    label(d, (x + pad, ky), "Rank", anchor="lm")
    kx = x + pad + 150
    if s["rank_before"] == s["rank_after"]:
        d.text((kx, ky), f"{s['rank_after']}  (no change)", font=f, fill=INK, anchor="lm")
    else:
        d.text((kx, ky), str(s["rank_before"]), font=f, fill=MUTED, anchor="lm")
        kx += d.textlength(str(s["rank_before"]), font=f) + 10
        kx = arrow(d, kx, ky, MUTED) + 10
        better = s["rank_after"] < s["rank_before"]
        d.text((kx, ky), str(s["rank_after"]), font=font("body", 600, 24), fill=UP if better else DOWN, anchor="lm")


def headline(res):
    w = next(s for s in res["teams"] if s["won"]); l = next(s for s in res["teams"] if not s["won"])
    return w, l, f"{w['team']} {w['points']}, {l['team']} {l['points']}"


def kicker(res, w):
    parts = ["Final" + (" (OT)" if res["overtime"] else "")]
    if res.get("season_type") == "postseason" and res.get("note"):
        from game_impact import game_title
        parts.append(game_title(res["note"]))
    parts.append("Neutral site" if res["neutral"] else ("Home win" if w["site"] == "home" else "Road win"))
    dt = date.fromisoformat(res["day"])
    parts.append(f"{dt.strftime('%b')} {dt.day}, {dt.year}")
    return "  ·  ".join(parts)


def ripple_rows(d, x, y, w, entries, up):
    color = UP if up else DOWN
    f = font("body", 500, 22); fb = font("body", 600, 22)
    shown = [e for e in entries if abs(e["change"]) >= 0.05][:3]
    if not shown:
        d.text((x, y + 4), "None moved by 0.1 or more", font=font("body", 400, 21), fill=MUTED)
        return
    for i, e in enumerate(shown):
        yy = y + i * 32
        d.text((x, yy), signed(e["change"]), font=fb, fill=color)
        tx = x + 76
        name = e["team"]
        d.text((tx, yy), name, font=fb, fill=INK)
        tx += d.textlength(name, font=fb) + 10
        link = e["link"][0]
        why = f"{link['result']} {link['vs']}"
        room = x + w - tx
        if d.textlength(why, font=f) > room:
            while why and d.textlength(why + "…", font=f) > room:
                why = why[:-1]
            why += "…"
        d.text((tx, yy), why, font=f, fill=MUTED)


def render(res):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    w, l, head = headline(res)
    # Header band
    d.rectangle([0, 0, W, 150], fill=ACCENT)
    mf = font("display", 700, 92)
    mtxt = str(res["matchup_rating"])
    mw = max(d.textlength(mtxt, font=mf), d.textlength("MATCHUP RATING", font=font("body", 600, 17)))
    label(d, (W - 48, 30), "Matchup Rating", fill="#cfe3d7", anchor="ra")
    d.text((W - 48, 46), mtxt, font=mf, fill=ON_ACCENT, anchor="ra")
    left_w = W - 48 - mw - 40 - 48
    d.text((48, 26), kicker(res, w).upper(), font=fit(d, kicker(res, w).upper(), "body", 600, 17, left_w, 12), fill="#cfe3d7")
    d.text((46, 52), head, font=fit(d, head, "display", 700, 68, left_w, 34), fill=ON_ACCENT)
    # Team panels (winner on the left)
    py, ph, gap = 172, 294, 24
    pw = (W - 2 * 48 - gap) // 2
    team_panel(d, 48, py, pw, ph, w, l["points"])
    team_panel(d, 48 + pw + gap, py, pw, ph, l, w["points"])
    # Ripple
    ry = py + ph + 18
    label(d, (48, ry), "Ripple: past opponents of these two teams")
    rp = res["ripple"]
    col = (W - 2 * 48 - gap) // 2
    ripple_rows(d, 48, ry + 28, col, rp["past_opponents_gained"], True)
    ripple_rows(d, 48 + col + gap, ry + 28, col, rp["past_opponents_lost"], False)
    # Footer
    fy = H - 40
    d.line([(48, fy - 26), (W - 48, fy - 26)], fill=LINE, width=1)
    wf = font("display", 700, 32)
    d.text((48, fy), "True", font=wf, fill=INK, anchor="lm")
    tx = 48 + d.textlength("True", font=wf)
    d.text((tx, fy), "CFB", font=wf, fill=ACCENT, anchor="lm")
    tx += d.textlength("CFB", font=wf) + 18
    d.text((tx, fy + 1), TAGLINE, font=font("body", 400, 19), fill=MUTED, anchor="lm")
    d.text((W - 48, fy), "truecfb.com", font=font("body", 600, 21), fill=INK, anchor="rm")
    return img


def main():
    results, out = json.load(open(sys.argv[1])), sys.argv[2]
    os.makedirs(out, exist_ok=True)
    for res in results:
        p = os.path.join(out, f"{res['game_id']}.png")
        render(res).save(p, optimize=True)
        print(p)


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
