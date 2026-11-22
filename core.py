"""RasaDesk core: config, PAKE crypto, Host, Viewer, files, clipboard  |  Amn Negar Rasa"""
import asyncio, base64, contextlib, ctypes, hashlib, hmac, io, itertools, json, os, re, secrets, socket, stat, string, struct, threading, time, zlib
import ctypes.wintypes as wt
import tkinter as tk

import mss
import pyautogui
import pyperclip
import websockets
from spake2 import SPAKE2_A, SPAKE2_B
from PIL import Image, ImageTk
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0
MAXW = 1280
APP = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "RasaDesk")
CFG, HIST = os.path.join(APP, "config.json"), os.path.join(APP, "history.json")

# ───────────────────────── Windows helpers (DPAPI, single instance) ─────────────────────────
if os.name == "nt":
    class _Blob(ctypes.Structure):
        _fields_ = [("n", wt.DWORD), ("p", ctypes.c_void_p)]

    K32 = ctypes.WinDLL("kernel32", use_last_error=True)
    K32.CreateMutexW.restype, K32.CreateMutexW.argtypes = wt.HANDLE, [ctypes.c_void_p, wt.BOOL, wt.LPCWSTR]
    K32.CloseHandle.argtypes = [wt.HANDLE]
    K32.LocalFree.argtypes = [ctypes.c_void_p]
    C32 = ctypes.WinDLL("crypt32")
    for _f in (C32.CryptProtectData, C32.CryptUnprotectData):
        _f.restype = wt.BOOL
        _f.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.POINTER(_Blob), ctypes.c_void_p,
                       ctypes.c_void_p, wt.DWORD, ctypes.POINTER(_Blob)]

_mutex = None


def single_instance():
    global _mutex
    _mutex = K32.CreateMutexW(None, False, "Local\\RasaDeskSingleton")
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS


def release_instance():
    if _mutex:
        K32.CloseHandle(_mutex)


def _dpapi(fn, data, flags=0):
    buf = ctypes.create_string_buffer(data, len(data))
    src, out = _Blob(len(data), ctypes.cast(buf, ctypes.c_void_p)), _Blob()
    if not fn(ctypes.byref(src), None, None, None, None, flags, ctypes.byref(out)):
        raise OSError("DPAPI failed")
    try:
        return ctypes.string_at(out.p, out.n)
    finally:
        K32.LocalFree(out.p)


def message_box(title, text, flags):
    return ctypes.windll.user32.MessageBoxW(0, text, title, flags)


def ask_allow(title, text):
    # YESNO | ICONQUESTION | DEFBUTTON2 (default = No) | TOPMOST
    return message_box(title, text, 0x4 | 0x20 | 0x100 | 0x40000) == 6


# ───────────────────────── Config (validated, atomic, private) ─────────────────────────
def new_id():
    return "".join(secrets.choice(string.digits) for _ in range(9))


def new_pw():
    return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))


_SERVER = re.compile(r"wss?://[A-Za-z0-9.\-]+(:\d{1,5})?")


def valid_server(v):
    return isinstance(v, str) and _SERVER.fullmatch(v) is not None


DEFAULTS = dict(id="", name="", server="ws://127.0.0.1:8765", lang="fa", mode="dark", accent="#E11D2E",
                approve=True, view_only=False, history=True, allow_open=True, allow_files=True, allow_clip=True, text_scale=1.0, fps=10, quality=55, perm="", update_url="")
CHECK = dict(
    id=lambda v: isinstance(v, str) and re.fullmatch(r"\d{9}", v) is not None,
    name=lambda v: isinstance(v, str) and len(v) <= 32,
    server=valid_server,
    lang=lambda v: v in ("fa", "en"),
    mode=lambda v: v in ("dark", "light", "system"),
    accent=lambda v: isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v) is not None,
    fps=lambda v: v in (5, 10, 15, 30),
    quality=lambda v: v in (35, 55, 75),
    text_scale=lambda v: v in (1.0, 1.15, 1.3),
    perm=lambda v: isinstance(v, str) and len(v) < 2048,
    update_url=lambda v: isinstance(v, str) and len(v) < 300,
)


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


def validate_cfg(raw):
    raw = raw if isinstance(raw, dict) else {}
    cfg = {}
    for k, d in DEFAULTS.items():
        v = raw.get(k, d)
        ok = CHECK.get(k, lambda x, d=d: type(x) is type(d))
        cfg[k] = v if ok(v) else d
    return cfg


def load_cfg(path=None):
    path = path or CFG
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        raw = {}
    if isinstance(raw, dict) and raw.get("accent") == "#E91D5E":  # previous default (pink) -> current default (red)
        raw["accent"] = DEFAULTS["accent"]
    cfg = validate_cfg(raw)
    if not cfg["id"]:
        cfg["id"] = new_id()
        save_cfg(cfg, path)
    return cfg


def save_cfg(cfg, path=None):
    try:
        _write(path or CFG, cfg)
    except OSError:
        pass


def load_history():
    try:
        with open(HIST, encoding="utf-8") as f:
            h = json.load(f)
        return [x for x in h if isinstance(x, dict)][-100:] if isinstance(h, list) else []
    except (OSError, ValueError):
        return []


def add_history(cfg, ev, name):
    if cfg["history"]:
        try:
            _write(HIST, (load_history() + [{"t": time.strftime("%Y-%m-%d %H:%M"), "e": ev, "n": name}])[-100:])
        except OSError:
            pass


def clear_history():
    try:
        os.remove(HIST)
    except OSError:
        pass


def clean_name(v, default=""):
    return re.sub(r"[^\w .\-]", "", str(v))[:32].strip() or default


# ───────────────────────── Crypto ─────────────────────────
def derive(pw, did):
    """Password -> 256-bit PAKE secret (PBKDF2-HMAC-SHA256, 600k iterations, ID-bound salt)."""
    return PBKDF2HMAC(hashes.SHA256(), 32, b"rasadesk-v2:" + did.encode(), 600_000).derive(pw.encode())


def perm_set(cfg, pw, machine=False):
    """Store the permanent secret under Windows DPAPI: per user, or per machine (0x4) for the service."""
    cfg["perm"] = (base64.b64encode(_dpapi(C32.CryptProtectData, derive(pw, cfg["id"]), 0x4 if machine else 0)).decode()
                   if pw else "")


def perm_key(cfg):
    if not cfg["perm"]:
        return None
    try:
        k = _dpapi(C32.CryptUnprotectData, base64.b64decode(cfg["perm"]))
        return k if len(k) == 32 else None
    except Exception:
        return None


# PAKE (SPAKE2, Ed25519 group): the password never leaves the device and is never a verifier the
# relay could attack offline. A wrong guess gives the attacker exactly one try per attempt.
IDA = b"rasadesk-viewer"


def idb(did):
    return b"rasadesk-host:" + did.encode()


def pk(*parts):  # length-prefixed framing
    return b"".join(struct.pack(">H", len(p)) + p for p in parts)


def unpk(b, n):
    out, i = [], 0
    for _ in range(n):
        if i + 2 > len(b):
            raise ValueError("short")
        (n_,) = struct.unpack_from(">H", b, i)
        i += 2
        if i + n_ > len(b):
            raise ValueError("short")
        out.append(b[i:i + n_])
        i += n_
    if i != len(b):
        raise ValueError("trailing")
    return out


def transcript(a, b, mode=0):
    return hashlib.sha256(b"rasadesk-v4" + bytes([mode]) + pk(*a, *b)).digest()


def open_secret(did):
    """Public constant for approval-only connections (no password): the channel is encrypted but NOT
    authenticated by a secret, so both sides show a short verification code (SAS) derived from the key."""
    return hashlib.sha256(b"rasadesk-open:" + did.encode()).digest()


def sas_code(sk):
    n = int.from_bytes(HKDF(hashes.SHA256(), 4, None, b"rasadesk-sas").derive(sk), "big") % 1_000_000
    return f"{n:06d}"


PROMPT = {
    "fa": ("درخواست اتصال", "«{n}» می‌خواهد صفحه این سیستم را ببیند و آن را کنترل کند.",
           "\n\nکد تأیید: {s}\nفقط اگر همین کد را روی سیستم آن شخص هم می‌بینید اجازه دهید.", "اجازه می‌دهید؟"),
    "en": ("Connection request", "\"{n}\" wants to view and control this computer.",
           "\n\nVerification code: {s}\nAllow only if the other person sees the same code.", "Do you allow it?"),
}


def prompt_text(lang, name, sas=None):
    title, intro, sas_line, q = PROMPT[lang]
    return title, intro.format(n=name) + (sas_line.format(s=sas[:3] + " " + sas[3:]) if sas else "") + "\n\n" + q


def derive_keys(k, tr):
    """PAKE shared key -> (session key, viewer-confirm key, host-confirm key)."""
    o = HKDF(hashes.SHA256(), 96, tr, b"rasadesk-v3-keys").derive(k)
    return o[:32], o[32:64], o[64:]


def tag(k, tr):
    return hmac.new(k, tr, hashlib.sha256).digest()


class Chan:
    """AES-256-GCM channel: counter nonce, per-direction, strict replay/reorder rejection."""

    def __init__(s, key, tx, rx):
        s.a, s.tx, s.rx, s.n, s.last = AESGCM(key), tx, rx, 0, 0

    def seal(s, b):
        s.n += 1
        c = struct.pack(">Q", s.n)
        return c + s.a.encrypt(struct.pack(">I", s.tx) + c, b, None)

    def open(s, m):
        c = m[:8]
        n = struct.unpack(">Q", c)[0]
        if n <= s.last:
            raise ValueError("replay")
        b = s.a.decrypt(struct.pack(">I", s.rx) + c, m[8:], None)
        s.last = n
        return b


def _json(b):
    try:
        d = json.loads(b)
        return d if isinstance(d, dict) else {}
    except ValueError:
        return {}


_tl = threading.local()


# ───────────────────────── Files & clipboard (run inside an authenticated Chan) ─────────────────────────
CHUNK, MAX_FILE, CLIP_MAX = 48 * 1024, 4 * 2 ** 30, 256 * 1024
FT = {b"T", b"A", b"c", b"E", b"a", b"L", b"l", b"G"}
_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


def _j(o):
    return json.dumps(o, ensure_ascii=False).encode()


def safe_name(n):
    """Peer-supplied file name -> harmless local name (no paths, no reserved device names)."""
    n = _BAD.sub("_", re.split(r"[\\/]", str(n))[-1]).strip(" .")[:120] or "file"  # same result on every OS
    return "_" + n if n.split(".")[0].lower() in _RESERVED else n


def unique_path(d, name):
    base, ext = os.path.splitext(name)
    for i in range(1000):
        p = os.path.join(d, name if i == 0 else f"{base} ({i}){ext}")
        if not os.path.exists(p) and not os.path.exists(p + ".part"):
            return p
    raise OSError("no free file name")


def _commit(tmp, path):
    try:
        os.rename(tmp, path)  # never overwrites on Windows
        return path
    except FileExistsError:
        p = unique_path(os.path.dirname(path), os.path.basename(path))
        os.rename(tmp, p)
        return p


def _rm(p):
    try:
        os.remove(p)
    except OSError:
        pass


def _listdir(p, home):
    if not p:
        return {"p": "", "items": [[home, 0, True]] + [[f"{c}:\\", 0, True] for c in string.ascii_uppercase
                                                       if os.path.exists(f"{c}:\\")]}
    if "\x00" in p or len(p) > 1000:
        raise OSError("bad path")
    p, items = os.path.abspath(p), []
    with os.scandir(p) as it:
        for e in it:
            if len(items) >= 3000:
                break
            try:
                d = e.is_dir()
                items.append([e.name[:255], 0 if d else e.stat().st_size, d])
            except OSError:
                pass
    items.sort(key=lambda x: (not x[2], x[0].lower()))
    return {"p": p, "items": items}


class Files:
    """Chunked, SHA-256-verified, bidirectional file transfer + remote folder listing.
    put(bytes, prio) is the session's ordered writer. allow: callable (host) or None (viewer accepts only
    files it asked for). ctx: context manager used around every disk access (user impersonation in the service)."""

    def __init__(s, put, allow, dest, ctx, home, notify, serve=False):
        s.put, s.allow, s.dest, s.ctx, s.home, s.notify, s.serve = put, allow, dest, ctx, home, notify, serve
        s.rx, s.tx, s.nid, s.on_list, s.expect, s.bg = {}, {}, itertools.count(1), None, set(), set()

    async def io(s, fn, *a):
        def run():
            with s.ctx():
                return fn(*a)
        return await asyncio.to_thread(run)

    def spawn(s, coro):
        t = asyncio.create_task(coro)
        s.bg.add(t)
        t.add_done_callback(s.bg.discard)

    async def handle(s, d):
        t, body = d[:1], d[1:]
        try:
            if t == b"c":
                await s.chunk(body)
                return
            j = _json(body)
            if t == b"T":
                await s.offer(j)
            elif t == b"A":
                w = s.tx.get(j.get("id"))
                if w:
                    w["ok"] = j.get("ok") is True
                    w["ack"].set()
            elif t == b"E":
                await s.finish(j)
            elif t == b"a":
                w = s.tx.get(j.get("id"))
                if w:
                    w["good"] = j.get("ok") is True
                    w["res"].set()
            elif t == b"L" and s.serving():
                await s.list(j)
            elif t == b"G" and s.serving():
                p = j.get("p")
                if isinstance(p, str) and "\x00" not in p and len(p) < 1000:
                    s.spawn(s.send(os.path.abspath(p)))  # separate task: never block the ordered worker
            elif t == b"l":
                cb, s.on_list = s.on_list, None
                if cb:
                    cb(j)
        except Exception:
            pass  # a malformed peer message must never kill the session

    def serving(s):
        return bool(s.serve and s.allow and s.allow())

    def accepts(s, name):
        if s.allow:
            return bool(s.allow())
        k = name.lower()
        if k in s.expect:
            s.expect.discard(k)
            return True
        return False

    # ---- receiving ----
    def _open_rx(s, name):
        d = s.dest()
        os.makedirs(d, exist_ok=True)
        final = unique_path(d, name)
        tmp = final + ".part"
        return open(tmp, "xb"), tmp, final

    async def offer(s, j):
        i, name, size = j.get("id"), j.get("name"), j.get("size")
        ok = (isinstance(i, int) and isinstance(size, int) and isinstance(name, str)
              and 0 <= size <= MAX_FILE and i not in s.rx and len(s.rx) < 4)
        if ok:
            name = safe_name(name)
            ok = s.accepts(name)
        if ok:
            try:
                f, tmp, final = await s.io(s._open_rx, name)
            except OSError:
                ok = False
        if not ok:
            await s.put(b"A" + _j({"id": i, "ok": False}), 0)
            return
        s.rx[i] = dict(f=f, tmp=tmp, path=final, size=size, got=0, shown=0, h=hashlib.sha256(), name=name)
        await s.put(b"A" + _j({"id": i, "ok": True}), 0)
        s.notify("progress", name=name, done=0, total=size, dir="in")

    async def chunk(s, b):
        if len(b) < 4:
            return
        i = struct.unpack(">I", b[:4])[0]
        r = s.rx.get(i)
        if not r:
            return
        data = b[4:]
        r["got"] += len(data)
        if r["got"] > r["size"]:  # peer sends more than it announced
            await s.finish({"id": i, "abort": True})
            return
        r["h"].update(data)
        await s.io(r["f"].write, data)
        if r["got"] - r["shown"] >= 262144:
            r["shown"] = r["got"]
            s.notify("progress", name=r["name"], done=r["got"], total=r["size"], dir="in")

    async def finish(s, j):
        r = s.rx.pop(j.get("id"), None)
        if not r:
            return
        ok = False
        try:
            await s.io(r["f"].close)
            ok = (not j.get("abort") and r["got"] == r["size"]
                  and hmac.compare_digest(r["h"].hexdigest(), str(j.get("sha"))))
            if ok:
                r["path"] = await s.io(_commit, r["tmp"], r["path"])
        except OSError:
            ok = False
        if not ok:
            await s.io(_rm, r["tmp"])
        await s.put(b"a" + _j({"id": j.get("id"), "ok": ok}), 0)
        s.notify("received" if ok else "failed", name=r["name"], path=r["path"], total=r["size"])

    def cleanup(s):  # session ended: remove half-written files
        for r in s.rx.values():
            try:
                r["f"].close()
            except OSError:
                pass
            _rm(r["tmp"])
        s.rx.clear()

    # ---- sending ----
    async def send(s, path):
        name = os.path.basename(path)
        try:
            st = await s.io(os.stat, path)
            if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_FILE:
                raise OSError("not a regular file")
        except OSError:
            s.notify("failed", name=name, path="", total=0)
            return
        i = next(s.nid)
        w = s.tx[i] = dict(ack=asyncio.Event(), ok=False, res=asyncio.Event(), good=False)
        try:
            await s.put(b"T" + _j({"id": i, "name": name, "size": st.st_size}), 0)
            await asyncio.wait_for(w["ack"].wait(), 30)
            if not w["ok"]:
                raise OSError("refused")
            f, h, sent, shown = await s.io(open, path, "rb"), hashlib.sha256(), 0, 0
            try:
                while True:
                    data = await s.io(f.read, CHUNK)
                    if not data:
                        break
                    h.update(data)
                    sent += len(data)
                    await s.put(b"c" + struct.pack(">I", i) + data, 1)
                    if sent - shown >= 262144:
                        shown = sent
                        s.notify("progress", name=name, done=sent, total=st.st_size, dir="out")
            finally:
                await s.io(f.close)
            if sent != st.st_size:  # file changed while sending
                await s.put(b"E" + _j({"id": i, "abort": True}), 1)
                raise OSError("changed")
            await s.put(b"E" + _j({"id": i, "sha": h.hexdigest()}), 1)
            await asyncio.wait_for(w["res"].wait(), 120)
            s.notify("sent" if w["good"] else "failed", name=name, path=path, total=st.st_size)
        except (asyncio.TimeoutError, OSError):
            s.notify("failed", name=name, path=path, total=st.st_size)
        finally:
            s.tx.pop(i, None)

    # ---- remote browsing ----
    async def list(s, j):
        p, out = j.get("p"), {"p": "", "items": [], "err": ""}
        try:
            out.update(await s.io(_listdir, p if isinstance(p, str) else "", s.home()))
        except OSError:
            out["err"] = "denied"
        await s.put(b"l" + _j(out), 0)

    async def request(s, path):  # viewer: ask the host to send us a file
        s.expect.add(safe_name(path).lower())
        await s.put(b"G" + _j({"p": path}), 0)


class Clip:
    """Text-only clipboard sync. Never sends what was on the clipboard before the session began."""

    def __init__(s, send, enabled):
        s.send, s.enabled, s.last, s.run = send, enabled, "", True
        threading.Thread(target=s.poll, daemon=True).start()

    def poll(s):
        try:
            s.last = pyperclip.paste()
        except Exception:
            pass
        while s.run:
            time.sleep(0.6)
            if not s.enabled():
                continue
            try:
                t = pyperclip.paste()
            except Exception:
                continue
            if t and t != s.last and len(t.encode()) <= CLIP_MAX:
                s.last = t
                s.send(t)

    def apply(s, t):
        if s.enabled() and isinstance(t, str) and len(t.encode()) <= CLIP_MAX:
            s.last = t
            try:
                pyperclip.copy(t)
            except Exception:
                pass

    def stop(s):
        s.run = False


# ───────────────────────── Host (the shared computer) ─────────────────────────
class Host:
    """Handshake: H(mode,A..) -> S(B..) -> C(tags) -> K(tag) -> [encrypted] N(name) -> approval -> W/D.
    mode 0 = password (temporary / permanent slot), mode 1 = approval only (public secret + verification code)."""
    agent = False  # AgentHost (Windows service) overrides the hooks below

    def __init__(s, cfg, status, prompt, events=None):
        s.cfg, s.status, s.prompt, s.events = cfg, status, prompt, events
        s.pws, s.ws, s.loop, s.mon, s.hs, s.chan = {}, None, None, None, None, None
        s.stage, s.tok, s.live, s.lock, s.fails, s.deadline = 0, 0, False, 0.0, [], None
        s.kind, s.mode, s.peer, s.open_lock, s.denials, s.sas = "temp", 0, "", 0.0, [], None
        s.tasks, s.bg, s.out, s.seq, s.files, s.fq, s.clip = [], set(), None, None, None, None, None
        s.refresh_perm()

    # ---- platform hooks ----
    def can_prompt(s):
        return True

    def ask(s, title, text):
        return ask_allow(title, text)

    def home(s):
        return os.path.expanduser("~")

    def dest(s):
        return os.path.join(s.home(), "Downloads", "RasaDesk")

    def ctx(s):
        return contextlib.nullcontext()

    def attach(s):
        return None

    def sas_event(s):
        pass

    def ev(s, what, **kw):
        if s.events:
            try:
                s.events(what, **kw)
            except Exception:
                pass

    # ---- lifecycle ----
    def set_temp(s, pw):
        def work():
            s.pws["temp"] = derive(pw, s.cfg["id"])
        threading.Thread(target=work, daemon=True).start()

    def refresh_perm(s):
        k = perm_key(s.cfg)
        if k:
            s.pws["perm"] = k
        else:
            s.pws.pop("perm", None)

    def start(s):
        threading.Thread(target=lambda: asyncio.run(s.run()), daemon=True).start()

    def reconnect(s):
        if s.loop and s.ws:
            asyncio.run_coroutine_threadsafe(s.ws.close(), s.loop)

    kick = reconnect  # dropping our relay link ends the session at once

    def spawn(s, coro):
        t = asyncio.create_task(coro)
        s.bg.add(t)
        t.add_done_callback(s.bg.discard)

    async def run(s):
        s.loop = asyncio.get_running_loop()
        while True:
            try:
                async with websockets.connect(s.cfg["server"], max_size=2 ** 22, open_timeout=8) as ws:
                    s.ws = ws
                    await ws.send(json.dumps({"t": "reg", "id": s.cfg["id"]}))
                    s.status("ready")
                    await s.serve(ws)
            except Exception:
                pass
            s.ws = None
            s.end()
            s.status("offline")
            await asyncio.sleep(4)

    def end(s):
        was = s.live
        s.live, s.chan, s.hs, s.stage, s.deadline = False, None, None, 0, None
        s.tok += 1
        for t in s.tasks:
            t.cancel()
        s.tasks = []
        if s.clip:
            s.clip.stop()
            s.clip = None
        if s.files:
            s.files.cleanup()
            s.files = None
        if was:  # never leave a key/button stuck down after a session
            try:
                for b in ("left", "right", "middle"):
                    pyautogui.mouseUp(button=b)
                for k in ("shift", "ctrl", "alt", "win"):
                    pyautogui.keyUp(k)
            except Exception:
                pass
            s.ev("end")

    async def watch(s, ws):  # a stalled or abandoned handshake must not occupy the host forever
        while True:
            await asyncio.sleep(1)
            if s.deadline and time.time() > s.deadline:
                s.deadline = None
                await ws.close()
                return

    # ---- receive loop ----
    async def serve(s, ws):
        dog = asyncio.create_task(s.watch(ws))
        try:
            async for m in ws:
                if isinstance(m, str):
                    if _json(m).get("t") == "bye":
                        s.end()
                        s.status("ready")
                    continue
                t = m[:1]
                if s.stage == 0 and t == b"H":
                    s.stage = -1
                    s.spawn(s.on_h(ws, m))
                elif s.stage == 1 and t == b"C":
                    s.stage = -1
                    s.spawn(s.on_c(ws, m))
                elif s.chan and s.stage >= 2:
                    try:
                        d = s.chan.open(m)
                    except Exception:
                        continue
                    t = d[:1]
                    if t == b"N" and s.stage == 2:
                        s.stage = 3
                        s.spawn(s.on_n(ws, d))
                    elif s.stage == 4:
                        if t == b"I":
                            s.inp(_json(d[1:]))
                        elif t == b"B" and s.clip:
                            s.spawn(asyncio.to_thread(s.clip.apply, d[1:].decode("utf-8", "replace")))
                        elif t in FT and s.fq is not None:
                            await s.fq.put(d)
        finally:
            dog.cancel()

    # ---- handshake ----
    async def on_h(s, ws, m):
        tok = s.tok
        try:
            now, mode = time.time(), m[1]
            if now < s.lock or mode not in (0, 1):
                s.stage = 0
                return
            if mode == 1:  # approval-only request
                if not s.cfg["allow_open"] or now < s.open_lock:
                    s.stage = 0
                    await ws.send(b"X\x01")
                    return
                if not s.can_prompt():  # nobody at the keyboard (lock screen / logon screen)
                    s.stage = 0
                    await ws.send(b"X\x02")
                    return
            a = unpk(m[2:], 2 - mode)
            if any(not 0 < len(x) <= 128 for x in a):
                raise ValueError("bad message")
            pws = ([s.pws.get("temp") or os.urandom(32), s.pws.get("perm") or os.urandom(32)] if mode == 0
                   else [open_secret(s.cfg["id"])])  # random = unused slot
            did = s.cfg["id"]

            def work():
                ins = [SPAKE2_B(p, idA=IDA, idB=idb(did)) for p in pws]
                b = [i.start() for i in ins]
                return b, [i.finish(x) for i, x in zip(ins, a)]
            b, ks = await asyncio.to_thread(work)
            if tok != s.tok:
                return
            s.mode, s.hs, s.deadline = mode, (ks, transcript(a, b, mode)), time.time() + 20
            await ws.send(b"S" + pk(*b))
            s.stage = 1
        except Exception:
            if tok == s.tok:
                s.stage, s.hs = 0, None

    async def on_c(s, ws, m):
        tok = s.tok
        try:
            ks, tr = s.hs
            t = unpk(m[1:], len(ks))
            s.hs, hit, now = None, None, time.time()
            for i, k in enumerate(ks):  # evaluate every slot (no early exit)
                sk, ckv, ckh = derive_keys(k, tr)
                if hmac.compare_digest(t[i], tag(ckv, tr)) and hit is None:
                    hit = (i, sk, ckh)
            if tok != s.tok:
                return
            if hit is None:  # wrong password: stay silent, count, lock out
                s.fails = [x for x in s.fails if now - x < 60] + [now]
                if len(s.fails) >= 5:
                    s.lock, s.fails = now + 300, []
                    add_history(s.cfg, "locked", "")
                s.stage = 0
                return
            s.fails = []
            s.kind = "open" if s.mode == 1 else ("perm" if hit[0] == 1 else "temp")
            s.chan, s.stage, s.deadline = Chan(hit[1], 2, 1), 2, time.time() + 20
            s.sas = sas_code(hit[1]) if s.mode == 1 else None
            await ws.send(b"K" + tag(hit[2], tr))  # proves to the viewer that we know the secret too
        except Exception:
            if tok == s.tok:
                s.stage, s.chan, s.hs = 0, None, None

    async def on_n(s, ws, d):
        tok, ch = s.tok, s.chan
        try:
            name = clean_name(_json(d[1:]).get("name"), "?")
            s.deadline = time.time() + 95
            auto = s.kind == "perm" and not s.cfg["approve"]
            reason = 0  # 0 = person said no, 2 = nobody there to ask
            if auto:
                allowed = True
            elif not s.can_prompt():
                allowed, reason = False, 2
            else:
                allowed = await asyncio.to_thread(s.ask, *s.prompt(name, s.sas))
            if tok != s.tok:  # viewer left while the dialog was open
                return
            if not allowed:
                add_history(s.cfg, "denied", name)
                if s.kind == "open":  # anti-spam: repeated refusals pause approval requests
                    now = time.time()
                    s.denials = [x for x in s.denials if now - x < 300] + [now]
                    if len(s.denials) >= 3:
                        s.open_lock, s.denials = now + 600, []
                s.stage, s.chan, s.deadline = 0, None, None
                await ws.send(ch.seal(b"D" + bytes([reason])))
                return
            add_history(s.cfg, "accepted", name)
            s.peer = name
            caps = {"agent": s.agent, "files": s.cfg["allow_files"], "clip": s.cfg["allow_clip"],
                    "view": s.cfg["view_only"]}
            s.begin(ws, ch, caps)
            s.status("sharing")
            s.ev("live", name=name)
        except Exception:
            if tok == s.tok:
                s.end()

    def begin(s, ws, ch, caps):
        loop = asyncio.get_running_loop()
        s.out, s.seq, s.fq = asyncio.PriorityQueue(64), itertools.count(), asyncio.Queue(64)
        s.out.put_nowait((-1, next(s.seq), b"W" + _j(caps)))  # first message of the session
        s.files = Files(s.put, lambda: s.cfg["allow_files"], s.dest, s.ctx, s.home,
                        lambda k, **kw: s.ev("file", kind=k, **kw), serve=True)
        s.clip = Clip(lambda t: loop.call_soon_threadsafe(s.clip_out, t), lambda: s.live and s.cfg["allow_clip"])
        s.live, s.stage, s.deadline = True, 4, None
        s.tasks = [asyncio.create_task(x) for x in (s.sender(ws, ch), s.stream(), s.fworker())]

    def clip_out(s, t):
        s.spawn(s.put(b"B" + t.encode(), 0))

    async def put(s, data, prio=1):
        await s.out.put((prio, next(s.seq), data))

    async def sender(s, ws, ch):  # the ONLY writer: keeps counters and wire order identical
        try:
            while True:
                _, _, d = await s.out.get()
                await ws.send(ch.seal(d))
        except Exception:
            pass

    async def fworker(s):  # file messages are processed strictly in order
        while True:
            await s.files.handle(await s.fq.get())

    # ---- screen ----
    def grab(s, last):
        tag_ = s.attach()
        sct = getattr(_tl, "s", None)
        if sct is None or getattr(_tl, "tag", None) != tag_:  # desktop changed -> fresh capture handles
            if sct:
                sct.close()
            sct = _tl.s = mss.mss()
            _tl.tag = tag_
        mon = sct.monitors[1]
        shot = sct.grab(mon)
        s.mon = dict(mon)
        crc = zlib.crc32(shot.raw)
        if crc == last:
            return None
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        if img.width > MAXW:
            img = img.resize((MAXW, img.height * MAXW // img.width), Image.Resampling.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=s.cfg["quality"])
        return buf.getvalue(), crc

    async def stream(s):
        last = 0
        try:
            while s.live:
                t0 = time.time()
                r = await asyncio.to_thread(s.grab, last)
                if r:
                    last = r[1]
                    await s.put(b"F" + r[0], 1)
                await asyncio.sleep(max(0.005, 1 / s.cfg["fps"] - (time.time() - t0)))
        except Exception:
            pass

    def inp(s, e):
        """Remote input: every field is validated; unknown keys are ignored."""
        m = s.mon
        if not (s.live and m) or s.cfg["view_only"] or not e:
            return
        k = e.get("k")
        try:
            s.attach()
            if k in ("move", "down", "up"):
                x, y = float(e["x"]), float(e["y"])
                b = e.get("b", "left")
                if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0) or b not in ("left", "middle", "right"):
                    return
                px, py = m["left"] + int(x * (m["width"] - 1)), m["top"] + int(y * (m["height"] - 1))
                if k == "move":
                    pyautogui.moveTo(px, py)
                elif k == "down":
                    pyautogui.mouseDown(px, py, button=b)
                else:
                    pyautogui.mouseUp(px, py, button=b)
            elif k == "scroll":
                pyautogui.scroll(max(-1200, min(1200, int(e["d"]))))
            elif k in ("kd", "ku"):
                n = e.get("n")
                if isinstance(n, str) and n in pyautogui.KEYBOARD_KEYS:
                    (pyautogui.keyDown if k == "kd" else pyautogui.keyUp)(n)
            elif k == "sas":  # Ctrl+Alt+Del (only the Windows service can send it)
                s.sas_event()
        except Exception:
            pass


# ───────────────────────── Viewer (the controlling computer) ─────────────────────────
KEYMAP = {"return": "enter", "escape": "esc", "prior": "pageup", "next": "pagedown", "control": "ctrl",
          "super": "win", "caps_lock": "capslock", "num_lock": "numlock", "scroll_lock": "scrolllock"}


class Viewer:
    """pw empty -> approval-only request (mode 1); otherwise password (mode 0).
    onevt(what, **kw) is always called on the UI thread: state / error / file / closed."""

    def __init__(s, root, cfg, target, pw, onevt, ui=None):
        s._state(root, cfg, target, pw, onevt, ui)
        threading.Thread(target=lambda: asyncio.run(s.run()), daemon=True).start()

    def _state(s, root, cfg, target, pw, onevt, ui):
        s.root, s.cfg, s.target, s.pw, s.onevt, s.ui = root, cfg, target, pw, onevt, ui
        s.name = clean_name(cfg["name"], socket.gethostname())
        s.ws = s.loop = s.out = s.seq = s.frame = s.img = s.win = s.lbl = s.files = s.clip = None
        s.caps, s.alive, s.ready, s.full = {}, True, False, False

    def home(s):
        return os.path.expanduser("~")

    def emit(s, what, **kw):
        if s.root:
            s.root.after(0, lambda: s.onevt(what, **kw))
        else:
            s.onevt(what, **kw)

    # ---- window ----
    def open_window(s):
        if not s.alive or s.win:
            return
        s.win = tk.Toplevel(s.root)
        s.win.title(f"RasaDesk - {s.target}")
        s.win.geometry("1180x760")
        s.win.configure(bg="#000000")
        if s.ui:
            s.ui(s.win, s)  # UI adds its toolbar (packed at the top)
        s.lbl = tk.Label(s.win, bg="#000000", bd=0)
        s.lbl.pack(expand=True)
        s.lbl.bind("<Motion>", lambda e: s.mouse("move", e))
        s.lbl.bind("<ButtonPress>", lambda e: s.mouse("down", e))
        s.lbl.bind("<ButtonRelease>", lambda e: s.mouse("up", e))
        s.lbl.bind("<MouseWheel>", lambda e: s.send({"k": "scroll", "d": e.delta}))
        s.win.bind("<KeyPress>", lambda e: s.send({"k": "kd", "n": s.kn(e)}))
        s.win.bind("<KeyRelease>", lambda e: s.send({"k": "ku", "n": s.kn(e)}))
        s.win.protocol("WM_DELETE_WINDOW", s.close)
        s.win.focus_force()
        s.refresh()

    def fullscreen(s):
        s.full = not s.full
        s.win.attributes("-fullscreen", s.full)

    @staticmethod
    def kn(e):
        if len(e.keysym) == 1:
            return e.keysym.lower()
        n = e.keysym.lower().replace("_l", "").replace("_r", "")
        return KEYMAP.get(n, n)

    def mouse(s, kind, e):
        w, h = s.lbl.winfo_width(), s.lbl.winfo_height()
        if w < 2 or h < 2:
            return
        d = {"k": kind, "x": min(1, max(0, e.x / w)), "y": min(1, max(0, e.y / h))}
        if kind != "move":
            d["b"] = {1: "left", 2: "middle", 3: "right"}.get(e.num, "left")
        s.send(d)

    def send(s, d):  # input events: lowest priority number, dropped if the queue is full
        if s.ready and s.loop:
            try:
                s.loop.call_soon_threadsafe(s._put, b"I" + json.dumps(d).encode())
            except RuntimeError:
                pass

    def _put(s, b):
        try:
            s.out.put_nowait((0, next(s.seq), b))
        except asyncio.QueueFull:
            pass

    async def put(s, data, prio=1):
        await s.out.put((prio, next(s.seq), data))

    def ctrl_alt_del(s):
        s.send({"k": "sas"})

    # ---- files (called from the UI thread) ----
    def _run(s, coro):
        if s.loop and s.ready:
            asyncio.run_coroutine_threadsafe(coro, s.loop)

    def send_files(s, paths):
        async def many():
            for p in paths:
                await s.files.send(p)
        s._run(many())

    def browse(s, path):  # the answer arrives as onevt("list", data=...)
        s.files.on_list = lambda j: s.emit("list", data=j)
        s._run(s.files.put(b"L" + _j({"p": path}), 0))

    def download(s, path):
        s._run(s.files.request(path))

    # ---- network ----
    async def run(s):
        s.loop, s.out, s.seq = asyncio.get_running_loop(), asyncio.PriorityQueue(64), itertools.count()
        try:
            code = await s.go()
        except asyncio.TimeoutError:
            code = "timeout"
        except websockets.ConnectionClosed:
            code = "closed"
        except Exception:
            code = "neterr"
        if s.alive and code:
            s.emit("error", code=code)
            s.root and s.root.after(0, s.close)

    async def expect(s, ws, typ, t):
        """Next binary message whose type byte is in `typ` (None = any). None result = relay closed the pairing."""
        loop = asyncio.get_running_loop()
        end = loop.time() + t
        typs = (typ,) if isinstance(typ, bytes) else typ
        while True:
            m = await asyncio.wait_for(ws.recv(), max(0.01, end - loop.time()))
            if isinstance(m, str):
                return None
            if typs is None or m[:1] in typs:
                return m

    async def go(s):
        mode = 0 if s.pw else 1
        secret = await asyncio.to_thread(derive, s.pw, s.target) if mode == 0 else open_secret(s.target)
        if not s.alive:
            return None
        s.emit("state", code="connecting")
        async with websockets.connect(s.cfg["server"], max_size=2 ** 22, open_timeout=8) as ws:
            s.ws = ws
            await ws.send(json.dumps({"t": "conn", "target": s.target}))
            if _json(await asyncio.wait_for(ws.recv(), 8)).get("t") != "ok":
                return "notfound"
            n = 2 - mode  # password mode: one SPAKE2 run per host slot (temporary / permanent)

            def begin():
                ins = [SPAKE2_A(secret, idA=IDA, idB=idb(s.target)) for _ in range(n)]
                return ins, [i.start() for i in ins]
            ins, a = await asyncio.to_thread(begin)
            await ws.send(b"H" + bytes([mode]) + pk(*a))
            m = await s.expect(ws, (b"S", b"X"), 12)
            if m is None:
                return "closed"
            if m[:1] == b"X":
                return "noapprover" if m[1:2] == b"\x02" else "noopen"
            b = unpk(m[1:], n)

            def finish():
                out = []
                for i, x in zip(ins, b):
                    try:
                        out.append(i.finish(x))
                    except Exception:
                        out.append(os.urandom(32))
                return out
            ks = await asyncio.to_thread(finish)
            tr = transcript(a, b, mode)
            kk = [derive_keys(k, tr) for k in ks]
            await ws.send(b"C" + pk(*[tag(x[1], tr) for x in kk]))
            m = await s.expect(ws, b"K", 12)  # silence = wrong password or temporary lockout
            if m is None:
                return "closed"
            hit = [x for x in kk if hmac.compare_digest(m[1:], tag(x[2], tr))]
            if not hit:
                return "authfail"
            ch = Chan(hit[0][0], 1, 2)
            await ws.send(ch.seal(b"N" + json.dumps({"name": s.name}).encode()))
            s.emit("state", code="approval", sas=sas_code(hit[0][0]) if mode == 1 else None)
            while True:  # waiting for the person at the host to approve
                m = await s.expect(ws, None, 95)
                if m is None:
                    return "closed"
                try:
                    d = ch.open(m)
                except Exception:
                    continue
                if d[:1] == b"D":
                    return "noapprover" if d[1:2] == b"\x02" else "denied"
                if d[:1] == b"W":
                    s.caps = _json(d[1:])
                    break
            fq = asyncio.Queue(64)
            s.files = Files(s.put, None, lambda: os.path.join(s.home(), "Downloads", "RasaDesk"),
                            contextlib.nullcontext, s.home, lambda k, **kw: s.emit("file", kind=k, **kw))
            loop = asyncio.get_running_loop()
            s.clip = Clip(lambda t: loop.call_soon_threadsafe(lambda: s.spawn_put(b"B" + t.encode())),
                          lambda: s.ready and s.cfg["allow_clip"] and s.caps.get("clip", False))
            s.ready = True
            s.emit("connected")
            if s.root:
                s.root.after(0, s.open_window)
            tasks = [asyncio.create_task(s.sender(ws, ch)), asyncio.create_task(s.fworker(fq))]
            try:
                async for m in ws:
                    if isinstance(m, str):
                        break
                    try:
                        d = ch.open(m)
                    except Exception:
                        continue
                    t = d[:1]
                    if t == b"F":
                        s.frame = d[1:]
                    elif t == b"B" and s.clip:
                        asyncio.create_task(asyncio.to_thread(s.clip.apply, d[1:].decode("utf-8", "replace")))
                    elif t in FT:
                        await fq.put(d)
            finally:
                s.ready = False
                for t in tasks:
                    t.cancel()
                s.clip.stop()
                s.files.cleanup()
        return "closed"

    def spawn_put(s, b):
        asyncio.create_task(s.put(b, 0))

    async def sender(s, ws, ch):
        try:
            while True:
                _, _, d = await s.out.get()
                await ws.send(ch.seal(d))
        except Exception:
            pass

    async def fworker(s, fq):
        while True:
            await s.files.handle(await fq.get())

    def refresh(s):
        if not s.alive or not s.win:
            return
        if s.frame:
            f, s.frame = s.frame, None
            try:
                img = Image.open(io.BytesIO(f))
                w, h = max(s.win.winfo_width(), 100), max(s.win.winfo_height() - 44, 100)
                k = min(w / img.width, h / img.height)
                if abs(k - 1) > 0.01:
                    img = img.resize((max(1, int(img.width * k)), max(1, int(img.height * k))),
                                     Image.Resampling.BILINEAR)
                s.img = ImageTk.PhotoImage(img)
                s.lbl.config(image=s.img)
            except Exception:
                pass
        s.root.after(33, s.refresh)

    def close(s):
        if not s.alive:
            return
        s.alive = False
        if s.win:
            try:
                s.win.destroy()
            except tk.TclError:
                pass
        if s.ws and s.loop:
            try:
                asyncio.run_coroutine_threadsafe(s.ws.close(), s.loop)
            except RuntimeError:
                pass
