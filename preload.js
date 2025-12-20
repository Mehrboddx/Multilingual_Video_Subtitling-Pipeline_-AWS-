const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  selectVideo: () => ipcRenderer.invoke('select-video'),
  selectOutput: (inputPath) => ipcRenderer.invoke('select-output', inputPath),
  processVideo: (data) => ipcRenderer.invoke('process-video', data),
  onProgress: (callback) => ipcRenderer.on('processing-progress', (event, message) => callback(message)),
  onShowTextPreview: (callback) => ipcRenderer.on('show-text-preview', (event, text) => callback(text)),
  sendEditedText: (text) => ipcRenderer.send('text-edited', text)
});
