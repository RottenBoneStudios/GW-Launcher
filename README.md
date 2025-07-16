# GW Launcher

> *Minecraft No‑Premium desktop launcher construido con Electron + Python*

---

## Índice

1. [Descripción](#descripción)
2. [Características](#características)
3. [Requisitos](#requisitos)
4. [Instalación](#instalación)
5. [Uso](#uso)
6. [Empaquetado y distribución](#empaquetado-y-distribución)
7. [Estructura del proyecto](#estructura-del-proyecto)
8. [CLI del backend](#cli-del-backend)
9. [Contribuir](#contribuir)
10. [Licencia](#licencia)

---

## Descripción

**GW Launcher** es un lanzador no‑premium para Minecraft escrito en JavaScript (Electron) y Python.
La interfaz gráfica corre en Electron 25 y delega todas las operaciones específicas del juego (descarga de versiones, instalación de mod‑loaders, construcción y ejecución del comando `java`) a un módulo Python (`gwlauncher_backend.py`).

Diseñado para ser **multiplataforma** (Windows, macOS y Linux) y fácil de clonar, ejecutar y empaquetar.

## Características

* Descarga automática de cualquier versión oficial de Minecraft.
* Soporte opcional para **Forge**, **Fabric** y **NeoForge**.
* Ejecución *offline* con UUID determinista por nombre de usuario.
* Persiste el último perfil usado en `~/.gwlauncher/profiles.json`.
* CLI de backend para instalar, lanzar o listar versiones sin abrir la GUI.

## Requisitos

| Herramienta | Versión recomendada | Comentario                     |
| ----------- | ------------------- | ------------------------------ |
| **Node.js** | ≥ 18.x              | Probado con Electron 25        |
| **npm**     | Pareada con tu Node | —                              |
| **Python**  | ≥ 3.9               | Necesario por `typing.Literal` |
| **Git**     | Cualquiera          | Para clonar el repo            |

### Dependencias Node (vienen en `package.json`)

```json
"dependencies": {},
"devDependencies": {
  "electron": "^25.0.0",
  "electron-builder": "^24.0.0"
}
```

### Dependencias Python (archivo [`requirements.txt`](requirements.txt))

```text
minecraft-launcher-lib>=7.1
```

> Si alguna otra librería se añade en el futuro, recuerda actualizar ambos archivos.

## Instalación

```bash
# 1. Clonar el repositorio
$ git clone https://github.com/tu_usuario/gw-launcher.git
$ cd gw-launcher

# 2. Instalar dependencias Node
$ npm install

# 3. Instalar dependencias Python
$ pip install -r requirements.txt
```

## Uso

### Desarrollo (ventana de depuración abierta)

```bash
$ npm run start
```

La ventana mostrará la GUI y, al pulsar **Launch**, ejecutará el backend Python y volcará la salida en el `pre#log`.

### Ejecución del backend en consola

```bash
# Instalar una versión
$ python src/python/gwlauncher_backend.py install 1.21.1

# Lanzar en modo offline con 4 GiB de RAM y Forge
$ python src/python/gwlauncher_backend.py launch 1.21.1 Alex --ram 4096 --modloader forge

# Listar catálogo de versiones (JSON)
$ python src/python/gwlauncher_backend.py versions
```

## Empaquetado y distribución

El empaquetado se realiza con **electron‑builder**.

```bash
$ npm run build
```

Por defecto generará instaladores en `dist/`:

* **Windows** → `GW Launcher Setup x.x.x.exe` (NSIS)
* **macOS**  → `GW Launcher.dmg`
* **Linux**  → `GW Launcher.AppImage` (si se configura)

Ajusta la sección **`build`** de `package.json` para cambiar íconos, targets o metadatos.

## Estructura del proyecto

```text
├─ main.js                 # Proceso principal de Electron
├─ package.json            # Configuración Node/Electron
├─ requirements.txt        # Dependencias Python
├─ src/
│  ├─ index.html           # GUI
│  ├─ renderer.js          # Lógica de la ventana
│  ├─ styles.css           # Estilos
│  ├─ icon.ico             # Ícono Windows
│  └─ ...
├─ python/
│  └─ gwlauncher_backend.py# Backend de línea de comandos
└─ dist/                   # (se genera al compilar)
```

## CLI del backend

| Comando              | Descripción                                                                               |        |             |
| -------------------- | ----------------------------------------------------------------------------------------- | ------ | ----------- |
| `install <ver>`      | Descarga o actualiza la versión indicada.                                                 |        |             |
| `launch <ver> <usr>` | Lanza el juego en modo offline. Args extra:<br>• `--ram <MiB>`<br>• \`--modloader \<forge | fabric | neoforge>\` |
| `versions`           | Muestra el catálogo oficial en JSON.                                                      |        |             |

## Contribuir

1. Crea un *fork* y una rama (`feat/…` o `fix/…`).
2. Haz cambios atómicos y documenta en el *commit*.
3. Abre un *pull request* describiendo el problema y la solución.

> Sigue las buenas prácticas de *clean code* y formatea con Prettier / Black.

## Licencia

Este proyecto se publica bajo la licencia **MIT**. Consulta [`LICENSE`](LICENSE) para más detalles.

---

*Happy crafting!*
