# Third-party components

RasaDesk uses the components below. Licenses are listed from general knowledge; **verify each project's current
license before commercial distribution** and keep the required notices with your installer.

| Component | Used for | License (verify) |
|---|---|---|
| spake2 | PAKE authentication (SPAKE2) | MIT |
| cryptography | AES-GCM, HKDF, PBKDF2 | Apache-2.0 / BSD |
| websockets | transport | BSD-3-Clause |
| mss | screen capture | MIT |
| PyAutoGUI, pyperclip | input injection, clipboard | BSD-3-Clause |
| Pillow | images, avatars | HPND |
| customtkinter | user interface | MIT |
| pywin32 | Windows service | PSF |
| PyInstaller (build tool) | packaging | GPL-2.0 with an exception that allows commercial/closed bundled apps |
| Inno Setup (build tool) | installer | Inno Setup License (free, incl. commercial use) |
| **Vazirmatn** font | UI font | SIL Open Font License 1.1 — **keep OFL.txt with the font files** |

Not included in this repository (add them yourself before building): `Vazirmatn-Regular.ttf`, `Vazirmatn-Bold.ttf`, `OFL.txt`.
Do not add fonts you do not have a redistribution/embedding license for.

The logo (`logo.png`, `rasadesk.ico`) is the property of Amn Negar Rasa. A copyright notice does not protect a brand
name or logo as a trademark; register them separately if you publish.
