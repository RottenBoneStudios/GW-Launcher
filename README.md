# GW Launcher

**GW Launcher** es un launcher personalizado de **Minecraft** escrito en **Python + PySide6**, con interfaz moderna y soporte para:

- Gestión de perfiles (nombre, versión, RAM, flags JVM, modloaders).
- Instalación automática de **Java** requerido por cada versión de Minecraft.
- Soporte para **Vanilla, Forge, Fabric y Quilt**.
- Discord Rich Presence con estado de "Jugando Minecraft" y la IP del servidor.
- Bloqueo de instancia única (solo un launcher abierto a la vez).
- Se minimiza a la bandeja del sistema mientras Minecraft está abierto y se cierra automáticamente al salir del juego.

---

## Requisitos

Antes de instalar, asegúrate de tener:

- Python **3.10+**
- [Git](https://git-scm.com/downloads)
- Discord instalado y abierto (para el Rich Presence)

Dependencias Python:

```bash
pip install PySide6 minecraft-launcher-lib requests pypresence
```

Ejecución
Ejecuta directamente con: python gw_launcher.py

## Crear la build (ejecutable)
Este proyecto usa PyInstaller para crear un ejecutable portable:
Instala PyInstaller:
```bash
pip install pyinstaller
```

Genera el ejecutable:
```bash
python -m PyInstaller --onefile --windowed --noconfirm --clean --icon="%CD%\src\assets\icon.ico" --add-data "src/assets;assets" --name "GWLauncher" src/gw_launcher.py
```
El ejecutable se generará en la carpeta dist/ como:
dist/GWLauncher.exe   (Windows)

## Estructura del proyecto
```
gw-launcher/
├── gw_launcher.py          # Interfaz principal (PySide6)
├── gwlauncher_backend.py   # Backend para instalación y lanzamiento de Minecraft
├── discord_rpc.py          # Integración con Discord Rich Presence
├── assets/                 # Imágenes, iconos y recursos
│   ├── icon.ico
│   ├── background.png
│   └── ...
└── README.md
```
## Notas
- El launcher instala automáticamente la versión de Java necesaria para cada versión de Minecraft.
- Se cierra automáticamente cuando cierras Minecraft.
- Si intentas abrir dos veces el launcher, la segunda instancia no se abrirá.
- Se recomienda usar Windows 10/11 o Linux moderno para compatibilidad total.

