"""TrueCFB vs the CFP ranking: a card (2400 x 1350) and a short post for X, made each week the
committee publishes a ranking.

The left column is the TrueCFB top 25 (rank, team, Team Rating, record), the right column is the
committee's 25 (rank, team, and in a right-aligned column how many spots higher (+) or lower (−) the
committee has the team than TrueCFB). A line joins each team; the top 12 lines are bold. Teams on only one list
start or end at a note under that list.

Brand: TrueCFB is always the base, on the left. Lines are in each team's main color
(data/team_colors.json), the one other place besides the Top 25 chart where team colors appear
(docs/BRAND.md); the (+#)/(−#) numbers keep blue for higher and orange for lower.

Everything is drawn from snapshot(), which reads only the engine's site/rankings.json, so the same
snapshot always gives the same image and text. The bot saves the snapshot in the draft and draws the
card again from it when posting.

Usage: cfp_card.py <site_dir> <data_dir> <out.png>     (prints the post and its length)
"""
import json
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from card import W, H, BG, LINE, INK, MUTED, ACCENT, ON_ACCENT, UP, DOWN, TAGLINE, font as _font  # noqa: E402

S = 4      # drawn at 4x the 1200 x 675 layout...
OUT = 2    # ...and saved at 2x (2400 x 1350), so it stays sharp on phones and when zoomed
BAND_FILL = "#e6ede7"


# ---------- data ----------

def snapshot(site_dir, data_dir):
    """The numbers the card and post need, from site/rankings.json, or None when the current point has no
    full CFP ranking. Holds the teams in either top 25, with their colors, so a redraw is identical."""
    R = json.load(open(os.path.join(site_dir, "rankings.json")))
    colors = json.load(open(os.path.join(data_dir, "team_colors.json")))
    teams = R["teams"]
    cfp = [t for t in teams if t.get("cfp_rank")]
    if len(cfp) != 25 or sorted(t["cfp_rank"] for t in cfp) != list(range(1, 26)):
        return None
    keep = [t for t in teams if t["rank"] <= 25 or t["cfp_rank"]]
    return {"season": R["season"], "point": R["point"],
            "teams": [{"rank": t["rank"], "team": t["team"], "rating": t["rating"], "wins": t["wins"],
                       "losses": t["losses"], "cfp_rank": t["cfp_rank"], "color": colors.get(t["team"])}
                      for t in keep]}


def lists(snap):
    teams = snap["teams"]
    ours = sorted([t for t in teams if t["rank"] <= 25], key=lambda t: t["rank"])
    cfp = sorted([t for t in teams if t["cfp_rank"]], key=lambda t: t["cfp_rank"])
    outside = sorted([t for t in cfp if t["rank"] > 25], key=lambda t: t["rank"])   # CFP's 25, outside the TrueCFB top 25
    not_ranked = [t for t in ours if not t["cfp_rank"]]   # TrueCFB top 25, not ranked by the CFP
    same12 = len({t["team"] for t in ours[:12]} & {t["team"] for t in cfp[:12]})
    return ours, cfp, outside, not_ranked, same12


def headline(snap):
    same12 = lists(snap)[4]
    if same12 == 12:
        return "Same top 12 as the committee. Different order."
    return f"{same12} of the TrueCFB top 12 are in the committee's top 12"


def cfp_gap(t):
    """How many spots higher (+) or lower (−) the committee has the team than TrueCFB."""
    return t["rank"] - t["cfp_rank"]


def signed(n):
    return ("+" if n > 0 else "−") + str(abs(n))


# ---------- text ----------

def post_text(snap):
    ours, cfp, outside, not_ranked, same12 = lists(snap)
    in_both = sum(1 for t in ours if t["cfp_rank"])
    by_gap = sorted(cfp, key=cfp_gap)
    higher = [t for t in reversed(by_gap) if cfp_gap(t) > 0][:2]
    lower = [t for t in by_gap if cfp_gap(t) < 0][:2]
    pair = lambda t: f"{t['team']} {t['rank']}/{t['cfp_rank']}"
    lines = ["TrueCFB vs the new CFP ranking: " + ("same top 12, different order." if same12 == 12
                                                  else f"{same12} of the top 12 match."), "",
             f"{in_both} of the TrueCFB top 25 are in the CFP's."]
    if higher:
        lines.append("CFP higher (TrueCFB/CFP): " + ", ".join(pair(t) for t in higher))
    if lower:
        lines.append(("CFP lower: " if higher else "CFP lower (TrueCFB/CFP): ") + ", ".join(pair(t) for t in lower))
    if not_ranked:
        lines.append("Not ranked by CFP: " + ", ".join(t["team"] for t in not_ranked))
    # No link, not even a bare "truecfb.com": X turns it into a link and charges $0.20 a post.
    # The address is on the card.
    return "\n".join(lines)


def alt_text(snap):
    ours, cfp, outside, not_ranked, _ = lists(snap)
    """Every number on the card in words, within X's 1,000-character limit for alt text."""
    def one(t):
        return f"{t['team']} {t['rank']}/{t['cfp_rank'] or 'NR'} ({t['rating']:.1f})"
    rows = [one(t) for t in ours] + [one(t) for t in outside]
    return (f"TrueCFB top 25 beside the CFP committee's 25, {snap['season']}, games {snap['point'].lower()}. "
            + headline(snap) + " Ranks as TrueCFB/CFP, Team Rating in brackets: " + "; ".join(rows) + ".")


# ---------- card ----------

def font(kind, weight, size):
    return _font(kind, weight, int(round(size * S)))


def P(*v):
    return tuple(x * S for x in v)


def rgb(h):
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


def lum(c):
    v = [(x / 255) / 12.92 if x / 255 <= .03928 else ((x / 255 + .055) / 1.055) ** 2.4 for x in c]
    return .2126 * v[0] + .7152 * v[1] + .0722 * v[2]


def line_color(hexcolor):
    """The team's main color, darkened until it reads on the background (the site chart's rule: 3:1)."""
    c, bl = rgb(hexcolor or MUTED), lum(rgb(BG))
    for _ in range(14):
        if (max(lum(c), bl) + .05) / (min(lum(c), bl) + .05) >= 3:
            break
        c = [round(v * .85) for v in c]
    return tuple(c)


def fade(c, k=.45):
    """Blend toward the background, so the lines outside the top 12 sit back."""
    return tuple(round(x + (y - x) * k) for x, y in zip(c, rgb(BG)))


def curve(d, x0, y0, x1, y1, w, c, n=160):
    """A smooth S-curve (cubic Bezier, flat at both ends) filled as one polygon, so it has no kinks."""
    k = (x1 - x0) * 0.45
    pts = []
    for i in range(n + 1):
        t = i / n
        a, b, cc, dd = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
        px = a * x0 + b * (x0 + k) + cc * (x1 - k) + dd * x1
        py = (a + b) * y0 + (cc + dd) * y1
        tx = 3 * (1 - t) ** 2 * k + 6 * (1 - t) * t * (x1 - x0 - 2 * k) + 3 * t ** 2 * k
        ty = 6 * (1 - t) * t * (y1 - y0)
        ln = (tx * tx + ty * ty) ** .5 or 1
        pts.append((px, py, -ty / ln, tx / ln))
    h = w / 2
    d.polygon([P(px + nx * h, py + ny * h) for px, py, nx, ny in pts]
              + [P(px - nx * h, py - ny * h) for px, py, nx, ny in reversed(pts)], fill=c)


def render(snap):
    ours, cfp, outside, not_ranked, _ = lists(snap)
    img = Image.new("RGB", (W * S, H * S), BG)
    d = ImageDraw.Draw(img)
    tl = lambda text, f: d.textlength(text, font=f) / S

    # Header band
    d.rectangle([0, 0, W * S, 112 * S], fill=ACCENT)
    d.text(P(48, 20), f"TrueCFB vs the CFP ranking · {snap['season']}, games {snap['point'].lower()}",
           font=font("body", 600, 18), fill="#cfe3d7")
    d.text(P(46, 42), headline(snap), font=font("display", 700, 56), fill=ON_ACCENT)

    # Geometry (1x layout units)
    TOP, ROW = 164, 17.3                 # row 1's center; 25 rows plus one for the off-list notes
    XL, XR = 410, 790                    # where the lines start and end
    L_RANK = 82                          # TrueCFB rank, right-aligned
    R_RANK = XR + 78                     # CFP rank, right-aligned
    R_GAP = W - 62                       # (+#)/(−#), right-aligned at the panel's edge
    y = lambda i: TOP + (i - 1) * ROW
    y_off = y(26) + 6

    # Column titles: TrueCFB (the wordmark's colors) on the left, the committee on the right
    TF = font("display", 700, 26)
    tx = L_RANK - 34
    for text, c in (("True", INK), ("CFB", ACCENT)):
        d.text(P(tx, TOP - 33), text, font=TF, fill=c, anchor="lm")
        tx += tl(text, TF)
    d.text(P(XR + 54, TOP - 33), "CFP committee", font=TF, fill=INK, anchor="lm")

    # Top 12 panels
    for x0, x1 in ((L_RANK - 34, XL + 8), (XR - 8, W - 46)):
        d.rounded_rectangle([*P(x0, y(1) - ROW / 2 - 2), *P(x1, y(12) + ROW / 2 + 2)], radius=8 * S, fill=BAND_FILL)
    d.text(P((XL + XR) / 2, y(1) - ROW / 2 - 9), "TOP 12", font=font("body", 600, 12), fill=MUTED, anchor="mm")

    # Lines: the rest first, then the top 12 on top
    segs = [(t, y(t["rank"]), y(t["cfp_rank"]) if t["cfp_rank"] else y_off) for t in ours]
    segs += [(t, y_off, y(t["cfp_rank"])) for t in outside]
    top12 = lambda t: t["rank"] <= 12 or (t["cfp_rank"] or 99) <= 12
    for t, y0, y1 in sorted(segs, key=lambda s: top12(s[0])):
        c = line_color(t["color"])
        w, r = (5, 4.6) if top12(t) else (2.5, 3.2)
        if not top12(t):
            c = fade(c)
        curve(d, XL, y0, XR, y1, w, c)
        for x, yy in ((XL, y0), (XR, y1)):
            d.ellipse([*P(x - r, yy - r), *P(x + r, yy + r)], fill=c)

    NAME, RANK = font("display", 600, 19), font("display", 700, 19)
    RATING, REC, GAP = font("display", 600, 18), font("body", 400, 12), font("display", 600, 17)
    # TrueCFB: rank, team, Team Rating, record by the line
    for t in ours:
        yy = y(t["rank"])
        d.text(P(L_RANK, yy), str(t["rank"]), font=RANK, fill=ACCENT, anchor="rm")
        d.text(P(L_RANK + 12, yy), t["team"], font=NAME, fill=INK, anchor="lm")
        d.text(P(XL - 52, yy), f"{t['rating']:.1f}", font=RATING, fill=INK, anchor="rm")
        d.text(P(XL - 12, yy + 1), f"{t['wins']}-{t['losses']}", font=REC, fill=MUTED, anchor="rm")
    d.text(P(XL - 52, TOP - 31), "Team Rating", font=font("body", 600, 13), fill=MUTED, anchor="rm")
    # Committee: record by the line, rank, team, (spots higher or lower than TrueCFB)
    for t in cfp:
        yy = y(t["cfp_rank"])
        d.text(P(XR + 12, yy + 1), f"{t['wins']}-{t['losses']}", font=REC, fill=MUTED, anchor="lm")
        d.text(P(R_RANK, yy), str(t["cfp_rank"]), font=RANK, fill=INK, anchor="rm")
        d.text(P(R_RANK + 12, yy), t["team"], font=NAME, fill=INK, anchor="lm")
        g = cfp_gap(t)
        if g:   # its own right-aligned column, like Team Rating on the TrueCFB side
            d.text(P(R_GAP, yy), f"({signed(g)})", font=GAP, fill=UP if g > 0 else DOWN, anchor="rm")
    d.text(P(R_GAP, TOP - 31), "vs TrueCFB", font=font("body", 600, 13), fill=MUTED, anchor="rm")

    # Teams on one list only
    note = font("display", 600, 17)
    if outside:
        d.text(P(XL - 12, y_off), "Outside top 25: " + ", ".join(f"{t['team']} {t['rank']}" for t in outside),
               font=note, fill=MUTED, anchor="rm")
    if not_ranked:
        d.text(P(XR + 12, y_off), "Not ranked by CFP: " + ", ".join(t["team"] for t in not_ranked),
               font=note, fill=MUTED, anchor="lm")

    # Footer: wordmark, tagline, address (as on the result card)
    fy = H - 28
    d.line([P(48, fy - 22), P(W - 48, fy - 22)], fill=LINE, width=S)
    wf = font("display", 700, 30)
    d.text(P(48, fy), "True", font=wf, fill=INK, anchor="lm")
    tx = 48 + tl("True", wf)
    d.text(P(tx, fy), "CFB", font=wf, fill=ACCENT, anchor="lm")
    tx += tl("CFB", wf) + 18
    d.text(P(tx, fy + 1), TAGLINE, font=font("body", 400, 19), fill=MUTED, anchor="lm")
    d.text(P(W - 48, fy), "truecfb.com", font=font("body", 600, 20), fill=INK, anchor="rm")
    return img.resize((W * OUT, H * OUT), Image.LANCZOS)


def main():
    site_dir, data_dir, out = sys.argv[1:4]
    snap = snapshot(site_dir, data_dir)
    if snap is None:
        sys.exit("the current point has no full CFP ranking")
    render(snap).save(out, optimize=True)
    import game_impact as GI
    text = post_text(snap)
    print(out, "\n" + text, f"\n[{GI.weighted_length(text)} of {GI.MAX_POST}]")


if __name__ == "__main__":
    main()
