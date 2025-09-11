from __future__ import annotations
import argparse, json, os, subprocess, sys, uuid, requests, tarfile, zipfile, shutil, time
from functools import partial
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Callable
import minecraft_launcher_lib as mll
from minecraft_launcher_lib import utils

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

def _patch_downloader(buffer_size: int = 1 << 20, max_workers: int = 64) -> None:
    try:
        from minecraft_launcher_lib import _helper as _mll_helper
        _mll_helper.download_file = partial(_mll_helper.download_file, buffer_size=buffer_size)
    except Exception:
        pass
    import concurrent.futures as _cf
    _orig_init = _cf.ThreadPoolExecutor.__init__
    def _patched_init(self, max_workers: int = max_workers, *a, **kw):
        return _orig_init(self, max_workers, *a, **kw)
    _cf.ThreadPoolExecutor.__init__ = _patched_init

_patch_downloader()

def get_required_java_version(minecraft_version: str) -> int:
    lowered = minecraft_version.lower()
    if "fabric" in lowered or "quilt" in lowered:
        return 21
    parts = minecraft_version.split(".")
    nums = []
    for p in parts:
        try:
            nums.append(int(p))
        except ValueError:
            break
    if not nums:
        return 8
    major = nums[0]
    minor = nums[1] if len(nums) > 1 else 0
    if major == 1:
        if 8 <= minor <= 16:
            return 8
        elif 17 <= minor <= 19:
            return 17
        elif minor >= 20:
            return 21
    return 21

def download_java_runtime(java_version: int, progress_cb: Optional[Callable[[int, str], None]] = None) -> Path:
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
            "Linux": "https://www.dropbox.com/scl/fi/a363ohfhydwwn1gfvgkhc/jdk-8u451-linux-x64.tar.gz?dl=1",
            "Darwin": "https://www.dropbox.com/scl/fi/mu9j2thwts7f79r1k7t5t/jdk-8u451-macosx-x64.tar.gz?dl=1",
            "Windows": "https://www.dropbox.com/scl/fi/m14dal0l5k2d5x4anhuyf/jdk-8u451-windows-x64.zip?dl=1",
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
    total = int(response.headers.get("content-length", 0))
    temp_file = JAVA_DIR / f"java_{java_version}.{package_type}"
    downloaded = 0
    with open(temp_file, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if not chunk:
                continue
            f.write(chunk)
            downloaded += len(chunk)
            if total and progress_cb:
                percent = int(downloaded * 100 / total)
                progress_cb(percent // 2, f"Descargando Java {java_version}…")
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

ModLoader = Literal["forge", "fabric", "quilt", ""]

def _dump_available_versions_json() -> None:
    _ensure_dir()
    def save_if_changed(data: Any, path: Path, label: str) -> None:
        new_json = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        if path.exists():
            current = path.read_text(encoding="utf-8")
            if current == new_json:
                return
        path.write_text(new_json, encoding="utf-8")
        if os.name == "posix":
            os.chmod(path, 0o644)
    try:
        all_versions = mll.utils.get_version_list()
    except AttributeError:
        all_versions = mll.utils.get_available_versions()
    save_if_changed(all_versions, GW_DIR / "versiones-minecraft.json", "Vanilla")
    try:
        forge_versions = mll.forge.list_forge_versions()
        save_if_changed(forge_versions, GW_DIR / "versiones-forge.json", "Forge")
    except Exception:
        pass
    try:
        fabric_versions = mll.fabric.get_all_minecraft_versions()
        save_if_changed(fabric_versions, GW_DIR / "versiones-fabric.json", "Fabric")
    except Exception:
        pass
    try:
        quilt_versions = mll.quilt.get_all_minecraft_versions()
        save_if_changed(quilt_versions, GW_DIR / "versiones-quilt.json", "Quilt")
    except Exception:
        pass

def _installed_ids() -> List[str]:
    _ensure_dir()
    return [v["id"] for v in utils.get_installed_versions(str(GW_DIR))]

def install_version(version: str) -> None:
    _ensure_dir()
    installed = _installed_ids()
    if version in installed:
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
    if loader == "quilt":
        try:
            mll.quilt.install_quilt(version, str(GW_DIR))
        except Exception:
            return version
        quilts = [vid for vid in _installed_ids() if version in vid and "quilt" in vid.lower()]
        return quilts[-1] if quilts else version
    if loader == "fabric":
        try:
            mll.fabric.install_fabric(version, str(GW_DIR))
        except Exception:
            return version
        facs = [vid for vid in _installed_ids() if version in vid and "fabric" in vid.lower()]
        return facs[-1] if facs else version
    return version

def _offline_options(username: str) -> mll.types.MinecraftOptions:
    u = uuid.uuid3(uuid.NAMESPACE_DNS, username)
    return {"username": username, "uuid": str(u).replace("-", ""), "token": "0"}

def _detect_java_version(minecraft_version: str) -> int:
    return get_required_java_version(minecraft_version)

def _extract_flag_key(flag: str) -> str:
    return flag.split("=", 1)[0]

def _is_gc_flag(flag: str) -> bool:
    return flag.startswith("-XX:+Use") and flag.endswith("GC")

def build_command(version_id: str, username: str, *, game_dir: Path, ram: Optional[int] = None, jvm_args: Optional[List[str]] = None, optimize: bool = False, progress_cb: Optional[Callable[[int, str], None]] = None) -> List[str]:
    opts = _offline_options(username)
    opts["gameDirectory"] = str(game_dir)
    if os.name == "posix":
        os.chmod(game_dir, 0o755)
    java_version = _detect_java_version(version_id)
    java_executable = download_java_runtime(java_version, progress_cb)
    user_flags: List[str] = list(jvm_args or [])
    filtered_user_flags: List[str] = []
    seen_keys = set()
    seen_gc = False
    for f in user_flags:
        key = _extract_flag_key(f)
        if _is_gc_flag(f):
            if seen_gc:
                continue
            seen_gc = True
        if key in seen_keys:
            continue
        seen_keys.add(key)
        filtered_user_flags.append(f)
    user_flags = filtered_user_flags
    final_args = user_flags[:]
    if ram is not None:
        final_args.append(f"-Xmx{ram}M")
    if final_args:
        opts["jvmArguments"] = final_args
    command = mll.command.get_minecraft_command(version_id, str(GW_DIR), opts)
    command[0] = str(java_executable)
    return command

def _wait_for_version(version_id: str, timeout_s: int = 600) -> None:
    version_path = VERSIONS_DIR / version_id
    expected_jar = version_path / f"{version_id}.jar"
    start = time.time()
    while time.time() - start < timeout_s:
        if expected_jar.exists():
            return
        time.sleep(0.5)
    raise TimeoutError(f"Tiempo agotado esperando la versión {version_id}")

def launch_detached(cmd: list[str], cwd: str) -> None:
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        subprocess.Popen(cmd, cwd=cwd, creationflags=flags)
    else:
        subprocess.Popen(cmd, cwd=cwd, start_new_session=True)

def launch_attached(cmd: list[str], cwd: str) -> subprocess.Popen:
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW
        return subprocess.Popen(cmd, cwd=cwd, creationflags=flags)
    else:
        return subprocess.Popen(cmd, cwd=cwd)

def _parse_cli(argv: List[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="gwlauncher")
    sub = p.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("install", help="Instala una versión vanilla")
    i.add_argument("version")
    l = sub.add_parser("launch", help="Instala (si falta) y lanza un Minecraft")
    l.add_argument("version")
    l.add_argument("username")
    l.add_argument("--ram", type=int, help="Memoria máxima en MiB (p. ej. 4096)")
    l.add_argument("--modloader", choices=["", "forge", "fabric", "quilt"], default="")
    l.add_argument("--jvm-arg", dest="jvm_args", action="append", metavar="ARG")
    sub.add_parser("versions", help="Muestra las versiones instaladas")
    return p.parse_args(argv)

def _main() -> None:
    args = _parse_cli()
    _dump_available_versions_json()
    if args.cmd == "install":
        install_version(args.version)
    elif args.cmd == "launch":
        install_version(args.version)
        real_id = install_modloader(args.modloader, args.version) if args.modloader else args.version
        _wait_for_version(real_id)
        game_dir = INSTANCES_DIR / real_id
        game_dir.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            os.chmod(game_dir, 0o755)
        save_profile(args.username, args.version)
        cmd = build_command(real_id, args.username, game_dir=game_dir, ram=args.ram, jvm_args=args.jvm_args, optimize=False)
        launch_attached(cmd, str(GW_DIR)).wait()
    elif args.cmd == "versions":
        print("\n".join(sorted(_installed_ids())))
    else:
        sys.exit(1)

if __name__ == "__main__":
    _main()
