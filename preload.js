const { contextBridge, ipcRenderer } = require('electron');

console.log('Preload script loaded');

contextBridge.exposeInMainWorld('electronAPI', {
  // Main window APIs
  selectVideo: () => ipcRenderer.invoke('select-video'),
  selectOutput: (inputPath) => ipcRenderer.invoke('select-output', inputPath),
  processVideo: (data) => ipcRenderer.invoke('process-video', data),
  onProgress: (callback) => {
    ipcRenderer.on('processing-progress', (event, message) => callback(message));
  },
  
  // Editor window APIs
  onEditorInit: (callback) => {
    console.log('Setting up editor-init listener');
    ipcRenderer.on('editor-init', (event, data) => {
      console.log('Received editor-init event with data:', data);
      callback(data);
    });
  },
  saveSubtitles: (subtitles) => {
    console.log('Sending subtitles-saved with', subtitles.length, 'subtitles');
    ipcRenderer.send('subtitles-saved', subtitles);
  },
  cancelEditor: () => {
    console.log('Sending editor-cancelled');
    ipcRenderer.send('editor-cancelled');
  }
});

console.log('electronAPI exposed to window');