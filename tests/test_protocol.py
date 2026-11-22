"""End-to-end protocol test: relay + host + viewer in one process (GUI/OS modules stubbed)."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import asyncio, sys, types, os, tempfile, hashlib, itertools, time, shutil

def mod(name, **kw):
    m = types.ModuleType(name); m.__dict__.update(kw); sys.modules[name] = m; return m
class TclError(Exception): pass
mod("tkinter", TclError=TclError, Toplevel=object, Label=object); mod("PIL.ImageTk", PhotoImage=object)
mod("mss", mss=lambda: None); mod("pyperclip", paste=lambda: "", copy=lambda t: None)
calls = []
mod("pyautogui", FAILSAFE=True, PAUSE=1, KEYBOARD_KEYS=["a", "enter", "shift", "ctrl", "alt", "win"],
    moveTo=lambda *a, **k: calls.append(("move", a)), mouseDown=lambda *a, **k: calls.append(("down", a)),
    mouseUp=lambda *a, **k: calls.append(("up", a)), keyDown=lambda n: calls.append(("kd", n)),
    keyUp=lambda n: calls.append(("ku", n)), scroll=lambda d: calls.append(("scroll", d)))
class ConnectionClosed(Exception): pass
CLOSE = object()
class WS:
    def __init__(s): s.q = asyncio.Queue(); s.peer = None; s.closed = False
    async def send(s, m):
        if s.peer.closed: raise ConnectionClosed()
        await s.peer.q.put(m)
    async def recv(s):
        m = await s.q.get()
        if m is CLOSE: raise ConnectionClosed()
        return m
    def __aiter__(s): return s
    async def __anext__(s):
        m = await s.q.get()
        if m is CLOSE: raise StopAsyncIteration
        return m
    async def close(s, code=1000):
        if s.closed: return
        s.closed = True; await s.q.put(CLOSE); await s.peer.q.put(CLOSE)
class Conn:
    async def __aenter__(s):
        import server
        c, sv = WS(), WS(); c.peer, sv.peer = sv, c
        s.c, s.t = c, asyncio.create_task(server.handler(sv)); return c
    async def __aexit__(s, *a): await s.c.close()
mod("websockets", ConnectionClosed=ConnectionClosed, connect=lambda url, **kw: Conn(), WebSocketException=Exception, serve=None)
import hashlib as _h, os as _o
class _S:
    def __init__(self, pw, idA=b"", idB=b""): self.pw, self.ids = pw, (idA, idB)
    def start(self): self.r = _o.urandom(32); return self.side + self.r
    def finish(self, m):
        if m[:1] == self.side or len(m) != 33: raise ValueError
        a, b = (self.r, m[1:]) if self.side == b"A" else (m[1:], self.r)
        return _h.sha256(self.pw + self.ids[0] + self.ids[1] + a + b).digest()
class SPAKE2_A(_S): side = b"A"
class SPAKE2_B(_S): side = b"B"
mod("spake2", SPAKE2_A=SPAKE2_A, SPAKE2_B=SPAKE2_B)
import core
core.add_history = lambda *a: None
ANSWER, PROMPTS = [True], []
def fake_ask(title, text): PROMPTS.append(text); return ANSWER[0]
core.ask_allow = fake_ask

class FakeClip:
    inst = []
    def __init__(self, send, enabled): self.send, self.enabled, self.applied = send, enabled, []; FakeClip.inst.append(self)
    def apply(self, t): self.applied.append(t)
    def stop(self): pass
core.Clip = FakeClip

TMP_H, TMP_V = tempfile.mkdtemp(), tempfile.mkdtemp()
def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond: raise SystemExit(1)

async def scenario():
    cfg = dict(core.DEFAULTS, id="123456789")
    status = []; events = []
    h = core.Host(cfg, status.append, lambda n, sas: ("t", f"{n}|{sas}"), lambda w, **k: events.append((w, k)))
    h.pws["temp"] = core.derive("GoodPass12", "123456789")
    h.grab = lambda last: (b"JPEG", last + 1)
    h.mon = {"left": 0, "top": 0, "width": 1000, "height": 500}
    h.home = lambda: TMP_H
    h.dest = lambda: os.path.join(TMP_H, "in")
    task = asyncio.create_task(h.run()); await asyncio.sleep(0.2)
    orig = asyncio.wait_for
    async def fast(c, t): return await orig(c, min(t, 0.8))

    def viewer(pw, target="123456789"):
        v = object.__new__(core.Viewer)
        v._state(None, cfg, target, pw, lambda w, **k: vevents.append((w, k)), None)
        v.loop, v.out, v.seq = asyncio.get_running_loop(), asyncio.PriorityQueue(64), itertools.count()
        v.home = lambda: TMP_V
        return v
    vevents = []

    async def up(v, secs=3):
        t = asyncio.create_task(v.go())
        for _ in range(int(secs * 20)):
            await asyncio.sleep(0.05)
            if v.ready: break
        return t

    # ---- password mode ----
    asyncio.wait_for = fast
    try: r = await viewer("Wrong").go()
    except asyncio.TimeoutError: r = "timeout"
    asyncio.wait_for = orig
    ok("wrong password -> silence/timeout", r == "timeout")
    ok("unknown id", await viewer("x", "999999999").go() == "notfound")

    # ---- approval mode (no password) ----
    ANSWER[0] = True; PROMPTS.clear()
    v = viewer(""); t = await up(v)
    ok("approval mode: session established without password", v.ready and h.kind == "open")
    sas_v = [k["sas"] for w, k in vevents if w == "state" and k.get("code") == "approval"][0]
    ok("verification code shown on both sides and equal", sas_v and len(sas_v) == 6 and PROMPTS[-1].endswith(f"|{sas_v}"))
    ok("prompt text formats the code", "123 456" in core.prompt_text("en", "Bob", "123456")[1] and "123 456" in core.prompt_text("fa", "Bob", "123456")[1])
    ok("caps delivered to viewer", v.caps == {"agent": False, "files": True, "clip": True, "view": False})
    ok("host reported live session", ("live", {"name": v.name.replace(" ", "")[:0] + h.peer}) in events or any(e[0] == "live" for e in events))

    # ---- clipboard (fake Clip: verify routing both directions) ----
    hc, vc = FakeClip.inst[-2], FakeClip.inst[-1]
    hc.send("from-host"); vc.send("from-viewer"); await asyncio.sleep(0.4)
    ok("clipboard host->viewer", vc.applied == ["from-host"])
    ok("clipboard viewer->host", hc.applied == ["from-viewer"])

    # ---- file transfer viewer -> host ----
    src = os.path.join(TMP_V, "report.bin"); data = os.urandom(300_000) + b"end"
    open(src, "wb").write(data)
    v.send_files([src]); await asyncio.sleep(1.0)
    got = os.path.join(TMP_H, "in", "report.bin")
    ok("file viewer->host arrives intact (sha256)", os.path.exists(got) and open(got, "rb").read() == data)
    ok("no .part left behind", not [f for f in os.listdir(os.path.join(TMP_H, "in")) if f.endswith(".part")])
    v.send_files([src]); await asyncio.sleep(1.0)
    ok("existing file never overwritten (unique name)", os.path.exists(os.path.join(TMP_H, "in", "report (1).bin")))
    # hostile names go through the protocol too
    for evil, want in (("..\\..\\evil.txt", "evil.txt"), ("con.txt", "_con.txt"), ("a:b?c.txt", "a_b_c.txt")):
        p = os.path.join(TMP_V, "x.dat"); open(p, "wb").write(b"1")
        async def offer(name):
            await v.files.put(b"T" + core._j({"id": 77, "name": name, "size": 1}), 0)
            await v.files.put(b"c" + (77).to_bytes(4, "big") + b"1", 1)
            await v.files.put(b"E" + core._j({"id": 77, "sha": hashlib.sha256(b"1").hexdigest()}), 1)
        await offer(evil); await asyncio.sleep(0.5)
        ok(f"hostile name {evil!r} -> {want}", os.path.exists(os.path.join(TMP_H, "in", want)))
        os.remove(os.path.join(TMP_H, "in", want))
    # overflow + wrong hash are rejected and cleaned
    await v.files.put(b"T" + core._j({"id": 80, "name": "o.bin", "size": 2}), 0)
    await v.files.put(b"c" + (80).to_bytes(4, "big") + b"123456", 1); await asyncio.sleep(0.5)
    ok("oversized stream aborted, no file", not os.path.exists(os.path.join(TMP_H, "in", "o.bin")) and not os.path.exists(os.path.join(TMP_H, "in", "o.bin.part")))
    await v.files.put(b"T" + core._j({"id": 81, "name": "h.bin", "size": 2}), 0)
    await v.files.put(b"c" + (81).to_bytes(4, "big") + b"ab", 1)
    await v.files.put(b"E" + core._j({"id": 81, "sha": "00" * 32}), 1); await asyncio.sleep(0.5)
    ok("wrong hash rejected, no file", not os.path.exists(os.path.join(TMP_H, "in", "h.bin")) and not os.path.exists(os.path.join(TMP_H, "in", "h.bin.part")))

    # ---- remote listing + download host -> viewer ----
    open(os.path.join(TMP_H, "doc.txt"), "wb").write(b"hello"); os.makedirs(os.path.join(TMP_H, "sub"), exist_ok=True)
    vevents.clear(); v.browse(TMP_H); await asyncio.sleep(0.5)
    lst = [k["data"] for w, k in vevents if w == "list"][0]
    names = [i[0] for i in lst["items"]]
    ok("remote listing (dirs first)", lst["err"] == "" and names.index("sub") < names.index("doc.txt"))
    v.download(os.path.join(TMP_H, "doc.txt")); await asyncio.sleep(0.8)
    ok("download host->viewer", open(os.path.join(TMP_V, "Downloads", "RasaDesk", "doc.txt"), "rb").read() == b"hello")
    # viewer must refuse files it did not ask for
    await h.put(b"T" + core._j({"id": 5, "name": "unsolicited.exe", "size": 1}), 0); await asyncio.sleep(0.4)
    ok("unsolicited push to viewer refused", not os.path.exists(os.path.join(TMP_V, "Downloads", "RasaDesk", "unsolicited.exe")))
    # host policy switches
    cfg["allow_files"] = False
    vevents.clear(); v.browse(TMP_H); await asyncio.sleep(0.4)
    ok("allow_files off: listing ignored", not [1 for w, k in vevents if w == "list"])
    v.send_files([src]); await asyncio.sleep(0.6)
    ok("allow_files off: upload refused", not os.path.exists(os.path.join(TMP_H, "in", "report (2).bin")))
    cfg["allow_files"] = True
    await v.ws.close(); await asyncio.sleep(0.4)
    ok("session cleaned up", h.chan is None and not h.live and h.files is None and status[-1] == "ready")

    # ---- approval refusals ----
    ANSWER[0] = False
    ok("approval denied by person", await viewer("").go() == "denied")
    cfg["allow_open"] = False
    ok("approval requests disabled -> noopen", await viewer("").go() == "noopen")
    cfg["allow_open"] = True
    h.can_prompt = lambda: False
    ok("nobody to approve -> noapprover (open)", await viewer("").go() == "noapprover")
    ANSWER[0] = True
    v2 = viewer("GoodPass12"); ok("password mode while locked: needs approver -> noapprover", await v2.go() == "noapprover")
    cfg["approve"] = False; h.pws["perm"] = core.derive("PermPass99", "123456789")
    v3 = viewer("PermPass99"); t3 = await up(v3)
    ok("permanent password + approve off works with nobody at the PC", v3.ready and h.kind == "perm")
    await v3.ws.close(); await asyncio.sleep(0.4)
    h.can_prompt = lambda: True; cfg["approve"] = True

    # ---- anti-spam: 3 refused approval requests pause approvals ----
    ANSWER[0] = False; h.denials = []
    for _ in range(3): await viewer("").go()
    ok("3 refusals -> approval requests paused", await viewer("").go() == "noopen")
    h.open_lock = 0; ANSWER[0] = True

    # ---- password session still fine after all that ----
    v4 = viewer("GoodPass12"); t4 = await up(v4)
    ok("password session works", v4.ready and h.kind == "temp")
    v4.send({"k": "move", "x": .5, "y": .5}); v4.send({"k": "move", "x": 9, "y": 0}); v4.send({"k": "kd", "n": "rm -rf"})
    await asyncio.sleep(0.4)
    ok("input validated", calls.count(("move", (499, 249))) == 1 and not any(c[0] == "kd" for c in calls))
    await v4.ws.close(); await asyncio.sleep(0.3)
    task.cancel(); print("ALL OK")

asyncio.run(scenario())
shutil.rmtree(TMP_H, True); shutil.rmtree(TMP_V, True)
