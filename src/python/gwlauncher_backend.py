from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import threading
import sys
import uuid
from functools import partial
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import minecraft_launcher_lib as mll
from minecraft_launcher_lib import utils

# ──────────────────────────────────────────────────────────────────────────────
#  Splash: logo PNG centrado, inmóvil y siempre en primer plano
# ──────────────────────────────────────────────────────────────────────────────
class _SplashLogo:
    def __init__(self, image_path: str = "logo.png") -> None:
        self._root_ready = threading.Event()
        self._root: "tk.Tk | None" = None # type: ignore

        self._thread = threading.Thread(
            target=self._gui_thread, args=(image_path,), daemon=True
        )
        self._thread.start()
        self._root_ready.wait()

    def close(self) -> None:
      if self._root:
          self._root.after(0, self._root.quit)
      self._thread.join()


    # ------------------------------------------------------------------
    #  Se ejecuta en el hilo-GUI: muestra la imagen y espera _stop
    # ------------------------------------------------------------------
    def _gui_thread(self, image_path: str) -> None:
      import tkinter as tk
      from pathlib import Path

      img_file = (Path(__file__).with_suffix("").parent / image_path).resolve()
      if not img_file.exists():
          self._root_ready.set()
          return

      root = tk.Tk()
      root.overrideredirect(True)
      root.attributes("-topmost", True)

      bg = "#010101"
      try:
          root.configure(bg=bg)
          root.wm_attributes("-transparentcolor", bg)
      except tk.TclError:
          pass

      img = tk.PhotoImage(file=str(img_file))
      w, h = img.width(), img.height()
      sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
      root.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")

      tk.Label(root, image=img, borderwidth=0, bg=bg).pack()

      self._root = root
      self._root_ready.set()
      root.mainloop()
      root.destroy()

# ──────────────────────────────────────────────────────────────────────────────
#  Parches de rendimiento
# ──────────────────────────────────────────────────────────────────────────────
def _patch_downloader(buffer_size: int = 1 << 20, max_workers: int = 64) -> None:
    try:
        from minecraft_launcher_lib import _helper as _mll_helper
        _mll_helper.download_file = partial(
            _mll_helper.download_file,
            buffer_size=buffer_size,
        )
    except Exception:
        pass

    import concurrent.futures as _cf
    _orig_init = _cf.ThreadPoolExecutor.__init__

    def _patched_init(self, max_workers: int = max_workers, *a, **kw):
        return _orig_init(self, max_workers, *a, **kw)

    _cf.ThreadPoolExecutor.__init__ = _patched_init

_patch_downloader()

# ──────────────────────────────────────────────────────────────────────────────
#  Rutas y persistencia
# ──────────────────────────────────────────────────────────────────────────────
GW_DIR: Path = Path.home() / ".gwlauncher"
VERSIONS_DIR: Path = GW_DIR / "versions"
INSTANCES_DIR: Path = GW_DIR / "instances"
_PROFILES_FILE = GW_DIR / "profiles.json"

def _ensure_dir() -> None:
    for d in (GW_DIR, VERSIONS_DIR, INSTANCES_DIR):
        d.mkdir(parents=True, exist_ok=True)

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

# ──────────────────────────────────────────────────────────────────────────────
#  Instalación
# ──────────────────────────────────────────────────────────────────────────────
ModLoader = Literal["forge", "fabric", ""]

def _installed_ids() -> List[str]:
    _ensure_dir()
    return [v["id"] for v in utils.get_installed_versions(str(GW_DIR))]

def install_version(version: str) -> None:
    _ensure_dir()
    if version in _installed_ids():
        return
    mll.install.install_minecraft_version(version, str(GW_DIR))

def install_modloader(loader: ModLoader, version: str) -> str:
    _ensure_dir()

    if loader == "forge":
        fv = mll.forge.find_forge_version(version)
        if not fv or not mll.forge.supports_automatic_install(fv):
            return version
        mid = mll.forge.forge_to_installed_version(fv)
        if mid not in _installed_ids():
            mll.forge.install_forge_version(fv, str(GW_DIR))
        return mid

    if loader == "fabric":
        mll.fabric.install_fabric(version, str(GW_DIR))
        facs = [vid for vid in _installed_ids() if version in vid and "fabric" in vid.lower()]
        return facs[-1] if facs else version

    return version

# ──────────────────────────────────────────────────────────────────────────────
#  Construcción de comando
# ──────────────────────────────────────────────────────────────────────────────
def _offline_options(username: str) -> mll.types.MinecraftOptions:  # type: ignore[attr-defined]
    u = uuid.uuid3(uuid.NAMESPACE_DNS, username)
    return {"username": username, "uuid": str(u).replace("-", ""), "token": "0"}

def _detect_java_version() -> int:
    try:
        java = utils.get_java_executable()
        out = subprocess.check_output([java, "-version"], stderr=subprocess.STDOUT, text=True)
        m = re.search(r'"(\d+)', out)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return 8

def _jvm_optimize_args(java_version: int | None = None) -> List[str]:
    java_version = java_version or _detect_java_version()
    base = [
        "-XX:+UnlockExperimentalVMOptions",
        "-XX:+DisableExplicitGC",
        "-XX:+AlwaysPreTouch",
    ]
    if java_version >= 17:
        base += ["-XX:+UseZGC"]
    else:
        base += ["-XX:+UseG1GC", "-XX:+UseStringDeduplication"]
        cpu = os.cpu_count() or 2
        base += [
            f"-XX:ParallelGCThreads={max(1, cpu - 1)}",
            f"-XX:ConcGCThreads={max(1, cpu // 2)}",
            "-XX:G1NewSizePercent=20",
            "-XX:G1ReservePercent=20",
            "-XX:MaxGCPauseMillis=50",
        ]
    return base

def _extract_flag_key(flag: str) -> str:
    return flag.split("=", 1)[0]

def _is_gc_flag(flag: str) -> bool:
    return flag.startswith("-XX:+Use") and flag.endswith("GC")

def build_command(
    version_id: str,
    username: str,
    *,
    game_dir: Path,
    ram: Optional[int] = None,
    jvm_args: Optional[List[str]] = None,
    optimize: bool = False,
) -> List[str]:
    opts = _offline_options(username)
    opts["gameDirectory"] = str(game_dir)

    opt_flags = _jvm_optimize_args() if optimize else []
    opt_keys = {_extract_flag_key(f) for f in opt_flags}

    user_flags: List[str] = []
    if jvm_args:
        for f in jvm_args:
            if _extract_flag_key(f) in opt_keys:
                continue
            user_flags.append(f)

    gc_in_opt = next((f for f in opt_flags if _is_gc_flag(f)), None)
    if gc_in_opt:
        user_flags = [f for f in user_flags if not _is_gc_flag(f)]
    else:
        first_gc_seen = False
        filtered: List[str] = []
        for f in user_flags:
            if _is_gc_flag(f):
                if first_gc_seen:
                    continue
                first_gc_seen = True
            filtered.append(f)
        user_flags = filtered

    final_args = [*opt_flags, *user_flags]
    if ram is not None:
        final_args.append(f"-Xmx{ram}M")
    if final_args:
        opts["jvmArguments"] = final_args

    return mll.command.get_minecraft_command(version_id, str(GW_DIR), opts)

# ──────────────────────────────────────────────────────────────────────────────
#  Flujo principal
# ──────────────────────────────────────────────────────────────────────────────
def launch(
    version: str,
    username: str,
    *,
    ram: Optional[int] = None,
    loader: ModLoader = "",
    jvm_args: Optional[List[str]] = None,
    optimize: bool = False,
) -> None:
    splash = _SplashLogo()
    try:
        install_version(version)
        real_id = install_modloader(loader, version)

        game_dir = INSTANCES_DIR / real_id
        game_dir.mkdir(parents=True, exist_ok=True)
        save_profile(username, version)

        cmd = build_command(
            real_id,
            username,
            game_dir=game_dir,
            ram=ram,
            jvm_args=jvm_args,
            optimize=optimize,
        )
    finally:
        splash.close()
    subprocess.Popen(cmd, cwd=str(GW_DIR))

# ──────────────────────────────────────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────────────────────────────────────
def _parse_cli(argv: List[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="gwlauncher")
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("install", help="Instala una versión vanilla")
    i.add_argument("version")

    l = sub.add_parser("launch", help="Instala (si falta) y lanza un Minecraft")
    l.add_argument("version")
    l.add_argument("username")
    l.add_argument("--ram", type=int, help="Memoria máxima en MiB (p. ej. 4096)")
    l.add_argument("--modloader", choices=["", "forge", "fabric"], default="")
    l.add_argument(
        "--jvm-arg", dest="jvm_args", action="append",
        metavar="ARG", help="Argumento JVM adicional (puede repetirse)"
    )
    l.add_argument("--optimize", action="store_true", help="Añade flags JVM rápidas")

    sub.add_parser("versions", help="Muestra las versiones instaladas")
    return p.parse_args(argv)

def _main() -> None:
    args = _parse_cli()

    if args.cmd == "install":
        splash = _SplashLogo()
        try:
            install_version(args.version)
        finally:
            splash.close()

    elif args.cmd == "launch":
        launch(
            args.version,
            args.username,
            ram=args.ram,
            loader=args.modloader,
            jvm_args=args.jvm_args,
            optimize=getattr(args, "optimize", False),
        )

    elif args.cmd == "versions":
        print("\n".join(sorted(_installed_ids())))
    else:
        sys.exit(1)

if __name__ == "__main__":
    _main()
