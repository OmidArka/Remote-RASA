"""RasaDesk contacts: the computers/people you connected to, each with a name, color and optional photo."""
import json, os, re, time

from PIL import Image, ImageDraw, ImageFont, ImageOps

import core

MAX = 500
_HEX = re.compile(r"#[0-9a-fA-F]{6}")
_ID = re.compile(r"\d{9}")


def _file():
    return os.path.join(core.APP, "contacts.json")


def avatar_path(i):
    if not _ID.fullmatch(str(i)):
        raise ValueError("bad id")  # ids become file names: only 9 digits are ever allowed
    return os.path.join(core.APP, "avatars", i + ".png")


def load():
    try:
        with open(_file(), encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return []
    out, seen = [], set()
    for c in (raw if isinstance(raw, list) else [])[:MAX]:
        if not isinstance(c, dict):
            continue
        i = c.get("id")
        if not (isinstance(i, str) and _ID.fullmatch(i)) or i in seen:
            continue
        seen.add(i)
        col, n, t = c.get("color"), c.get("count"), c.get("last")
        out.append({"id": i, "name": core.clean_name(c.get("name", "")),
                    "color": col if isinstance(col, str) and _HEX.fullmatch(col) else "",
                    "count": n if isinstance(n, int) and n >= 0 else 0,
                    "last": t if isinstance(t, int) and t >= 0 else 0})
    return sorted(out, key=lambda c: -c["last"])


def save(lst):
    try:
        core._write(_file(), lst[:MAX])
    except OSError:
        pass


def touch(i):
    """Record a successful connection to `i` (creates the contact on first use)."""
    if not _ID.fullmatch(str(i)):
        return None
    lst = load()
    c = next((x for x in lst if x["id"] == i), None) or {"id": i, "name": "", "color": "", "count": 0, "last": 0}
    c["count"], c["last"] = c["count"] + 1, int(time.time())
    # newest first; the stable sort keeps the one just touched ahead of others from the same second
    save(sorted([c] + [x for x in lst if x["id"] != i], key=lambda x: -x["last"]))
    return c


def update(i, name=None, color=None):
    lst = load()
    for c in lst:
        if c["id"] == i:
            if name is not None:
                c["name"] = core.clean_name(name)
            if color is not None and _HEX.fullmatch(color):
                c["color"] = color
    save(lst)


def delete(i):
    save([c for c in load() if c["id"] != i])
    remove_avatar(i)


# ---- photos: decoded, cropped square, re-encoded as a clean PNG (no metadata, no original kept) ----
def make_avatar(path):
    if os.path.getsize(path) > 15 * 2 ** 20:
        raise ValueError("file too large")
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGBA")
    return ImageOps.fit(im, (192, 192), Image.Resampling.LANCZOS)


def save_avatar(i, im):
    p = avatar_path(i)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    im.save(p, "PNG")


def remove_avatar(i):
    try:
        os.remove(avatar_path(i))
    except (OSError, ValueError):
        pass


def _mix(a, b, t):
    pa, pb = ([int(x[k:k + 2], 16) for k in (1, 3, 5)] for x in (a, b))
    return tuple(round(p * (1 - t) + q * t) for p, q in zip(pa, pb))


def _font(path, px):
    """Always a scalable font: the app font, then common system fonts, then Pillow's built-in scalable one."""
    for cand in (path, "segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
        if cand:
            try:
                return ImageFont.truetype(cand, px)
            except OSError:
                pass
    return ImageFont.load_default(size=px)


def render(c, size, color, photo=None, use_file=True, font=None):
    """Round avatar with a colored ring: the contact's photo, or a colored disc with the first letter."""
    S = size * 4
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((0, 0, S - 1, S - 1), fill=_mix(color, "#FFFFFF", 0) + (255,))
    ring = S // 14
    D = S - 2 * ring
    if photo is None and use_file:
        try:
            with Image.open(avatar_path(c["id"])) as f:
                photo = f.convert("RGBA")
        except (OSError, ValueError):
            photo = None
    mask = Image.new("L", (D, D), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, D - 1, D - 1), fill=255)
    if photo is not None:
        im.paste(ImageOps.fit(photo, (D, D), Image.Resampling.LANCZOS), (ring, ring), mask)
    else:
        disc = Image.new("RGBA", (D, D), _mix(color, "#000000", 0.12) + (255,))
        im.paste(disc, (ring, ring), mask)
        txt = ((c.get("name") or "") or c["id"])[:1].upper()
        f = _font(font, int(S * 0.44))
        try:
            d.text((S / 2, S / 2), txt, font=f, fill="white", anchor="mm")
        except (ValueError, TypeError):
            d.text((S / 3, S / 3), txt, font=f, fill="white")
    return im.resize((size, size), Image.Resampling.LANCZOS)
