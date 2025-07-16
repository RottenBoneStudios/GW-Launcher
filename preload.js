const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  openProfileEditor: (name) => ipcRenderer.invoke('open-profile-editor', name)
});
