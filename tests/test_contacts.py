"""Contacts: storage, validation, hostile files, photos, rendering."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import types, tempfile, json, time
def mod(n, **kw):
    m = types.ModuleType(n); m.__dict__.update(kw); sys.modules[n] = m
class TclError(Exception): pass
mod("tkinter", TclError=TclError, Toplevel=object, Label=object); mod("PIL.ImageTk", PhotoImage=object)
mod("mss", mss=lambda: None); mod("pyautogui", FAILSAFE=1, PAUSE=1, KEYBOARD_KEYS=[]); mod("pyperclip", paste=lambda: "", copy=lambda t: None)
mod("websockets", ConnectionClosed=Exception, connect=None, WebSocketException=Exception); mod("spake2", SPAKE2_A=object, SPAKE2_B=object)
import core, contacts
from PIL import Image
core.APP = tempfile.mkdtemp()
assert contacts.load() == []
assert contacts.touch("123456789")["count"] == 1
contacts.touch("987654321"); contacts.touch("123456789")
lst = contacts.load(); assert [x["id"] for x in lst] == ["123456789", "987654321"] and lst[0]["count"] == 2, lst
print("PASS touch: create, count, newest first")
assert contacts.touch("../../etc") is None and contacts.touch("12345678") is None
try: contacts.avatar_path("../x"); raise SystemExit("path traversal!")
except ValueError: pass
print("PASS ids validated before becoming file names")
contacts.update("123456789", name="Ali <script>/..\\x", color="#ff0000"); contacts.update("123456789", color="red")
c = contacts.load()[0]; assert c["color"] == "#ff0000" and not any(ch in c["name"] for ch in "<>/\\"), c
print("PASS name sanitized, invalid color ignored")
json.dump([{"id": "123456789", "name": "x" * 500, "color": "javascript:1", "count": -5, "last": "now"}, {"id": "../..", "name": "evil"}, "str", None, {"id": "123456789"}], open(os.path.join(core.APP, "contacts.json"), "w"))
l = contacts.load(); assert len(l) == 1 and len(l[0]["name"]) <= 32 and l[0]["color"] == "" and l[0]["count"] == 0, l
print("PASS hostile contacts.json cleaned")
p = os.path.join(core.APP, "photo.jpg"); Image.new("RGB", (900, 400), (10, 120, 200)).save(p)
av = contacts.make_avatar(p); assert av.size == (192, 192)
contacts.save_avatar("123456789", av); assert os.path.exists(contacts.avatar_path("123456789"))
bad = os.path.join(core.APP, "bad.png"); open(bad, "wb").write(b"not an image")
try: contacts.make_avatar(bad); raise SystemExit("bad image accepted")
except SystemExit: raise
except Exception: pass
print("PASS photo cropped to 192px PNG, non-image rejected")
for c_, kw in (({"id": "123456789", "name": "x", "color": ""}, {}), ({"id": "123456789", "name": "Bob"}, {"use_file": False}), ({"id": "555555555", "name": ""}, {})):
    im = contacts.render(c_, 104, "#E11D2E", **kw); assert im.size == (104, 104) and im.getpixel((0, 0))[3] == 0 and im.getpixel((52, 52))[3] == 255
print("PASS render: round avatar, transparent corners")
contacts.delete("123456789"); assert not os.path.exists(contacts.avatar_path("123456789")) and all(x["id"] != "123456789" for x in contacts.load())
print("PASS delete removes record and photo"); print("ALL OK")
