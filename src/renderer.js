// renderer.js

const { spawn } = require('child_process')
const { ipcRenderer, shell } = require('electron')
const path = require('path')
const os = require('os')
const fs = require('fs')

const pythonScript = path.join(__dirname, '..', 'src', 'python', 'gwlauncher_backend.py')
const profilesFile = path.join(os.homedir(), '.gwlauncher', 'ui_profiles.json')
const versionsDir = path.join(os.homedir(), '.gwlauncher', 'instances')

let active = null
let profiles = {}

function $(sel) { return document.querySelector(sel) }

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

function launch() {
    if (!active) return
    const p = profiles[active]
    if (!p) return

    const args = ['launch', p.version, p.username]
    if (p.ram) args.push('--ram', p.ram)
    if (p.modloader && p.modloader !== 'vanilla')
        args.push('--modloader', p.modloader)
    for (const f of (p.jvmFlags || []))
        args.push(`--jvm-arg=${f}`)

    args.push('--optimize')

    const py = spawn('python3', [pythonScript, ...args], {
        cwd: process.cwd(),
        stdio: ['ignore', 'inherit', 'inherit']
    })
    py.on('error', err => console.error('Error al lanzar Python backend:', err))

    ipcRenderer.send('close-launcher')
}

window.addEventListener('DOMContentLoaded', () => {
    profiles = loadProfiles()
    renderProfileList()

    $('#btn-new-profile').onclick = () => ipcRenderer.send('open-editor', null)
    $('#btn-edit-profile').onclick = () => ipcRenderer.send('open-editor', active)
    $('#btn-launch').onclick = launch

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
