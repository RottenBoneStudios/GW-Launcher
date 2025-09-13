# gw_launcher.py
from __future__ import annotations
import json, math, os, random, sys, threading, shutil
from datetime import date
from pathlib import Path
from discord_rpc import DiscordRPC
from dataclasses import dataclass
from typing import Callable, List, Optional, Dict, Any
from PySide6.QtCore import QPoint, QPointF, QTimer, Qt, QObject, Signal, Slot, QThread, QProcess, QUrl
from PySide6.QtGui import QFont, QGuiApplication, QPainter, QPixmap, QTransform, QColor, QPainterPath, QLinearGradient, QRadialGradient, QBrush, QIcon, QAction, QDesktopServices
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QPushButton, QTextBrowser, QTextEdit, QVBoxLayout, QWidget, QMessageBox, QComboBox, QGridLayout, QSpinBox, QSystemTrayIcon, QMenu, QInputDialog, QCheckBox, QSizePolicy
from PySide6.QtCore import QSharedMemory
from functools import lru_cache

def _bundle_base() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) if base else Path(__file__).resolve().parent

BASE_DIR = _bundle_base()
GW_DIR = Path.home() / ".gwlauncher"
GW_DIR.mkdir(parents=True, exist_ok=True)
UI_PROFILES = GW_DIR / "ui_profiles.json"

PALETTE = {"bg": "#0b0c22", "bg_card": "#15173850", "bg_sidebar": "#0d0f2c", "fg": "#ffffff", "primary": "#9333ea", "primary_hov": "#a855f7", "accent": "#06b6d4", "launch_grad_left": "#9333ea", "launch_grad_right": "#06b6d4", "radius": 16}
ASSETS = {
    "background": BASE_DIR / "assets/background.png",
    "cat_main": BASE_DIR / "assets/gatitos.png",
    "cat_world": BASE_DIR / "assets/gatitosworld.png",
    "leaf": BASE_DIR / "assets/leaf.png",
    "snow": BASE_DIR / "assets/snow.png",
    "sunflower": BASE_DIR / "assets/sunflower.png",
    "icon": BASE_DIR / "assets/icon.ico",
    "login": BASE_DIR / "assets/login.png"
}

@lru_cache(maxsize=64)
def _cached_pm(path_str: str) -> QPixmap:
    pm = QPixmap(path_str)
    return pm if not pm.isNull() else QPixmap()

def load_pixmap(path: os.PathLike | str) -> QPixmap:
    return _cached_pm(str(path))

def current_season_sprite() -> QPixmap:
    m = date.today().month
    if m in (3, 4, 5): return load_pixmap(ASSETS["leaf"])
    if m in (6, 7, 8): return load_pixmap(ASSETS["snow"])
    if m in (12, 1, 2): return load_pixmap(ASSETS["sunflower"])
    return load_pixmap(ASSETS["leaf"])

class BackgroundLayer(QLabel):
    def __init__(self, path: os.PathLike | str, parent: QWidget | None = None):
        super().__init__(parent)
        self._pix = load_pixmap(path)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setGeometry(parent.rect())
        self._rescale(parent.size())
    def resizeEvent(self, e): super().resizeEvent(e); self._rescale(self.parent().size())
    def _rescale(self, size):
        if self._pix.isNull(): self.clear(); return
        pm = self._pix.scaled(size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        self.setPixmap(pm)

class OverlayImages(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.cat_main = QLabel(self); self.cat_world = QLabel(self)
        self._pm_main = load_pixmap(ASSETS["cat_main"]); self._pm_world = load_pixmap(ASSETS["cat_world"])
    def resizeEvent(self, e):
        super().resizeEvent(e)
        w, h = self.width(), self.height()
        if not self._pm_main.isNull():
            width_main = min(400, int(w * 0.45))
            aspect = self._pm_main.height() / self._pm_main.width()
            height_main = max(1, int(width_main * aspect))
            pm_scaled = self._pm_main.scaled(width_main, height_main, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.cat_main.setPixmap(pm_scaled); self.cat_main.resize(pm_scaled.size())
            self.cat_main.move(int(w * 0.60 - self.cat_main.width() / 2), int(h * 0.50 - self.cat_main.height() / 2))
        if not self._pm_world.isNull():
            width_world = min(200, int(w * 0.20))
            aspect2 = self._pm_world.height() / self._pm_world.width()
            height_world = max(1, int(width_world * aspect2))
            pm2 = self._pm_world.scaled(width_world, height_world, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.cat_world.setPixmap(pm2); self.cat_world.resize(pm2.size())
            self.cat_world.move(int(w * 0.02), int(h * 0.80 - self.cat_world.height()))

@dataclass(slots=True)
class Particle:
    pos: QPointF; vy: float; base_x: float; sway_amp: float; sway_freq: float; angle: float; ang_vel: float; scale: float

class ParticleLayer(QWidget):
    def __init__(self, parent=None, count=12):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.sprite = current_season_sprite()
        self.particles: List[Particle] = []
        self.t = 0.0
        self._pending_count = count
        self._initialized = False
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if not self._initialized and self.width() > 0 and self.height() > 0:
            self._init_particles(self._pending_count)
            self._initialized = True

    def _rand_particle(self) -> Particle:
        w, h = max(self.width(), 1), max(self.height(), 1)
        x = random.uniform(0, w); y = random.uniform(-h * 0.5, -20); vy = random.uniform(30, 70) / 100.0
        sway_amp = random.uniform(15, 45); sway_freq = random.uniform(0.25, 0.6)
        angle = random.uniform(0, 360); ang_vel = random.uniform(-40, 40) / 10.0
        scale = random.uniform(0.35, 0.7)
        return Particle(QPointF(x, y), vy, x, sway_amp, sway_freq, angle, ang_vel, scale)

    def _init_particles(self, count):
        self.particles = [self._rand_particle() for _ in range(count)]

    def _tick(self):
        self.t += 0.033
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        for p in self.particles:
            p.pos.setY(p.pos.y() + p.vy * 10)
            sway = p.sway_amp * math.sin(self.t * p.sway_freq + p.base_x * 0.01)
            p.pos.setX(p.base_x + sway)
            p.angle = (p.angle + p.ang_vel) % 360
            if p.pos.y() > h + 40:
                np = self._rand_particle()
                p.pos, p.vy, p.base_x, p.sway_amp, p.sway_freq, p.angle, p.ang_vel, p.scale = \
                    np.pos, np.vy, np.base_x, np.sway_amp, np.sway_freq, np.angle, np.ang_vel, np.scale
            if p.pos.x() < -60 or p.pos.x() > w + 60:
                p.base_x = random.uniform(0, w)
        self.update()

    def showEvent(self, e):
        super().showEvent(e)
        if not self.timer.isActive():
            self.timer.start(33)

    def hideEvent(self, e):
        super().hideEvent(e)
        if self.timer.isActive():
            self.timer.stop()

    def setActive(self, on: bool):
        if on and not self.timer.isActive():
            self.timer.start(33)
        elif not on and self.timer.isActive():
            self.timer.stop()

    def paintEvent(self, e):
        if self.sprite.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        sw, sh = self.sprite.width(), self.sprite.height()
        pm = self.sprite
        for p in self.particles:
            painter.save()
            painter.translate(p.pos)
            painter.rotate(p.angle)
            painter.scale(p.scale, p.scale)
            painter.setOpacity(0.9)
            painter.drawPixmap(-sw / 2, -sh / 2, pm)
            painter.restore()

class ModalOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "QWidget#overlay { background: rgba(0,0,0,0.6); } "
            "QFrame#box { background: #151738; color: #ffffff; border-radius: 8px; padding: 12px; } "
            "QLabel#title { color: #ffffff; font-weight: 700; font-size: 16px; margin-bottom: 6px; } "
            "QLabel#text { color: #ffffff; font-size: 14px; } "
            "QTextBrowser#content { background: #272822; color: #ffffff; border-radius: 4px; padding: 8px; font-family: monospace; } "
            "QLabel#msg { color: #ff5555; font-size: 14px; margin: 4px 0; } "
            "QPushButton#modal-btn { padding: 6px 12px; border: 0; border-radius: 4px; "
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #9333ea, stop:1 #06b6d4); color: #ffffff; } "
            "QPushButton#modal-btn:hover { opacity: 0.9; }"
        )
        self.setObjectName("overlay")
        self.hide()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self._center = QWidget(self)
        lay_center = QVBoxLayout(self._center)
        lay_center.setAlignment(Qt.AlignCenter)
        self.box = QFrame(self._center)
        self.box.setObjectName("box")
        self.box.setMaximumWidth(360)
        v = QVBoxLayout(self.box)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(4)

        self.title = QLabel("Título", self.box)
        self.title.setObjectName("title")

        self._stack = QWidget(self.box)
        self._stack_lay = QVBoxLayout(self._stack)
        self._stack_lay.setContentsMargins(0, 0, 0, 0)

        self.text = QLabel(self.box)
        self.text.setObjectName("text")
        self.text.setWordWrap(True)
        self.text.setAlignment(Qt.AlignCenter)
        self.text.hide()

        self.content = QTextBrowser(self.box)
        self.content.setObjectName("content")
        self.content.hide()

        from PySide6.QtWidgets import QSizePolicy
        self.msg_label = QLabel(self.box)
        self.msg_label.setObjectName("msg")
        self.msg_label.setWordWrap(False)
        self.msg_label.setAlignment(Qt.AlignCenter)
        self.msg_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.msg_label.setMaximumHeight(22)
        self.msg_label.hide()

        self.buttons = QWidget(self.box)
        self.buttons.setObjectName("buttons")
        self.buttons_lay = QHBoxLayout(self.buttons)
        self.buttons_lay.setContentsMargins(0, 4, 0, 0)
        self.buttons_lay.setSpacing(8)
        self.buttons_lay.setAlignment(Qt.AlignRight)

        v.addWidget(self.title)
        v.addWidget(self._stack)
        v.addWidget(self.text)
        v.addWidget(self.content)
        v.addWidget(self.msg_label)
        v.addWidget(self.buttons)

        lay_center.addWidget(self.box)
        lay.addWidget(self._center)

        self._current_form: Optional[QWidget] = None
        self._on_dismiss: Optional[Callable] = None

    def _rebuild_buttons(self, buttons: List[tuple[str, Callable]]):
        if not buttons:
            buttons = [("Cerrar", self.hide_modal)]

        while self.buttons_lay.count():
            w = self.buttons_lay.takeAt(0).widget()
            if w:
                w.deleteLater()

        for text, cb in buttons:
            b = QPushButton(text, self.buttons)
            b.setObjectName("modal-btn")
            b.setProperty("class", "modal-btn")
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, fn=cb: fn())
            self.buttons_lay.addWidget(b)
        self.buttons.show()

    def request_close(self):
        if self._on_dismiss is not None:
            cb = self._on_dismiss
            self._on_dismiss = None
            try:
                cb()
            except Exception:
                pass
        else:
            self.hide_modal()

    def mousePressEvent(self, e):
        if not self.box.geometry().contains(e.position().toPoint()):
            self.request_close()
        else:
            super().mousePressEvent(e)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter):
            self.request_close()
        else:
            super().keyPressEvent(e)

    def clear_form(self):
        if self._current_form:
            self._current_form.setParent(None)
            self._current_form.deleteLater()
            self._current_form = None
        self._on_dismiss = None

    def hide_modal(self):
        self.clear_form()
        self.hide()

    def show_modal_2(self, title: str, message: str, buttons: List[tuple[str, Callable]], on_dismiss: Optional[Callable] = None):
        self.clear_form()
        self._on_dismiss = on_dismiss
        self.title.setText(title)
        self.text.setText(message)
        self.text.show()
        self.content.hide()
        self.msg_label.hide()
        self._rebuild_buttons(buttons)
        self.show()
        self.raise_()

    def show_modal(self, title: str, html_or_text: str, buttons: List[tuple[str, Callable]], on_dismiss: Optional[Callable] = None):
        self.clear_form()
        self._on_dismiss = on_dismiss
        self.title.setText(title)
        if "<" in html_or_text and ">" in html_or_text:
            self.content.setHtml(html_or_text)
            self.content.show()
            self.msg_label.hide()
            self.text.hide()
        else:
            self.msg_label.setText(html_or_text)
            self.msg_label.show()
            self.content.hide()
            self.text.hide()
        self._rebuild_buttons(buttons)
        self.show()
        self.raise_()

    def show_form(self, title: str, form: QWidget, buttons: List[tuple[str, Callable]], on_dismiss: Optional[Callable] = None):
        self.clear_form()
        self._on_dismiss = on_dismiss
        self.title.setText(title)
        self.content.hide()
        self.msg_label.hide()
        self.text.hide()
        self._current_form = form
        self._stack_lay.addWidget(form)
        self._rebuild_buttons(buttons)
        self.show()
        self.raise_()

class TitleBar(QWidget):
    def __init__(self, parent: QMainWindow):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.addStretch(1)
        self.btn_login = QPushButton(self)
        self.btn_min = QPushButton("─", self)
        self.btn_close = QPushButton("✕", self)
        self.lbl_login_status = QLabel("Iniciar sesión con Mojang", self)
        self.lbl_login_status.setStyleSheet(f"color:{PALETTE['fg']}; font-size:13px; margin-left:4px;")
        for b in (self.btn_login, self.btn_min, self.btn_close):
            b.setFixedHeight(28)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton {{ border: 0; background: transparent; color: {PALETTE['fg']}; font-size: 16px; }}"
                f"QPushButton:hover {{ background: rgba(255,255,255,0.1); }}"
            )
        self.btn_login.setFixedWidth(36)
        icon_login = QIcon(str(ASSETS["login"])) if Path(ASSETS["login"]).exists() else None
        if icon_login:
            self.btn_login.setIcon(icon_login)
        else:
            self.btn_login.setText("👤")
        self.btn_close.setStyleSheet(
            f"QPushButton {{ border: 0; background: transparent; color: {PALETTE['fg']}; font-size: 16px; }}"
            f"QPushButton:hover {{ background: #e81123; }}"
        )
        self.btn_min.setFixedWidth(40)
        self.btn_close.setFixedWidth(40)
        self.btn_min.clicked.connect(parent.showMinimized)
        self.btn_close.clicked.connect(parent.close)
        self.btn_login.clicked.connect(getattr(parent, "_open_login", lambda: None))
        lay.addWidget(self.btn_login)
        lay.addWidget(self.lbl_login_status)
        lay.addWidget(self.btn_min)
        lay.addWidget(self.btn_close)
        self._drag_pos: Optional[QPoint] = None

def _read_json(p: Path, default: Any) -> Any:
    if not p.exists(): return default
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return default

def _write_json(p: Path, data: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def _versions_sources() -> Dict[str, Path]:
    return {"vanilla": GW_DIR / "versiones-minecraft.json", "fabric": GW_DIR / "versiones-fabric.json", "forge": GW_DIR / "versiones-forge.json", "quilt": GW_DIR / "versiones-quilt.json"}

def _version_key(ver: str) -> tuple[int, ...]:
    parts: list[int] = []
    for p in ver.replace('-', '.').split('.'):
        if p.isdigit():
            parts.append(int(p))
        else:
            digits = ''.join(ch for ch in p if ch.isdigit())
            parts.append(int(digits) if digits else -1)
    return tuple(parts)

def _load_versions() -> List[Dict[str,str]]:
    out = {}
    for modloader, fp in _versions_sources().items():
        if not fp.exists(): continue
        try:
            data = _read_json(fp, {})
            if modloader == "forge":
                versions = set()
                for ver in data:
                    mc = str(ver).split("-")[0].split("_")[0]
                    if mc: versions.add(mc)
                for v in versions: out[f"{v}|{modloader}"]= {"version":v,"modloader":modloader}
            else:
                seq = data if isinstance(data, list) else data.get("versions", [])
                if modloader == "vanilla":
                    for it in seq:
                        if isinstance(it, dict) and it.get("type")=="release":
                            v = it.get("id") or it.get("version")
                            if v: out[f"{v}|{modloader}"]= {"version":v,"modloader":modloader}
                else:
                    for it in seq:
                        v = it if isinstance(it, str) else (it.get("version") or it.get("id"))
                        if not v: continue
                        if isinstance(it, dict) and it.get("stable") is False: continue
                        out[f"{v}|{modloader}"]= {"version":v,"modloader":modloader}
        except Exception: pass
    lst = list(out.values())
    lst.sort(key=lambda d: _version_key(d["version"]), reverse=True)
    return lst

RECOMMENDED = {
    8:  ["-XX:+UseG1GC","-XX:G1NewSizePercent=30","-XX:G1MaxNewSizePercent=40","-XX:G1HeapRegionSize=16M","-XX:G1ReservePercent=20","-XX:MaxGCPauseMillis=50","-XX:G1HeapWastePercent=5","-XX:G1MixedGCCountTarget=4","-XX:+UnlockExperimentalVMOptions","-XX:+PerfDisableSharedMem","-XX:+AlwaysPreTouch"],
    17: ["-XX:+UseZGC","-XX:+UnlockExperimentalVMOptions","-XX:+DisableExplicitGC","-XX:+AlwaysPreTouch"],
    21: ["--enable-preview","-XX:+UseZGC","-XX:+UnlockExperimentalVMOptions","-XX:+DisableExplicitGC","-XX:+AlwaysPreTouch"]
}

def _java_version_for_mc(ver: str) -> int:
    import gwlauncher_backend as backend
    return backend.get_required_java_version(ver)

def _recommended_flags(version: str, modloader: str) -> List[str]:
    if modloader in ("fabric","forge","quilt"): return []
    jv = _java_version_for_mc(version)
    return RECOMMENDED.get(jv, [])

class EditorForm(QWidget):
    def __init__(self, existing_names: List[str], profile: Optional[Dict[str,Any]]=None):
        super().__init__()
        from PySide6.QtWidgets import QCheckBox
        up_path = (BASE_DIR / "assets" / "arriba.png").as_posix()
        down_path = (BASE_DIR / "assets" / "abajo.png").as_posix()
        self.setStyleSheet(
            f"QLabel, QLineEdit, QTextEdit, QComboBox, QSpinBox, QCheckBox{{color:#fff;font-size:14px}}"
            f" QLineEdit{{background:#0f1027;border:1px solid rgba(255,255,255,0.2);border-radius:6px;padding:6px;color:#fff;}}"
            f" QTextEdit{{background:transparent;border:0;}}"
            f" QPushButton.reco{{border:0;border-radius:12px;padding:10px;background:{PALETTE['primary']};color:#fff;font-weight:600}}"
            f" QPushButton.reco:hover{{background:{PALETTE['primary_hov']}}}"
            f" QComboBox{{background:#0f1027;border-radius:8px;padding:8px}}"
            f" QSpinBox{{background:transparent;border:0;color:#fff;padding-left:42px;padding-right:42px;}}"
            f" QSpinBox::down-button{{subcontrol-origin:border; subcontrol-position:left;"
            f"  width:30px;height:24px; margin:2px 0 2px 8px; border:0; background:transparent; image: url('{down_path}');}}"
            f" QSpinBox::up-button{{subcontrol-origin:border; subcontrol-position:right;"
            f"  width:30px;height:24px; margin:2px 8px 2px 0; border:0; background:transparent; image: url('{up_path}');}}"
            f" QSpinBox::down-button:pressed{{margin-left:9px}}"
            f" QSpinBox::up-button:pressed{{margin-right:9px}}"
            f" .warn{{color:#ffb4b4}}"
        )
        grid = QGridLayout(self); grid.setVerticalSpacing(12); grid.setHorizontalSpacing(10)

        self.name = QLineEdit(); self.name.setPlaceholderText("Nombre del perfil")
        self.chk_ms = QCheckBox("Iniciar con cuenta oficial de Microsoft")
        self.username = QLineEdit(); self.username.setPlaceholderText("Username de Minecraft")
        self.version = QComboBox(); self.version.setMinimumWidth(320)
        self.ram = QSpinBox(); self.ram.setRange(512, 65536); self.ram.setSingleStep(1024); self.ram.setAccelerated(True); self.ram.setSuffix(" MiB"); self.ram.setFixedHeight(36)
        self.jvm = QTextEdit(); self.jvm.setPlaceholderText("JVM flags (espacio-separadas)")
        self.btnReco = QPushButton("Flags recomendadas"); self.btnReco.setProperty("class","reco")
        self.warn = QLabel(); self.warn.setObjectName("warn")

        grid.addWidget(self._row("Nombre de perfil", self.name),0,0,1,2)
        grid.addWidget(self.chk_ms,1,0,1,2)
        self.username_row = self._row("Username", self.username)
        grid.addWidget(self.username_row,2,0,1,2)
        grid.addWidget(self._row("Versión", self.version),3,0,1,2)
        grid.addWidget(self._row("RAM", self.ram),4,0,1,2)
        grid.addWidget(self._row("JVM Flags", self.jvm),5,0,1,2)
        grid.addWidget(self.btnReco,6,0,1,1); grid.addWidget(self.warn,6,1,1,1)

        self._existing = set(existing_names); self._versions = _load_versions()
        self.version.addItem("Selecciona una versión", userData={"version":"","modloader":""})
        for it in self._versions:
            label = it["version"] if it["modloader"]=="vanilla" else f"{it['version']} ({it['modloader']})"
            self.version.addItem(label, userData=it)
        self.ram.setValue(2048)

        self.name.setText(profile.get("name","") if profile else "")
        if profile and profile.get("name_locked"): self.name.setEnabled(False)
        self.username.setText(profile.get("username","") if profile else "")
        sel_ver = profile.get("version","") if profile else ""
        sel_mod = profile.get("modloader","vanilla") if profile else "vanilla"
        if sel_ver:
            for i in range(self.version.count()):
                d = self.version.itemData(i)
                if d and d.get("version")==sel_ver and d.get("modloader")==sel_mod: self.version.setCurrentIndex(i); break
        if profile: self.ram.setValue(int(profile.get("ram", 2048)))
        self.jvm.setPlainText(" ".join(profile.get("jvmFlags",[])) if profile else "")
        auth_mode = (profile.get("auth","offline") if profile else "offline")
        self.chk_ms.setChecked(auth_mode == "microsoft")

        def toggle_username():
            self.username_row.setVisible(not self.chk_ms.isChecked())
        toggle_username()
        self.chk_ms.stateChanged.connect(lambda _: toggle_username())

        def on_change_version():
            cur = self.jvm.toPlainText().strip().split()
            equal8 = cur==RECOMMENDED[8]; equal17 = cur==RECOMMENDED[17]; equal21 = cur==RECOMMENDED[21]
            d = self.version.currentData() or {"version":"","modloader":""}
            rec = _recommended_flags(d.get("version",""), d.get("modloader",""))
            if equal8 or equal17 or equal21: self.jvm.setPlainText(" ".join(rec))
        self.version.currentIndexChanged.connect(on_change_version)

        def on_reco():
            d = self.version.currentData() or {"version":"","modloader":""}
            v = d.get("version","")
            if not v: self.warn.setText("Selecciona primero una versión."); return
            self.warn.setText(""); self.jvm.setPlainText(" ".join(_recommended_flags(v, d.get("modloader",""))))
        self.btnReco.clicked.connect(on_reco)

    def _row(self, label: str, control: QWidget) -> QWidget:
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(0,0,0,0); lay.setSpacing(4)
        tl = QLabel(label); tl.setStyleSheet("opacity:.8;font-size:12px;color:#fff")
        box = QFrame(); box.setObjectName("wrap")
        box.setStyleSheet("QFrame#wrap{background:rgba(255,255,255,0.05);border-radius:8px;}")
        bl = QVBoxLayout(box); bl.setContentsMargins(12,8,12,8); bl.setSpacing(4); bl.addWidget(control)
        lay.addWidget(tl); lay.addWidget(box)
        return w

    def get_data(self) -> Optional[Dict[str,Any]]:
        name = self.name.text().strip()
        if not name: self.warn.setText("Rellena el nombre del perfil"); return None
        if self.name.isEnabled() and name in self._existing: self.warn.setText("Ya existe un perfil con ese nombre"); return None
        d = self.version.currentData() or {"version":"","modloader":""}
        version = d.get("version",""); modloader = d.get("modloader","vanilla") or "vanilla"
        if not version: self.warn.setText("Selecciona una versión"); return None
        ram = max(2048, int(self.ram.value()))
        jvm = [s for s in self.jvm.toPlainText().strip().split() if s]
        auth = "microsoft" if self.chk_ms.isChecked() else "offline"
        return {"name": name, "username": self.username.text().strip(), "version": version, "modloader": modloader, "ram": ram, "jvmFlags": jvm, "auth": auth}

class GlowPlayButton(QPushButton):
    def __init__(self, text="▶ PLAY", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumSize(240, 68)
        self.setFont(QFont(self.font().family(), 14, QFont.Black))
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._t = 0.0
        self._glow_on = False
        self.setCheckable(False)
        self.setEnabled(False)
        self.setStyleSheet("QPushButton{background:transparent;border:none;color:#ffffff;} QPushButton:disabled{color:rgba(255,255,255,0.45);} ")
    def setGlowing(self, on: bool):
        self._glow_on = on and self.isEnabled()
        if self._glow_on:
            if not self._timer.isActive(): self._timer.start(16)
        else:
            self._timer.stop()
            self.update()
    def setEnabled(self, enabled: bool):
        super().setEnabled(enabled)
        self.setGlowing(enabled and self._glow_on)
    def _tick(self):
        self._t += 0.035
        if self._t > 1e6: self._t = 0.0
        self.update()
    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        r = self.rect().adjusted(2, 2, -2, -2)
        radius = r.height() / 2
        path = QPainterPath(); path.addRoundedRect(r, radius, radius)
        grad = QLinearGradient(r.topLeft(), r.topRight())
        grad.setColorAt(0.0, QColor(PALETTE["launch_grad_left"]))
        grad.setColorAt(1.0, QColor(PALETTE["launch_grad_right"]))
        painter.fillPath(path, grad)
        if self.isEnabled():
            pulse = 0.35 + 0.30 * math.sin(self._t * 2.0 * math.pi)
            rg = QRadialGradient(r.center(), r.width()*0.75)
            rg.setColorAt(0.0, QColor(255,255,255, int(90*pulse)))
            rg.setColorAt(0.35, QColor(6,182,212, int(180*pulse)))
            rg.setColorAt(0.75, QColor(147,51,234, int(140*pulse)))
            rg.setColorAt(1.0, QColor(0,0,0,0))
            painter.save()
            painter.setClipPath(path)
            painter.fillRect(r, QBrush(rg))
            painter.restore()
            edge = QColor(255,255,255, int(60+40*pulse))
            painter.setPen(edge)
            painter.drawPath(path)
        else:
            painter.setOpacity(0.45)
            painter.fillPath(path, grad)
            painter.setOpacity(1.0)
        painter.setPen(Qt.white if self.isEnabled() else QColor(255,255,255,120))
        painter.drawText(self.rect(), Qt.AlignCenter, self.text())

class PlayDock(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.btn = GlowPlayButton(parent=self)
    def set_ready(self, ready: bool):
        self.btn.setEnabled(ready)
        self.btn.setGlowing(ready)
    def resizeEvent(self, e):
        super().resizeEvent(e)
        bw, bh = self.btn.minimumWidth(), self.btn.minimumHeight()
        self.btn.resize(bw, bh)
        self.btn.move(self.width()-bw, self.height()-bh)

class LoadingOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("loadingOverlay")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.hide()
        self.setStyleSheet(
            "#loadingOverlay{background: rgba(0,0,0,0.75);} "
            "#box{background: rgba(21,23,56,0.9); border-radius: 16px; padding: 24px;} "
            "#percent{color:#fff; font-size:42px; font-weight:800;} "
            "#label{color:#ffffff; font-size:14px; opacity:0.9;} "
            "QProgressBar{background: rgba(255,255,255,0.08); border: 0; border-radius: 10px; height: 18px;} "
            "QProgressBar::chunk{background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #9333ea, stop:1 #06b6d4); border-radius: 10px;}"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0,0,0,0)
        lay.setSpacing(0)

        center = QWidget(self)
        cl = QVBoxLayout(center)
        cl.setAlignment(Qt.AlignCenter)

        box = QFrame(center)
        box.setObjectName("box")
        bl = QVBoxLayout(box)
        bl.setSpacing(12)

        self.lbl_percent = QLabel("0%", box)
        self.lbl_percent.setObjectName("percent")
        self.lbl_percent.setAlignment(Qt.AlignHCenter)

        self.lbl_text = QLabel("Inicializando…", box)
        self.lbl_text.setObjectName("label")
        self.lbl_text.setAlignment(Qt.AlignHCenter)

        from PySide6.QtWidgets import QProgressBar
        self.bar = QProgressBar(box)
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)

        bl.addWidget(self.lbl_percent)
        bl.addWidget(self.lbl_text)
        bl.addWidget(self.bar)

        cl.addWidget(box)
        lay.addWidget(center)
    def set_progress(self, percent: int, text: str):
        p = max(0, min(100, int(percent)))
        self.bar.setValue(p)
        self.lbl_percent.setText(f"{p}%")
        self.lbl_text.setText(text)
    def start(self, text: str = "Preparando…"):
        self.set_progress(0, text)
        self.show(); self.raise_()
    def finish(self):
        self.set_progress(100, "Listo")
        self.hide()

class GWLauncher(QMainWindow):
    class LaunchWorker(QObject):
        progress = Signal(int, str)
        finished_err = Signal(str)
        ready_to_launch = Signal(list, str)

        def __init__(self, version: str, username: str, loader: str, ram: int, jvm: list[str], gw_dir: Path, profile_name: str):
            super().__init__()
            self.version = version
            self.username = username
            self.loader = loader
            self.ram = ram
            self.jvm = jvm
            self.gw_dir = gw_dir
            self.profile_name = profile_name

        @Slot()
        def run(self):
            try:
                import gwlauncher_backend as backend
                self.progress.emit(5, "Instalando versión…")
                backend.install_version(self.version)
                self.progress.emit(20, "Instalando modloader…")
                ml = "" if self.loader == "vanilla" else (self.loader or "")
                real_id = backend.install_modloader(ml, self.version) if ml else self.version
                self.progress.emit(40, "Verificando archivos…")
                backend._wait_for_version(real_id)
                self.progress.emit(55, "Preparando entorno…")
                instances_dir = getattr(backend, "INSTANCES_DIR", self.gw_dir / "instances")
                game_dir = instances_dir / f"{real_id}_{self.profile_name}"
                game_dir.mkdir(parents=True, exist_ok=True)
                if os.name == "posix":
                    os.chmod(game_dir, 0o755)
                self.progress.emit(65, "Aplicando modpack GatitosWorld…")
                backend.ensure_modpack(game_dir)
                backend.save_profile(self.username, self.version)
                self.progress.emit(80, "Construyendo comando…")
                cmd = backend.build_command(
                    real_id,
                    self.username,
                    game_dir=game_dir,
                    ram=self.ram,
                    jvm_args=self.jvm,
                    optimize=False,
                    server="na37.holy.gg",
                    port=19431,
                    progress_cb=lambda p, t: self.progress.emit(80 + p // 5, t),
                )
                self.progress.emit(95, "Listo para lanzar…")
                self.ready_to_launch.emit(cmd, str(backend.GW_DIR))
            except Exception as e:
                self.finished_err.emit(str(e))

        def _handle_stdout(self):
            if self.proc:
                data = self.proc.readAllStandardOutput().data().decode(errors="ignore")
                sys.stdout.write(data)
                sys.stdout.flush()

        def _handle_stderr(self):
            if self.proc:
                data = self.proc.readAllStandardError().data().decode(errors="ignore")
                sys.stderr.write(data)
                sys.stderr.flush()

    class DeviceLoginForm(QWidget):
        def __init__(self, code: str, url: str):
            super().__init__()
            self.setStyleSheet("QLabel{color:#fff} QLineEdit{background:#0f1027;color:#fff;border:0;border-radius:8px;padding:10px} QFrame#wrap{background:#0f1027;border-radius:12px;padding:16px}")
            v = QVBoxLayout(self); v.setContentsMargins(0,0,0,0); v.setSpacing(10)
            box = QFrame(); box.setObjectName("wrap")
            vb = QVBoxLayout(box); vb.setContentsMargins(16,16,16,16); vb.setSpacing(8)
            lbl1 = QLabel("Código para ingresar en la web:")
            self.txt_code = QLineEdit(); self.txt_code.setReadOnly(True); self.txt_code.setText(code); self.txt_code.setCursorPosition(0)
            lbl2 = QLabel("Abre este enlace y pega el código:")
            self.txt_url = QLineEdit(); self.txt_url.setReadOnly(True); self.txt_url.setText(url); self.txt_url.setCursorPosition(0)
            vb.addWidget(lbl1); vb.addWidget(self.txt_code); vb.addWidget(lbl2); vb.addWidget(self.txt_url)
            v.addWidget(box)
            
    def _start_rpc(self):
        try:
            self.rpc.start()
            self.rpc.set_browsing()
        except Exception:
            pass
        
    def _cleanup_ms_login_thread(self, force: bool = False, wait_ms: int = 5000):
        t = getattr(self, "_ms_login_thread", None)
        w = getattr(self, "_ms_login_worker", None)
        if t is None:
            if w:
                w.deleteLater()
                self._ms_login_worker = None
            return
        if t.isRunning() and not force:
            return
        if t.isRunning() and force:
            try:
                t.requestInterruption()
            except Exception:
                pass
            t.quit()
            if not t.wait(wait_ms):
                t.terminate()
                t.wait(200)
        if w:
            w.deleteLater()
            self._ms_login_worker = None
        t.deleteLater()
        self._ms_login_thread = None
        
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GW Launcher")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowSystemMenuHint)
        self.resize(1100, 700)
        root = QWidget(self)
        root.setObjectName("root")
        root.setStyleSheet(f"QWidget#root {{ background: transparent; color: {PALETTE['fg']}; }}")
        self.setCentralWidget(root)
        self.bg = BackgroundLayer(ASSETS["background"], root)
        self.overlay_images = OverlayImages(root)
        self.particles = ParticleLayer(root)
        self.window_frame = QFrame(root)
        self.window_frame.setObjectName("window")
        self.window_frame.setStyleSheet("QFrame#window { background: transparent; border: none; }")
        self.window_frame.setGeometry(root.rect())
        self.titlebar = TitleBar(self)
        self.titlebar.setParent(root)
        main = QWidget(root)
        main.setObjectName("main")
        main_lay = QHBoxLayout(main)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        sidebar = QFrame(main)
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(300)
        sidebar.setMaximumWidth(420)
        sidebar.setStyleSheet(
            f"QFrame#sidebar {{ background: rgba(0,0,0,0.5); padding: 24px; }} "
            f"QLabel#sideTitle {{ color: #ffffff; font-size: 22px; font-weight: 600; }} "
            f"QListWidget#profiles {{ background: transparent; border: none; color: #ffffff; font-size: 16px; }} "
            f"QListWidget#profiles::item {{ margin: 0; padding: 0; border: 0; }} "
            f"QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 0 4px 0; }} "
            f"QScrollBar::handle:vertical {{ background: {PALETTE['primary']}; border-radius: 5px; min-height: 24px; }} "
            f"QScrollBar::handle:vertical:hover {{ background: {PALETTE['primary_hov']}; }} "
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }} "
            f"QPushButton.side {{ border: 0; border-radius: 12px; padding: 12px; color: #ffffff; font-weight: 600; font-size: 15px; }} "
            f"QPushButton#btnNew {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #9333ea, stop:1 #06b6d4); }} "
            f"QPushButton#btnNew:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #a855f7, stop:1 #22d3ee); }} "
            f"QPushButton#btnEdit[enabled=\"false\"] {{ background: rgba(147, 51, 234, 0.5); color: #ffffff; }} "
            f"QPushButton#btnEdit[enabled=\"true\"] {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #9333ea, stop:1 #06b6d4); color: #ffffff; }}"
        )
        sv = QVBoxLayout(sidebar)
        sv.setContentsMargins(20, 20, 20, 20)
        sv.setSpacing(14)
        st = QLabel("Perfiles", sidebar)
        st.setObjectName("sideTitle")
        self.profiles = QListWidget(sidebar)
        self.profiles.setUniformItemSizes(True)
        self.profiles.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        from PySide6.QtGui import QIcon
        self._icon_folder = QIcon((BASE_DIR / "assets" / "folder.png").as_posix())
        self._icon_trash  = QIcon((BASE_DIR / "assets" / "trash.png").as_posix())
        self.profiles.setObjectName("profiles")
        self.profiles.itemSelectionChanged.connect(self._on_profile_select)
        self.profiles.setSpacing(10)
        from PySide6.QtWidgets import QAbstractItemView, QSizePolicy
        self.profiles.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.profiles.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.profiles.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.profiles.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        footer = QFrame(sidebar)
        fv = QVBoxLayout(footer)
        fv.setContentsMargins(0, 8, 0, 0)
        fv.setSpacing(8)
        self.btn_new = QPushButton("＋ Crear perfil", footer)
        self.btn_new.setObjectName("btnNew")
        self.btn_new.setProperty("class", "side")
        self.btn_new.setCursor(Qt.PointingHandCursor)
        self.btn_edit = QPushButton("✎ Editar perfil", footer)
        self.btn_edit.setObjectName("btnEdit")
        self.btn_edit.setProperty("class", "side")
        self.btn_edit.setEnabled(False)
        self.btn_edit.setCursor(Qt.PointingHandCursor)
        fv.addWidget(self.btn_new)
        fv.addWidget(self.btn_edit)
        self._sync_btn_edit_style()
        sv.addWidget(st)
        sv.addWidget(self.profiles, 1)
        sv.addWidget(footer, 0, Qt.AlignBottom)
        content = QFrame(main)
        content.setObjectName("content")
        content.setStyleSheet(
            f"QFrame#content {{ background: rgba(21,23,56,0.5); padding: 24px 32px; }} "
            f"QLabel#headline {{ color: #ffffff; font-size: 21px; font-weight: 500; }} "
            f"QTextBrowser#news {{ background: transparent; border: none; color: #ffffff; }}"
        )
        cv = QVBoxLayout(content)
        cv.setContentsMargins(24, 24, 24, 24)
        cv.setSpacing(16)
        self.headline = QLabel("Selecciona un perfil", content)
        self.headline.setObjectName("headline")
        self.news = QTextBrowser(content)
        self.news.setObjectName("news")
        self.news.setHtml('<p style="opacity:0.9;font-style:italic;text-align:center;margin-top:40%;color:#ffffff;">ℹ️ Aquí aparecerán las noticias y changelogs de Minecraft…</p>')
        self.news.installEventFilter(self)
        cv.addWidget(self.headline)
        cv.addWidget(self.news, 1)
        main_lay.addWidget(sidebar)
        main_lay.addWidget(content, 1)
        main.setParent(root)
        self.play_dock = PlayDock(root)
        self.modal = ModalOverlay(root)
        self.loading = LoadingOverlay(root)
        self._launch_thread: Optional[QThread] = None
        self._launch_worker: Optional[QObject] = None
        self._ms_login_thread: Optional[QThread] = None
        self._ms_login_worker: Optional[QObject] = None
        self._ms_login_cancelled: bool = False
        self._ms_login_in_progress: bool = False
        self.rpc = DiscordRPC()
        QTimer.singleShot(0, self._start_rpc)
        self.tray = QSystemTrayIcon(QIcon(str(ASSETS["icon"])), self)
        tray_menu = QMenu()
        act_restore = QAction("Mostrar", self)
        act_exit = QAction("Salir", self)
        act_restore.triggered.connect(self.showNormal)
        act_exit.triggered.connect(QApplication.instance().quit)
        tray_menu.addAction(act_restore)
        tray_menu.addAction(act_exit)
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(lambda r: self.showNormal() if r == QSystemTrayIcon.Trigger else None)
        self.tray.show()
        self.btn_new.clicked.connect(self._create_profile)
        self.btn_edit.clicked.connect(lambda: self._open_editor(self._current_profile_name()))
        self.profiles.itemDoubleClicked.connect(lambda _: self._launch())
        self.play_dock.btn.clicked.connect(self._launch)
        self._relayout()
        self._stacking_order()
        self._profiles: Dict[str, Any] = self._load_profiles()
        if "GatitosWorld ModPack" not in self._profiles:
            self._profiles["GatitosWorld ModPack"] = {
                "name_locked": True,
                "username": "",
                "version": "1.21.1",
                "modloader": "fabric",
                "ram": 4096,
                "jvmFlags": [],
                "server": "na37.holy.gg",
                "port": 19431
            }
            self._save_profiles()
        self._refresh_list()
        self._set_play_ready(False)
        self._refresh_versions_async()
        from auth_backend import list_accounts
        self._refresh_login_status()

    def _refresh_login_status(self):
        from auth_backend import list_accounts
        accounts = list_accounts()
        if accounts:
            acc = next(iter(accounts.values()))
            self.titlebar.lbl_login_status.setText(acc.get("name", "Jugador"))
        else:
            self.titlebar.lbl_login_status.setText("Iniciar sesión con Mojang")

    def _rpc_set_ip(self):
        try:
            if hasattr(self.rpc, "set_state"):
                self.rpc.set_state("IP: na37.holy.gg")
            elif hasattr(self.rpc, "update"):
                self.rpc.update(state="IP: na37.holy.gg")
            elif hasattr(self.rpc, "set_minecraft"):
                try:
                    self.rpc.set_minecraft("IP: na37.holy.gg")
                except TypeError:
                    self.rpc.set_minecraft()
            else:
                self.rpc.set_browsing()
        except Exception:
            pass

    def _rpc_set_browsing(self):
        try:
            self.rpc.set_browsing()
        except Exception:
            pass

    def _refresh_versions_async(self):
        def worker():
            try:
                import gwlauncher_backend as backend
                backend._dump_available_versions_json()
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj is self.news and event.type() == QEvent.Wheel and (QApplication.keyboardModifiers() & Qt.ControlModifier): return True
        return super().eventFilter(obj, event)

    def _stacking_order(self):
        self.bg.lower(); self.overlay_images.stackUnder(self.window_frame); self.particles.stackUnder(self.window_frame)
        self.window_frame.raise_(); self.findChild(QWidget, "main").raise_(); self.titlebar.raise_(); self.play_dock.raise_(); self.modal.raise_(); self.loading.raise_()

    def resizeEvent(self, e): super().resizeEvent(e); self._relayout()

    def _relayout(self):
        r = self.centralWidget().rect(); self.bg.setGeometry(r); self.overlay_images.setGeometry(r); self.particles.setGeometry(r); self.titlebar.setGeometry(0, 0, r.width(), 32)
        for child in self.centralWidget().findChildren(QWidget, options=Qt.FindDirectChildrenOnly):
            if child not in (self.bg, self.overlay_images, self.particles, self.titlebar, self.modal, self.play_dock, self.loading): child.setGeometry(r)
        m = 24
        dock_w, dock_h = 280, 120
        self.play_dock.setGeometry(r.right()-dock_w-m+1, r.bottom()-dock_h-m+1, dock_w, dock_h)
        self.modal.setGeometry(r)
        self.loading.setGeometry(r)

    def _profiles_path(self) -> Path: return UI_PROFILES
    def _load_profiles(self) -> Dict[str,Any]:
        return _read_json(self._profiles_path(), {})
    def _save_profiles(self):
        _write_json(self._profiles_path(), self._profiles)

    def _refresh_list(self):
        self.profiles.setUpdatesEnabled(False)
        self.profiles.clear()
        for name in sorted(self._profiles.keys()):
            item = QListWidgetItem()
            w = self._make_profile_item(name)
            item.setSizeHint(w.sizeHint())
            self.profiles.addItem(item)
            self.profiles.setItemWidget(item, w)
        self.profiles.setUpdatesEnabled(True)

    def _make_profile_item(self, name: str) -> QWidget:
        from PySide6.QtCore import QSize
        card = QFrame()
        card.setObjectName("profileCard")
        card.setStyleSheet(
            "#profileCard{background: rgba(21,23,56,0.75); border-radius: 10px;} "
            "#lblName{font-size:16px; color: #ffffff;} "
            "QPushButton.tool{border:0; background: transparent; padding: 0; border-radius: 6px;} "
            "QPushButton.tool:hover{background: rgba(255,255,255,0.08);} "
        )
        card.setMinimumHeight(48)
        lay = QHBoxLayout(card); lay.setContentsMargins(12, 8, 12, 8); lay.setSpacing(10)
        lbl = QLabel(name, card); lbl.setObjectName("lblName"); lbl.setWordWrap(False)
        from PySide6.QtWidgets import QSizePolicy
        lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        btn_folder = QPushButton(card); btn_trash = QPushButton(card)
        btn_folder.setProperty("class","tool"); btn_trash.setProperty("class","tool")
        btn_folder.setObjectName("btnFolder"); btn_trash.setObjectName("btnTrash")
        btn_folder.setCursor(Qt.PointingHandCursor); btn_trash.setCursor(Qt.PointingHandCursor)
        btn_folder.setFlat(True); btn_trash.setFlat(True)
        btn_folder.setFixedSize(32, 32); btn_trash.setFixedSize(32, 32)
        btn_folder.setIcon(self._icon_folder); btn_trash.setIcon(self._icon_trash)
        btn_folder.setIconSize(QSize(20, 20)); btn_trash.setIconSize(QSize(20, 20))
        btn_folder.clicked.connect(lambda _, n=name: self._open_profile_dir(n))
        btn_trash.clicked.connect(lambda _, n=name: self._delete_profile(n))
        lay.addWidget(lbl, 1)
        lay.addStretch(0)
        lay.addWidget(btn_folder, 0, Qt.AlignVCenter)
        lay.addWidget(btn_trash, 0, Qt.AlignVCenter)
        return card

    def changeEvent(self, e):
        from PySide6.QtCore import QEvent
        super().changeEvent(e)
        if e.type() == QEvent.WindowStateChange:
            minimized = bool(self.windowState() & Qt.WindowMinimized)
            try:
                self.particles.setActive(not minimized)
            except Exception:
                pass
            try:
                self.play_dock.btn.setGlowing(self.play_dock.btn.isEnabled() and not minimized)
            except Exception:
                pass

    def _open_profile_dir(self, name: str):
        p = self._instance_path_for(name)
        p.mkdir(parents=True, exist_ok=True)
        self._open_path(p)

    def _delete_instance_dir(self, path: Path):
        try:
            import gwlauncher_backend as backend
            base = Path(getattr(backend, "INSTANCES_DIR", GW_DIR / "instances")).resolve()
            p = path.resolve()
            if p.is_dir() and base in p.parents and p != base:
                shutil.rmtree(str(p), ignore_errors=True)
        except Exception:
            pass

    def _delete_profile(self, name: str):
        if name == "GatitosWorld ModPack":
            QMessageBox.information(self, "Perfil protegido", "Este perfil no se puede borrar.")
            return
        if name in self._profiles:
            inst = self._instance_path_for(name)
            del self._profiles[name]
            self._save_profiles()
            self._delete_instance_dir(inst)
            self._refresh_list()
            self._set_play_ready(len(self.profiles.selectedItems()) > 0)

    def _instance_path_for(self, name: str) -> Path:
        data = self._profiles.get(name, {})
        version = data.get("version", "")
        loader = (data.get("modloader", "vanilla") or "vanilla").lower()
        import gwlauncher_backend as backend
        base = getattr(backend, "INSTANCES_DIR", GW_DIR / "instances")
        if loader in ("vanilla", ""):
            return base / version if version else base
        try:
            candidates = [p for p in base.iterdir() if p.is_dir() and version in p.name and loader in p.name.lower()]
            if candidates:
                candidates.sort()
                return candidates[-1]
        except Exception:
            pass
        return base / version if version else base

    def _open_path(self, path: Path):
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(path))
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", str(path)])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", str(path)])
        except Exception:
            pass

    def _create_profile(self):
        existing = list(self._profiles.keys()); form = EditorForm(existing)
        def on_cancel(): self.modal.hide_modal()
        def on_save():
            data = form.get_data()
            if not data: return
            name = data.pop("name")
            self._profiles[name] = data; self._save_profiles(); self._refresh_list()
            for i in range(self.profiles.count()):
                w = self.profiles.itemWidget(self.profiles.item(i)).findChild(QLabel, "lblName")
                if w and w.text()==name: self.profiles.setCurrentRow(i); break
            self.modal.hide_modal(); self._set_play_ready(True)
        self.modal.show_form("Nuevo perfil", form, [("Cancelar", on_cancel), ("Guardar", on_save)])

    def _open_editor(self, profile_name: str):
        if not profile_name: return
        p = self._profiles.get(profile_name, {})
        form = EditorForm(list(self._profiles.keys()), {"name":profile_name,"name_locked":True, **p})
        def on_cancel(): self.modal.hide_modal()
        def on_save():
            data = form.get_data()
            if not data: return
            data["name"]=profile_name
            self._profiles[profile_name] = {k:v for k,v in data.items() if k!="name"}; self._save_profiles(); self._refresh_list(); self.modal.hide_modal(); self._set_play_ready(True)
        self.modal.show_form(f"Editar: {profile_name}", form, [("Cancelar", on_cancel), ("Guardar", on_save)])

    def _on_profile_select(self):
        has = len(self.profiles.selectedItems()) > 0
        self.btn_edit.setEnabled(has); self._sync_btn_edit_style()
        self.headline.setText(self._current_profile_name() if has else "Selecciona un perfil")
        self._set_play_ready(has)

    def _sync_btn_edit_style(self):
        self.btn_edit.setProperty("enabled", "true" if self.btn_edit.isEnabled() else "false"); self.btn_edit.style().unpolish(self.btn_edit); self.btn_edit.style().polish(self.btn_edit)

    def _current_profile_name(self) -> str:
        items = self.profiles.selectedItems()
        if not items: return ""
        w = self.profiles.itemWidget(items[0]).findChild(QLabel, "lblName")
        return w.text() if w else items[0].text()

    def _set_play_ready(self, ready: bool):
        self.play_dock.set_ready(ready)

    def _cleanup_launch_thread(self):
        if self._launch_thread:
            self._launch_thread.quit()
            self._launch_thread.wait()
            self._launch_thread.deleteLater()
            self._launch_thread = None
        if self._launch_worker:
            self._launch_worker.deleteLater()
            self._launch_worker = None

    def _launch(self):
        name = self._current_profile_name()
        if not name:
            return
        p = self._profiles.get(name)
        if not p:
            QMessageBox.warning(self, "Perfil no encontrado", "No se pudo cargar el perfil seleccionado.")
            return
        version = p.get("version", "")
        loader = p.get("modloader", "vanilla")
        ram = int(p.get("ram", 2048))
        jvm = p.get("jvmFlags", [])
        if p.get("auth") == "microsoft":
            from auth_backend import list_accounts
            accounts = list_accounts()
            if not accounts:
                QMessageBox.warning(self, "Cuenta Microsoft", "No tienes ninguna cuenta vinculada. Inicia sesión primero.")
                return
            acc = next(iter(accounts.values()))
            username = acc["name"]
        else:
            username = p.get("username") or "Player"
            if name == "GatitosWorld ModPack" and not p.get("username"):
                username, ok = QInputDialog.getText(self, "Nombre de usuario", "Ingresa tu username de Minecraft:")
                if not ok or not username.strip():
                    QMessageBox.warning(self, "Falta username", "Debes ingresar un username para jugar.")
                    return
                p["username"] = username.strip()
                self._profiles[name] = p
                self._save_profiles()
        self.loading.start("Preparando el lanzamiento…")
        self._set_play_ready(False)
        self._launch_thread = QThread(self)
        self._launch_worker = GWLauncher.LaunchWorker(version, username, loader, ram, jvm, GW_DIR, name)
        self._launch_worker.moveToThread(self._launch_thread)
        self._launch_worker.progress.connect(self.loading.set_progress)
        self._launch_worker.finished_err.connect(self._on_launch_error)
        self._launch_worker.ready_to_launch.connect(self._start_process)
        self._launch_thread.started.connect(self._launch_worker.run)
        self._launch_thread.start()

    def _on_launch_error(self, msg: str):
        self.loading.hide()
        QMessageBox.critical(self, "Error al lanzar", msg)
        self._set_play_ready(True)
        self._rpc_set_browsing()
        self._cleanup_launch_thread()

    def _start_process(self, cmd: list[str], cwd: str):
        proc = QProcess(self)
        proc.setProgram(cmd[0])
        proc.setArguments(cmd[1:])
        proc.setWorkingDirectory(cwd)
        proc.setProcessChannelMode(QProcess.MergedChannels)
        proc.readyReadStandardOutput.connect(lambda: sys.stdout.write(proc.readAllStandardOutput().data().decode(errors="ignore")))
        proc.readyReadStandardError.connect(lambda: sys.stderr.write(proc.readAllStandardError().data().decode(errors="ignore")))
        proc.started.connect(lambda: (self.loading.finish(), self._rpc_set_ip(), self.hide(), self.tray.showMessage("GW Launcher", "Minecraft iniciado", QSystemTrayIcon.Information, 2000)))
        proc.finished.connect(lambda _, __: QApplication.instance().quit())
        proc.start()

    def show_profiles_json(self):
        html = "<pre>"+json.dumps(self._profiles, indent=2, ensure_ascii=False)+"</pre>"
        self.modal.show_modal("Perfiles", html, [("Cerrar", self.modal.hide_modal)])

    def _open_login(self):
        from auth_backend import begin_device_login, complete_device_login, _save_accounts, list_accounts

        if self._ms_login_in_progress:
            try:
                self.modal.show()
                self.modal.raise_()
            except Exception:
                pass
            return

        accounts = list_accounts()
        if accounts:
            acc = next(iter(accounts.values()))
            def do_logout():
                _save_accounts({})
                self.modal.hide_modal()
                QMessageBox.information(self, "Cerrar sesión", f"Cerró la sesión de {acc.get('name')}.")
                self._refresh_login_status()
            self.modal.show_modal_2(
                "Cerrar sesión",
                f"<p style='color:#ff5555;font-weight:bold;'>¿Cerrar sesión <b>{acc.get('name')}</b>?</p>",
                [("Cancelar", self.modal.hide_modal), ("❌ Cerrar sesión", do_logout)]
            )
            return

        try:
            step = begin_device_login()
        except Exception as e:
            QMessageBox.critical(self, "Error de login", str(e))
            return

        self._ms_login_in_progress = True
        try:
            self.titlebar.btn_login.setEnabled(False)
        except Exception:
            pass

        form = GWLauncher.DeviceLoginForm(step["user_code"], step["verification_uri"])

        def open_link():
            QDesktopServices.openUrl(QUrl(step["verification_uri"]))

        class DeviceWorker(QObject):
            finished = Signal(dict)
            failed = Signal(str)

            @Slot()
            def run(self):
                try:
                    acc = complete_device_login(step["device_code"], 3, 300)
                    self.finished.emit(acc)
                except Exception as ex:
                    self.failed.emit(str(ex))

        worker = DeviceWorker()
        th = QThread(self)
        worker.moveToThread(th)
        th.setObjectName("MsLoginThread")
        th.started.connect(worker.run)

        self._ms_login_worker = worker
        self._ms_login_thread = th
        
        def stop_thread():
            try:
                th.quit()
                th.wait(50)
            except Exception:
                pass
            worker.deleteLater()
            th.deleteLater()
            
        def _stop_ms_timers():
            if hasattr(self, "_ms_login_timer") and self._ms_login_timer.isActive():
                self._ms_login_timer.stop()
            if hasattr(self, "_ms_login_progress") and self._ms_login_progress.isActive():
                self._ms_login_progress.stop()

        self._ms_login_cancelled = False
        
        def _thread_quit_and_cleanup():
            t = self._ms_login_thread
            if t:
                try:
                    t.quit()
                    t.wait(200)
                except Exception:
                    pass
            self._cleanup_ms_login_thread(force=False)
            
        def _finish_ui_common():
            _stop_ms_timers()
            self.loading.finish()
            self._ms_login_in_progress = False
            try:
                self.titlebar.btn_login.setEnabled(True)
            except Exception:
                pass
                
        def on_done(acc: dict):
            def ui_update():
                _finish_ui_common()

                if not self._ms_login_cancelled:
                    data = {acc["id"]: acc}
                    _save_accounts(data)

                    sel = self._current_profile_name()
                    if sel and sel in self._profiles and not self._profiles[sel].get("username"):
                        self._profiles[sel]["username"] = acc.get("name", "")
                        self._save_profiles()
                        self._refresh_list()

                    self.modal.hide_modal()
                    self._refresh_login_status()
                    self._set_play_ready(len(self.profiles.selectedItems()) > 0)
                    try:
                        self.tray.showMessage(
                            "GW Launcher",
                            f"Sesión iniciada como {acc.get('name','')}",
                            QSystemTrayIcon.Information,
                            2000
                        )
                    except Exception:
                        pass
                _thread_quit_and_cleanup()
            QTimer.singleShot(0, ui_update)

        def on_fail(msg: str):
            def ui_update():
                _finish_ui_common()

                if not self._ms_login_cancelled:
                    self.modal.show_modal_2(
                        "Error de login",
                        msg,
                        [("Cerrar", self.modal.hide_modal)]
                    )

                _thread_quit_and_cleanup()

            QTimer.singleShot(0, ui_update)

        worker.finished.connect(on_done)
        worker.failed.connect(on_fail)

        timeout_s = 300
        self.loading.start("Iniciando sesión con Microsoft…")
        th.start()

        self._ms_login_timer = QTimer(self)
        self._ms_login_timer.setSingleShot(True)
        self._ms_login_timer.timeout.connect(lambda: on_fail("Tiempo de espera agotado (5 min). Intenta de nuevo."))
        self._ms_login_timer.start(timeout_s * 1000)

        self._ms_login_elapsed = 0
        
        def tick_progress():
            self._ms_login_elapsed += 1
            percent = int(min(self._ms_login_elapsed / timeout_s, 1) * 100)
            self.loading.set_progress(percent, "Esperando confirmación de Microsoft…")
            if self._ms_login_elapsed >= timeout_s:
                self._ms_login_progress.stop()

        self._ms_login_progress = QTimer(self)
        self._ms_login_progress.timeout.connect(tick_progress)
        self._ms_login_progress.start(1000)
        
        def on_cancel():
            self._ms_login_cancelled = True
            _finish_ui_common()
            self.modal.hide_modal()
            
        self.modal.show_form(
            "Iniciar sesión con Microsoft",
            form,
            [("Enlace", open_link), ("Cancelar", on_cancel)],
            on_dismiss=on_cancel
        )
        
    def closeEvent(self, e):
        try:
            self._cleanup_ms_login_thread(force=True)
            self._cleanup_launch_thread()
            try:
                self.particles.setActive(False)
            except Exception:
                pass
            try:
                self.play_dock.btn.setGlowing(False)
            except Exception:
                pass
            self.rpc.stop()
        except Exception:
            pass
        super().closeEvent(e)

def _single_instance_guard(key: str = "GWLauncherSingletonKey") -> Optional[QSharedMemory]:
    shm = QSharedMemory(key)
    if not shm.create(1):
        return None
    return shm

def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    guard = _single_instance_guard()
    if guard is None:
        QMessageBox.critical(None, "GW Launcher", "Ya hay una instancia en ejecución.")
        sys.exit(1)

    w = GWLauncher()
    screen = QGuiApplication.primaryScreen().availableGeometry()
    w.resize(int(screen.width() * 0.8), int(screen.height() * 0.8))
    w.move(screen.center().x() - w.width() // 2, screen.center().y() - w.height() // 2)
    w.setWindowIcon(QIcon(str(ASSETS["icon"])))
    w.show()

    exit_code = app.exec()
    del guard
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
