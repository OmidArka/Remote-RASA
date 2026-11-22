"""RasaDesk self-test: verifies the real SPAKE2 library + RasaDesk's handshake helpers on THIS machine.
Run:  py selftest.py"""
import hashlib, os, time
from spake2 import SPAKE2_A, SPAKE2_B
import core

DID = "123456789"
ok = True


def check(name, cond):
    global ok
    ok &= bool(cond)
    print(("PASS  " if cond else "FAIL  ") + name)


def handshake(pw_viewer, pw_host):
    a = SPAKE2_A(pw_viewer, idA=core.IDA, idB=core.idb(DID))
    b = SPAKE2_B(pw_host, idA=core.IDA, idB=core.idb(DID))
    ma, mb = a.start(), b.start()
    return a.finish(mb), b.finish(ma), ma, mb


t = time.time()
pw = core.derive("CorrectPass1", DID)
print(f"derive() took {time.time() - t:.2f}s")

t = time.time()
ka, kb, ma, mb = handshake(pw, pw)
print(f"SPAKE2 round took {(time.time() - t) * 1000:.0f} ms, message sizes {len(ma)}/{len(mb)} bytes")
check("same password -> same shared key", ka == kb and len(ka) == 32)
ka2, kb2, _, _ = handshake(pw, core.derive("WrongPass99", DID))
check("wrong password -> different keys", ka2 != kb2)
check("fresh randomness every run", handshake(pw, pw)[0] != ka)

# RasaDesk's own key schedule and confirmation tags
tr = core.transcript([ma, ma], [mb, mb])
sv, cv, ch = core.derive_keys(ka, tr)
sv2, cv2, ch2 = core.derive_keys(kb, tr)
check("both sides derive identical session keys", (sv, cv, ch) == (sv2, cv2, ch2))
check("viewer and host confirmation tags differ", core.tag(cv, tr) != core.tag(ch, tr))
a, b = core.Chan(sv, 1, 2), core.Chan(sv2, 2, 1)
check("encrypted channel round-trip", b.open(a.seal(b"hello")) == b"hello")

# framing
parts = [os.urandom(33), os.urandom(33)]
check("framing round-trip", core.unpk(core.pk(*parts), 2) == parts)
try:
    core.unpk(b"\x00\x05ab", 1)
    check("malformed framing rejected", False)
except ValueError:
    check("malformed framing rejected", True)

check("verification code is 6 digits and equal on both sides", len(core.sas_code(sv)) == 6 and core.sas_code(sv) == core.sas_code(sv2))
check("file-name sanitizer blocks paths and device names", core.safe_name("..\\..\\con.txt") == "_con.txt" and core.safe_name("a:b?.txt") == "a_b_.txt")
check("approval-mode secret is stable", core.open_secret(DID) == core.open_secret(DID) and core.open_secret(DID) != core.open_secret("987654321"))

print("\nALL TESTS PASSED" if ok else "\nSOME TESTS FAILED")
input("Press Enter to exit...")
