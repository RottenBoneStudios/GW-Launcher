# gw_modpack_profile.py
from pathlib import Path
import json

GW_DIR = Path.home() / ".gwlauncher"
UI_PROFILES = GW_DIR / "ui_profiles.json"

def add_gatitosworld_profile():
    UI_PROFILES.parent.mkdir(parents=True, exist_ok=True)

    profile = {
        "name": "GatitosWorld ModPack",
        "name_locked": True,
        "username": "",
        "version": "1.21.1",
        "modloader": "fabric",
        "ram": 4096,
        "jvmFlags": [],
        "server": "na37.holy.gg",
        "port": 19431
    }

    if UI_PROFILES.exists():
        try:
            profiles = json.loads(UI_PROFILES.read_text(encoding="utf-8"))
        except Exception:
            profiles = {}
    else:
        profiles = {}

    profiles[profile["name"]] = {k: v for k, v in profile.items() if k != "name"}

    UI_PROFILES.write_text(json.dumps(profiles, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Perfil '{profile['name']}' agregado/actualizado en {UI_PROFILES}")

if __name__ == "__main__":
    add_gatitosworld_profile()
