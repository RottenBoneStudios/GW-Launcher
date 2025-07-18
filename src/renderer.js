const { spawn } = require('child_process')
const { ipcRenderer, shell } = require('electron')
const path = require('path')
const os = require('os')
const fs = require('fs')

const pythonScript = getPythonScriptPath()
const profilesFile = path.join(os.homedir(), '.gwlauncher', 'ui_profiles.json')
const versionsDir = path.join(os.homedir(), '.gwlauncher', 'instances')

let active = null
let profiles = {}

function $(sel) { return document.querySelector(sel) }

function getPythonScriptPath() {
    const devPath = path.join('src', 'python', 'gwlauncher_backend.py')
    const prodPath = path.join('python', 'gwlauncher_backend.py')

    if (fs.existsSync(devPath)) {
        return devPath
    } else if (fs.existsSync(prodPath)) {
        return prodPath
    } else {
        throw new Error('No se encontró el script Python en ninguna ruta esperada')
    }
}

function execPython(args, inherit = false) {
    return new Promise((resolve, reject) => {
        const isWin = process.platform === 'win32'

        const opts = inherit
            ? { stdio: 'inherit', windowsHide: true }
            : { stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true }

        if (isWin) {
            opts.creationFlags = 0x08000000
        }

        const py = spawn('python3', args, opts)

        py.on('error', reject)
        py.on('exit', code => {
            if (code === 0) resolve()
            else reject(new Error(`python3 salió con código ${code}`))
        })
    })
}

async function ensurePythonAndLibs() {
  try {
    await execPython(['--version']);
  } catch {
    await showModal({
      title: 'Python 3 no encontrado',
      html: `
        No se encontró <strong>Python 3</strong> en tu sistema.<br>
        Descárgalo e instálalo desde  
        <a href="#" id="link-py">https://python.org</a>
      `,
      buttons: [
        { label: 'Visitar sitio', value: 'visit' },
        { label: 'Cerrar', value: 'cancel' }
      ]
    }).then(choice => choice === 'visit' && shell.openExternal('https://python.org'));
    return false;
  }

  try {
    await execPython(['-c', 'import minecraft_launcher_lib; import tkinter']);
    return true;
  } catch {
    const platform = os.platform();
    const pipArgs = platform === 'linux'
      ? ['-m', 'pip3', 'install', '--user', 'minecraft_launcher_lib']
      : ['-m', 'pip', 'install', 'minecraft_launcher_lib'];

    try {
      await execPython(pipArgs, true);
    } catch {
      await showModal({
        title: 'Error al instalar minecraft_launcher_lib',
        html: `
          No se pudo instalar <strong>minecraft_launcher_lib</strong>.<br>
          Ejecuta manualmente:<br>
          <code>pip install minecraft_launcher_lib</code>
        `,
        buttons: [{ label: 'OK', value: null }]
      });
      return false;
    }

    if (platform === 'linux') {
      try {
        await execShell('sudo apt-get update');
        await execShell('sudo apt-get install -y python3-tk');
      } catch {
        await showModal({
          title: 'Error en apt-get',
          html: `
            No se pudo instalar <strong>python3-tk</strong>.<br>
            Instálalo manualmente con:<br>
            <code>sudo apt-get install python3-tk</code>
          `,
          buttons: [{ label: 'OK', value: null }]
        });
        return false;
      }
    }

    try {
      await execPython(['-c', 'import minecraft_launcher_lib; import tkinter']);
      return true;
    } catch {
      await showModal({
        title: 'Error al cargar librerías',
        html: `
          No se pudieron cargar las librerías después de la instalación.
        `,
        buttons: [{ label: 'OK', value: null }]
      });
      return false;
    }
  }
}

function showModal({ title, html, buttons }) {
    return new Promise(resolve => {
        const overlay = document.getElementById('modal-overlay')
        const box = document.getElementById('modal-box')
        const t = document.getElementById('modal-title')
        const c = document.getElementById('modal-content')
        const bwrap = document.getElementById('modal-buttons')

        t.textContent = title
        c.innerHTML = html
        bwrap.innerHTML = ''

        buttons.forEach(btn => {
            const b = document.createElement('button')
            b.textContent = btn.label
            b.className = 'modal-btn ' + (btn.className || '')
            b.onclick = () => {
                overlay.classList.add('hidden')
                resolve(btn.value)
            }
            bwrap.appendChild(b)
        })

        overlay.classList.remove('hidden')
    })
}

function loadProfiles() {
    try {
        return JSON.parse(fs.readFileSync(profilesFile, 'utf8'))
    } catch {
        return {}
    }
}

function renderProfileList() {
    const ul = $('#profile-list')
    ul.innerHTML = ''

    for (const [name, data] of Object.entries(profiles)) {
        const li = document.createElement('li')
        li.dataset.name = name
        li.onclick = () => {
            active = name
            renderProfileList()
        }
        if (name === active) li.classList.add('active')

        const folder = document.createElement('img')
        folder.src = '../assets/folder.webp'
        folder.classList.add('folder-btn')
        folder.onclick = e => {
            e.stopPropagation()
            if (fs.existsSync(versionsDir)) shell.openPath(versionsDir)
            else alert('Aún no se ha iniciado ninguna versión de Minecraft')
        }
        li.append(folder)

        const span = document.createElement('span')
        span.textContent = name
        li.append(span)

        const del = document.createElement('img')
        del.src = '../assets/trash.webp'
        del.classList.add('delete-btn')
        del.onclick = e => {
            e.stopPropagation()
            ipcRenderer.send('open-delete-confirm', name)
        }
        li.append(del)

        ul.append(li)
    }

    $('#btn-edit-profile').disabled = !active
    $('#btn-launch').disabled = !active
    $('#profile-headline').textContent =
        active ? `Perfil: ${active}` : 'Selecciona un perfil'
}

function getParticleImage() {
    const date = new Date()
    const month = date.getMonth() + 1
    const day = date.getDate()

    if ((month === 9 && day >= 21) || month === 10 || month === 11 || (month === 12 && day <= 20)) {
        return '../assets/leaf.webp'
    } else if ((month === 12 && day >= 21) || month === 1 || month === 2 || (month === 3 && day <= 20)) {
        return '../assets/sunflower.webp'
    } else if ((month === 3 && day >= 21) || month === 4 || month === 5 || (month === 6 && day <= 20)) {
        return '../assets/leaf.webp'
    } else {
        return '../assets/snow.webp'
    }
}

function renderParticles() {
    const container = document.querySelector('.particle-container')
    const particleCount = 15
    const particleImage = getParticleImage()

    const redLine = document.querySelector('.red-line')
    const containerTop = container.getBoundingClientRect().top
    const redY = redLine
        ? redLine.getBoundingClientRect().top - containerTop
        : 0

    for (let i = 0; i < particleCount; i++) {
        const p = document.createElement('img')
        p.src = particleImage
        p.classList.add('particle')
        p.style.left = `${Math.random() * 100}%`
        p.style.top = `${redY}px`
        p.style.animationDelay = `${Math.random() * 5}s`
        p.style.animationDuration = `${8 + Math.random() * 4}s`

        const swayAmount = (Math.random() - 0.5) * 50
        const rotateAmount = Math.random() * 360
        p.style.setProperty('--sway', `${swayAmount}px`)
        p.style.setProperty('--rotate', `${rotateAmount}deg`)

        container.appendChild(p)
    }
}

async function launch() {
    if (!active) return
    const p = profiles[active]
    if (!p) return

    const ok = await ensurePythonAndLibs()
    if (!ok) return

    const args = ['launch', p.version, p.username]
    if (p.ram) args.push('--ram', p.ram)
    if (p.modloader && p.modloader !== 'vanilla')
        args.push('--modloader', p.modloader)
    for (const f of (p.jvmFlags || []))
        args.push(`--jvm-arg=${f}`)

    args.push('--optimize')

    const py = spawn(
        process.platform === 'win32' ? 'pythonw' : 'python3',
        [pythonScript, ...args],
        {
            cwd: process.cwd(),
            stdio: ['ignore', 'pipe', 'pipe'],
            windowsHide: true
        }
    )
    py.on('error', err => console.error('Error al lanzar Python backend:', err))

    ipcRenderer.send('close-launcher')
}

window.addEventListener('DOMContentLoaded', () => {
    profiles = loadProfiles()
    renderProfileList()
    renderParticles()

    $('#btn-new-profile').onclick = () => ipcRenderer.send('open-editor', null)
    $('#btn-edit-profile').onclick = () => ipcRenderer.send('open-editor', active)
    $('#btn-launch').onclick = launch

    $('#minimize-btn').onclick = () => ipcRenderer.send('window-minimize');
    $('#close-btn').onclick = () => ipcRenderer.send('close-launcher');

    ipcRenderer.on('profile-saved', (_e, name) => {
        profiles = loadProfiles()
        active = name
        renderProfileList()
    })
    ipcRenderer.on('profile-deleted', (_e, name) => {
        profiles = loadProfiles()
        if (active === name) active = null
        renderProfileList()
    })
})
