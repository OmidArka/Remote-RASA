"""RasaDesk relay server | Amn Negar Rasa
Forwards encrypted bytes between a viewer and a host. It holds no keys and cannot read sessions.

Run:        python server.py
Env vars:   RASA_HOST (default 0.0.0.0)  RASA_PORT (default 8765)
            RASA_CERT / RASA_KEY  -> serve wss:// (TLS) directly
"""
import asyncio, json, os, re, ssl
import websockets

ID = re.compile(r"\d{9}")
MAX_CONN = 2000
hosts, pair, conns = {}, {}, set()


async def handler(ws):
    if len(conns) >= MAX_CONN:
        await ws.close(1013)
        return
    conns.add(ws)
    me, bad = None, 0
    try:
        async for m in ws:
            if isinstance(m, str):
                if len(m) > 256:
                    break
                try:
                    d = json.loads(m)
                except ValueError:
                    break
                t, i = (d.get("t"), str(d.get("id") or d.get("target") or "")) if isinstance(d, dict) else (None, "")
                if not ID.fullmatch(i):
                    break
                if t == "reg" and me is None and ws not in pair:
                    if i in hosts:  # never let a newcomer take over a live ID
                        break
                    me, hosts[i] = i, ws
                elif t == "conn" and me is None and ws not in pair:
                    h = hosts.get(i)
                    if h is None or h in pair:
                        bad += 1
                        if bad >= 5:  # stop ID scanning
                            break
                        await ws.send('{"t":"err"}')
                        continue
                    pair[ws], pair[h] = h, ws
                    await ws.send('{"t":"ok"}')
                else:
                    break
            elif ws in pair:
                try:
                    await pair[ws].send(m)
                except websockets.ConnectionClosed:
                    pass
    except websockets.ConnectionClosed:
        pass
    finally:
        conns.discard(ws)
        if me and hosts.get(me) is ws:
            del hosts[me]
        peer = pair.pop(ws, None)
        if peer:
            pair.pop(peer, None)
            try:
                await peer.send('{"t":"bye"}')
            except websockets.ConnectionClosed:
                pass


async def main():
    ctx = None
    if os.environ.get("RASA_CERT"):
        ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ctx.load_cert_chain(os.environ["RASA_CERT"], os.environ.get("RASA_KEY"))
    host, port = os.environ.get("RASA_HOST", "0.0.0.0"), int(os.environ.get("RASA_PORT", "8765"))
    async with websockets.serve(handler, host, port, ssl=ctx, max_size=2 ** 22, max_queue=8):
        print(f"RasaDesk relay on {host}:{port} ({'wss' if ctx else 'ws'})")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
