
const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 900,
    height: 700,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
    backgroundColor: '#1e1e1e',
    titleBarStyle: 'hidden',
    titleBarOverlay: {
      color: '#1e1e1e',
      symbolColor: '#ffffff'
    }
  });

  mainWindow.loadFile('index.html');
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

// Select video file
ipcMain.handle('select-video', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: [
      { name: 'Videos', extensions: ['mp4', 'avi', 'mov', 'mkv', 'webm'] }
    ]
  });
  
  if (!result.canceled) {
    return result.filePaths[0];
  }
  return null;
});

// Select output location
ipcMain.handle('select-output', async (event, inputPath) => {
  const inputName = path.basename(inputPath, path.extname(inputPath));
  
  const result = await dialog.showSaveDialog(mainWindow, {
    defaultPath: `${inputName}_translated.mp4`,
    filters: [
      { name: 'Video', extensions: ['mp4'] }
    ]
  });
  
  if (!result.canceled) {
    return result.filePath;
  }
  return null;
});

// ===== THIS IS WHERE YOUR PYTHON SCRIPT RUNS =====
ipcMain.handle('process-video', async (event, { inputPath, outputPath, sourceLang, targetLang }) => {
  return new Promise((resolve, reject) => {
    // Path to your Python script
    const pythonScript = path.join(__dirname, 'video_processor.py');
    
    // Spawn Python process
    const pythonProcess = spawn('python', [
      pythonScript,
      inputPath,
      outputPath,
      sourceLang,
      targetLang
    ], {
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
      encoding: 'utf8'
    });

    let outputData = '';
    let errorData = '';
    let waitingForUserInput = false;

    // Capture stdout (for progress updates)
    pythonProcess.stdout.on('data', (data) => {
      const message = data.toString().trim();
      outputData += message + '\n';
      
      // Check if this is a preview request
      if (message.startsWith('PREVIEW_TEXT::')) {
        const transcriptText = message.replace('PREVIEW_TEXT::', '');
        waitingForUserInput = true;
        
        // Send preview to frontend and wait for edited text
        mainWindow.webContents.send('show-text-preview', transcriptText);
        return;
      }
      
      // Send progress updates to frontend
      mainWindow.webContents.send('processing-progress', message);
    });

    // Handle edited text from user
    ipcMain.once('text-edited', (event, editedText) => {
      if (waitingForUserInput) {
        pythonProcess.stdin.write(`EDITED_TEXT::${editedText}\n`);
        waitingForUserInput = false;
      }
    });

    // Capture stderr (for errors)
    pythonProcess.stderr.on('data', (data) => {
      errorData += data.toString();
    });

    // Handle process completion
    pythonProcess.on('close', (code) => {
      if (code === 0) {
        resolve({ success: true, output: outputData });
      } else {
        reject({ success: false, error: errorData });
      }
    });

    // Handle process errors
    pythonProcess.on('error', (error) => {
      reject({ success: false, error: error.message });
    });
  });
});




