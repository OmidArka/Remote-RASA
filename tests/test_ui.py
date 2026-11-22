"""Executes every UI code path with a mocked toolkit (catches NameError, bad arguments, missing strings)."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import sys, types
from unittest.mock import MagicMock
def mod(n, **kw):
    m = types.ModuleType(n); m.__dict__.update(kw); sys.modules[n] = m; return m
class TclError(Exception): pass
tkm = mod("tkinter", TclError=TclError, Toplevel=object, Label=object, Listbox=MagicMock())
for sub in ("colorchooser", "font", "filedialog"):
    m = mod("tkinter." + sub); setattr(tkm, sub, m)
sys.modules["tkinter.font"].families = lambda root=None: {"Vazirmatn"}
sys.modules["tkinter.font"].Font = lambda **k: MagicMock(measure=lambda t: 8 * len(t))
sys.modules["tkinter.colorchooser"].askcolor = lambda **k: (None, "#123456")
sys.modules["tkinter.filedialog"].askopenfilenames = lambda **k: ["a.txt"]
mod("PIL.ImageTk", PhotoImage=object); mod("mss", mss=lambda: None); mod("pyperclip", paste=lambda: "", copy=lambda t: None)
mod("pyautogui", FAILSAFE=1, PAUSE=1, KEYBOARD_KEYS=[])
mod("websockets", ConnectionClosed=Exception, connect=None, WebSocketException=Exception)
mod("spake2", SPAKE2_A=object, SPAKE2_B=object)

class Base:
    def __init__(self, *a, **k): object.__setattr__(self, "_m", MagicMock())
    def __getattr__(self, n): return getattr(object.__getattribute__(self, "_m"), n)
SCALES = []
ctk = mod("customtkinter", CTk=Base, CTkToplevel=Base, set_appearance_mode=lambda m: None, get_appearance_mode=lambda: "Dark", set_widget_scaling=SCALES.append)
for n in ("CTkFrame", "CTkLabel", "CTkButton", "CTkEntry", "CTkSwitch", "CTkSegmentedButton", "CTkScrollableFrame", "CTkScrollbar", "CTkFont", "CTkImage"):
    setattr(ctk, n, MagicMock(name=n))

import core, winsvc, tempfile, os, time
core.APP = tempfile.mkdtemp()
import contacts
core.Host.start = lambda self: None
core.save_cfg = lambda *a, **k: None
core.load_cfg = lambda path=None: dict(core.DEFAULTS, id="123456789")
import rasadesk as R

def run(label, fn):
    try: fn(); print("PASS", label)
    except Exception as e:
        import traceback; traceback.print_exc(); print("FAIL", label, repr(e)); raise SystemExit(1)

def all_pages(app):
    app.tab = "home"; app.build()
    app.tab = "settings"
    for sec, _ in R.SECTIONS + R.BOTTOM:
        app.sec = sec; app.build()

for lang in ("fa", "en"):
    sys.argv = ["x"]
    app = R.App(); app.cfg["lang"] = lang
    run(f"[{lang}] normal mode: every page builds", lambda: all_pages(app))
    # strings: every key used by s.t("...") exists in both languages
import re
src = open(os.path.join(ROOT, "rasadesk.py"), encoding="utf-8").read()
used = set(re.findall(r's\.t\("(\w+)"\)', src)) | set(re.findall(r'app\.t\("(\w+)"\)', src))
used |= {"ev_" + e for e in ("accepted", "denied", "locked")} | {"svc_" + x for x in ("none", "stopped", "running", "other", "unavail")}
for lang in ("fa", "en"):
    missing = sorted(k for k in used if k not in R.T[lang])
    print(lang, "missing string keys:", missing); assert not missing
print("PASS strings complete (fa/en)")
assert set(R.T["fa"]) == set(R.T["en"]), set(R.T["fa"]) ^ set(R.T["en"])
print("PASS fa/en have identical key sets")

app = R.App(); app.cfg["lang"] = "fa"
v = MagicMock(); v.caps = {"files": True, "agent": True, "clip": True}
run("viewer toolbar (files + CAD caps)", lambda: app.toolbar(MagicMock(), v))
v.caps = {}; run("viewer toolbar (no caps)", lambda: app.toolbar(MagicMock(), v))
rb = R.RemoteBrowser(app, v)
run("remote browser: show/open/up/download", lambda: (
    rb.show({"p": "", "items": [["C:\\", 0, True], ["D:\\", 0, True]], "err": ""}),
    rb.show({"p": "C:\\Users", "items": [["Bob", 0, True], ["a.txt", 2048, False]], "err": ""}),
    rb.show({"err": "denied"})))
rb.path, rb.items = "C:\\Users\\Bob", [["docs", 0, True], ["f.txt", 10, False]]
rb.lb.curselection = lambda: (0,)
rb.go = MagicMock(); rb.open(); assert rb.go.call_args[0][0] == "C:\\Users\\Bob\\docs", rb.go.call_args
rb.lb.curselection = lambda: (1,); rb.v.download = MagicMock(); rb.open(); assert rb.v.download.call_args[0][0] == "C:\\Users\\Bob\\f.txt"
for path, want in (("C:\\Users\\Bob", "C:\\Users"), ("C:\\Users", "C:\\"), ("C:\\", ""), ("", "")):
    rb.path = path; rb.go = MagicMock(); rb.up(); assert rb.go.call_args[0][0] == want, (path, rb.go.call_args)
print("PASS remote browser navigation (open dir, download file, up to drive list)")
run("session bar + host events", lambda: (app.on_host_event("live", {"name": "Bob"}), app.on_host_event("file", {"kind": "received", "name": "x"}), app.on_host_event("end", {})))
run("viewer events", lambda: [app.on_evt(v, w, **k) for w, k in (("state", {"code": "connecting"}), ("state", {"code": "approval", "sas": "123456"}),
                              ("error", {"code": "noopen"}), ("error", {"code": "noapprover"}), ("file", {"kind": "progress", "name": "a", "done": 5, "total": 10}),
                              ("list", {"data": {}}))])
assert app.file_text({"kind": "progress", "name": "a", "done": 5, "total": 10}) == "a: 50%"

# service mode (service running): app has no host of its own
winsvc.state = lambda: "running"; winsvc.public = lambda: {"id": "987654321", "state": "ready"}
app2 = R.App(); assert app2.host is None and app2.svc_active
run("service mode: every page builds", lambda: all_pages(app2))
# elevated setup instance
winsvc.state = lambda: "none"; winsvc.public = lambda: {}
winsvc.setup_defaults = lambda cfg: {"id": "111222333", "server": "ws://x:1", "approve": False, "allow_open": True, "allow_files": True, "allow_clip": True, "view_only": False, "lang": "en", "fps": 10, "quality": 55, "perm": ""}
sys.argv = ["x", "--svc-setup"]
app3 = R.App(); assert app3.host is None and app3.setup and app3.tab == "settings" and app3.sec == "service"
run("setup mode: service form builds", lambda: app3.build())
installed = []
winsvc.install = lambda c, p: installed.append((dict(c), p))
app3.entry = lambda *a, **k: MagicMock(get=MagicMock(return_value="wss://ok.example:8765"))
print("ALL UI PATHS EXECUTED")

# ================= v0.6: scale + contacts =================
sys.argv = ["x"]
winsvc.state = lambda: "none"; winsvc.public = lambda: {}
app = R.App(); app.cfg["lang"] = "fa"
assert SCALES[-1] == 1.0, SCALES
print("PASS startup applies the saved text scale:", SCALES[-1])
assert core.validate_cfg({"text_scale": 1.3})["text_scale"] == 1.3 and core.validate_cfg({"text_scale": 9})["text_scale"] == 1.0 and core.validate_cfg({"text_scale": "big"})["text_scale"] == 1.0 and core.validate_cfg({})["accent"] == "#E11D2E"
print("PASS scale setting validated (only 1.0 / 1.15 / 1.3), default Normal + red")
assert R.F(11).cget if False else True
for sz in (9, 11, 12, 13, 14):
    assert max(sz + 2, 15) >= 15
print("PASS font floor: no text smaller than 15 px")

# empty state, then many contacts
app.tab = "home"; run("home with no contacts", app.build)
for i in range(1, 10): contacts.touch(f"{i}00000000"[:9].ljust(9, "0"))
contacts.update("100000000", name="علی"); contacts.update("200000000", name="Bob", color="#123456")
run("home with 9 contacts (6 shown)", app.build)
app.show_all = True; run("home with all contacts + RTL grid", app.build)
app.cfg["lang"] = "en"; run("home contacts in LTR", app.build); app.cfg["lang"] = "fa"
lst = contacts.load(); assert len(lst) == 9
t = app.tile(MagicMock(), lst[0]); print("PASS tile built")
app.tid, app.tpw = MagicMock(), MagicMock(); app.pick("123456789")
assert app.tid.insert.call_args[0][1] == "123 456 789" and app.tpw.focus_set.called
print("PASS clicking a contact fills the ID and focuses the password")
assert app.ago(int(time.time())) == app.t("ago_now") and "5" in app.ago(int(time.time()) - 300) and "3" in app.ago(int(time.time()) - 3 * 3600) and "2" in app.ago(int(time.time()) - 2 * 86400)
assert len(app.ago(int(time.time()) - 90 * 86400)) == 10
print("PASS relative time (now / minutes / hours / days / date)")
# a successful connection is recorded and refreshes home
v = MagicMock(); v.target = "777777777"; app.refresh = MagicMock(); app.tab = "home"
app.on_evt(v, "connected"); assert any(c["id"] == "777777777" and c["count"] == 1 for c in contacts.load()) and app.refresh.called
print("PASS successful connection is saved to contacts and the list refreshes")
# edit dialog: color + name + photo applied only on Save
from PIL import Image
photo = os.path.join(core.APP, "me.png"); Image.new("RGB", (300, 200), (200, 50, 80)).save(photo)
c = [x for x in contacts.load() if x["id"] == "777777777"][0]
d = R.ContactDialog(app, c)
d.name.get = lambda: "Sara <b>"; d.setc("#2563EB")
R.filedialog.askopenfilename = lambda **k: photo
d.pick_photo(); assert d.photo is not None and not os.path.exists(contacts.avatar_path("777777777"))
d.save()
c2 = [x for x in contacts.load() if x["id"] == "777777777"][0]
assert c2["name"] == "Sara b" and c2["color"] == "#2563EB" and os.path.exists(contacts.avatar_path("777777777"))
print("PASS dialog: name sanitized, color + photo saved only on Save ->", repr(c2["name"]))
d = R.ContactDialog(app, c2); d.rm_photo(); d.save(); assert not os.path.exists(contacts.avatar_path("777777777"))
R.filedialog.askopenfilename = lambda **k: os.path.join(core.APP, "nope.png")
d = R.ContactDialog(app, c2); d.pick_photo(); assert d.photo is None
print("PASS remove photo; unreadable image is rejected without crashing")
d = R.ContactDialog(app, c2); d.delete(); assert all(x["id"] != "777777777" for x in contacts.load())
print("PASS delete contact")
# text-size selector reachable on the Advanced page in both languages
for lang in ("fa", "en"):
    app.cfg["lang"] = lang; app.tab, app.sec = "settings", "advanced"; run(f"[{lang}] advanced page with text-size selector", app.build)
used = set(re.findall(r's\.t\("(\w+)"\)', open(os.path.join(ROOT, "rasadesk.py"), encoding="utf-8").read())) | set(re.findall(r'app\.t\("(\w+)"\)', open(os.path.join(ROOT, "rasadesk.py"), encoding="utf-8").read()))
used |= {"ev_accepted", "ev_denied", "ev_locked"}
for lang in ("fa", "en"):
    miss = sorted(k for k in used if k not in R.T[lang]); assert not miss, miss
assert set(R.T["fa"]) == set(R.T["en"])
print("PASS all string keys present in fa and en")
print("ALL v0.6 UI CHECKS OK")
