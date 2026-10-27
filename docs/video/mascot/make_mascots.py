"""Vigil mascot family: the Capsule (the product) and the agent crew (one capsule per agent).
Run: python -I docs/video/mascot/make_mascots.py

Writes transparent PNG sprites to sprites/ for the video, plus vigil-mascots.svg, a sheet
of every sprite, and 1x copies to app/static/mascots/ for the investigation page. All sprites share one 20 x 18 pixel canvas, so they line up when swapped
frame to frame. Colours come from the Vigil logo in docs/logo.
"""
from pathlib import Path

from PIL import Image

COLOURS = {
    "N": "#14366B",   # logo navy
    "T": "#0F7C86",   # logo teal
    "O": "#B4441B",   # logo orange
    "S": "#5B6676",   # logo slate
    "W": "#FFFFFF",
    "K": "#14161F",   # eyes on light tops
    "L": "#CDE8EA",   # lens, sweat drop
}
BG, INK, MUTED = "#F7F1E4", "#14366B", "#5B6676"
CANVAS_W, CANVAS_H = 20, 18
BODY_X, BODY_Y = 2, 3          # where the body grid sits on the canvas
PNG_SCALE = 32                 # canvas pixels -> PNG pixels (640 x 576)

# X = top half, Z = bottom half, W = seam, N = legs; "." is empty
BODY = """
......XXXX......
....XXXXXXXX....
...XXXXXXXXXX...
...XXXXXXXXXX...
...XXXXXXXXXX...
...XXXXXXXXXX...
...XXXXXXXXXX...
...WWWWWWWWWW...
..ZZZZZZZZZZZZ..
..ZZZZZZZZZZZZ..
...ZZZZZZZZZZ...
...ZZZZZZZZZZ...
....ZZZZZZZZ....
....N.N..N.N....
....N.N..N.N....
"""

# Eye pixels per expression, in body-grid coordinates (x, y), plus extra marks.
EXPRESSIONS = {
    "neutral":   {"eyes": [(5, 4), (5, 5), (10, 4), (10, 5)]},
    "blink":     {"eyes": [(4, 5), (5, 5), (10, 5), (11, 5)]},
    "happy":     {"eyes": [(4, 5), (5, 4), (6, 5), (9, 5), (10, 4), (11, 5)]},
    "alert":     {"eyes": [(5, 3), (5, 4), (5, 5), (10, 3), (10, 4), (10, 5)]},
    "look":      {"eyes": [(6, 4), (6, 5), (11, 4), (11, 5)]},
    "squint":    {"eyes": [(5, 4), (5, 5), (10, 5)]},
    "concerned": {"eyes": [(5, 5), (5, 6), (10, 5), (10, 6), (4, 3), (5, 2), (11, 3), (10, 2)],
                  "marks": [(13, 1, "L"), (13, 2, "L")]},
}

# Arm poses: body-grid pixels to clear (back to empty) and to paint in the bottom colour.
POSES = {
    "stand": {"clear": [], "add": []},
    "wave":  {"clear": [(13, 9)], "add": [(13, 7), (14, 6), (14, 5)]},
    "point": {"clear": [(13, 9)], "add": [(14, 8), (15, 8)]},
    "cheer": {"clear": [(13, 9), (2, 9)], "add": [(13, 7), (14, 6), (14, 5), (2, 7), (1, 6), (1, 5)]},
}

# Agent props, in canvas coordinates.
PROPS = {
    "clerk":    [(16, 10, "W"), (17, 10, "W"), (18, 10, "W"), (16, 11, "S"), (17, 11, "S"), (18, 11, "S"),
                 (16, 12, "W"), (17, 12, "W"), (18, 12, "W"), (16, 13, "S"), (17, 13, "S"), (18, 13, "S")],
    "analyst":  [(17, 3, "N"), (18, 3, "N"), (16, 4, "N"), (17, 4, "L"), (18, 4, "L"), (19, 4, "N"),
                 (16, 5, "N"), (17, 5, "L"), (18, 5, "L"), (19, 5, "N"), (17, 6, "N"), (18, 6, "N"),
                 (16, 7, "O"), (16, 8, "O"), (16, 9, "O"), (16, 10, "O")],
    "reviewer": [(14, 2, "T"), (15, 3, "T"), (16, 2, "T"), (17, 1, "T"), (18, 0, "T")],
    "skeptic":  [(16, 0, "K"), (17, 0, "K"), (15, 1, "K"), (18, 1, "K"), (17, 2, "K"), (16, 3, "K"),
                 (16, 5, "K")],
}

# name: (top, bottom, eye colour, prop, default expression, one-line role)
CAST = {
    "vigil":    ("T", "O", "K", None, "neutral", "The product"),
    "clerk":    ("N", "T", "W", "clerk", "neutral", "Data Clerk: fetches the counts"),
    "analyst":  ("T", "N", "K", "analyst", "look", "Analyst: builds the case"),
    "reviewer": ("O", "N", "K", "reviewer", "neutral", "Reviewer: checks the numbers"),
    "skeptic":  ("S", "O", "W", "skeptic", "squint", "Skeptic: raises objections"),
}


def build(who, expression=None, pose="stand", bob=False):
    """Return the sprite as a list of rows of colour keys ("." for empty)."""
    top, bottom, eye, prop, default, _ = CAST[who]
    expr = EXPRESSIONS[expression or default]
    body = [list(r) for r in BODY.strip("\n").split("\n")]
    for x, y in POSES[pose]["clear"]:
        body[y][x] = "."
    for x, y in POSES[pose]["add"]:
        body[y][x] = "Z"
    for x, y in expr["eyes"]:
        body[y][x] = "E"
    for x, y, c in expr.get("marks", []):
        body[y][x] = c
    if bob:                                   # squash one row: drop the legs' lower row
        body = [["."] * len(body[0])] + body[:-1]
    g = [["."] * CANVAS_W for _ in range(CANVAS_H)]
    for y, row in enumerate(body):
        for x, c in enumerate(row):
            if c != ".":
                g[y + BODY_Y][x + BODY_X] = {"X": top, "Z": bottom, "E": eye}.get(c, c)
    for x, y, c in PROPS.get(prop, []):
        g[y][x] = c
    return g


def to_png(g, path, scale=PNG_SCALE):
    img = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    for y, row in enumerate(g):
        for x, c in enumerate(row):
            if c != ".":
                h = COLOURS[c].lstrip("#")
                img.putpixel((x, y), tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (255,))
    img.resize((CANVAS_W * scale, CANVAS_H * scale), Image.NEAREST).save(path)


def svg_sprite(g, cx, bottom, px):
    x0, y0 = cx - CANVAS_W * px / 2, bottom - CANVAS_H * px
    out = [f'<ellipse cx="{cx}" cy="{bottom + 3}" rx="{6 * px}" ry="{max(3, px * 0.6):.0f}" fill="#E9DFCB"/>']
    for y, row in enumerate(g):
        for x, c in enumerate(row):
            if c != ".":
                out.append(f'<rect x="{x0 + x * px:.0f}" y="{y0 + y * px:.0f}" width="{px}" height="{px}" '
                           f'fill="{COLOURS[c]}"/>')
    return "".join(out)


FONT = "font-family=\"'IBM Plex Sans', 'Segoe UI', Arial, sans-serif\""


def label(x, y, s, size=15, colour=MUTED, weight=400, anchor="middle"):
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" {FONT} font-size="{size}" font-weight="{weight}" fill="{colour}">{s}</text>'


def sheet(hero_frames, crew_rows):
    W, H = 1400, 1180
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           f'shape-rendering="crispEdges">', f'<rect width="{W}" height="{H}" fill="{BG}"/>',
           label(60, 66, "Vigil mascot family", 30, INK, 600, "start"),
           label(60, 98, "Vigil the capsule stands for the product; each agent is a recoloured capsule with its own prop.",
                 17, MUTED, 400, "start"),
           label(60, 160, "Vigil: expressions and poses", 20, INK, 600, "start")]
    step = W / len(hero_frames)
    for i, (name, g) in enumerate(hero_frames):
        cx = step * (i + 0.5)
        out += [svg_sprite(g, cx, 370, 8), label(cx, 405, name)]

    out.append(label(60, 480, "The agent crew: neutral, happy, concerned", 20, INK, 600, "start"))
    step = W / len(crew_rows)
    for i, (role, frames) in enumerate(crew_rows):
        cx = step * (i + 0.5)
        for j, g in enumerate(frames):
            out.append(svg_sprite(g, cx + (j - 1) * 108, 690, 5))
        out.append(label(cx, 730, role, 15))

    out.append(label(60, 800, "Line-up: Vigil with its crew", 20, INK, 600, "start"))
    lineup = [("clerk", 7), ("analyst", 7), ("vigil", 11), ("reviewer", 7), ("skeptic", 7)]
    for i, (who, px) in enumerate(lineup):
        cx = 260 + i * 220
        out.append(svg_sprite(build(who), cx, 1120, px))
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    here = Path(__file__).parent
    sprites = here / "sprites"
    sprites.mkdir(exist_ok=True)
    count = 0
    for who in CAST:
        for expr in EXPRESSIONS:
            to_png(build(who, expr), sprites / f"{who}-{expr}.png")
            count += 1
        to_png(build(who, bob=True), sprites / f"{who}-bob.png")
        count += 1
    for pose, expr in (("wave", "happy"), ("point", "look"), ("cheer", "happy")):
        to_png(build("vigil", expr, pose), sprites / f"vigil-{pose}.png")
        count += 1

    # The investigation page's copies: one pixel per canvas pixel, scaled up in CSS (image-rendering: pixelated).
    page = here.parents[2] / "app" / "static" / "mascots"
    page.mkdir(exist_ok=True)
    for who in CAST:
        for expr in EXPRESSIONS:
            to_png(build(who, expr), page / f"{who}-{expr}.png", 1)
        to_png(build(who, bob=True), page / f"{who}-bob.png", 1)

    hero = [(e, build("vigil", e)) for e in ("neutral", "happy", "alert", "concerned", "blink")]
    hero += [(p, build("vigil", e, p)) for p, e in (("wave", "happy"), ("point", "look"), ("cheer", "happy"))]
    crew = [(CAST[w][5], [build(w), build(w, "happy"), build(w, "concerned")])
            for w in ("clerk", "analyst", "reviewer", "skeptic")]
    (here / "vigil-mascots.svg").write_text(sheet(hero, crew), encoding="utf-8")
    print(f"{count} sprites in {sprites}")
