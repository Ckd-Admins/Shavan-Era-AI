const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('eraDesktop', {
  platform: process.platform,
  isElectron: true,
  getVersion: () => process.env.npm_package_version || '1.0.0',
  openExternal: (url) => ipcRenderer.send('open-external', url),
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close')
});
