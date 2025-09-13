# modrinth_browser.py
import sys, json, urllib.request, base64, zlib
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QMessageBox, QComboBox, QLabel, QFrame, QAbstractItemView,
    QDialog
)
from PySide6.QtCore import Qt, QPoint, QThreadPool, QRunnable, Signal, QObject
from PySide6.QtGui import QPixmap, QPalette, QBrush, QIcon, QPainter, QColor
from gw_launcher import BASE_DIR, GW_DIR, PALETTE, ASSETS

INSTANCES_DIR = GW_DIR / "instances"
INSTANCES_DIR.mkdir(parents=True, exist_ok=True)

def fetch_modrinth_search(query: str, limit=20, popular=False):
    if popular:
        url = f"https://api.modrinth.com/v2/search?limit={limit}&index=downloads"
    else:
        url = f"https://api.modrinth.com/v2/search?query={query}&limit={limit}"
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read().decode("utf-8")).get("hits", [])

def fetch_mod_versions(mod_id: str):
    url = f"https://api.modrinth.com/v2/project/{mod_id}/version"
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read().decode("utf-8"))

def download_file(url: str, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest)

class WorkerSignals(QObject):
    result = Signal(object)
    error = Signal(Exception)
    finished = Signal()

class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.result.emit(result)
        except Exception as e:
            self.signals.error.emit(e)
        finally:
            self.signals.finished.emit()

class ModCard(QWidget):
    def __init__(self, mod: dict):
        super().__init__()
        self.mod = mod
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: rgba(21, 23, 56, 0.6);
                border: none;
            }}
            QLabel {{
                color: {PALETTE['fg']};
            }}
            QLabel#title {{
                font-size: 16px;
                font-weight: bold;
                color: white;
            }}
            QLabel#desc {{
                font-size: 13px;
                color: #bbb;
            }}
            """
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(32, 16, 32, 16)
        layout.setSpacing(16)
        self.img_label = QLabel()
        self.img_label.setFixedSize(56, 56)
        self.img_label.setStyleSheet("background: #222;")
        layout.addWidget(self.img_label)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(8)
        self.title = QLabel(mod.get("title", "Sin título"))
        self.title.setObjectName("title")
        self.desc = QLabel(mod.get("description", ""))
        self.desc.setObjectName("desc")
        self.desc.setWordWrap(True)
        self.desc.setFixedHeight(48)
        text_layout.addWidget(self.title)
        text_layout.addWidget(self.desc)
        layout.addLayout(text_layout)
        icon_url = mod.get("icon_url")
        if icon_url:
            worker = Worker(self._load_icon, icon_url)
            worker.signals.result.connect(self._set_icon)
            QThreadPool.globalInstance().start(worker)

    def _load_icon(self, url):
        data = urllib.request.urlopen(url).read()
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        return pixmap

    def _set_icon(self, pixmap: QPixmap):
        self.img_label.setPixmap(pixmap.scaled(56, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation))

class MiniTitleBar(QWidget):
    def __init__(self, parent: QDialog):
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.addStretch(1)
        self.btn_close = QPushButton("✕", self)
        self.btn_close.setFixedSize(40, 28)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setStyleSheet(
            f"QPushButton {{ border: 0; background: transparent; color: {PALETTE['fg']}; font-size: 16px; }}"
            f"QPushButton:hover {{ background: #e81123; }}"
        )
        self.btn_close.clicked.connect(self._close_window)
        lay.addWidget(self.btn_close)

    def _close_window(self):
        self.window().close()

class ModrinthBrowser(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Explorador de Mods")
        self.setWindowIcon(QIcon(str(ASSETS["icon"])))
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.resize(850, 600)
        if ASSETS["background"].exists():
            pm = QPixmap(str(ASSETS["background"]))
            palette = QPalette()
            scaled = pm.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            darkened = QPixmap(scaled.size())
            darkened.fill(Qt.transparent)

            p = QPainter(darkened)
            p.drawPixmap(0, 0, scaled)
            p.fillRect(darkened.rect(), QColor(0, 0, 0, 120))  # <- aquí controlas el nivel de oscurecimiento
            p.end()

            palette.setBrush(QPalette.Window, QBrush(darkened))
            self.setPalette(palette)
            self.setAutoFillBackground(True)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.titlebar = MiniTitleBar(self)
        root_layout.addWidget(self.titlebar)
        main = QFrame()
        main.setObjectName("content")
        main.setStyleSheet(
            f"QFrame#content {{ background: {PALETTE['bg_card']}; border-radius: {PALETTE['radius']}px; padding: 16px; }} "
            f"QLabel#headline {{ color: {PALETTE['fg']}; font-size: 20px; font-weight: 600; }} "
            f"QLineEdit {{ background: #0f1027; border: 1px solid rgba(255,255,255,0.2); border-radius: 8px; padding: 8px; color: {PALETTE['fg']}; }} "
            f"QPushButton {{ border: 0; border-radius: 8px; padding: 8px 14px; font-weight: 600; }} "
            f"QPushButton#btnSearch {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {PALETTE['primary']}, stop:1 {PALETTE['accent']}); color: white; }} "
            f"QPushButton#btnSearch:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {PALETTE['primary_hov']}, stop:1 {PALETTE['accent']}); }} "
            f"QPushButton#btnEdit {{ background: #555; color: white; }} "
            f"QPushButton#btnEdit:hover {{ background: #666; }} "
            f"QListWidget {{ background: transparent; border: none; color: {PALETTE['fg']}; font-size: 14px; }} "
            f"QListWidget::item {{ padding: 8px; border: none; }} "
            f"QListWidget::item:hover {{ background: rgba(255,255,255,0.08); }} "
            f"QComboBox {{ background: #0f1027; border-radius: 6px; padding: 6px; color: {PALETTE['fg']}; }} "
            f"QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 0 4px 0; }} "
            f"QScrollBar::handle:vertical {{ background: {PALETTE['primary']}; border-radius: 5px; min-height: 24px; }} "
            f"QScrollBar::handle:vertical:hover {{ background: {PALETTE['primary_hov']}; }} "
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }} "
            f"QScrollBar:horizontal {{ height: 0; }} "
        )
        v = QVBoxLayout(main)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(12)
        title = QLabel("🌍 Explorar Mods en Modrinth")
        title.setObjectName("headline")
        v.addWidget(title)
        search_layout = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Buscar mods en Modrinth...")
        self.btn_search = QPushButton("🔍 Buscar")
        self.btn_search.setObjectName("btnSearch")
        self.btn_search.clicked.connect(self.do_search)
        search_layout.addWidget(self.search_box, 1)
        search_layout.addWidget(self.btn_search)
        v.addLayout(search_layout)
        self.results = QListWidget()
        self.results.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.results.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.results.itemDoubleClicked.connect(self.show_mod_versions)
        v.addWidget(self.results, 1)
        footer = QFrame()
        fv = QHBoxLayout(footer)
        fv.setContentsMargins(0, 0, 0, 0)
        lbl_profile = QLabel("Instalar en perfil:")
        lbl_profile.setStyleSheet(f"color: {PALETTE['fg']};")
        self.profiles_box = QComboBox()
        self._load_profiles()
        self.btn_edit = QPushButton("Editar Mods")
        self.btn_edit.setObjectName("btnEdit")
        self.btn_edit.clicked.connect(self.edit_instance)
        self.btn_share = QPushButton("Compartir")
        self.btn_share.setObjectName("btnEdit")
        self.btn_share.clicked.connect(self.share_instance)
        self.btn_import = QPushButton("Importar")
        self.btn_import.setObjectName("btnEdit")
        self.btn_import.clicked.connect(self.import_instance)
        fv.addWidget(lbl_profile)
        fv.addWidget(self.profiles_box, 1)
        fv.addWidget(self.btn_edit)
        fv.addWidget(self.btn_share)
        fv.addWidget(self.btn_import)
        v.addWidget(footer)
        root_layout.addWidget(main, 1)
        self.show_popular()

    def share_instance(self):
        profile_dir: Path = self.profiles_box.currentData()
        if not profile_dir:
            QMessageBox.warning(self, "Perfil no seleccionado", "Selecciona un perfil para compartir sus mods.")
            return
        dlg = ShareDialog(self, profile_dir)
        dlg.exec()

    def import_instance(self):
        profile_dir: Path = self.profiles_box.currentData()
        if not profile_dir:
            QMessageBox.warning(self, "Perfil no seleccionado", "Selecciona un perfil para importar mods.")
            return
        dlg = ImportDialog(self, profile_dir)
        dlg.exec()

    def edit_instance(self):
        profile_dir: Path = self.profiles_box.currentData()
        if not profile_dir:
            QMessageBox.warning(self, "Perfil no seleccionado", "Selecciona un perfil para editar sus mods.")
            return
        dlg = InstanceEditorDialog(self, profile_dir)
        dlg.exec()

    def _load_profiles(self):
        if INSTANCES_DIR.exists():
            for folder in INSTANCES_DIR.iterdir():
                if folder.is_dir():
                    self.profiles_box.addItem(folder.name, folder)

    def _load_mods(self, query="", popular=False):
        self.results.clear()
        worker = Worker(fetch_modrinth_search, query, 20, popular)
        worker.signals.result.connect(self._populate_mods)
        worker.signals.error.connect(lambda e: QMessageBox.critical(self, "Error", str(e)))
        QThreadPool.globalInstance().start(worker)

    def _populate_mods(self, mods: list):
        for mod in mods:
            card = ModCard(mod)
            item = QListWidgetItem(self.results)
            item.setSizeHint(card.sizeHint())
            item.setData(Qt.UserRole, mod)
            self.results.addItem(item)
            self.results.setItemWidget(item, card)

    def show_popular(self):
        self._load_mods("", popular=True)

    def do_search(self):
        query = self.search_box.text().strip()
        if not query:
            self.show_popular()
        else:
            self._load_mods(query)

    def _install_with_dependencies(self, version: dict, profile_dir: Path):
        mods_dir = profile_dir / "mods"
        mods_dir.mkdir(parents=True, exist_ok=True)
        installed_files = {f.name for f in mods_dir.glob("*.jar")}
        to_install = [(version["project_id"], version)]
        while to_install:
            mod_id, v = to_install.pop(0)
            file = v["files"][0]
            filename = file["filename"]
            dest = mods_dir / filename
            if filename in installed_files:
                continue
            download_file(file["url"], dest)
            installed_files.add(filename)
            for dep in v.get("dependencies", []):
                if dep.get("dependency_type") in ("required", "embedded"):
                    dep_id = dep.get("project_id")
                    if dep_id:
                        dep_versions = fetch_mod_versions(dep_id)
                        if dep_versions:
                            to_install.append((dep_id, dep_versions[0]))

    def show_mod_versions(self, item: QListWidgetItem):
        mod = item.data(Qt.UserRole)
        try:
            versions = fetch_mod_versions(mod["project_id"])
            if not versions:
                QMessageBox.information(self, "Sin versiones", "Este mod no tiene builds disponibles.")
                return
            stable_per_mc = {}
            for v in versions:
                if v.get("version_type") == "release":
                    for mc in v.get("game_versions", []):
                        if mc not in stable_per_mc:
                            stable_per_mc[mc] = v
            filtered = list(stable_per_mc.values())
            latest = versions[0] if versions else None
            if latest and latest not in filtered:
                filtered.insert(0, latest)
            if not filtered:
                QMessageBox.information(self, "Sin versiones válidas", "No se encontraron versiones para mostrar.")
                return
            profile_dir: Path = self.profiles_box.currentData()
            if not profile_dir:
                QMessageBox.warning(self, "Perfil no seleccionado", "Selecciona un perfil para instalar el mod.")
                return
            profile = {}
            profile_file = profile_dir / "profile.json"
            if profile_file.exists():
                try:
                    profile = json.loads(profile_file.read_text())
                except Exception:
                    pass
            dlg = VersionSelectDialog(self, mod["title"], filtered, profile)
            if dlg.exec() == QDialog.Accepted and dlg.selected_version:
                self._install_with_dependencies(dlg.selected_version, profile_dir)
                QMessageBox.information(self, "Instalado", f"{dlg.selected_version['name']} y dependencias instalados en {profile_dir / 'mods'}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

class VersionSelectDialog(QDialog):
    def __init__(self, parent, mod_name: str, versions: list[dict], profile: dict):
        super().__init__(parent)
        self.setWindowTitle(f"Seleccionar versión - {mod_name}")
        self.setWindowIcon(QIcon(str(ASSETS["icon"])))
        self.setFixedSize(600, 300)
        self.setFixedSize(600, 300)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.selected_version = None
        self.profile = profile

        if ASSETS["background"].exists():
            pm = QPixmap(str(ASSETS["background"]))
            palette = QPalette()
            palette.setBrush(QPalette.Window, QBrush(pm.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)))
            self.setPalette(palette)
            self.setAutoFillBackground(True)

        frame = QFrame(self)
        frame.setObjectName("content")
        frame.setStyleSheet(
            f"QFrame#content {{ background: {PALETTE['bg_card']}; border-radius: {PALETTE['radius']}px; }}"
            f"QLabel {{ color: {PALETTE['fg']}; font-size: 14px; }}"
            f"QPushButton {{ border: 0; border-radius: 8px; padding: 8px 14px; font-weight: 600; }}"
            f"QPushButton#btnOk {{ background: {PALETTE['primary']}; color: white; }}"
            f"QPushButton#btnOk:hover {{ background: {PALETTE['primary_hov']}; }}"
            f"QPushButton#btnCancel {{ background: #333; color: {PALETTE['fg']}; }}"
            f"QPushButton#btnCancel:hover {{ background: #444; }}"
            f"QListWidget {{ background: #0f1027; border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; color: {PALETTE['fg']}; }}"
            f"QListWidget::item {{ padding: 8px; }}"
            f"QListWidget::item:selected {{ background: {PALETTE['primary']}; color: white; }}"
        )

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        lbl = QLabel("Selecciona la versión que deseas instalar:")
        layout.addWidget(lbl)

        self.list = QListWidget(self)
        for v in versions:
            mc_versions = ", ".join(v.get("game_versions", []))
            loaders = ", ".join(v.get("loaders", []))
            item = QListWidgetItem(f"{v['name']} | MC: {mc_versions} | Loader: {loaders}")
            item.setData(Qt.UserRole, v)

            if profile:
                pv = profile.get("version")
                pl = profile.get("modloader", "vanilla").lower()
                if pv not in v.get("game_versions", []) or pl not in v.get("loaders", []):
                    item.setForeground(Qt.red)
                    item.setText(item.text() + " ❌ Incompatible")
                else:
                    item.setForeground(Qt.green)
                    item.setText(item.text() + " ✅ Compatible")

            self.list.addItem(item)

        layout.addWidget(self.list, 1)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setObjectName("btnCancel")
        btn_ok = QPushButton("Instalar")
        btn_ok.setObjectName("btnOk")
        btn_ok.clicked.connect(self._accept)
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_ok)
        layout.addLayout(btns)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(frame)

    def _accept(self):
        item = self.list.currentItem()
        if not item:
            QMessageBox.warning(self, "Nada seleccionado", "Debes elegir una versión.")
            return
        v = item.data(Qt.UserRole)

        pv = self.profile.get("version")
        pl = self.profile.get("modloader", "vanilla").lower()
        if pv not in v.get("game_versions", []) or pl not in v.get("loaders", []):
            QMessageBox.critical(self, "Incompatible", f"⚠️ Esta versión no es compatible con tu perfil ({pv}, {pl}).")
            return

        self.selected_version = v
        self.accept()

class InstanceEditorDialog(QDialog):
    def __init__(self, parent, profile_dir: Path):
        super().__init__(parent)
        self.setWindowTitle("Editar Mods de la Instancia")
        self.setWindowIcon(QIcon(str(ASSETS["icon"])))
        self.setFixedSize(600, 400)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.profile_dir = profile_dir
        self.mods_dir = profile_dir / "mods"
        self.selected_file = None

        if ASSETS["background"].exists():
            pm = QPixmap(str(ASSETS["background"]))
            palette = QPalette()
            palette.setBrush(QPalette.Window, QBrush(pm.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)))
            self.setPalette(palette)
            self.setAutoFillBackground(True)

        frame = QFrame(self)
        frame.setObjectName("content")
        frame.setStyleSheet(
            f"QFrame#content {{ background: {PALETTE['bg_card']}; border-radius: {PALETTE['radius']}px; }} "
            f"QLabel {{ color: {PALETTE['fg']}; font-size: 14px; }} "
            f"QPushButton {{ border: 0; border-radius: 8px; padding: 8px 14px; font-weight: 600; }} "
            f"QPushButton#btnRemove {{ background: #d9534f; color: white; }} "
            f"QPushButton#btnRemove:hover {{ background: #c9302c; }} "
            f"QPushButton#btnClose {{ background: #333; color: {PALETTE['fg']}; }} "
            f"QPushButton#btnClose:hover {{ background: #444; }} "
            f"QListWidget {{ background: #0f1027; border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; color: {PALETTE['fg']}; }} "
            f"QListWidget::item {{ padding: 8px; }} "
            f"QListWidget::item:selected {{ background: {PALETTE['primary']}; color: white; }} "
        )

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        lbl = QLabel(f"Mods instalados en: {profile_dir.name}")
        layout.addWidget(lbl)

        self.list = QListWidget(self)
        if self.mods_dir.exists():
            for mod_file in sorted(self.mods_dir.glob("*.jar")):
                item = QListWidgetItem(mod_file.name)
                item.setData(Qt.UserRole, mod_file)
                self.list.addItem(item)
        layout.addWidget(self.list, 1)

        btns = QHBoxLayout()
        self.btn_remove = QPushButton("Eliminar seleccionado")
        self.btn_remove.setObjectName("btnRemove")
        self.btn_close = QPushButton("Cerrar")
        self.btn_close.setObjectName("btnClose")
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_close.clicked.connect(self.reject)
        btns.addWidget(self.btn_remove)
        btns.addWidget(self.btn_close)
        layout.addLayout(btns)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(frame)

    def _remove_selected(self):
        item = self.list.currentItem()
        if not item:
            QMessageBox.warning(self, "Nada seleccionado", "Debes seleccionar un mod para eliminar.")
            return
        mod_file: Path = item.data(Qt.UserRole)
        confirm = QMessageBox.question(self, "Confirmar eliminación", f"¿Eliminar {mod_file.name}?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            try:
                mod_file.unlink()
                self.list.takeItem(self.list.row(item))
                QMessageBox.information(self, "Eliminado", f"{mod_file.name} eliminado de la instancia.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo eliminar el mod: {e}")

class ShareDialog(QDialog):
    def __init__(self, parent, profile_dir: Path):
        super().__init__(parent)
        self.setWindowTitle("Compartir Mods")
        self.setWindowIcon(QIcon(str(ASSETS["icon"])))
        self.setFixedSize(600, 300)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.profile_dir = profile_dir
        self.mods_dir = profile_dir / "mods"

        if ASSETS["background"].exists():
            pm = QPixmap(str(ASSETS["background"]))
            palette = QPalette()
            palette.setBrush(QPalette.Window, QBrush(pm.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)))
            self.setPalette(palette)
            self.setAutoFillBackground(True)

        frame = QFrame(self)
        frame.setObjectName("content")
        frame.setStyleSheet(
            f"QFrame#content {{ background: {PALETTE['bg_card']}; border-radius: {PALETTE['radius']}px; }}"
            f"QLabel {{ color: {PALETTE['fg']}; font-size: 14px; }}"
            f"QLineEdit {{ background: #0f1027; border: 1px solid rgba(255,255,255,0.2); border-radius: 6px; padding: 6px; color: {PALETTE['fg']}; }}"
            f"QPushButton {{ border: 0; border-radius: 8px; padding: 6px 12px; font-weight: 600; }}"
            f"QPushButton#btnClose {{ background: #333; color: {PALETTE['fg']}; }}"
            f"QPushButton#btnClose:hover {{ background: #444; }}"
        )

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16,16,16,16)
        layout.setSpacing(10)

        lbl = QLabel("Código para compartir mods con tus amigos:")
        layout.addWidget(lbl)

        self.code_box = QLineEdit(self)
        self.code_box.setReadOnly(True)
        layout.addWidget(self.code_box, 1)

        btns = QHBoxLayout()
        self.btn_close = QPushButton("Cerrar")
        self.btn_close.setObjectName("btnClose")
        self.btn_close.clicked.connect(self.reject)
        btns.addStretch(1)
        btns.addWidget(self.btn_close)
        layout.addLayout(btns)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(frame)

        self._generate_code()

    def _generate_code(self):
        mods = []
        if self.mods_dir.exists():
            for jar in sorted(self.mods_dir.glob("*.jar")):
                mods.append(jar.name)
        payload = json.dumps({"mods": mods}).encode("utf-8")
        compressed = zlib.compress(payload)
        code = base64.urlsafe_b64encode(compressed).decode("utf-8")
        self.code_box.setText(code)

class ImportDialog(QDialog):
    def __init__(self, parent, profile_dir: Path):
        super().__init__(parent)
        self.setWindowTitle("Importar Mods")
        self.setWindowIcon(QIcon(str(ASSETS["icon"])))
        self.setFixedSize(600, 300)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.profile_dir = profile_dir
        self.mods_dir = profile_dir / "mods"

        if ASSETS["background"].exists():
            pm = QPixmap(str(ASSETS["background"]))
            palette = QPalette()
            palette.setBrush(QPalette.Window, QBrush(pm.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)))
            self.setPalette(palette)
            self.setAutoFillBackground(True)

        frame = QFrame(self)
        frame.setObjectName("content")
        frame.setStyleSheet(
            f"QFrame#content {{ background: {PALETTE['bg_card']}; border-radius: {PALETTE['radius']}px; }}"
            f"QLabel {{ color: {PALETTE['fg']}; font-size: 14px; }}"
            f"QLineEdit {{ background: #0f1027; border: 1px solid rgba(255,255,255,0.2); border-radius: 6px; padding: 6px; color: {PALETTE['fg']}; }}"
            f"QPushButton {{ border: 0; border-radius: 8px; padding: 6px 12px; font-weight: 600; }}"
            f"QPushButton#btnImport {{ background: {PALETTE['primary']}; color: white; }}"
            f"QPushButton#btnImport:hover {{ background: {PALETTE['primary_hov']}; }}"
            f"QPushButton#btnClose {{ background: #333; color: {PALETTE['fg']}; }}"
            f"QPushButton#btnClose:hover {{ background: #444; }}"
        )

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16,16,16,16)
        layout.setSpacing(10)

        lbl = QLabel("Pega el código compartido:")
        layout.addWidget(lbl)

        self.code_box = QLineEdit(self)
        layout.addWidget(self.code_box, 1)

        btns = QHBoxLayout()
        self.btn_import = QPushButton("Importar")
        self.btn_import.setObjectName("btnImport")
        self.btn_import.clicked.connect(self._do_import)
        self.btn_close = QPushButton("Cerrar")
        self.btn_close.setObjectName("btnClose")
        self.btn_close.clicked.connect(self.reject)
        btns.addWidget(self.btn_import)
        btns.addWidget(self.btn_close)
        layout.addLayout(btns)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(frame)

    def _do_import(self):
        try:
            code = self.code_box.text().strip()
            if not code:
                QMessageBox.warning(self, "Error", "Debes pegar un código.")
                return
            data = base64.urlsafe_b64decode(code.encode("utf-8"))
            payload = json.loads(zlib.decompress(data).decode("utf-8"))
            mods = payload.get("mods", [])
            if not mods:
                QMessageBox.information(self, "Vacío", "No se encontraron mods en el código.")
                return
            installed = []
            for name in mods:
                if not any((self.mods_dir / f).exists() for f in [name]):
                    installed.append(name)
            QMessageBox.information(self, "Importado", f"Lista de mods importada: {', '.join(mods)}\nLos mods deben descargarse manualmente desde Modrinth.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Código inválido: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(ASSETS["icon"])))
    dlg = ModrinthBrowser()
    dlg.exec()
    sys.exit(0)
    