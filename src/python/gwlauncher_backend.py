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
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk, messagebox
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

def _show_error(title: str, msg: str) -> None:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(title, msg)
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
    if "fabric" in minecraft_version.lower():
        return 21

    parts = minecraft_version.split(".")
    version_nums = []
    for p in parts:
        try:
            version_nums.append(int(p))
        except ValueError:
            break

    if not version_nums:
        return 8

    major = version_nums[0]
    minor = version_nums[1] if len(version_nums) > 1 else 0

    if major == 1:
        if 8 <= minor <= 16:
            return 8
        elif 17 <= minor <= 19:
            return 17
        elif minor >= 20:
            return 21
    return 21

def download_java_runtime(java_version: int) -> Path:
    _ensure_dir()
    java_path = JAVA_DIR / str(java_version)

    if java_path.exists():
        bin_dir = java_path / "bin"
        if os.name == "nt":
            javaw = bin_dir / "javaw.exe"
            javaexe = bin_dir / "java.exe"
            if javaw.exists():
                return javaw
            if javaexe.exists():
                return javaexe
        else:
            javaexe = bin_dir / "java"
            if javaexe.exists():
                return javaexe

    java_urls = {
        8: {
            "Linux": "https://www.dropbox.com/scl/fi/a363ohfhydwwn1gfvgkhc/jdk-8u451-linux-x64.tar.gz?rlkey=rjf74dnl5sdg30bey86k8kndk&st=kzarvil0&dl=1",
            "Darwin": "https://www.dropbox.com/scl/fi/mu9j2thwts7f79r1k7t5t/jdk-8u451-macosx-x64.tar.gz?rlkey=58sfz30osfea6avid0v6skgi9&st=nntyp855&dl=1",
            "Windows": "https://www.dropbox.com/scl/fi/m14dal0l5k2d5x4anhuyf/jdk-8u451-windows-x64.zip?rlkey=2qshv0hq2a6i1e8s2te4mny5c&st=8zfqpd4p&dl=1",
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

    response = requests.get(url, stream=True, allow_redirects=True, timeout=60)
    response.raise_for_status()
    temp_file = JAVA_DIR / f"java_{java_version}.{package_type}"
    with open(temp_file, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    extract_path = JAVA_DIR / f"java_{java_version}_temp"
    extract_path.mkdir(parents=True, exist_ok=True)
    if package_type == "zip":
        with zipfile.ZipFile(temp_file, "r") as zf:
            zf.extractall(extract_path)
    else:
        with tarfile.open(temp_file, "r:gz") as tf:
            tf.extractall(extract_path)
    extracted_dir = next(extract_path.iterdir(), None)
    if not extracted_dir:
        raise RuntimeError(f"No se extrajeron archivos para Java {java_version}")
    shutil.move(str(extracted_dir), java_path)
    temp_file.unlink(missing_ok=True)
    shutil.rmtree(extract_path, ignore_errors=True)

    bin_dir = java_path / "bin"
    if os.name == "nt":
        javaw = bin_dir / "javaw.exe"
        javaexe = bin_dir / "java.exe"
        return javaw if javaw.exists() else javaexe
    else:
        javaexe = bin_dir / "java"
        os.chmod(javaexe, 0o755)
        return javaexe

# ──────────────────────────────────────────────────────────────────────────────
#  Instalación
# ──────────────────────────────────────────────────────────────────────────────
ModLoader = Literal["forge", "fabric", ""]

def _dump_available_versions_json() -> None:
    _ensure_dir()

    def save_if_changed(data: Any, path: Path, label: str) -> None:
        new_json = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        if path.exists():
            current = path.read_text(encoding="utf-8")
            if current == new_json:
                print(f"[OK] Sin cambios en {label}: {path}")
                return
        path.write_text(new_json, encoding="utf-8")
        if os.name == "posix":
            os.chmod(path, 0o644)
        print(f"[OK] {label} actualizado: {path}")

    # Vanilla
    try:
        all_versions = mll.utils.get_version_list()
    except AttributeError:
        all_versions = mll.utils.get_available_versions()
    save_if_changed(all_versions, GW_DIR / "versiones-minecraft.json", "Vanilla")

    # Forge
    try:
        forge_versions = mll.forge.list_forge_versions()
        save_if_changed(forge_versions, GW_DIR / "versiones-forge.json", "Forge")
    except Exception as e:
        print(f"[WARN] No se pudo obtener Forge: {e}")

    # Fabric
    try:
        fabric_versions = mll.fabric.get_all_minecraft_versions()
        save_if_changed(fabric_versions, GW_DIR / "versiones-fabric.json", "Fabric")
    except Exception as e:
        print(f"[WARN] No se pudo obtener Fabric: {e}")

    # Quilt (opcional)
    try:
        quilt_versions = mll.quilt.get_all_minecraft_versions()
        save_if_changed(quilt_versions, GW_DIR / "versiones-quilt.json", "Quilt")
    except Exception as e:
        print(f"[INFO] Quilt no disponible o falló: {e}")

def _installed_ids() -> List[str]:
    _ensure_dir()
    return [v["id"] for v in utils.get_installed_versions(str(GW_DIR))]

def install_version(version: str) -> None:
    _ensure_dir()
    installed = _installed_ids()
    print(f"[DEBUG] Instalados (vanilla): {installed}")
    if version in installed:
        print(f"[DEBUG] Versión vanilla '{version}' ya instalada")
        return
    try:
        print(f"[DEBUG] Instalando vanilla {version!r}...")
        mll.install.install_minecraft_version(version, str(GW_DIR))
    except Exception as e:
        print(f"[ERROR] Falló instalación vanilla {version!r}: {e}")
        _show_error("Error Vanilla", f"No se pudo instalar la versión vanilla {version}:\n{e}")
        raise

def install_modloader(loader: ModLoader, version: str) -> str:
    _ensure_dir()

    if loader == "forge":
        print(f"[DEBUG] Intentando Forge para {version!r}")
        fv = mll.forge.find_forge_version(version)
        print(f"[DEBUG] find_forge_version {fv!r}")
        if not fv or not mll.forge.supports_automatic_install(fv):
            msg = f"No existe instalador automático de Forge para la versión {version}"
            print(f"[WARN] {msg}")
            _show_error("Forge No Encontrado", msg)
            return version
        mid = mll.forge.forge_to_installed_version(fv)
        print(f"[DEBUG] Forge build seleccionado: {mid!r}")
        if mid not in _installed_ids():
            try:
                print(f"[DEBUG] Instalando Forge {fv!r} para {version!r}...")
                mll.forge.install_forge_version(fv, str(GW_DIR))
            except Exception as e:
                print(f"[ERROR] Falló instalación de Forge {fv!r}: {e}")
                _show_error("Error Forge", f"No se pudo instalar Forge {fv}:\n{e}")
                return version
        return mid

    if loader == "fabric":
        print(f"[DEBUG] Intentando Fabric para {version!r}")
        try:
            mll.fabric.install_fabric(version, str(GW_DIR))
        except Exception as e:
            msg = f"No se pudo instalar Fabric para la versión {version}: {e}"
            print(f"[ERROR] {msg}")
            _show_error("Error Fabric", msg)
            return version
        facs = [vid for vid in _installed_ids() if version in vid and "fabric" in vid.lower()]
        print(f"[DEBUG] Builds Fabric instalados tras instalación: {facs}")
        chosen = facs[-1] if facs else version
        if chosen == version:
            msg = f"No se encontró build Fabric para {version}"
            print(f"[WARN] {msg}")
            _show_error("Fabric No Encontrado", msg)
        return chosen
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

    if java_version == 8:
        return [
            "-XX:+UseG1GC",
            "-XX:G1NewSizePercent=30",
            "-XX:G1MaxNewSizePercent=40",
            "-XX:G1HeapRegionSize=16M",
            "-XX:G1ReservePercent=20",
            "-XX:MaxGCPauseMillis=50",
            "-XX:G1HeapWastePercent=5",
            "-XX:G1MixedGCCountTarget=4",
            "-XX:+UnlockExperimentalVMOptions",
            "-XX:+PerfDisableSharedMem",
            "-XX:+AlwaysPreTouch"
        ]
    elif java_version == 17:
        return [
            "-XX:+UseZGC",
            "-XX:+UnlockExperimentalVMOptions",
            "-XX:+DisableExplicitGC",
            "-XX:+AlwaysPreTouch"
        ]
    elif java_version == 21:
        return [
            "--enable-preview",
            "-XX:+UseZGC",
            "-XX:+UnlockExperimentalVMOptions",
            "-XX:+DisableExplicitGC",
            "-XX:+AlwaysPreTouch"
        ]
    return []

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
    print(f"[DEBUG] Usando Java {java_version} en {java_executable}")

    parts = version_id.split('.')
    use_opt = optimize
    if len(parts) >= 2 and parts[0] == '1' and parts[1] in ('14','15'):
        print(f"[WARN] Desactivando optimize para versión {version_id} (incompatible con Java 8)")
        use_opt = False

    opt_flags = _jvm_optimize_args(java_version) if use_opt else []
    user_flags: List[str] = jvm_args or []

    if user_flags:
        print(f"[INFO] Flags del jugador detectadas, omitiendo JVM optimize flags")
        opt_flags = []

    print(f"[DEBUG] JVM Optimize Flags: {opt_flags}")
    print(f"[DEBUG] JVM User Flags (raw): {user_flags}")

    opt_keys = {_extract_flag_key(f) for f in opt_flags}
    filtered_user_flags: List[str] = []
    seen_keys = set()
    for f in user_flags:
        key = _extract_flag_key(f)
        if key in seen_keys or key in opt_keys:
            print(f"[DEBUG] Ignorando flag duplicada: {f}")
            continue
        seen_keys.add(key)
        filtered_user_flags.append(f)

    user_flags = filtered_user_flags
    print(f"[DEBUG] JVM User Flags (filtered): {user_flags}")

    if not use_opt and user_flags:
        seen_gc = False
        filtered = []
        for f in user_flags:
            if _is_gc_flag(f):
                if seen_gc:
                    print(f"[DEBUG] Eliminando GC flag extra: {f}")
                    continue
                seen_gc = True
            filtered.append(f)
        user_flags = filtered

    final_args = opt_flags + user_flags
    if ram is not None:
        final_args.append(f"-Xmx{ram}M")
    if final_args:
        opts["jvmArguments"] = final_args

    command = mll.command.get_minecraft_command(version_id, str(GW_DIR), opts)
    command[0] = str(java_executable)

    print(f"[DEBUG] Comando final: {command}")
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

        _wait_for_version(real_id)

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

def _wait_for_version(version_id: str) -> None:
    version_path = VERSIONS_DIR / version_id
    expected_jar = version_path / f"{version_id}.jar"

    root = tk.Tk()
    root.title("Descargando Minecraft")
    root.resizable(False, False)
    tk.Label(root, text=f"Descargando versión {version_id}, por favor espera…").pack(padx=20, pady=(10, 0))
    pb = ttk.Progressbar(root, mode="indeterminate", length=300)
    pb.pack(padx=20, pady=10)
    pb.start(50)

    def check():
        if expected_jar.exists():
            pb.stop()
            root.destroy()
        else:
            root.after(500, check)

    root.after(500, check)
    root.mainloop()

def launch_detached(cmd: list[str], cwd: str) -> None:
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        subprocess.Popen(cmd, cwd=cwd, creationflags=flags)
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
        _dump_available_versions_json()
        print("\n".join(sorted(_installed_ids())))
    else:
        sys.exit(1)

if __name__ == "__main__":
    _main()
