# Security policy

## Reporting a vulnerability
Please **do not open a public issue**. Email the maintainers privately (add your security contact address here) or use
GitHub's "Report a vulnerability" (Security → Advisories) feature. Include the version, steps to reproduce and impact.

## Security model
- **Password mode:** SPAKE2 over Ed25519 (library `spake2`) with mutual key confirmation. The password is never sent;
  an attacker, including the relay, gets one online guess per attempt. 5 failures in 60 s lock the host for 5 minutes.
- **Approval mode (no password):** the channel is encrypted but has no shared secret to authenticate it. A 6-digit
  verification code derived from the session key is shown on both screens; **comparing it is what defeats a malicious relay.**
- **Session:** AES-256-GCM, fresh key per session, directional counter nonces; replayed/reordered/reflected frames are rejected.
- **Files:** size cap, SHA-256 verification, sanitized names, never overwrites, `.part` files removed on failure; the
  viewer accepts only files it requested; the host can disable transfer and clipboard.
- **Service:** installs only from Program Files by an administrator; its config is readable only by SYSTEM and
  Administrators; file access runs as the logged-on user; approval prompts appear only on the user's own desktop and
  approval-only requests are refused when nobody is present.

## Known limitations
- Not independently audited; no formal penetration test yet.
- Relay metadata (who connects to which ID, when) is visible to the relay operator; use TLS and a private network.
- The relay has a global connection cap but no per-IP rate limiting yet.
- Approval mode is vulnerable to a malicious relay if users do not compare the code.
- `spake2` is pure Python (no constant-time guarantee).
- In service mode the approval dialog is shown by a SYSTEM-owned process on the user's desktop (protected by UIPI);
  running it as the user would be stronger.
- Installers are unsigned unless you sign them (use a code-signing certificate).

## Repository hygiene
Never commit certificates, private keys, signing certificates, `.env` files, or runtime data (see `.gitignore`).
Enable on GitHub: 2FA for all members, branch protection on `main`, secret scanning + push protection, Dependabot alerts.
