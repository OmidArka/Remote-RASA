"""RasaDesk | Amn Negar Rasa | Modern bilingual (RTL/LTR) UI"""
import asyncio, ctypes, json, os, re, subprocess, sys, threading, time, urllib.request, webbrowser
import ntpath
import tkinter as tk
import tkinter.colorchooser as cc
import tkinter.font as tkf
from tkinter import filedialog

import customtkinter as ctk
import websockets
from PIL import Image

import contacts
import core
import winsvc
from core import (Host, Viewer, clean_name, clear_history, load_cfg, load_history, new_pw,
                  perm_key, perm_set, save_cfg, valid_server)

VERSION = "0.6.0"
FONTS = ("Vazirmatn",)  # Regular + Bold static files form one family; falls back to Segoe UI if missing
FONT_FILES = ("Vazirmatn-Regular.ttf", "Vazirmatn-Bold.ttf")
FONT, ICON = FONTS[0], "Segoe MDL2 Assets"
BG, CARD, FIELD = ("#F1F3F6", "#0C0E13"), ("#FFFFFF", "#161920"), ("#F1F3F6", "#0C0E13")
TXT, MUTED, LINE = ("#111827", "#F3F4F6"), ("#6B7280", "#9AA3B2"), ("#E5E7EB", "#262B35")
GREEN, RED = "#22C55E", "#EF4444"
ACCENTS = ["#E11D2E", "#E91D5E", "#2563EB", "#059669", "#7C3AED", "#EA580C"]
G = dict(home="\uE80F", settings="\uE713", user="\uE77B", lock="\uE72E", globe="\uE774", shield="\uEA18",
         tool="\uE90F", sync="\uE72C", info="\uE946", history="\uE81C", ok="\uE73E", no="\uE711", eye="\uE7B3", edit="\uE70F")
SECTIONS = (("profile", "user"), ("security", "lock"), ("servers", "globe"),
            ("privacy", "shield"), ("advanced", "tool"), ("service", "lock"), ("updates", "sync"))
BOTTOM = (("changelog", "history"), ("about", "info"))
STATUS_COLOR = {"ready": GREEN, "sharing": "#F59E0B", "offline": RED}

T = {
    "fa": dict(
        home="خانه", settings="تنظیمات", profile="پروفایل", security="امنیت", servers="سرورها",
        privacy="حریم خصوصی", advanced="پیشرفته", updates="به‌روزرسانی", changelog="تاریخچه تغییرات",
        about="درباره ما", ready="آنلاین", sharing="در حال اشتراک‌گذاری", offline="آفلاین",
        home_title="کنترل از راه دور", home_sub="امن به هر سیستم وصل شوید یا اجازه دهید دیگران به سیستم شما وصل شوند",
        your_desk="سیستم شما", your_desk_d="این شناسه و رمز را به شخص مقابل بدهید", id="شناسه (ID)",
        pw_temp="رمز موقت", copy="کپی", copied="کپی شد", new_pw="رمز جدید",
        connect_t="اتصال به سیستم دیگر", connect_d="شناسه و رمز سیستم مقصد را وارد کنید",
        remote_id="شناسه سیستم مقصد", remote_pw="رمز (اختیاری)", connect="اتصال",
        sec_strip="احراز هویت PAKE  •  رمزنگاری سرتاسری AES-256  •  تأیید دستی  •  قفل خودکار",
        notfound="شناسه پیدا نشد یا سیستم مشغول است", closed="اتصال بسته شد", authfail="هویت سیستم مقصد تأیید نشد؛ اتصال قطع شد",
        denied="کاربر مقصد اتصال را رد کرد", neterr="اتصال به سرور برقرار نشد",
        timeout="پاسخی دریافت نشد؛ رمز اشتباه است یا سیستم مقصد در دسترس نیست",
        badid="شناسه باید ۹ رقم باشد", nopw="رمز را وارد کنید", self="به سیستم خودتان نمی‌توانید وصل شوید",
        name_t="نام نمایشی", name_d="این نام هنگام اتصال شما به دیگران نشان داده می‌شود", name_ph="نام شما",
        save="ذخیره", saved="ذخیره شد", myid_t="شناسه شما",
        pwt_t="رمز موقت", pwt_d="با هر بار اجرای برنامه رمز تازه‌ای ساخته می‌شود. اتصال با این رمز همیشه تأیید شما را می‌خواهد.",
        perm_t="رمز دائمی", perm_d="رمز ثابت برای اتصال بدون ساخت رمز جدید. فقط به‌صورت رمزشده و مخصوص حساب ویندوز شما ذخیره می‌شود. رمز قوی و حداقل ۸ نویسه انتخاب کنید.",
        perm_new="رمز جدید", perm_confirm="تکرار رمز", change="تغییر", clear="حذف",
        is_set="تنظیم شده", not_set="تنظیم نشده", short="رمز باید حداقل ۸ نویسه باشد",
        mismatch="رمزها یکسان نیستند", cleared="رمز دائمی حذف شد",
        access_t="کنترل دسترسی", approve="تأیید دستی هر اتصال",
        approve_d="اگر خاموش باشد، اتصال با رمز دائمی بدون پرسش برقرار می‌شود. رمز موقت همیشه تأیید می‌خواهد.",
        viewonly="فقط مشاهده", viewonly_d="مقابل فقط صفحه را می‌بیند و ماوس و کیبورد را کنترل نمی‌کند",
        srv_t="آدرس سرور", srv_d="آدرس سرور واسط سازمان خود را وارد کنید. مثال: wss://relay.example.com:8765",
        srv_save="ذخیره و اتصال مجدد", srv_test="آزمایش اتصال", srv_ok="اتصال به سرور موفق بود",
        srv_fail="اتصال به سرور ناموفق بود", srv_bad="آدرس نامعتبر است؛ باید با ws:// یا wss:// شروع شود",
        srv_warn="برای استفاده واقعی از wss:// استفاده کنید. محتوا همچنان رمزنگاری سرتاسری است اما اطلاعات اتصال قابل مشاهده می‌ماند.",
        hist_t="تاریخچه اتصال‌ها", hist_d="فقط روی همین سیستم ذخیره می‌شود", hist_on="ذخیره تاریخچه",
        hist_clear="پاک کردن تاریخچه", hist_empty="موردی ثبت نشده است", ev_accepted="پذیرفته شد",
        ev_denied="رد شد", ev_locked="قفل موقت پس از تلاش ناموفق", e2e_t="حفاظت از داده‌ها",
        e2e_d="رمز شما هرگز ارسال نمی‌شود و با پروتکل PAKE (SPAKE2) فقط اثبات آن بین دو سیستم رد و بدل می‌شود؛ بنابراین حدس آفلاین رمز حتی برای سرور واسط ممکن نیست و هر حدس باید به‌صورت زنده انجام شود و پس از ۵ تلاش قفل می‌شود. تصویر و ورودی‌ها هم با AES-256-GCM و کلید یک‌بارمصرف هر نشست رمز می‌شوند.",
        look_t="ظاهر", mode="حالت نمایش", dark="تیره", light="روشن", system="سیستم", accent="رنگ اصلی",
        custom="رنگ دلخواه", lang_t="زبان", lang_d="تغییر زبان نیاز به راه‌اندازی مجدد برنامه دارد",
        restart_t="راه‌اندازی مجدد", restart_d="برای اعمال زبان جدید، برنامه بسته و دوباره باز می‌شود. ادامه می‌دهید؟",
        restart="راه‌اندازی مجدد", later="انصراف", perf_t="کارایی", fps="نرخ فریم", quality="کیفیت تصویر",
        q_low="کم", q_mid="متوسط", q_high="بالا", ver_t="نسخه برنامه", version="نسخه فعلی",
        upd_ph="https://example.com/rasadesk.json", upd_d="آدرس فایل JSON به‌روزرسانی (فقط HTTPS)",
        check="بررسی به‌روزرسانی", upd_none="آدرس به‌روزرسانی تنظیم نشده است",
        upd_latest="شما از آخرین نسخه استفاده می‌کنید", upd_new="نسخه جدید {v} موجود است؛ صفحه دانلود باز شد",
        upd_fail="بررسی به‌روزرسانی ناموفق بود",
        pw_hint="رمز اختیاری است. اگر خالی بگذارید، درخواست اتصال برای تأیید به سیستم مقصد ارسال می‌شود.",
        connecting="در حال اتصال...", approval="در انتظار تأیید سیستم مقصد...",
        approval_sas="در انتظار تأیید سیستم مقصد...  کد تأیید: {sas}",
        noopen="این سیستم اتصال بدون رمز را قبول نمی‌کند؛ رمز را وارد کنید",
        noapprover="کسی پشت سیستم مقصد نیست که اتصال را تأیید کند؛ با رمز دائمی وصل شوید",
        allow_open="پذیرش درخواست اتصال بدون رمز",
        allow_open_d="مقابل فقط با وارد کردن شناسه درخواست می‌دهد و شما باید تأیید کنید. هر بار یک کد تأیید نمایش داده می‌شود.",
        allow_files="انتقال فایل", allow_files_d="ارسال و دریافت فایل و مرور پوشه‌ها توسط مقابل، فقط در طول اتصال تأییدشده",
        allow_clip="اشتراک کلیپ‌بورد", allow_clip_d="کپی و پیست متن بین دو سیستم",
        tb_send="ارسال فایل", tb_get="دریافت فایل", tb_cad="Ctrl+Alt+Del", tb_full="تمام‌صفحه", tb_end="قطع اتصال",
        f_sent="ارسال شد", f_recv="دریافت شد (Downloads\\RasaDesk)", f_fail="ناموفق",
        rb_title="فایل‌های سیستم مقصد", rb_up="بالا", rb_home="شروع", rb_dl="دریافت",
        rb_denied="دسترسی به این مسیر ممکن نیست", rb_saved="فایل‌های دریافتی در Downloads\\RasaDesk ذخیره می‌شوند",
        bar_live="{name} به این سیستم متصل است", bar_end="قطع اتصال",
        service="سرویس ویندوز", svc_t="دسترسی بدون حضور (سرویس ویندوز)",
        svc_d="با نصب سرویس، این سیستم حتی روی صفحه UAC، قفل و ورود به ویندوز قابل کنترل است و بعد از هر راه‌اندازی خودکار آماده می‌شود. شناسه و رمز سرویس جدا از رمز موقت برنامه است.",
        svc_none="نصب نشده", svc_stopped="متوقف", svc_running="در حال اجرا", svc_other="در حال تغییر", svc_unavail="نامشخص",
        svc_manage="نصب / مدیریت سرویس (نیازمند مدیر سیستم)", svc_log="باز کردن گزارش", svc_refresh="بررسی دوباره",
        svc_path="نصب سرویس فقط از برنامه نصب‌شده در Program Files ممکن است؛ ابتدا با نصب‌کننده نصب کنید.",
        svc_active="سرویس فعال است و این سیستم را مدیریت می‌کند. برای اتصال از رمز دائمی سرویس استفاده می‌شود.",
        svc_note="سرویس ویندوز فعال است و رمز موقت وجود ندارد. رمز دائمی را در بخش سرویس ویندوز تنظیم کنید.",
        su_title="تنظیم و نصب سرویس", su_pw="رمز دائمی سرویس (حداقل ۸ نویسه)", su_keep="برای حفظ رمز فعلی خالی بگذارید",
        su_install="نصب / به‌روزرسانی و شروع", su_remove="حذف سرویس", su_ok="انجام شد. سرویس در حال اجراست.",
        su_removed="سرویس حذف شد", su_err="ناموفق: {e}", su_noauth="رمز دائمی بگذارید یا پذیرش درخواست بدون رمز را فعال کنید",
        su_approve="تأیید دستی حتی با رمز دائمی", su_approve_d="برای دسترسی بدون حضور خاموش بماند",
        recent_t="اتصال‌های اخیر", recent_d="روی هر مورد بزنید تا شناسه پر شود. با دکمه مداد نام، رنگ و عکس را تغییر دهید.",
        recent_empty="هنوز به سیستمی وصل نشده‌اید. بعد از اولین اتصال، اینجا نمایش داده می‌شود.",
        show_all="نمایش همه ({n})", show_less="نمایش کمتر",
        ct_edit="ویرایش مخاطب", ct_name="نام", ct_color="رنگ", ct_photo="عکس", ct_pick="انتخاب عکس", ct_rm="حذف عکس",
        ct_del="حذف از فهرست", ct_count="{n} بار", ct_bad_img="این فایل تصویر قابل استفاده‌ای نیست",
        ago_now="همین حالا", ago_min="{n} دقیقه پیش", ago_hour="{n} ساعت پیش", ago_day="{n} روز پیش",
        scale_t="اندازه متن", scale_s="معمولی", scale_m="بزرگ", scale_l="خیلی بزرگ",
        about_txt="RasaDesk محصول شرکت امن‌نگر راسا\nدسترسی امن از راه دور برای ویندوز",
        log=(("0.6.0", "فهرست اتصال‌های اخیر با نام، رنگ و عکس برای هر مخاطب؛ متن بزرگ‌تر با انتخاب اندازه"), ("0.5.0", "اتصال دو حالته (رمز یا تأیید)، انتقال فایل، کلیپ‌بورد، سرویس ویندوز برای UAC و قفل صفحه"), ("0.4.0", "احراز هویت PAKE (SPAKE2) به‌جای رمزنگاری مبتنی بر رمز، لوگوی جدید، قطع خودکار اتصال‌های نیمه‌کاره"), ("0.3.0", "رابط راست‌به‌چپ، فونت ایران‌سنس، تنظیمات کامل، رمز دائمی، رمزنگاری نشست با کلید یک‌بارمصرف، قفل خودکار"),
             ("0.2.0", "رابط جدید با تم قابل تغییر و فایل نصبی"), ("0.1.0", "نسخه اولیه: اتصال، نمایش صفحه، کنترل ماوس و کیبورد"))),
    "en": dict(
        home="Home", settings="Settings", profile="Profile", security="Security", servers="Servers",
        privacy="Privacy", advanced="Advanced", updates="Updates", changelog="Changelog", about="About",
        ready="Online", sharing="Sharing screen", offline="Offline",
        home_title="Remote Access", home_sub="Connect securely to any computer, or let others connect to yours",
        your_desk="Your Desk", your_desk_d="Share this ID and password with the other person", id="ID",
        pw_temp="Temporary password", copy="Copy", copied="Copied", new_pw="New password",
        connect_t="Connect to a Desk", connect_d="Enter the remote ID and password",
        remote_id="Remote ID", remote_pw="Password (optional)", connect="Connect",
        sec_strip="PAKE authentication  •  AES-256 end-to-end encryption  •  Manual approval  •  Lockout",
        notfound="ID not found or computer is busy", closed="Connection closed", authfail="Could not verify the remote computer; connection dropped",
        denied="The remote user denied the connection", neterr="Could not reach the server",
        timeout="No response: wrong password or the computer is unavailable",
        badid="The ID must be 9 digits", nopw="Enter the password", self="You cannot connect to your own computer",
        name_t="Display name", name_d="Shown to the other person when you connect", name_ph="Your name",
        save="Save", saved="Saved", myid_t="Your ID",
        pwt_t="Temporary password", pwt_d="A new password is generated every time the app starts. Connections using it always need your approval.",
        perm_t="Permanent password", perm_d="A fixed password so you can connect without generating a new one. Stored encrypted and bound to your Windows account. Use a strong password of at least 8 characters.",
        perm_new="New password", perm_confirm="Confirm password", change="Change", clear="Clear",
        is_set="Set", not_set="Not set", short="Password must be at least 8 characters",
        mismatch="Passwords do not match", cleared="Permanent password removed",
        access_t="Access control", approve="Approve every connection",
        approve_d="When off, connections using the permanent password are accepted without asking. The temporary password always asks.",
        viewonly="View only", viewonly_d="The other side can see the screen but cannot control mouse or keyboard",
        srv_t="Server address", srv_d="Enter your organization's relay server. Example: wss://relay.example.com:8765",
        srv_save="Save & reconnect", srv_test="Test connection", srv_ok="Server connection succeeded",
        srv_fail="Server connection failed", srv_bad="Invalid address; it must start with ws:// or wss://",
        srv_warn="Use wss:// in production. Content stays end-to-end encrypted, but connection metadata remains visible.",
        hist_t="Connection history", hist_d="Stored on this computer only", hist_on="Save history",
        hist_clear="Clear history", hist_empty="Nothing recorded yet", ev_accepted="Accepted",
        ev_denied="Denied", ev_locked="Temporarily locked after failed attempts", e2e_t="Data protection",
        e2e_d="Your password is never sent. The PAKE protocol (SPAKE2) only exchanges a proof of it, so even the relay server cannot guess it offline; every guess must be made live and is locked out after 5 attempts. Screen and input are encrypted with AES-256-GCM using a one-time key per session.",
        look_t="Appearance", mode="Theme", dark="Dark", light="Light", system="System", accent="Accent color",
        custom="Custom color", lang_t="Language", lang_d="Changing the language restarts the app",
        restart_t="Restart required", restart_d="The app will close and reopen to apply the new language. Continue?",
        restart="Restart", later="Cancel", perf_t="Performance", fps="Frame rate", quality="Image quality",
        q_low="Low", q_mid="Medium", q_high="High", ver_t="App version", version="Current version",
        upd_ph="https://example.com/rasadesk.json", upd_d="Update manifest URL (HTTPS only)",
        check="Check for updates", upd_none="No update URL configured",
        upd_latest="You are on the latest version", upd_new="Version {v} is available; the download page was opened",
        upd_fail="Update check failed",
        pw_hint="The password is optional. Leave it empty to send a connection request for approval.",
        connecting="Connecting...", approval="Waiting for the remote user to approve...",
        approval_sas="Waiting for the remote user to approve...  Verification code: {sas}",
        noopen="That computer does not accept requests without a password; enter the password",
        noapprover="Nobody is at the remote computer to approve; connect with the permanent password",
        allow_open="Accept requests without a password",
        allow_open_d="The other person only enters your ID and you approve. A verification code is shown every time.",
        allow_files="File transfer", allow_files_d="The other side can send/receive files and browse folders, only during an approved connection",
        allow_clip="Clipboard sharing", allow_clip_d="Copy and paste text between the two computers",
        tb_send="Send file", tb_get="Get file", tb_cad="Ctrl+Alt+Del", tb_full="Full screen", tb_end="Disconnect",
        f_sent="Sent", f_recv="Received (Downloads\\RasaDesk)", f_fail="Failed",
        rb_title="Remote files", rb_up="Up", rb_home="Start", rb_dl="Download",
        rb_denied="Cannot access this location", rb_saved="Downloads are saved to Downloads\\RasaDesk",
        bar_live="{name} is connected to this computer", bar_end="Disconnect",
        service="Windows service", svc_t="Unattended access (Windows service)",
        svc_d="With the service installed, this computer can be controlled even on the UAC prompt, lock screen and Windows sign-in, and is ready after every restart. The service has its own ID and permanent password, separate from the app's temporary password.",
        svc_none="Not installed", svc_stopped="Stopped", svc_running="Running", svc_other="Changing", svc_unavail="Unknown",
        svc_manage="Install / manage service (needs administrator)", svc_log="Open log", svc_refresh="Check again",
        svc_path="The service can only be installed from the copy in Program Files; install RasaDesk with the installer first.",
        svc_active="The service is active and manages this computer. Connections use the service's permanent password.",
        svc_note="The Windows service is active, so there is no temporary password. Set the permanent password in the Windows service section.",
        su_title="Configure and install the service", su_pw="Service permanent password (min 8 characters)", su_keep="Leave empty to keep the current password",
        su_install="Install / update and start", su_remove="Remove service", su_ok="Done. The service is running.",
        su_removed="Service removed", su_err="Failed: {e}", su_noauth="Set a permanent password or enable requests without a password",
        su_approve="Require approval even with the permanent password", su_approve_d="Keep off for unattended access",
        recent_t="Recent connections", recent_d="Click a contact to fill in its ID. Use the pencil to change its name, color and photo.",
        recent_empty="You have not connected to anyone yet. After your first connection it appears here.",
        show_all="Show all ({n})", show_less="Show less",
        ct_edit="Edit contact", ct_name="Name", ct_color="Color", ct_photo="Photo", ct_pick="Choose photo", ct_rm="Remove photo",
        ct_del="Remove from list", ct_count="{n} times", ct_bad_img="That file is not a usable image",
        ago_now="just now", ago_min="{n} min ago", ago_hour="{n} h ago", ago_day="{n} d ago",
        scale_t="Text size", scale_s="Normal", scale_m="Large", scale_l="Extra large",
        about_txt="RasaDesk by Amn Negar Rasa\nSecure remote access for Windows",
        log=(("0.6.0", "Recent connections with a name, color and photo per contact; larger text with a size setting"), ("0.5.0", "Two connection modes (password or approval), file transfer, clipboard, Windows service for UAC and lock screen"), ("0.4.0", "PAKE (SPAKE2) authentication replaces password-derived keys, new logo, stalled handshakes are dropped"), ("0.3.0", "RTL interface, Iranian Sans font, full settings, permanent password, per-session keys, automatic lockout"),
             ("0.2.0", "New interface with themes and installer"), ("0.1.0", "Initial release: connect, view screen, mouse and keyboard"))),
}


def mix(a, b, t):
    pa, pb = ([int(x[i:i + 2], 16) for i in (1, 3, 5)] for x in (a, b))
    return "#%02x%02x%02x" % tuple(round(p * (1 - t) + q * t) for p, q in zip(pa, pb))


def rp(p):
    return os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), p)


def F(size, bold=False, mono=False):
    # customtkinter font sizes are pixels: small text gets a readable floor, the rest a gentle bump.
    # The user's "text size" setting multiplies everything on top (ctk.set_widget_scaling).
    return ctk.CTkFont(family="Consolas" if mono else FONT, size=max(size + 2, 15), weight="bold" if bold else "normal")


def logo_img(px):
    try:
        return ctk.CTkImage(Image.open(rp("logo.png")), size=(px, px))
    except Exception:
        return None


def FI(size):
    return ctk.CTkFont(family=ICON, size=size + 2)


def flash(label, text, ok=True):
    try:
        label.configure(text=text, text_color=GREEN if ok else RED)
    except Exception:  # widget already destroyed
        pass


def hand(w):
    try:
        w.configure(cursor="hand2")
    except Exception:
        pass


class App(ctk.CTk):
    def __init__(s):
        cfg = load_cfg()
        ctk.set_appearance_mode(cfg["mode"])
        super().__init__()
        global FONT
        s.cfg = cfg
        ctk.set_widget_scaling(cfg["text_scale"])
        s.show_all = False
        fams = set(tkf.families(s))
        FONT = next((f for f in FONTS if f in fams), "Segoe UI")  # safe fallback if the font failed to load
        s.title("RasaDesk")
        s.geometry("1160x760")
        s.minsize(1020, 680)
        s.after(250, s.set_icon)
        s.tab, s.sec, s.stat, s.note, s.shell, s.errl = "home", "profile", "offline", None, None, None
        s.pw = new_pw()
        s.setup = "--svc-setup" in sys.argv  # elevated service-configuration instance: no host of its own
        s.svc_active = (not s.setup) and winsvc.state() == "running"
        s.bar, s.host = None, None
        if not (s.setup or s.svc_active):
            s.host = Host(s.cfg, lambda c: s.after(0, s.set_status, c), s.prompt, s.hevents)
            s.host.set_temp(s.pw)
            s.host.start()
        if s.setup:
            s.tab, s.sec, s.svc_cfg = "settings", "service", winsvc.setup_defaults(s.cfg)
        if s.svc_active:
            s.poll_svc()
        s.build()
        s.protocol("WM_DELETE_WINDOW", s.quit_app)

    # ───────── helpers ─────────
    def set_icon(s):
        try:
            s.iconbitmap(rp("rasadesk.ico"))
        except Exception:
            pass

    def t(s, k):
        return T[s.cfg["lang"]][k]

    def px(s, start, end):
        return (end, start) if s.rtl else (start, end)

    def prompt(s, name, sas=None):
        return core.prompt_text(s.cfg["lang"], name, sas)

    def poll_svc(s):  # service mode: show the service's live status
        st = winsvc.public().get("state")
        if st:
            s.set_status(st)
        s.after(3000, s.poll_svc)

    def hevents(s, what, **kw):  # host thread -> UI thread
        s.after(0, lambda: s.on_host_event(what, kw))

    def on_host_event(s, what, kw):
        if what == "live":
            if s.bar:
                s.bar.destroy()
            s.bar = SessionBar(s, kw["name"])
        elif what == "end":
            if s.bar:
                s.bar.destroy()
                s.bar = None
        elif what == "file" and s.bar:
            s.bar.note(s.file_text(kw))

    def file_text(s, kw):
        k, n = kw.get("kind"), kw.get("name", "")
        if k == "progress":
            return f"{n}: {min(100, kw.get('done', 0) * 100 // max(1, kw.get('total', 1)))}%"
        return {"received": s.t("f_recv"), "sent": s.t("f_sent"), "failed": s.t("f_fail")}.get(k, "") + f": {n}"

    def setcfg(s, k, v):
        s.cfg[k] = v
        save_cfg(s.cfg)

    def set_status(s, c):
        s.stat = c
        try:
            s.dot.configure(text_color=STATUS_COLOR[c])
            s.stxt.configure(text=s.t(c))
        except Exception:
            pass

    def copy(s, v):
        s.clipboard_clear()
        s.clipboard_append(v)

    def quit_app(s):
        save_cfg(s.cfg)
        s.destroy()

    def restart(s):
        save_cfg(s.cfg)
        core.release_instance()
        env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
        argv = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, os.path.abspath(__file__)]
        try:
            subprocess.Popen(argv, env=env, close_fds=True)
        except OSError:
            return
        os._exit(0)

    def refresh(s):
        s.after(30, s.build)

    def goto(s, tab, sec=None):
        s.tab, s.note = tab, None
        s.sec = sec or s.sec
        s.refresh()

    # ───────── building blocks ─────────
    def item(s, parent, icon, text, active, cmd, w=0):
        if w:
            w = max(w, tkf.Font(family=FONT, size=-17, weight="bold").measure(text) + 76)
        f = ctk.CTkFrame(parent, height=44, width=w, corner_radius=12, fg_color=s.tint if active else "transparent")
        f.pack_propagate(False)
        il = ctk.CTkLabel(f, text=icon, font=FI(16), text_color=s.ac if active else MUTED)
        tl = ctk.CTkLabel(f, text=text, font=F(13, active), text_color=s.ac if active else TXT)
        il.pack(side=s.S, padx=s.px(16, 8))
        tl.pack(side=s.S)
        for x in (f, il, tl):
            x.bind("<Button-1>", lambda e: cmd())
            hand(x)
        return f

    def card(s, parent, icon, title, badge=None, grid=None):
        c = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=18, border_width=1, border_color=LINE)
        if grid:
            c.grid(**grid)
        else:
            c.pack(fill="x", pady=(0, 14))
        h = ctk.CTkFrame(c, fg_color="transparent")
        h.pack(fill="x", padx=22, pady=(18, 6))
        ctk.CTkLabel(h, text=G[icon], font=FI(18), text_color=s.ac).pack(side=s.S, padx=s.px(0, 10))
        ctk.CTkLabel(h, text=title, font=F(16, True), text_color=TXT).pack(side=s.S)
        if badge is not None:
            ok, txt = badge
            bf = ctk.CTkFrame(h, fg_color="transparent")
            bf.pack(side=s.E)
            col = GREEN if ok else RED
            ctk.CTkLabel(bf, text=G["ok" if ok else "no"], font=FI(13), text_color=col).pack(side=s.S, padx=s.px(0, 6))
            ctk.CTkLabel(bf, text=txt, font=F(12), text_color=col).pack(side=s.S)
        b = ctk.CTkFrame(c, fg_color="transparent")
        b.pack(fill="both", expand=True, padx=22, pady=(0, 18))
        return b

    def desc(s, b, text):
        ctk.CTkLabel(b, text=text, font=F(12), text_color=MUTED, justify=s.J, anchor=s.A,
                     wraplength=600).pack(fill="x", pady=(0, 10))

    def entry(s, b, ph="", show=None, ltr=False, mono=False, center=False):
        kw = {"show": show} if show else {}
        e = ctk.CTkEntry(b, placeholder_text=ph, height=46, corner_radius=12, font=F(14 if mono else 13),  # always the app font so Persian placeholders match
                         fg_color=FIELD, border_color=LINE, text_color=TXT, placeholder_text_color=MUTED,
                         justify="center" if center else ("left" if ltr else s.J), **kw)
        e.pack(fill="x", pady=(0, 8))
        return e

    def btn(s, parent, text, cmd, kind="pri", w=120):
        fg, hv, tc, bc = {"pri": (s.ac, s.hv, "white", s.ac), "gho": ("transparent", FIELD, TXT, LINE),
                          "dan": ("transparent", ("#FDE8E8", "#2A1517"), RED, RED)}[kind]
        w = max(w, tkf.Font(family=FONT, size=-17, weight="bold").measure(text) + 44)
        return ctk.CTkButton(parent, text=text, command=cmd, width=w, height=40, corner_radius=12, font=F(13, True),
                             fg_color=fg, hover_color=hv, text_color=tc, border_width=0 if kind == "pri" else 1,
                             border_color=bc)

    def row(s, b, *specs):  # specs: (text, cmd[, kind[, width]])
        r = ctk.CTkFrame(b, fg_color="transparent")
        r.pack(fill="x", pady=(2, 0))
        for spec in specs:
            s.btn(r, *spec).pack(side=s.S, padx=s.px(0, 8))
        return r

    def msg(s, b):
        m = ctk.CTkLabel(b, text="", font=F(12), text_color=MUTED, anchor=s.A, justify=s.J, wraplength=600)
        m.pack(fill="x", pady=(8, 0))
        return m

    def switch(s, b, title, d, key, store=None):
        st = s.cfg if store is None else store
        r = ctk.CTkFrame(b, fg_color="transparent")
        r.pack(fill="x", pady=6)

        def toggle():
            if store is None:
                s.setcfg(key, bool(sw.get()))
            else:
                store[key] = bool(sw.get())
        sw = ctk.CTkSwitch(r, text="", width=52, switch_width=46, switch_height=24, progress_color=s.ac,
                           button_color="#FFFFFF", button_hover_color="#F3F4F6", fg_color=("#D1D5DB", "#2A2F3A"),
                           command=toggle)
        sw.pack(side=s.E)
        if st[key]:
            sw.select()
        col = ctk.CTkFrame(r, fg_color="transparent")
        col.pack(side=s.S, fill="x", expand=True)
        ctk.CTkLabel(col, text=title, font=F(14, True), text_color=TXT, anchor=s.A).pack(fill="x")
        if d:
            ctk.CTkLabel(col, text=d, font=F(12), text_color=MUTED, anchor=s.A, justify=s.J,
                         wraplength=520).pack(fill="x")

    def seg(s, b, values, cur, cmd):
        w = ctk.CTkSegmentedButton(b, values=values, command=cmd, height=38, font=F(13), corner_radius=12,
                                   selected_color=s.ac, selected_hover_color=s.hv, fg_color=FIELD,
                                   unselected_color=FIELD, unselected_hover_color=LINE, text_color=TXT)
        w.set(cur)
        w.pack(anchor=s.A, pady=(0, 4))
        return w

    def ask(s, title, text, ok, no, on_ok, on_no=None):
        d = ctk.CTkToplevel(s)
        d.title("RasaDesk")
        d.geometry("460x240")
        d.resizable(False, False)
        d.configure(fg_color=CARD)
        d.transient(s)

        def done(fn):
            d.destroy()
            if fn:
                fn()

        def focus():
            try:
                d.lift()
                d.focus_force()
                d.grab_set()
            except Exception:
                pass
        ctk.CTkLabel(d, text=title, font=F(18, True), text_color=TXT, anchor=s.A).pack(fill="x", padx=26, pady=(26, 6))
        ctk.CTkLabel(d, text=text, font=F(13), text_color=MUTED, justify=s.J, anchor=s.A,
                     wraplength=400).pack(fill="x", padx=26)
        r = ctk.CTkFrame(d, fg_color="transparent")
        r.pack(side="bottom", fill="x", padx=26, pady=22)
        s.btn(r, ok, lambda: done(on_ok)).pack(side=s.S, padx=s.px(0, 10))
        s.btn(r, no, lambda: done(on_no), "gho").pack(side=s.S)
        d.protocol("WM_DELETE_WINDOW", lambda: done(on_no))
        d.after(150, focus)

    # ───────── shell ─────────
    def build(s):
        if s.shell is not None:
            s.shell.destroy()  # only our own shell: viewer windows stay alive
        s.rtl = s.cfg["lang"] == "fa"
        s.S, s.E, s.A, s.J = ("right", "left", "e", "right") if s.rtl else ("left", "right", "w", "left")
        s.ac = s.cfg["accent"]
        s.hv = mix(s.ac, "#000000", .18)
        s.tint = (mix(s.ac, "#FFFFFF", .90), mix(s.ac, "#0C0E13", .80))
        s.configure(fg_color=BG)
        s.shell = ctk.CTkFrame(s, fg_color="transparent", corner_radius=0)
        s.shell.pack(fill="both", expand=True)
        top = ctk.CTkFrame(s.shell, height=70, corner_radius=0, fg_color=CARD)
        top.pack(fill="x")
        top.pack_propagate(False)
        img = logo_img(42)
        if img:
            ctk.CTkLabel(top, image=img, text="").pack(side=s.S, padx=s.px(26, 10))
        ctk.CTkLabel(top, text="RasaDesk", font=F(20, True), text_color=TXT).pack(side=s.S, padx=s.px(0 if img else 26, 30))
        for k, ic in (("home", "home"), ("settings", "settings")):
            s.item(top, G[ic], s.t(k), s.tab == k, lambda k=k: s.goto(k), 130).pack(side=s.S, padx=4, pady=13)
        pill = ctk.CTkFrame(top, corner_radius=18, fg_color=FIELD)
        pill.pack(side=s.E, padx=26)
        s.dot = ctk.CTkLabel(pill, text="●", font=F(14), text_color=STATUS_COLOR[s.stat])
        s.dot.pack(side=s.S, padx=s.px(14, 6), pady=8)
        s.stxt = ctk.CTkLabel(pill, text=s.t(s.stat), font=F(12), text_color=TXT)
        s.stxt.pack(side=s.S, padx=s.px(0, 14))
        ctk.CTkFrame(s.shell, height=1, corner_radius=0, fg_color=LINE).pack(fill="x")
        body = ctk.CTkFrame(s.shell, fg_color="transparent")
        body.pack(fill="both", expand=True)
        (s.page_home if s.tab == "home" else s.page_settings)(body)

    # ───────── home ─────────
    def page_home(s, body):
        w = ctk.CTkScrollableFrame(body, fg_color="transparent")
        w.pack(fill="both", expand=True, padx=26, pady=18)
        ctk.CTkLabel(w, text=s.t("home_title"), font=F(28, True), text_color=TXT, anchor=s.A).pack(fill="x")
        ctk.CTkLabel(w, text=s.t("home_sub"), font=F(14), text_color=MUTED, anchor=s.A).pack(fill="x", pady=(2, 18))
        g = ctk.CTkFrame(w, fg_color="transparent")
        g.pack(fill="x")
        g.columnconfigure((0, 1), weight=1, uniform="c")
        mine, conn = (1, 0) if s.rtl else (0, 1)
        i = (winsvc.public().get("id") or s.cfg["id"]) if s.svc_active else s.cfg["id"]
        b = s.card(g, "home", s.t("your_desk"), grid=dict(row=0, column=mine, sticky="nsew", padx=(0, 12) if not s.rtl else (12, 0)))
        s.desc(b, s.t("your_desk_d"))
        ctk.CTkLabel(b, text=s.t("id"), font=F(12), text_color=MUTED, anchor=s.A).pack(fill="x")
        ctk.CTkLabel(b, text=f"{i[:3]} {i[3:6]} {i[6:]}", font=F(36, True, True), text_color=TXT, anchor=s.A).pack(fill="x")
        specs = [(s.t("copy") + " ID", lambda: s.copy(i), "gho")]
        if s.svc_active:
            ctk.CTkLabel(b, text=s.t("svc_active"), font=F(12), text_color=GREEN, wraplength=380, justify=s.J,
                         anchor=s.A).pack(fill="x", pady=(14, 0))
        else:
            ctk.CTkLabel(b, text=s.t("pw_temp"), font=F(12), text_color=MUTED, anchor=s.A).pack(fill="x", pady=(14, 0))
            pwl = ctk.CTkLabel(b, text=s.pw, font=F(28, True, True), text_color=s.ac, anchor=s.A)
            pwl.pack(fill="x")

            def regen():
                s.pw = new_pw()
                s.host.set_temp(s.pw)
                pwl.configure(text=s.pw)
            specs += [(s.t("copy") + " " + s.t("pw_temp"), lambda: s.copy(s.pw), "gho"), (s.t("new_pw"), regen, "pri")]
        r = ctk.CTkFrame(b, fg_color="transparent")
        r.pack(fill="x", pady=(22, 0))
        for text, cmd, kind in specs:
            s.btn(r, text, cmd, kind, 130).pack(side=s.S, padx=s.px(0, 8))

        b2 = s.card(g, "globe", s.t("connect_t"), grid=dict(row=0, column=conn, sticky="nsew", padx=(12, 0) if not s.rtl else (0, 12)))
        s.desc(b2, s.t("connect_d"))
        s.tid = s.entry(b2, s.t("remote_id"), mono=True, center=True)
        s.tpw = s.entry(b2, s.t("remote_pw"), show="•", mono=True, center=True)
        s.tpw.bind("<Return>", lambda e: s.connect())
        ctk.CTkLabel(b2, text=s.t("pw_hint"), font=F(11), text_color=MUTED, wraplength=380, justify=s.J,
                     anchor=s.A).pack(fill="x")
        ctk.CTkButton(b2, text=s.t("connect"), height=52, corner_radius=14, font=F(16, True), fg_color=s.ac,
                      hover_color=s.hv, text_color="white", command=s.connect).pack(fill="x", pady=(10, 4))
        s.errl = ctk.CTkLabel(b2, text="", font=F(12), text_color=RED, wraplength=380, justify="center")
        s.errl.pack(fill="x", pady=(6, 0))
        s.contacts_card(w)
        s.strip(w)

    def strip(s, w):
        f = ctk.CTkFrame(w, fg_color="transparent")
        f.pack(pady=(16, 0))
        ctk.CTkLabel(f, text=G["shield"], font=FI(14), text_color=GREEN).pack(side=s.S, padx=s.px(0, 8))
        ctk.CTkLabel(f, text=s.t("sec_strip"), font=F(12), text_color=MUTED).pack(side=s.S)

    def say(s, text, ok=None):  # ok None = neutral progress message
        try:
            s.errl.configure(text=text, text_color=s.ac if ok is None else (GREEN if ok else RED))
        except Exception:
            pass

    def on_err(s, code):
        s.say(s.t(code) if code else "", False)

    def connect(s):
        t, pw = s.tid.get().strip().replace(" ", ""), s.tpw.get()
        if not re.fullmatch(r"\d{9}", t):
            return s.on_err("badid")
        if t == s.cfg["id"]:
            return s.on_err("self")
        s.say("")
        holder = []
        holder.append(Viewer(s, s.cfg, t, pw, lambda w, **k: s.on_evt(holder[0], w, **k), s.toolbar))

    def on_evt(s, v, what, **kw):  # viewer events, always on the UI thread
        if what == "state":
            c, sas = kw.get("code"), kw.get("sas")
            s.say(s.t("approval_sas").format(sas=sas[:3] + " " + sas[3:]) if (c == "approval" and sas) else s.t(c))
        elif what == "error":
            s.say(s.t(kw["code"]), False)
        elif what == "connected":  # remember who we connected to
            contacts.touch(v.target)
            if s.tab == "home":
                s.refresh()
        elif what == "file":
            try:
                v.tb_label.configure(text=s.file_text(kw))
            except Exception:
                pass
        elif what == "list" and getattr(v, "browser", None):
            v.browser.show(kw["data"])

    def toolbar(s, win, v):  # remote-session toolbar (called by Viewer.open_window)
        bar = ctk.CTkFrame(win, height=44, corner_radius=0, fg_color=CARD)
        bar.pack(side="top", fill="x")
        bar.pack_propagate(False)

        def add(text, cmd, kind="gho", w=120):
            b = s.btn(bar, text, cmd, kind, w)
            b.configure(height=32)
            b.pack(side=s.S, padx=4, pady=6)

        def send():
            paths = filedialog.askopenfilenames(parent=win)
            if paths:
                v.send_files(list(paths))

        def get():
            if getattr(v, "browser", None) and v.browser.winfo_exists():
                v.browser.lift()
            else:
                v.browser = RemoteBrowser(s, v)
        if v.caps.get("files"):
            add(s.t("tb_send"), send)
            add(s.t("tb_get"), get)
        if v.caps.get("agent"):
            add(s.t("tb_cad"), v.ctrl_alt_del, "gho", 130)
        add(s.t("tb_full"), v.fullscreen)
        add(s.t("tb_end"), v.close, "dan")
        v.tb_label = ctk.CTkLabel(bar, text="", font=F(12), text_color=MUTED)
        v.tb_label.pack(side=s.E, padx=14)

    # ───────── recent connections (contacts) ─────────
    def ago(s, ts):
        d = max(0, int(time.time()) - ts)
        if d < 60:
            return s.t("ago_now")
        if d < 3600:
            return s.t("ago_min").format(n=d // 60)
        if d < 86400:
            return s.t("ago_hour").format(n=d // 3600)
        if d < 30 * 86400:
            return s.t("ago_day").format(n=d // 86400)
        return time.strftime("%Y-%m-%d", time.localtime(ts))

    def ccolor(s, c):  # chosen color, else a stable pleasant default per ID
        return c["color"] or ACCENTS[int(c["id"]) % len(ACCENTS)]

    def avatar(s, c, px, **kw):
        im = contacts.render(c, px * 2, s.ccolor(c), font=rp("Vazirmatn-Bold.ttf"), **kw)
        return ctk.CTkImage(light_image=im, dark_image=im, size=(px, px))

    def pick(s, i):  # click on a contact -> fill the ID and jump to the password field
        try:
            s.tid.delete(0, "end")
            s.tid.insert(0, f"{i[:3]} {i[3:6]} {i[6:]}")
            s.tpw.focus_set()
        except Exception:
            pass

    def toggle_all(s):
        s.show_all = not s.show_all
        s.refresh()

    def tile(s, parent, c):
        f = ctk.CTkFrame(parent, corner_radius=16, fg_color=FIELD, border_width=1, border_color=LINE)
        av = ctk.CTkLabel(f, image=s.avatar(c, 52), text="")
        av.pack(side=s.S, padx=s.px(12, 10), pady=12)
        edit = ctk.CTkButton(f, text=G["edit"], font=FI(14), width=34, height=34, corner_radius=17, fg_color="transparent",
                             hover_color=LINE, text_color=MUTED, command=lambda: ContactDialog(s, c))
        edit.pack(side=s.E, padx=8)
        info = ctk.CTkFrame(f, fg_color="transparent")
        info.pack(side=s.S, fill="x", expand=True, pady=8)
        i = c["id"]
        fid = f"{i[:3]} {i[3:6]} {i[6:]}"
        ctk.CTkLabel(info, text=c["name"] or fid, font=F(14, True), text_color=TXT, anchor=s.A).pack(fill="x")
        if c["name"]:
            ctk.CTkLabel(info, text=fid, font=F(11, False, True), text_color=MUTED, anchor=s.A).pack(fill="x")
        ctk.CTkLabel(info, text=f"{s.ago(c['last'])}  •  {s.t('ct_count').format(n=c['count'])}", font=F(11),
                     text_color=s.ccolor(c), anchor=s.A).pack(fill="x")
        for x in (f, av, info, *info.winfo_children()):
            x.bind("<Button-1>", lambda e, i=i: s.pick(i))
            hand(x)
        return f

    def contacts_card(s, w):
        lst = contacts.load()
        b = s.card(w, "history", s.t("recent_t") + (f"  ({len(lst)})" if lst else ""))
        if not lst:
            ctk.CTkLabel(b, text=s.t("recent_empty"), font=F(13), text_color=MUTED, anchor=s.A).pack(fill="x", pady=8)
            return
        s.desc(b, s.t("recent_d"))
        grid = ctk.CTkFrame(b, fg_color="transparent")
        grid.pack(fill="x")
        cols = 3
        for k in range(cols):
            grid.columnconfigure(k, weight=1, uniform="t")
        for n, c in enumerate(lst if s.show_all else lst[:6]):
            r, col = divmod(n, cols)
            s.tile(grid, c).grid(row=r, column=(cols - 1 - col) if s.rtl else col, sticky="nsew", padx=5, pady=5)
        if len(lst) > 6:
            s.row(b, (s.t("show_less") if s.show_all else s.t("show_all").format(n=len(lst)), s.toggle_all, "gho", 170))

    # ───────── settings ─────────
    def page_settings(s, body):
        nav = ctk.CTkFrame(body, width=260, corner_radius=18, fg_color=CARD, border_width=1, border_color=LINE)
        nav.pack(side=s.S, fill="y", padx=s.px(26, 0), pady=26)
        nav.pack_propagate(False)
        for k, ic in reversed(BOTTOM):
            s.item(nav, G[ic], s.t(k), s.sec == k, lambda k=k: s.goto("settings", k)).pack(side="bottom", fill="x", padx=12, pady=(2, 12 if k == "about" else 2))
        for n, (k, ic) in enumerate(SECTIONS):
            s.item(nav, G[ic], s.t(k), s.sec == k, lambda k=k: s.goto("settings", k)).pack(fill="x", padx=12, pady=(14 if n == 0 else 2, 2))
        sc = ctk.CTkScrollableFrame(body, fg_color="transparent")
        sc.pack(side=s.S, fill="both", expand=True, padx=26, pady=(18, 14))
        ctk.CTkLabel(sc, text=s.t(s.sec), font=F(26, True), text_color=TXT, anchor=s.A).pack(fill="x", pady=(0, 14))
        getattr(s, "sec_" + s.sec)(sc)

    def sec_profile(s, sc):
        b = s.card(sc, "user", s.t("name_t"))
        s.desc(b, s.t("name_d"))
        e = s.entry(b, s.t("name_ph"))
        e.insert(0, s.cfg["name"])
        m = s.msg(b)

        def save():
            v = clean_name(e.get())
            s.setcfg("name", v)
            flash(m, s.t("saved"))
        s.row(b, (s.t("save"), save))
        b = s.card(sc, "info", s.t("myid_t"))
        i = s.cfg["id"]
        ctk.CTkLabel(b, text=f"{i[:3]} {i[3:6]} {i[6:]}", font=F(30, True, True), text_color=TXT, anchor=s.A).pack(fill="x")
        m2 = s.msg(b)

        def cp():
            s.copy(i)
            flash(m2, s.t("copied"))
        s.row(b, (s.t("copy"), cp, "gho"))

    def sec_security(s, sc):
        if s.host is None:  # service mode: the app has no temporary/permanent password of its own
            b = s.card(sc, "lock", s.t("pwt_t"))
            s.desc(b, s.t("svc_note"))
            return
        b = s.card(sc, "lock", s.t("pwt_t"))
        s.desc(b, s.t("pwt_d"))
        pwl = ctk.CTkLabel(b, text=s.pw, font=F(26, True, True), text_color=s.ac, anchor=s.A)
        pwl.pack(fill="x", pady=(0, 10))

        def regen():
            s.pw = new_pw()
            s.host.set_temp(s.pw)
            pwl.configure(text=s.pw)
        s.row(b, (s.t("copy"), lambda: s.copy(s.pw), "gho"), (s.t("new_pw"), regen))

        has = perm_key(s.cfg) is not None
        b = s.card(sc, "lock", s.t("perm_t"), badge=(has, s.t("is_set" if has else "not_set")))
        s.desc(b, s.t("perm_d"))
        e1 = s.entry(b, s.t("perm_new"), show="•", ltr=True)
        e2 = s.entry(b, s.t("perm_confirm"), show="•", ltr=True)
        m = s.msg(b)
        if s.note:
            flash(m, *s.note)
            s.note = None

        def change():
            p, q = e1.get(), e2.get()
            if len(p) < 8:
                return flash(m, s.t("short"), False)
            if p != q:
                return flash(m, s.t("mismatch"), False)
            try:
                perm_set(s.cfg, p)
            except OSError:
                return flash(m, s.t("srv_fail"), False)
            save_cfg(s.cfg)
            s.host.refresh_perm()
            s.note = (s.t("saved"), True)
            s.refresh()

        def clear():
            perm_set(s.cfg, "")
            save_cfg(s.cfg)
            s.host.refresh_perm()
            s.note = (s.t("cleared"), True)
            s.refresh()
        s.row(b, (s.t("change"), change), (s.t("clear"), clear, "dan"))

        b = s.card(sc, "shield", s.t("access_t"))
        s.switch(b, s.t("approve"), s.t("approve_d"), "approve")
        s.switch(b, s.t("viewonly"), s.t("viewonly_d"), "view_only")
        s.switch(b, s.t("allow_open"), s.t("allow_open_d"), "allow_open")
        s.switch(b, s.t("allow_files"), s.t("allow_files_d"), "allow_files")
        s.switch(b, s.t("allow_clip"), s.t("allow_clip_d"), "allow_clip")

    def sec_servers(s, sc):
        b = s.card(sc, "globe", s.t("srv_t"))
        s.desc(b, s.t("srv_d"))
        e = s.entry(b, "wss://", ltr=True, mono=True)
        e.insert(0, s.cfg["server"])
        m = s.msg(b)

        def save():
            v = e.get().strip()
            if not valid_server(v):
                return flash(m, s.t("srv_bad"), False)
            s.setcfg("server", v)
            s.host and s.host.reconnect()
            insecure = v.startswith("ws://") and not re.match(r"ws://(localhost|127\.|10\.|192\.168\.)", v)
            flash(m, s.t("saved") + ("\n" + s.t("srv_warn") if insecure else ""), not insecure)

        def test():
            v = e.get().strip()
            if not valid_server(v):
                return flash(m, s.t("srv_bad"), False)

            def work():
                async def probe():
                    async with websockets.connect(v, open_timeout=5):
                        return True
                try:
                    ok = asyncio.run(probe())
                except Exception:
                    ok = False
                s.after(0, lambda: flash(m, s.t("srv_ok" if ok else "srv_fail"), ok))
            threading.Thread(target=work, daemon=True).start()
        s.row(b, (s.t("srv_save"), save, "pri", 170), (s.t("srv_test"), test, "gho", 150))

    def sec_privacy(s, sc):
        b = s.card(sc, "history", s.t("hist_t"))
        s.desc(b, s.t("hist_d"))
        s.switch(b, s.t("hist_on"), "", "history")
        items = list(reversed(load_history()))[:8]
        if not items:
            ctk.CTkLabel(b, text=s.t("hist_empty"), font=F(13), text_color=MUTED, anchor=s.A).pack(fill="x", pady=8)
        for h in items:
            r = ctk.CTkFrame(b, fg_color=FIELD, corner_radius=10)
            r.pack(fill="x", pady=3)
            ev = h.get("e") if h.get("e") in ("accepted", "denied", "locked") else "denied"
            ctk.CTkLabel(r, text=str(h.get("t", "")), font=F(12, False, True), text_color=MUTED).pack(side=s.S, padx=14, pady=9)
            ctk.CTkLabel(r, text=s.t("ev_" + ev), font=F(12, True), text_color=GREEN if ev == "accepted" else RED).pack(side=s.S, padx=4)
            ctk.CTkLabel(r, text=clean_name(h.get("n", "")), font=F(12), text_color=TXT).pack(side=s.S, padx=10)

        def wipe():
            clear_history()
            s.refresh()
        s.row(b, (s.t("hist_clear"), wipe, "dan", 160))
        b = s.card(sc, "shield", s.t("e2e_t"))
        s.desc(b, s.t("e2e_d"))

    def sec_advanced(s, sc):
        b = s.card(sc, "tool", s.t("look_t"))
        names = {"dark": s.t("dark"), "light": s.t("light"), "system": s.t("system")}
        inv = {v: k for k, v in names.items()}

        def mode(v):
            ctk.set_appearance_mode(inv[v])
            s.setcfg("mode", inv[v])
            s.refresh()
        ctk.CTkLabel(b, text=s.t("mode"), font=F(13, True), text_color=TXT, anchor=s.A).pack(fill="x", pady=(0, 6))
        s.seg(b, list(names.values()), names[s.cfg["mode"]], mode)
        ctk.CTkLabel(b, text=s.t("scale_t"), font=F(13, True), text_color=TXT, anchor=s.A).pack(fill="x", pady=(14, 6))
        sizes = {s.t("scale_s"): 1.0, s.t("scale_m"): 1.15, s.t("scale_l"): 1.3}

        def scale(v):
            s.setcfg("text_scale", sizes[v])
            ctk.set_widget_scaling(sizes[v])
            s.refresh()
        s.seg(b, list(sizes), next(k for k, x in sizes.items() if x == s.cfg["text_scale"]), scale)
        ctk.CTkLabel(b, text=s.t("accent"), font=F(13, True), text_color=TXT, anchor=s.A).pack(fill="x", pady=(14, 6))
        r = ctk.CTkFrame(b, fg_color="transparent")
        r.pack(fill="x")

        def accent(c):
            s.setcfg("accent", c)
            s.refresh()

        def pick():
            v = cc.askcolor(color=s.ac, title=s.t("custom"))[1]
            if v:
                accent(v)
        for c in ACCENTS:
            ctk.CTkButton(r, text=G["ok"] if c.lower() == s.ac.lower() else "", font=FI(15), width=40, height=40,
                          corner_radius=20, fg_color=c, hover_color=mix(c, "#000000", .15), text_color="white",
                          command=lambda c=c: accent(c)).pack(side=s.S, padx=3)
        ctk.CTkButton(r, text="+", font=F(20), width=40, height=40, corner_radius=20, fg_color=FIELD, text_color=TXT,
                      hover_color=LINE, border_width=1, border_color=LINE, command=pick).pack(side=s.S, padx=3)

        b = s.card(sc, "globe", s.t("lang_t"))
        s.desc(b, s.t("lang_d"))

        def lang(v):
            new = "fa" if v == "فارسی" else "en"
            if new == s.cfg["lang"]:
                return

            def go():
                s.cfg["lang"] = new
                s.restart()
            s.ask(s.t("restart_t"), s.t("restart_d"), s.t("restart"), s.t("later"), go, s.refresh)
        s.seg(b, ["فارسی", "English"], "فارسی" if s.rtl else "English", lang)

        b = s.card(sc, "sync", s.t("perf_t"))
        ctk.CTkLabel(b, text=s.t("fps"), font=F(13, True), text_color=TXT, anchor=s.A).pack(fill="x", pady=(0, 6))
        s.seg(b, ["5", "10", "15", "30"], str(s.cfg["fps"]), lambda v: s.setcfg("fps", int(v)))
        ctk.CTkLabel(b, text=s.t("quality"), font=F(13, True), text_color=TXT, anchor=s.A).pack(fill="x", pady=(14, 6))
        q = {s.t("q_low"): 35, s.t("q_mid"): 55, s.t("q_high"): 75}
        cur = next(k for k, v in q.items() if v == s.cfg["quality"])
        s.seg(b, list(q), cur, lambda v: s.setcfg("quality", q[v]))

    def sec_service(s, sc):
        st = winsvc.state()
        label = {"none": "svc_none", "stopped": "svc_stopped", "running": "svc_running", "other": "svc_other"}.get(st, "svc_unavail")
        b = s.card(sc, "shield", s.t("svc_t"), badge=(st == "running", s.t(label)))
        s.desc(b, s.t("svc_d"))
        pub = winsvc.public()
        if st == "running" and pub:
            i = pub["id"]
            ctk.CTkLabel(b, text=s.t("id"), font=F(12), text_color=MUTED, anchor=s.A).pack(fill="x")
            ctk.CTkLabel(b, text=f"{i[:3]} {i[3:6]} {i[6:]}", font=F(30, True, True), text_color=TXT,
                         anchor=s.A).pack(fill="x", pady=(0, 6))
        m = s.msg(b)
        if s.note:
            flash(m, *s.note)
            s.note = None
        if not s.setup:
            if not winsvc.protected_exe():
                flash(m, s.t("svc_path"), False)

            def manage():
                if not winsvc.launch_elevated("--svc-setup"):
                    flash(m, s.t("svc_path"), False)
            s.row(b, (s.t("svc_manage"), manage, "pri", 330), (s.t("svc_refresh"), s.refresh, "gho", 150),
                  (s.t("svc_log"), winsvc.open_log, "gho", 150))
            return
        c = s.svc_cfg  # elevated instance: configuration form
        f = s.card(sc, "lock", s.t("su_title"))
        s.desc(f, s.t("su_pw") + "  -  " + s.t("su_keep"))
        srv = s.entry(f, "wss://", ltr=True, mono=True)
        srv.insert(0, c["server"])
        e1 = s.entry(f, s.t("perm_new"), show="•", ltr=True)
        e2 = s.entry(f, s.t("perm_confirm"), show="•", ltr=True)
        s.switch(f, s.t("su_approve"), s.t("su_approve_d"), "approve", c)
        s.switch(f, s.t("allow_open"), s.t("allow_open_d"), "allow_open", c)
        s.switch(f, s.t("allow_files"), s.t("allow_files_d"), "allow_files", c)
        s.switch(f, s.t("allow_clip"), s.t("allow_clip_d"), "allow_clip", c)
        s.switch(f, s.t("viewonly"), s.t("viewonly_d"), "view_only", c)
        fm = s.msg(f)

        def install():
            p, q = e1.get(), e2.get()
            if (p or q) and len(p) < 8:
                return flash(fm, s.t("short"), False)
            if p != q:
                return flash(fm, s.t("mismatch"), False)
            if not valid_server(srv.get().strip()):
                return flash(fm, s.t("srv_bad"), False)
            c["server"], c["lang"] = srv.get().strip(), s.cfg["lang"]
            try:
                winsvc.install(c, p)
            except ValueError:
                return flash(fm, s.t("su_noauth"), False)
            except Exception as e:
                return flash(fm, s.t("su_err").format(e=e), False)
            s.note = (s.t("su_ok"), True)
            s.refresh()

        def remove():
            try:
                winsvc.uninstall()
            except Exception as e:
                return flash(fm, s.t("su_err").format(e=e), False)
            s.note = (s.t("su_removed"), True)
            s.refresh()
        s.row(f, (s.t("su_install"), install, "pri", 250), (s.t("su_remove"), remove, "dan", 150))

    def sec_updates(s, sc):
        b = s.card(sc, "sync", s.t("ver_t"))
        ctk.CTkLabel(b, text=f"{s.t('version')}:  {VERSION}", font=F(15, True, True), text_color=TXT, anchor=s.A).pack(fill="x", pady=(0, 8))
        s.desc(b, s.t("upd_d"))
        e = s.entry(b, s.t("upd_ph"), ltr=True, mono=True)
        e.insert(0, s.cfg["update_url"])
        m = s.msg(b)

        def ver(x):
            return tuple(int(n) for n in re.findall(r"\d+", x))

        def check():
            url = e.get().strip()
            if not url:
                return flash(m, s.t("upd_none"), False)
            if not url.startswith("https://") or len(url) > 300:
                return flash(m, s.t("srv_bad"), False)
            s.setcfg("update_url", url)

            def work():
                try:
                    with urllib.request.urlopen(url, timeout=8) as r:
                        d = json.loads(r.read(4096))
                    v, link = str(d["version"]), str(d.get("url", ""))
                    if ver(v) > ver(VERSION):
                        if link.startswith("https://"):
                            webbrowser.open(link)
                        res = (s.t("upd_new").format(v=v), True)
                    else:
                        res = (s.t("upd_latest"), True)
                except Exception:
                    res = (s.t("upd_fail"), False)
                s.after(0, lambda: flash(m, *res))
            threading.Thread(target=work, daemon=True).start()
        s.row(b, (s.t("check"), check, "pri", 180))

    def sec_changelog(s, sc):
        b = s.card(sc, "history", s.t("changelog"))
        for v, txt in s.t("log"):
            r = ctk.CTkFrame(b, fg_color=FIELD, corner_radius=12)
            r.pack(fill="x", pady=4)
            ctk.CTkLabel(r, text=v, font=F(14, True, True), text_color=s.ac).pack(side=s.S, padx=16, pady=14, anchor="n")
            ctk.CTkLabel(r, text=txt, font=F(13), text_color=TXT, justify=s.J, anchor=s.A, wraplength=480).pack(
                side=s.S, fill="x", expand=True, padx=s.px(0, 16), pady=12)

    def sec_about(s, sc):
        b = s.card(sc, "info", "RasaDesk")
        img = logo_img(84)
        if img:
            ctk.CTkLabel(b, image=img, text="").pack(anchor=s.A, pady=(0, 12))
        ctk.CTkLabel(b, text=s.t("about_txt"), font=F(15), text_color=TXT, justify=s.J, anchor=s.A).pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(b, text=f"v{VERSION}", font=F(13, False, True), text_color=MUTED, anchor=s.A).pack(fill="x")


def human(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024


class RemoteBrowser(ctk.CTkToplevel):
    """Browse the remote computer's folders (as the logged-on user) and download files."""

    def __init__(s, app, v):
        super().__init__(app)
        s.app, s.v, s.path, s.items = app, v, "", []
        s.title(app.t("rb_title"))
        s.geometry("680x540")
        s.configure(fg_color=CARD)
        top = ctk.CTkFrame(s, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(14, 6))
        for text, cmd in ((app.t("rb_home"), lambda: s.go("")), (app.t("rb_up"), s.up)):
            app.btn(top, text, cmd, "gho", 90).pack(side=app.S, padx=app.px(0, 6))
        s.pl = ctk.CTkLabel(top, text="", font=F(12, False, True), text_color=MUTED, anchor="w")
        s.pl.pack(side=app.S, fill="x", expand=True, padx=8)
        dark = ctk.get_appearance_mode() == "Dark"
        mid = ctk.CTkFrame(s, fg_color="transparent")
        mid.pack(fill="both", expand=True, padx=14)
        sb = ctk.CTkScrollbar(mid)
        sb.pack(side="right", fill="y")
        s.lb = tk.Listbox(mid, selectmode="extended", bd=0, highlightthickness=0, activestyle="none",
                          bg="#0C0E13" if dark else "#F1F3F6", fg="#F3F4F6" if dark else "#111827",
                          selectbackground=app.ac, selectforeground="white", font=(FONT, round(12 * app.cfg["text_scale"])),
                          yscrollcommand=sb.set)
        s.lb.pack(side="left", fill="both", expand=True)
        sb.configure(command=s.lb.yview)
        s.lb.bind("<Double-Button-1>", lambda e: s.open())
        bot = ctk.CTkFrame(s, fg_color="transparent")
        bot.pack(fill="x", padx=14, pady=12)
        app.btn(bot, app.t("rb_dl"), s.download, "pri", 130).pack(side=app.S)
        s.ml = ctk.CTkLabel(bot, text=app.t("rb_saved"), font=F(11), text_color=MUTED)
        s.ml.pack(side=app.S, padx=12)
        s.go("")

    def go(s, path):
        s.v.browse(path)

    def up(s):
        cur = s.path.rstrip("\\")
        par = ntpath.dirname(cur)
        s.go("" if (not par or par == cur) else par)

    def full(s, name):
        return name if not s.path else ntpath.join(s.path, name)

    def show(s, j):
        if j.get("err"):
            s.ml.configure(text=s.app.t("rb_denied"), text_color=RED)
            return
        s.path, s.items = j.get("p", ""), j.get("items", [])
        s.pl.configure(text=s.path or "...")
        s.lb.delete(0, "end")
        for n, size, d in s.items:
            s.lb.insert("end", ("▸ " + n) if d else f"    {n}   ({human(size)})")
        s.ml.configure(text=s.app.t("rb_saved"), text_color=MUTED)

    def open(s):
        sel = s.lb.curselection()
        if sel:
            n, _, d = s.items[sel[0]]
            s.go(s.full(n)) if d else s.v.download(s.full(n))

    def download(s):
        for i in s.lb.curselection():
            n, _, d = s.items[i]
            if not d:
                s.v.download(s.full(n))


class ContactDialog(ctk.CTkToplevel):
    """Name, color and photo for one contact (changes are applied only on Save)."""

    def __init__(s, app, c):
        super().__init__(app)
        s.app, s.c, s.photo, s.drop = app, c, None, False
        s.color = app.ccolor(c)
        s.title(app.t("ct_edit"))
        s.geometry("500x640")
        s.configure(fg_color=CARD)
        s.transient(app)
        s.pv = ctk.CTkLabel(s, text="")
        s.pv.pack(pady=(24, 4))
        i = c["id"]
        ctk.CTkLabel(s, text=f"{i[:3]} {i[3:6]} {i[6:]}", font=F(13, False, True), text_color=MUTED).pack()
        body = ctk.CTkFrame(s, fg_color="transparent")
        body.pack(fill="x", padx=28, pady=(14, 0))
        ctk.CTkLabel(body, text=app.t("ct_name"), font=F(13, True), text_color=TXT, anchor=app.A).pack(fill="x", pady=(0, 6))
        s.name = app.entry(body, app.t("name_ph"))
        s.name.insert(0, c["name"])
        s.name.bind("<KeyRelease>", lambda e: s.draw())
        ctk.CTkLabel(body, text=app.t("ct_color"), font=F(13, True), text_color=TXT, anchor=app.A).pack(fill="x", pady=(10, 6))
        r = ctk.CTkFrame(body, fg_color="transparent")
        r.pack(fill="x")
        for col in ACCENTS:
            ctk.CTkButton(r, text="", width=34, height=34, corner_radius=17, fg_color=col, hover_color=mix(col, "#000000", .15),
                          command=lambda col=col: s.setc(col)).pack(side=app.S, padx=3)
        ctk.CTkButton(r, text="+", font=F(18), width=34, height=34, corner_radius=17, fg_color=FIELD, text_color=TXT,
                      hover_color=LINE, border_width=1, border_color=LINE, command=s.custom).pack(side=app.S, padx=3)
        ctk.CTkLabel(body, text=app.t("ct_photo"), font=F(13, True), text_color=TXT, anchor=app.A).pack(fill="x", pady=(14, 6))
        pr = ctk.CTkFrame(body, fg_color="transparent")
        pr.pack(fill="x")
        app.btn(pr, app.t("ct_pick"), s.pick_photo, "gho", 140).pack(side=app.S, padx=app.px(0, 8))
        app.btn(pr, app.t("ct_rm"), s.rm_photo, "gho", 120).pack(side=app.S)
        s.msg = ctk.CTkLabel(body, text="", font=F(12), text_color=RED, anchor=app.A)
        s.msg.pack(fill="x", pady=(8, 0))
        bot = ctk.CTkFrame(s, fg_color="transparent")
        bot.pack(side="bottom", fill="x", padx=28, pady=22)
        app.btn(bot, app.t("save"), s.save, "pri", 120).pack(side=app.S, padx=app.px(0, 8))
        app.btn(bot, app.t("later"), s.destroy, "gho", 100).pack(side=app.S, padx=app.px(0, 8))
        app.btn(bot, app.t("ct_del"), s.delete, "dan", 140).pack(side=app.S)
        s.draw()
        s.after(150, s.focus)

    def focus(s):
        try:
            s.lift()
            s.focus_force()
            s.grab_set()
        except Exception:
            pass

    def draw(s):
        c = {"id": s.c["id"], "name": s.name.get(), "color": s.color}
        im = contacts.render(c, 224, s.color, photo=s.photo, use_file=not s.drop and s.photo is None,
                             font=rp("Vazirmatn-Bold.ttf"))
        s.img = ctk.CTkImage(light_image=im, dark_image=im, size=(112, 112))
        s.pv.configure(image=s.img)

    def setc(s, col):
        s.color = col
        s.draw()

    def custom(s):
        v = cc.askcolor(color=s.color, title=s.app.t("custom"))[1]
        if v:
            s.setc(v)

    def pick_photo(s):
        p = filedialog.askopenfilename(parent=s, filetypes=[(s.app.t("ct_photo"), "*.png *.jpg *.jpeg *.bmp *.webp *.gif")])
        if not p:
            return
        try:
            s.photo, s.drop = contacts.make_avatar(p), False
            s.msg.configure(text="")
            s.draw()
        except Exception:
            flash(s.msg, s.app.t("ct_bad_img"), False)

    def rm_photo(s):
        s.photo, s.drop = None, True
        s.draw()

    def save(s):
        i = s.c["id"]
        contacts.update(i, name=s.name.get(), color=s.color)
        if s.photo is not None:
            contacts.save_avatar(i, s.photo)
        elif s.drop:
            contacts.remove_avatar(i)
        s.destroy()
        s.app.refresh()

    def delete(s):
        contacts.delete(s.c["id"])
        s.destroy()
        s.app.refresh()


class SessionBar(ctk.CTkToplevel):
    """Always-visible banner while someone is connected to this computer, with a disconnect button."""

    def __init__(s, app, name):
        super().__init__(app)
        s.overrideredirect(True)
        s.attributes("-topmost", True)
        s.configure(fg_color=app.ac)
        f = ctk.CTkFrame(s, corner_radius=0, fg_color=CARD)
        f.pack(padx=2, pady=2)
        ctk.CTkLabel(f, text="●", font=F(14), text_color=RED).pack(side=app.S, padx=app.px(14, 6), pady=8)
        ctk.CTkLabel(f, text=app.t("bar_live").format(name=name), font=F(12, True), text_color=TXT).pack(side=app.S)
        s.nl = ctk.CTkLabel(f, text="", font=F(11), text_color=MUTED)
        s.nl.pack(side=app.S, padx=10)
        b = app.btn(f, app.t("bar_end"), lambda: app.host and app.host.kick(), "dan", 110)
        b.configure(height=30)
        b.pack(side=app.S, padx=10, pady=6)
        s.update_idletasks()
        s.geometry(f"+{(s.winfo_screenwidth() - s.winfo_reqwidth()) // 2}+6")

    def note(s, text):
        s.nl.configure(text=text)


def load_font():
    for f in FONT_FILES:
        try:
            ctypes.windll.gdi32.AddFontResourceExW(rp(f), 0x10, 0)  # FR_PRIVATE: this process only
        except Exception:
            pass


def main():
    a = sys.argv[1:]
    if a[:1] == ["--service"]:  # started by the Service Control Manager
        winsvc.run_service()
        return
    if a[:1] == ["--agent"]:  # started by the service inside the user's session
        winsvc.run_agent()
        return
    if a[:1] == ["--svc-uninstall"]:  # used by the uninstaller
        try:
            winsvc.uninstall()
        except Exception:
            pass
        return
    if a[:1] != ["--svc-setup"] and not core.single_instance():
        core.message_box("RasaDesk", "RasaDesk is already running.\nراسا دسک در حال اجراست.", 0x40)
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
    load_font()
    App().mainloop()


if __name__ == "__main__":
    main()
