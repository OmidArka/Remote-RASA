"""RasaDesk Windows service + session agent (UAC / lock-screen / logon-screen support)  |  Amn Negar Rasa

  RasaDeskService (LocalSystem, session 0)
      └─ spawns ─> RasaDesk.exe --agent   (SYSTEM, inside the active console session)

The agent is the normal Host engine with four differences:
  1. it follows the *input desktop* (Default / Winlogon / UAC secure desktop) for capture and input,
  2. file access happens as the logged-on user (impersonation), never as SYSTEM,
  3. approval prompts are shown only on the user's Default desktop (a remote person can never click them
     on the lock screen) and approval-only requests are refused when nobody is there,
  4. Ctrl+Alt+Del is relayed to the service, which is the only process allowed to call SendSAS.
Secrets live in %ProgramData%\\RasaDesk\\service.json (SYSTEM + Administrators only). Only non-secret status is
published in the "pub" sub-folder so the normal app can show it.
"""
import asyncio, contextlib, ctypes, json, os, re, subprocess, sys, threading, time
import ctypes.wintypes as wt

import core

SVC, DISPLAY = "RasaDeskService", "RasaDesk Service"
PD = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "RasaDesk")
PUB = os.path.join(PD, "pub")
CFG = os.path.join(PD, "service.json")
PUBLIC, LOG = os.path.join(PUB, "public.json"), os.path.join(PUB, "service.log")
SAS_EVENT = "Global\\RasaDeskSAS"
NOWIN = 0x08000000  # CREATE_NO_WINDOW


def log(msg):  # never log secrets
    try:
        os.makedirs(PUB, exist_ok=True)
        if os.path.exists(LOG) and os.path.getsize(LOG) > 200_000:
            os.replace(LOG, LOG + ".1")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + str(msg) + "\n")
    except OSError:
        pass


# ───────────────────────── desktop helpers (agent) ─────────────────────────
_u = None


def u32():
    global _u
    if _u is None:
        _u = ctypes.WinDLL("user32", use_last_error=True)
        _u.OpenInputDesktop.restype, _u.OpenInputDesktop.argtypes = wt.HANDLE, [wt.DWORD, wt.BOOL, wt.DWORD]
        _u.OpenDesktopW.restype, _u.OpenDesktopW.argtypes = wt.HANDLE, [wt.LPCWSTR, wt.DWORD, wt.BOOL, wt.DWORD]
        _u.SetThreadDesktop.restype, _u.SetThreadDesktop.argtypes = wt.BOOL, [wt.HANDLE]
        _u.CloseDesktop.restype, _u.CloseDesktop.argtypes = wt.BOOL, [wt.HANDLE]
        _u.GetUserObjectInformationW.restype = wt.BOOL
        _u.GetUserObjectInformationW.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD,
                                                 ctypes.POINTER(wt.DWORD)]
    return _u


def desktop_name(h):
    buf, need = ctypes.create_unicode_buffer(256), wt.DWORD()
    return buf.value if u32().GetUserObjectInformationW(h, 2, buf, ctypes.sizeof(buf), ctypes.byref(need)) else ""


def input_desktop_name():
    h = u32().OpenInputDesktop(0, False, 0x0001)  # DESKTOP_READOBJECTS
    if not h:
        return ""
    try:
        return desktop_name(h)
    finally:
        u32().CloseDesktop(h)


def user_token():
    import win32ts
    sid = win32ts.WTSGetActiveConsoleSessionId()
    if sid == 0xFFFFFFFF:
        raise OSError("no console session")
    try:
        return win32ts.WTSQueryUserToken(sid)
    except Exception as e:  # logon screen: nobody is logged on
        raise OSError("no user logged on") from e


class AgentHost(core.Host):
    agent = True

    def __init__(s, *a, **k):
        super().__init__(*a, **k)
        s.tl = threading.local()

    def attach(s):
        """Make the calling thread use the current input desktop; returns its name."""
        u = u32()
        h = u.OpenInputDesktop(0, False, 0x10000000)  # GENERIC_ALL
        if not h:
            return getattr(s.tl, "name", None)
        name = desktop_name(h)
        if name == getattr(s.tl, "name", None):
            u.CloseDesktop(h)
        elif u.SetThreadDesktop(h):
            old = getattr(s.tl, "h", None)
            s.tl.name, s.tl.h = name, h
            if old:
                u.CloseDesktop(old)
        else:
            u.CloseDesktop(h)
        return getattr(s.tl, "name", None)

    def can_prompt(s):
        return input_desktop_name() == "Default"

    def ask(s, title, text):  # always on the user's own desktop
        u = u32()
        h = u.OpenDesktopW("Default", 0, False, 0x10000000)
        if h and u.SetThreadDesktop(h):
            old = getattr(s.tl, "h", None)
            s.tl.name, s.tl.h = "Default", h
            if old:
                u.CloseDesktop(old)
        return core.ask_allow(title, text)

    @contextlib.contextmanager
    def ctx(s):
        import win32security
        tok = user_token()
        try:
            try:
                win32security.ImpersonateLoggedOnUser(tok)
            except Exception as e:
                raise OSError("cannot impersonate") from e
            try:
                yield
            finally:
                win32security.RevertToSelf()
        finally:
            tok.Close()

    def home(s):
        import win32profile
        tok = user_token()
        try:
            return win32profile.GetUserProfileDirectory(tok)
        except Exception as e:
            raise OSError("no profile") from e
        finally:
            tok.Close()

    def sas_event(s):
        try:
            import win32event
            h = win32event.OpenEvent(0x0002, False, SAS_EVENT)  # EVENT_MODIFY_STATE
            win32event.SetEvent(h)
            h.Close()
        except Exception as e:
            log(f"SAS request failed: {e}")


def run_agent():
    try:
        core.HIST = os.path.join(PD, "history.json")
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass
        if not os.path.exists(CFG):
            log("agent: no service configuration, exiting")
            return
        cfg = core.load_cfg(CFG)

        def status(code):
            try:
                core._write(PUBLIC, {"id": cfg["id"], "state": code, "t": int(time.time())})
            except OSError:
                pass
        host = AgentHost(cfg, status, lambda name, sas: core.prompt_text(cfg["lang"], name, sas))
        log("agent started")
        asyncio.run(host.run())
    except Exception as e:
        log(f"agent crashed: {e!r}")


# ───────────────────────── the service itself ─────────────────────────
def run_service():
    import servicemanager, win32api, win32event, win32process, win32profile, win32security, win32service
    import win32serviceutil, win32ts

    class Svc(win32serviceutil.ServiceFramework):
        _svc_name_, _svc_display_name_ = SVC, DISPLAY

        def __init__(self, args):
            super().__init__(args)
            self.stop = win32event.CreateEvent(None, 0, 0, None)
            self.proc, self.sid, self.retry = None, None, 0.0

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self.stop)

        def SvcDoRun(self):
            self.ReportServiceStatus(win32service.SERVICE_RUNNING)
            log("service running")
            sas = win32event.CreateEvent(None, 0, 0, SAS_EVENT)
            try:
                while True:
                    r = win32event.WaitForMultipleObjects([self.stop, sas], False, 2000)
                    if r == win32event.WAIT_OBJECT_0:
                        break
                    if r == win32event.WAIT_OBJECT_0 + 1:
                        self.send_sas()
                    else:
                        self.tick()
            except Exception as e:
                log(f"service loop error: {e!r}")
            finally:
                self.kill()
                log("service stopped")

        def send_sas(self):
            try:
                ctypes.WinDLL("sas").SendSAS(0)
            except Exception as e:
                log(f"SendSAS failed: {e}")

        def alive(self):
            return self.proc is not None and win32event.WaitForSingleObject(self.proc, 0) == win32event.WAIT_TIMEOUT

        def kill(self):
            if self.proc is not None:
                try:
                    if self.alive():
                        win32process.TerminateProcess(self.proc, 0)
                    self.proc.Close()
                except Exception:
                    pass
            self.proc, self.sid = None, None

        def tick(self):
            sid = win32ts.WTSGetActiveConsoleSessionId()
            if sid == 0xFFFFFFFF or not os.path.exists(CFG):
                self.kill()
                return
            if self.alive() and sid == self.sid:
                return
            if time.time() < self.retry:
                return
            self.kill()
            self.retry = time.time() + 5  # back-off if the agent keeps dying
            try:
                self.spawn(sid)
            except Exception as e:
                log(f"cannot start agent in session {sid}: {e!r}")

        def spawn(self, sid):
            exe = sys.executable
            tok = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32security.TOKEN_ALL_ACCESS)
            dup = win32security.DuplicateTokenEx(tok, win32security.SecurityImpersonation,
                                                 win32security.TOKEN_ALL_ACCESS, win32security.TokenPrimary)
            win32security.SetTokenInformation(dup, win32security.TokenSessionId, sid)
            env = win32profile.CreateEnvironmentBlock(dup, False)
            si = win32process.STARTUPINFO()
            si.lpDesktop = "winsta0\\default"
            hp, ht, pid, _ = win32process.CreateProcessAsUser(
                dup, exe, f'"{exe}" --agent', None, None, False, 0x400 | NOWIN, env, os.path.dirname(exe), si)
            ht.Close()
            self.proc, self.sid = hp, sid
            log(f"agent started in session {sid} (pid {pid})")

    servicemanager.Initialize()
    servicemanager.PrepareToHostSingle(Svc)
    servicemanager.StartServiceCtrlDispatcher()


# ───────────────────────── management (used by the normal app) ─────────────────────────
def state():
    """none | stopped | running | other | unavailable"""
    try:
        import win32service
    except ImportError:
        return "unavailable"
    try:
        scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)
        try:
            hs = win32service.OpenService(scm, SVC, win32service.SERVICE_QUERY_STATUS)
            code = win32service.QueryServiceStatus(hs)[1]
            win32service.CloseServiceHandle(hs)
        finally:
            win32service.CloseServiceHandle(scm)
        return {win32service.SERVICE_RUNNING: "running", win32service.SERVICE_STOPPED: "stopped"}.get(code, "other")
    except Exception as e:
        return "none" if getattr(e, "winerror", None) == 1060 else "unavailable"


def public():
    try:
        with open(PUBLIC, encoding="utf-8") as f:
            j = json.load(f)
        if isinstance(j, dict) and re.fullmatch(r"\d{9}", str(j.get("id", ""))):
            return {"id": j["id"], "state": j.get("state") if j.get("state") in ("ready", "sharing", "offline") else "offline"}
    except (OSError, ValueError):
        pass
    return {}


def open_log():
    try:
        os.startfile(LOG)
    except OSError:
        pass


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def protected_exe():
    """The service binary must live where standard users cannot replace it (Program Files)."""
    if not getattr(sys, "frozen", False):
        return False
    exe = os.path.realpath(sys.executable).lower()
    roots = [os.environ.get(k, "") for k in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432")]
    return any(r and exe.startswith(os.path.realpath(r).lower() + "\\") for r in roots)


def launch_elevated(arg):
    if not getattr(sys, "frozen", False):
        return False
    return ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, arg, None, 1) > 32


def _acl(path, grants, inherit=False):
    args = ["icacls", path] + ([] if inherit else ["/inheritance:r"]) + ["/grant:r"] + grants
    subprocess.run(args, check=True, capture_output=True, creationflags=NOWIN)


ADMINS = ["*S-1-5-18:(OI)(CI)F", "*S-1-5-32-544:(OI)(CI)F"]  # SYSTEM, Administrators


def setup_defaults(user_cfg):
    base = core.load_cfg(CFG) if os.path.exists(CFG) else dict(core.DEFAULTS, id=core.new_id(), approve=False,
                                                              server=user_cfg["server"], lang=user_cfg["lang"])
    return {k: base[k] for k in ("id", "server", "approve", "allow_open", "allow_files", "allow_clip", "view_only",
                                 "lang", "fps", "quality", "perm")}


def install(cfg_in, password):
    """Administrator only. Writes the protected service config, registers and (re)starts the service."""
    if not is_admin():
        raise PermissionError("Administrator rights are required")
    if not protected_exe():
        raise PermissionError("Install RasaDesk with the installer (Program Files) before installing the service")
    import pywintypes, win32service
    os.makedirs(PUB, exist_ok=True)
    _acl(PD, ADMINS + ["*S-1-5-32-545:RX"])  # Users: list/traverse this folder only, no inheritance to files
    _acl(PUB, ADMINS + ["*S-1-5-32-545:(OI)(CI)RX"])  # public, non-secret status + log
    old = core.load_cfg(CFG) if os.path.exists(CFG) else None
    cfg = core.validate_cfg({**(old or core.DEFAULTS),
                             **{k: v for k, v in cfg_in.items() if k not in ("id", "perm")},
                             "id": (old or {}).get("id") or cfg_in.get("id") or core.new_id(),
                             "perm": (old or {}).get("perm", "")})
    if password:
        core.perm_set(cfg, password, machine=True)
    if not cfg["perm"] and not cfg["allow_open"]:
        raise ValueError("no way to connect")
    core.save_cfg(cfg, CFG)  # inherits only SYSTEM + Administrators from the folder
    _acl(CFG, ["*S-1-5-18:F", "*S-1-5-32-544:F"])
    exe = sys.executable
    cmd = f'"{exe}" --service'
    scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ALL_ACCESS)
    try:
        try:
            hs = win32service.OpenService(scm, SVC, win32service.SERVICE_ALL_ACCESS)
            win32service.ChangeServiceConfig(hs, win32service.SERVICE_NO_CHANGE, win32service.SERVICE_AUTO_START,
                                             win32service.SERVICE_NO_CHANGE, cmd, None, 0, None, None, None, DISPLAY)
        except pywintypes.error as e:
            if e.winerror != 1060:
                raise
            hs = win32service.CreateService(scm, SVC, DISPLAY, win32service.SERVICE_ALL_ACCESS,
                                            win32service.SERVICE_WIN32_OWN_PROCESS, win32service.SERVICE_AUTO_START,
                                            win32service.SERVICE_ERROR_NORMAL, cmd, None, 0, None, None, None)
        win32service.ChangeServiceConfig2(hs, win32service.SERVICE_CONFIG_DESCRIPTION,
                                          "RasaDesk unattended remote access (Amn Negar Rasa)")
        win32service.ChangeServiceConfig2(hs, win32service.SERVICE_CONFIG_FAILURE_ACTIONS, {
            "ResetPeriod": 86400, "RebootMsg": "", "Command": "",
            "Actions": [(win32service.SC_ACTION_RESTART, 5000)] * 3})
        _stop(hs)
        win32service.StartService(hs, None)
        win32service.CloseServiceHandle(hs)
    finally:
        win32service.CloseServiceHandle(scm)
    log("service installed / updated")


def _stop(hs):
    import win32service
    if win32service.QueryServiceStatus(hs)[1] != win32service.SERVICE_STOPPED:
        try:
            win32service.ControlService(hs, win32service.SERVICE_CONTROL_STOP)
        except Exception:
            pass
        for _ in range(30):
            if win32service.QueryServiceStatus(hs)[1] == win32service.SERVICE_STOPPED:
                break
            time.sleep(0.5)


def uninstall():
    if not is_admin():
        raise PermissionError("Administrator rights are required")
    import win32service
    scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ALL_ACCESS)
    try:
        try:
            hs = win32service.OpenService(scm, SVC, win32service.SERVICE_ALL_ACCESS)
        except Exception:
            hs = None
        if hs:
            _stop(hs)
            win32service.DeleteService(hs)
            win32service.CloseServiceHandle(hs)
    finally:
        win32service.CloseServiceHandle(scm)
    for p in (CFG, PUBLIC):
        with contextlib.suppress(OSError):
            os.remove(p)
    log("service removed")
