# RasaDesk

Secure remote desktop for Windows by **Amn Negar Rasa** (امن‌نگر راسا). Persian-first (RTL) interface, English supported.
Persian documentation: [README.fa.md](README.fa.md).

> **Status:** early version (0.6). Not independently security-audited. The Windows service (UAC / lock screen support)
> is the newest and least-tested part. Do not use it for high-stakes systems before an independent audit.

## Features
- Two connection modes: **password** (PAKE-authenticated) or **ID only with on-screen approval** (6-digit verification code shown on both sides).
- End-to-end encryption: SPAKE2 (PAKE) → HKDF → AES-256-GCM with per-session keys, directional counters, replay/reflection rejection.
- File transfer (chunked, SHA-256 verified, safe names, size cap) and text clipboard sync; remote folder browser.
- Always-visible session banner on the shared computer, with a disconnect button.
- Recent connections with per-contact name, color and photo.
- Windows service for unattended access, UAC prompts, lock and sign-in screens.
- Dark/light themes, accent colors, text size, Persian and English (restart on language change).

## Architecture
```
 viewer app  ──wss──>  relay server  <──wss──  host app / Windows service agent
        \__________ end-to-end encrypted session (the relay only sees ciphertext) __________/
```
The relay (`server.py`) forwards opaque bytes between two peers. It holds no keys and cannot read sessions.

## Build (Windows)
Requires Python 3.10+ and [Inno Setup 6](https://jrsoftware.org/isdl.php).
1. Put `Vazirmatn-Regular.ttf`, `Vazirmatn-Bold.ttf` and `OFL.txt` next to `build.bat` (see `NOTICE.md`).
2. `py -m pip install -r requirements.txt`
3. `py selftest.py` — verifies the real SPAKE2 library on your machine.
4. `build.bat` → `installer\RasaDesk-Setup.exe` and `dist\RasaDeskServer.exe`.

The app is built as a **folder** (not one file) because Windows services cannot run from a PyInstaller one-file build.

## Run the relay
`RasaDeskServer.exe` (or `python server.py`), port 8765. Env: `RASA_HOST`, `RASA_PORT`, `RASA_CERT`, `RASA_KEY` (TLS).
Keep it on a private network/VPN, or behind TLS (Caddy/nginx) on a dedicated server. Never run it as SYSTEM on a desktop.

## Tests
`python tests/test_protocol.py && python tests/test_ui.py && python tests/test_contacts.py`
These run on Linux in CI with GUI/OS modules stubbed; they cover the protocol, file/clipboard handling, approval flow,
lockouts, hostile input, and every UI code path. They do **not** replace testing on real Windows.

## Security
See [SECURITY.md](SECURITY.md) for the threat model, known limitations and how to report a vulnerability.

## License
Proprietary — all rights reserved (see [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md)).
