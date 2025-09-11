# discord_rpc.py
import os, time, threading
try:
    from pypresence import Presence
except Exception:
    Presence = None

class DiscordRPC:
    def __init__(self, client_id: str | None = None):
        self.client_id = client_id or os.getenv("DISCORD_CLIENT_ID", "1397615014478872727")
        self.rpc = None
        self._stop = False
        self._lock = threading.Lock()
        self._last = None
    def start(self):
        if Presence is None or self.rpc is not None:
            return
        def run():
            try:
                self.rpc = Presence(self.client_id)
                self.rpc.connect()
                self.set_browsing()
                while not self._stop:
                    with self._lock:
                        if self._last:
                            self.rpc.update(**self._last)
                    time.sleep(15)
            except Exception:
                self.rpc = None
        threading.Thread(target=run, daemon=True).start()
    def stop(self):
        self._stop = True
        try:
            if self.rpc:
                self.rpc.clear()
                self.rpc.close()
        except Exception:
            pass
    def _set(self, **kw):
        payload = {
            "details": "Usando GW Launcher",
            "state": "¡Jugando Minecraft!",
            "start": int(time.time()),
            "large_image": "logo",
            "large_text": "GW Launcher"
        }
        payload.update(kw)
        with self._lock:
            self._last = payload
    def set_browsing(self):
        self._set()
    def set_minecraft(self):
        self._set()
