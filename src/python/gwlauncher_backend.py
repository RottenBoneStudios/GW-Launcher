"""gwlauncher_backend.py

Backend Python module for GWLauncher – a non-premium Minecraft launcher.

Features
--------
* Download / update Minecraft versions (`minecraft_launcher_lib.install.install_minecraft_version`)
* Optional Forge / Fabric / NeoForge support
* Construct and run the correct Java CLI.
* Persist last-played version per username in ~/.gwlauncher/profiles.json
* Provide a `versions` sub-command that prints Mojang's catalogue as JSON.
* Stand-alone CLI for quick testing:

    python gwlauncher_backend.py install 1.21.1
    python gwlauncher_backend.py launch 1.21.1 Alex --ram 4096

Folder layout
-------------
~/.gwlauncher          (Linux/macOS)
%USERPROFILE%\\.gwlauncher   (Windows)

Everything – assets, libraries, runtimes, logs & profiles – lives inside.

Copyright 2025.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import minecraft_launcher_lib as mll  # type: ignore

# --------------------------------------------------------------------------- #
#  Directory layout
# --------------------------------------------------------------------------- #

GW_DIR: Path = Path.home() / ".gwlauncher"
_PROFILES_FILE = GW_DIR / "profiles.json"


def _ensure_dir() -> None:
    """Create ~/.gwlauncher and sub-folders if they do not exist."""
    GW_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
#  Profiles helpers
# --------------------------------------------------------------------------- #


def _load_profiles() -> Dict[str, Any]:
    if not _PROFILES_FILE.exists():
        return {}
    try:
        return json.loads(_PROFILES_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_profiles(profiles: Dict[str, Any]) -> None:
    _PROFILES_FILE.write_text(json.dumps(profiles, indent=2), encoding="utf-8")


def save_profile(username: str, version: str) -> None:
    profiles = _load_profiles()
    profiles[username] = {"last_version": version}
    _save_profiles(profiles)


# --------------------------------------------------------------------------- #
#  Installation helpers
# --------------------------------------------------------------------------- #


def install_version(version: str) -> None:
    """Download or update *version* if missing."""
    _ensure_dir()
    print(f"[GWLauncher] Checking Minecraft {version}…", flush=True)
    mll.install.install_minecraft_version(version, str(GW_DIR))
    print("[GWLauncher] Version ready.")


ModLoader = Literal["forge", "fabric", "neoforge", ""]


def install_modloader(loader: ModLoader, version: str) -> None:
    """Install selected mod-loader on top of *version* (idempotent)."""
    if not loader:
        return

    print(f"[GWLauncher] Ensuring {loader} for {version}…", flush=True)
    if loader == "forge":
        mll.install.install_forge(version, str(GW_DIR))
    elif loader == "fabric":
        mll.install.install_fabric(version, str(GW_DIR))
    elif loader == "neoforge":
        mll.install.install_neoforge(version, str(GW_DIR))
    else:
        raise ValueError(f"Unknown mod-loader: {loader}")
    print("[GWLauncher] Mod-loader ready.")


def list_available_versions() -> List[Dict[str, str]]:
    """Return Mojang catalogue."""
    return mll.utils.get_available_versions(str(GW_DIR))


# --------------------------------------------------------------------------- #
#  Launch helpers
# --------------------------------------------------------------------------- #


def _offline_options(username: str) -> mll.types.MinecraftOptions:  # type: ignore
    user_uuid = uuid.uuid3(uuid.NAMESPACE_DNS, username)
    return {
        "username": username,
        "uuid": str(user_uuid).replace("-", ""),
        "token": "0",
    }


def build_command(
    version: str,
    username: str,
    *,
    ram: Optional[int] = None,
) -> List[str]:
    opts: Dict[str, Any] = _offline_options(username)
    if ram:
        opts["jvmArguments"] = [f"-Xmx{ram}M"]

    return mll.command.get_minecraft_command(version, str(GW_DIR), opts)


def launch(
    version: str,
    username: str,
    *,
    ram: Optional[int] = None,
    loader: ModLoader = "",
) -> None:
    install_version(version)
    install_modloader(loader, version)
    cmd = build_command(version, username, ram=ram)
    save_profile(username, version)

    print(f"[GWLauncher] Running: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(GW_DIR), check=False)


# --------------------------------------------------------------------------- #
#  CLI
# --------------------------------------------------------------------------- #


def _parse_cli(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GWLauncher backend CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_install = sub.add_parser("install", help="Install/update a version")
    p_install.add_argument("version")

    p_launch = sub.add_parser("launch", help="Launch a version offline")
    p_launch.add_argument("version")
    p_launch.add_argument("username")
    p_launch.add_argument("--ram", type=int)
    p_launch.add_argument(
        "--modloader", choices=["", "forge", "fabric", "neoforge"], default=""
    )

    sub.add_parser("versions", help="Print Mojang version list as JSON")

    return parser.parse_args(argv)


def _main() -> None:
    args = _parse_cli()

    if args.cmd == "install":
        install_version(args.version)
    elif args.cmd == "launch":
        launch(
            args.version,
            args.username,
            ram=args.ram,
            loader=args.modloader,
        )
    elif args.cmd == "versions":
        print(json.dumps(list_available_versions()))
    else:
        sys.exit(1)


if __name__ == "__main__":
    _main()