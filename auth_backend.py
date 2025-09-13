# auth_backend.py
from __future__ import annotations
import json, os, time, requests, uuid
from pathlib import Path
from typing import Any, Dict, Optional

GW_DIR: Path = Path.home() / ".gwlauncher"
ACCOUNTS_FILE: Path = GW_DIR / "accounts.json"

CLIENT_ID = "54fd49e4-2103-4044-9603-2b028c814ec3"

OAUTH_DEVICE_CODE = "https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode"
OAUTH_TOKEN = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"

XBOX_AUTH = "https://user.auth.xboxlive.com/user/authenticate"
XSTS_AUTH = "https://xsts.auth.xboxlive.com/xsts/authorize"
MC_LOGIN = "https://api.minecraftservices.com/authentication/login_with_xbox"
MC_PROFILE = "https://api.minecraftservices.com/minecraft/profile"

def _ensure_dir() -> None:
    GW_DIR.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        os.chmod(GW_DIR, 0o755)

def _read_json(p: Path, default: Any) -> Any:
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def _write_json(p: Path, data: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    if os.name == "posix":
        os.chmod(p, 0o644)

def list_accounts() -> Dict[str, Any]:
    return _read_json(ACCOUNTS_FILE, {})

def _save_accounts(data: Dict[str, Any]) -> None:
    _write_json(ACCOUNTS_FILE, data)

def get_account_by_name(name: str) -> Optional[Dict[str, Any]]:
    for aid, acc in list_accounts().items():
        if acc.get("name") == name:
            return {"id": aid, **acc}
    return None

def remove_account(account_id: str) -> None:
    data = list_accounts()
    if account_id in data:
        del data[account_id]
        _save_accounts(data)

def begin_device_login() -> Dict[str, str]:
    resp = requests.post(OAUTH_DEVICE_CODE, data={
        "client_id": CLIENT_ID,
        "scope": "XboxLive.signin offline_access"
    }, headers={"Content-Type": "application/x-www-form-urlencoded"})
    resp.raise_for_status()
    return resp.json()

def poll_device_login(device_code: str, interval: int = 3, timeout: int = 300) -> Dict[str, str]:
    start = time.time()
    cur = max(1, int(interval))
    while True:
        if time.time() - start >= timeout:
            raise RuntimeError("Tiempo de espera agotado")
        time.sleep(cur)
        resp = requests.post(OAUTH_TOKEN, data={
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": CLIENT_ID,
            "device_code": device_code,
        })
        data = resp.json()
        if "error" in data:
            err = data["error"]
            if err in ("authorization_pending",):
                continue
            if err in ("slow_down",):
                cur += 1
                continue
            if err in ("authorization_declined", "expired_token", "bad_verification_code", "access_denied"):
                raise RuntimeError(f"Error en login: {data}")
            raise RuntimeError(f"Error en login: {data}")
        return data

def refresh_account(account_id: str) -> Dict[str, Any]:
    data = list_accounts()
    acc = data.get(account_id)
    if not acc:
        raise RuntimeError("Cuenta no encontrada")
    resp = requests.post(OAUTH_TOKEN, data={
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "refresh_token": acc["refresh_token"],
    })
    if resp.status_code != 200:
        raise RuntimeError("Error al refrescar token")
    tokens = resp.json()
    acc.update({
        "ms_access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", acc["refresh_token"]),
        "updated_at": int(time.time())
    })
    data[account_id] = acc
    _save_accounts(data)
    return {"id": account_id, **acc}

def _auth_xbox(ms_access_token: str) -> str:
    resp = requests.post(XBOX_AUTH, json={
        "Properties": {
            "AuthMethod": "RPS",
            "SiteName": "user.auth.xboxlive.com",
            "RpsTicket": f"d={ms_access_token}"
        },
        "RelyingParty": "http://auth.xboxlive.com",
        "TokenType": "JWT"
    }, headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    return resp.json()["Token"]

def _auth_xsts(xbl_token: str) -> tuple[str, str]:
    resp = requests.post(XSTS_AUTH, json={
        "Properties": {
            "SandboxId": "RETAIL",
            "UserTokens": [xbl_token]
        },
        "RelyingParty": "rp://api.minecraftservices.com/",
        "TokenType": "JWT"
    }, headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    data = resp.json()
    return data["Token"], data["DisplayClaims"]["xui"][0]["uhs"]

def _auth_minecraft(xsts_token: str, uhs: str) -> str:
    resp = requests.post(MC_LOGIN, json={
        "identityToken": f"XBL3.0 x={uhs};{xsts_token}"
    }, headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    return resp.json()["access_token"]

def _get_mc_profile(mc_token: str) -> Dict[str, str]:
    resp = requests.get(MC_PROFILE, headers={"Authorization": f"Bearer {mc_token}"})
    resp.raise_for_status()
    return resp.json()

def complete_device_login(device_code: str, interval: int = 3, timeout: int = 300) -> Dict[str, Any]:
    ms_tokens = poll_device_login(device_code, interval, timeout)
    ms_access = ms_tokens["access_token"]
    xbl_token = _auth_xbox(ms_access)
    xsts_token, uhs = _auth_xsts(xbl_token)
    mc_token = _auth_minecraft(xsts_token, uhs)
    profile = _get_mc_profile(mc_token)
    acc_id = profile["id"]
    acc = {
        "name": profile["name"],
        "uuid": profile["id"],
        "ms_access_token": ms_access,
        "refresh_token": ms_tokens["refresh_token"],
        "mc_access_token": mc_token,
        "updated_at": int(time.time())
    }
    data = list_accounts()
    data[acc_id] = acc
    _save_accounts(data)
    return {"id": acc_id, **acc}

def get_login_options_for_username(username: str) -> Optional[Dict[str, str]]:
    acc = get_account_by_name(username)
    if not acc:
        return None
    try:
        acc = refresh_account(acc["id"])
    except Exception:
        pass
    return {
        "username": acc["name"],
        "uuid": acc["uuid"],
        "token": acc.get("mc_access_token") or acc["ms_access_token"]
    }
