// main.js
const { app, BrowserWindow, ipcMain, dialog } = require('electron')
const path = require('path')
const fs = require('fs')
const os = require('os')

app.commandLine.appendSwitch('disable-backgrounding-occluded-windows')

let mainWindow

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 900,
    height: 680,
    resizable: false,
    show: false,
    frame: false,
    autoHideMenuBar: true,
    backgroundColor: '#151738',
    transparent: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: true,
      contextIsolation: false
    }
  })

  mainWindow.loadFile(path.join(__dirname, 'src', 'index.html'))

  mainWindow.webContents.on('did-finish-load', () => {
    mainWindow.show()
  })
}

ipcMain.on('profile-saved', (_e, name) => {
  if (mainWindow) mainWindow.webContents.send('profile-saved', name)
})

ipcMain.on('open-editor', (_e, name) => {
  const editor = new BrowserWindow({
    parent: mainWindow,
    modal: true,
    width: 500,
    height: 780,
    show: false,
    frame: false,
    autoHideMenuBar: true,
    backgroundColor: '#151738',
    transparent: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  })

  editor.loadFile(
    path.join(__dirname, 'src', 'editor', 'profile-editor.html'),
    { query: name ? { name } : {} }
  )
  editor.webContents.on('did-finish-load', () => {
    editor.show()
  })
})

ipcMain.on('open-delete-confirm', (_e, name) => {
  dialog.showMessageBox(mainWindow, {
    type: 'question',
    buttons: ['Cancelar', 'Borrar'],
    defaultId: 1,
    cancelId: 0,
    title: 'Confirmar borrado',
    message: `¿Seguro que quieres borrar el perfil "${name}"?`,
    noLink: true
  }).then(result => {
    if (result.response === 1) {
      const profilesFile = path.join(os.homedir(), '.gwlauncher', 'ui_profiles.json')
      let profiles = {}
      try {
        profiles = JSON.parse(fs.readFileSync(profilesFile, 'utf8'))
      } catch { }
      delete profiles[name]
      fs.mkdirSync(path.dirname(profilesFile), { recursive: true })
      fs.writeFileSync(profilesFile, JSON.stringify(profiles, null, 2))
      mainWindow.webContents.send('profile-deleted', name)
    }
  })
})

ipcMain.on('close-launcher', () => {
  if (mainWindow) {
    mainWindow.close()
  }
  app.quit()
})

app.whenReady().then(createWindow)

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

ipcMain.on('window-minimize', () => {
  if (mainWindow) mainWindow.minimize();
});

ipcMain.on('window-close', () => {
  if (mainWindow) mainWindow.close();
});