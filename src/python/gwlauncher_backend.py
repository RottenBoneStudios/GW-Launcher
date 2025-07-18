from __future__ import annotations

import argparse
import json
import os
import subprocess
import threading
import sys
import uuid
import requests
import tarfile
import zipfile
import shutil
from functools import partial
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import minecraft_launcher_lib as mll
from minecraft_launcher_lib import utils

def _hide_console() -> None:
    if os.name == "nt":
        try:
            import ctypes

            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception:
            pass
_hide_console()

# ──────────────────────────────────────────────────────────────────────────────
#  Splash: logo PNG centrado, inmóvil y siempre en primer plano
# ──────────────────────────────────────────────────────────────────────────────
class _SplashLogo:
    def __init__(self, image_path: str = "logo.png") -> None:
        self._root_ready = threading.Event()
        self._root: "tk.Tk | None" = None  # type: ignore

        self._thread = threading.Thread(
            target=self._gui_thread, args=(image_path,), daemon=True
        )
        self._thread.start()
        self._root_ready.wait()

    def close(self) -> None:
        if self._root:
            self._root.after(0, self._root.quit)
        self._thread.join()

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
JAVA_DIR: Path = GW_DIR / "java"
_PROFILES_FILE = GW_DIR / "profiles.json"


def _ensure_dir() -> None:
    for d in (GW_DIR, VERSIONS_DIR, INSTANCES_DIR, JAVA_DIR):
        d.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            os.chmod(d, 0o755)


def _load_profiles() -> Dict[str, Any]:
    if not _PROFILES_FILE.exists():
        return {}
    try:
        return json.loads(_PROFILES_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_profiles(profiles: Dict[str, Any]) -> None:
    _PROFILES_FILE.write_text(json.dumps(profiles, indent=2), encoding="utf-8")
    if os.name == "posix":
        os.chmod(_PROFILES_FILE, 0o644)


def save_profile(username: str, version: str) -> None:
    profiles = _load_profiles()
    profiles[username] = {"last_version": version}
    _save_profiles(profiles)


# ──────────────────────────────────────────────────────────────────────────────
#  Gestión de versiones de Java
# ──────────────────────────────────────────────────────────────────────────────

def get_required_java_version(minecraft_version: str) -> int:
    version_parts = [int(x) for x in minecraft_version.split(".") if x.isdigit()]
    if not version_parts:
        return 8

    major, minor = version_parts[0], version_parts[1] if len(version_parts) > 1 else 0

    if major == 1:
        if minor <= 12:
            return 8
        elif minor <= 19:
            return 17
        else:
            return 21
    return 21


def download_java_runtime(java_version: int) -> Path:
    _ensure_dir()
    java_path = JAVA_DIR / str(java_version)

    if java_path.exists():
        java_executable = java_path / "bin" / ("java.exe" if os.name == "nt" else "java")
        if java_executable.exists():
            return java_executable

    java_urls = {
        8: {
            "Linux": "https://download1526.mediafire.com/s9v45nklqe7gml-OrsVbyyammR8oZ7AReMP2YkSFlbEmsqnOAyeQyamdJOx1xV1guy8Kpt9EJhIIXJweXNdK6859CQPyYp-eabomHIe5iG8C5dSMZpO2WE634y8ONx7SrMDzPcrd6h99uBeAFU8zDLunnHcOyNAtWOsCWDArEA/3wwy6tiuoyy1cz9/jdk-8u451-linux-x64.tar.gz",
            "Darwin": "https://download938.mediafire.com/ws8s9n3aasvg49N82Z_41TBEWCg1Fzg1DM22zDecgo3v4XGf91bLklbIVRxBdkxlyW4Y2E2KKuHYNPdGK7ZD-qcdtE3vYPdrIWvYmgHVHae0Ru_Tj9GuNQPmmPDluqgsHwF14oJ4oox6u47SQIYK4pKvL-tCW81fxSE8b7SgWA/jyshtko9ugr4ng0/jdk-8u451-macosx-x64.tar.gz",
            "Windows": "https://download856.mediafire.com/rpvmnbdxjrsgUIfNthinUvRztRP0qtER3fVrATgI25SzIXjpwm8rv-7hmnfBsX51Qqp6Exc0wDEm6nM8BORKn1cIMLb2J67yBtCn6ueBUKUCnNz0qyBstRiSYJ6z5utk7ijo0WzsYerYssWpUUqZm9uELIgUToxtqJo-UBPRXw/l739w5pvdy1n6jm/jdk-8u451-windows-x64.zip",
        },
        17: {
            "Linux": "https://download.oracle.com/java/17/archive/jdk-17.0.12_linux-x64_bin.tar.gz",
            "Darwin": "https://download.oracle.com/java/17/archive/jdk-17.0.12_macos-x64_bin.tar.gz",
            "Windows": "https://download.oracle.com/java/17/archive/jdk-17.0.12_windows-x64_bin.zip",
        },
        21: {
            "Linux": "https://download.oracle.com/java/21/latest/jdk-21_linux-x64_bin.tar.gz",
            "Darwin": "https://download.oracle.com/java/21/latest/jdk-21_macos-x64_bin.tar.gz",
            "Windows": "https://download.oracle.com/java/21/latest/jdk-21_windows-x64_bin.zip",
        },
    }

    ext_map = {"Windows": "zip", "Linux": "tar.gz", "Darwin": "tar.gz"}
    system = "Windows" if os.name == "nt" else "Linux" if os.name == "posix" else "Darwin"

    url = java_urls[java_version][system]
    package_type = ext_map[system]

    try:
        response = requests.get(url, stream=True, allow_redirects=True, timeout=60)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"No se pudo descargar Java {java_version} para {system}: {exc}")

    temp_file = JAVA_DIR / f"java_{java_version}.{package_type}"
    with open(temp_file, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    extract_path = JAVA_DIR / f"java_{java_version}_temp"
    extract_path.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        os.chmod(extract_path, 0o755)

    try:
        if package_type == "zip":
            with zipfile.ZipFile(temp_file, "r") as zf:
                zf.extractall(extract_path)
        else:
            with tarfile.open(temp_file, "r:gz") as tf:
                tf.extractall(extract_path)

        extracted_dir = next(extract_path.iterdir(), None)
        if not extracted_dir:
            raise RuntimeError(f"No se extrajeron archivos para Java {java_version}")

        if os.name == "posix":
            os.chmod(extracted_dir, 0o755)
        shutil.move(str(extracted_dir), java_path)
    finally:
        temp_file.unlink(missing_ok=True)
        shutil.rmtree(extract_path, ignore_errors=True)

    java_executable = java_path / "bin" / ("java.exe" if os.name == "nt" else "java")
    if os.name != "nt":
        os.chmod(java_path / "bin", 0o755)
        os.chmod(java_executable, 0o755)

    return java_executable


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

def _offline_options(username: str) -> mll.types.MinecraftOptions:
    u = uuid.uuid3(uuid.NAMESPACE_DNS, username)
    return {"username": username, "uuid": str(u).replace("-", ""), "token": "0"}


def _detect_java_version(minecraft_version: str) -> int:
    return get_required_java_version(minecraft_version)


def _jvm_optimize_args(java_version: int | None = None) -> List[str]:
    java_version = java_version or 8
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
    if os.name == "posix":
        os.chmod(game_dir, 0o755)

    java_version = _detect_java_version(version_id)
    java_executable = download_java_runtime(java_version)

    opt_flags = _jvm_optimize_args(java_version) if optimize else []
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

    command = mll.command.get_minecraft_command(version_id, str(GW_DIR), opts)
    command[0] = str(java_executable)

    return command


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
        if os.name == "posix":
            os.chmod(game_dir, 0o755)
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
    launch_detached(cmd, str(GW_DIR))


def launch_detached(cmd: list[str], cwd: str) -> None:
    if os.name == "nt":
        DETACHED = 0x00000008 | 0x00000008
        subprocess.Popen(cmd, cwd=cwd, creationflags=DETACHED)
    else:
        subprocess.Popen(cmd, cwd=cwd, start_new_session=True)

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
