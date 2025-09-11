# GW Launcher

**GW Launcher** es un launcher personalizado de **Minecraft** escrito en **Python + PySide6**, con interfaz moderna y soporte para:

- Gesti贸n de perfiles (nombre, versi贸n, RAM, flags JVM, modloaders).
- Instalaci贸n autom谩tica de **Java** requerido por cada versi贸n de Minecraft.
- Soporte para **Vanilla, Forge, Fabric y Quilt**.
- Discord Rich Presence con estado de "Jugando Minecraft" y la IP del servidor.
- Bloqueo de instancia 煤nica (solo un launcher abierto a la vez).
- Se minimiza a la bandeja del sistema mientras Minecraft est谩 abierto y se cierra autom谩ticamente al salir del juego.

---

## Requisitos

Antes de instalar, aseg煤rate de tener:

- Python **3.10+**
- [Git](https://git-scm.com/downloads)
- Discord instalado y abierto (para el Rich Presence)

Dependencias Python:

```bash
pip install PySide6 minecraft-launcher-lib requests pypresence
```

---

## Instalaci贸n y ejecuci贸n

Clona el repositorio y entra al directorio:

```bash
git clone https://github.com/tuusuario/gw-launcher.git
cd gw-launcher
```

Ejecuta directamente con:

```bash
python gw_launcher.py
```

---

## Crear la build (ejecutable)

Este proyecto usa **PyInstaller** para crear un ejecutable portable:

1. Instala PyInstaller:

```bash
pip install pyinstaller
```

2. Genera el ejecutable:

```bash
pyinstaller -F gw_launcher.py --hidden-import pypresence --name GWLauncher --icon assets/icon.ico
```

El ejecutable se generar谩 en la carpeta `dist/` como:

```
dist/GWLauncher.exe   (Windows)
dist/GWLauncher       (Linux/Mac)
```

---

## Estructura del proyecto

```
gw-launcher/
鈹溾攢鈹€ gw_launcher.py          # Interfaz principal (PySide6)
鈹溾攢鈹€ gwlauncher_backend.py   # Backend para instalaci贸n y lanzamiento de Minecraft
鈹溾攢鈹€ discord_rpc.py          # Integraci贸n con Discord Rich Presence
鈹溾攢鈹€ assets/                 # Im谩genes, iconos y recursos
鈹?  鈹溾攢鈹€ icon.ico
鈹?  鈹溾攢鈹€ background.png
鈹?  鈹斺攢鈹€ ...
鈹斺攢鈹€ README.md
```

---

## Notas

- El launcher instala autom谩ticamente la versi贸n de **Java** necesaria para cada versi贸n de Minecraft.
- Se cierra autom谩ticamente cuando cierras Minecraft.
- Si intentas abrir dos veces el launcher, la segunda instancia no se abrir谩.
- Se recomienda usar **Windows 10/11** o **Linux** moderno para compatibilidad total.

---

## Licencia

Este proyecto es de uso personal/educativo.  
No est谩 afiliado con **Mojang Studios** ni **Microsoft**.
