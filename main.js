const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

let mainWindow;
let editorWindow;

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
  // Open maximized for better UX
  mainWindow.maximize();
}

function createEditorWindow(videoPath, subtitleData) {
  editorWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: false, // Allow loading local video files
    },
    backgroundColor: '#1a1a1a',
    parent: mainWindow,
  });

  editorWindow.loadFile('editor.html');

  // Send data after window loads
  editorWindow.webContents.once('did-finish-load', () => {
    console.log('Editor window loaded, sending data...');
    console.log('Video path:', videoPath);
    console.log('Subtitles count:', subtitleData.length);
    
    // Convert Windows path to proper file URL with encoding
    // Handle backslashes and special characters properly
    const normalizedPath = videoPath.replace(/\\/g, '/');
    const fileUrl = `file:///${normalizedPath}`;
    
    console.log('File URL:', fileUrl);
    
    editorWindow.webContents.send('editor-init', {
      videoPath: fileUrl,
      subtitles: subtitleData
    });
  });

  editorWindow.on('closed', () => {
    editorWindow = null;
  });
  // Open maximized for better UX
  editorWindow.maximize();
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
  const inputExt = path.extname(inputPath);
  
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
    title: 'Select Output Folder'
  });
  
  if (!result.canceled) {
    const outputFolder = result.filePaths[0];
    // Base filename
    let outputFileName = `${inputName}_subtitled${inputExt}`;
    let outputPath = path.join(outputFolder, outputFileName);
    
    // If file exists, append a numeric suffix (e.g., "_subtitled (1)")
    let counter = 1;
    while (fs.existsSync(outputPath)) {
      outputFileName = `${inputName}_subtitled (${counter})${inputExt}`;
      outputPath = path.join(outputFolder, outputFileName);
      counter += 1;
    }
    
    return outputPath;
  }
  return null;
});

// Process video with editor integration
ipcMain.handle('process-video', async (event, { inputPath, outputPath, sourceLang, targetLang }) => {
  return new Promise((resolve, reject) => {
    const pythonScript = path.join(__dirname, 'video_processor.py');
    const fontInfoPath = path.join(app.getPath('userData'), 'font-info.json');
    try {
      if (fs.existsSync(fontInfoPath)) fs.unlinkSync(fontInfoPath);
    } catch (cleanupErr) {
      console.warn('Could not clear previous font info file:', cleanupErr);
    }
    
    // Store inputPath in a variable accessible to handlers
    let currentVideoPath = inputPath;
    
    const pythonProcess = spawn('python', [
      pythonScript,
      inputPath,
      outputPath,
      sourceLang,
      targetLang
    ], {
      env: { ...process.env, PYTHONIOENCODING: 'utf-8', FONT_INFO_PATH: fontInfoPath },
      encoding: 'utf8'
    });

    let outputData = '';
    let errorData = '';
    let waitingForUserInput = false;
    let waitingForEditorConfirmation = false;
    let tempSubtitleFile = '';
    let successMessage = '';

    pythonProcess.stdout.on('data', (data) => {
      const chunk = data.toString();
      outputData += chunk;

      const lines = chunk.split(/\r?\n/).filter(l => l.trim().length > 0);
      for (const line of lines) {
        // Editor request with subtitle data
        if (line.startsWith('EDITOR_REQUEST::')) {
          const jsonData = line.slice('EDITOR_REQUEST::'.length);
          try {
            const editorData = JSON.parse(jsonData);
            tempSubtitleFile = editorData.subtitleFile;
            
            // Open editor window with the ORIGINAL video path
            createEditorWindow(currentVideoPath, editorData.subtitles);
            waitingForEditorConfirmation = true;
            mainWindow.webContents.send('processing-progress', 'Opening subtitle editor...');
          } catch (err) {
            console.error('Failed to parse editor data:', err);
          }
          continue;
        }

        // Success message from Python for celebration overlay
        if (line.startsWith('SUCCESS_MESSAGE::')) {
          successMessage = line.slice('SUCCESS_MESSAGE::'.length);
          mainWindow.webContents.send('processing-progress', 'Generating success message...');
          continue;
        }

        mainWindow.webContents.send('processing-progress', line.trim());
      }
    });

    // Handle subtitle save from editor (persistent handler)
    const onSubtitlesSaved = (event, payload) => {
      if (!waitingForEditorConfirmation) {
        console.warn('Received subtitles-saved but not waiting for editor confirmation');
        return;
      }
      if (!tempSubtitleFile) {
        console.error('No temporary subtitle file path available');
        return;
      }

      const payloadObj = Array.isArray(payload) ? { subtitles: payload } : (payload || {});
      const subtitleList = payloadObj.subtitles || [];
      const fontChoice = payloadObj.font;

      try {
        const srtContent = convertToSRT(subtitleList);
        fs.writeFileSync(tempSubtitleFile, srtContent, 'utf-8');
        mainWindow.webContents.send('processing-progress', 'Subtitle edits saved, continuing...');
      } catch (err) {
        console.error('Failed to write SRT file:', err);
        mainWindow.webContents.send('processing-progress', 'Error saving subtitles file');
      }

      // Stage custom font (if provided) for FFmpeg/libass consumption
      try {
        const fontsDir = path.join(app.getPath('userData'), 'fonts');
        const fontResource = prepareFontResource(fontChoice, fontsDir);
        if (fontResource) {
          fs.writeFileSync(fontInfoPath, JSON.stringify(fontResource), 'utf-8');
          console.log('Font info written for processing:', fontResource);
        } else if (fs.existsSync(fontInfoPath)) {
          fs.unlinkSync(fontInfoPath);
        }
      } catch (fontErr) {
        console.error('Failed to persist font info:', fontErr);
      }

      // Signal Python to continue
      try {
        pythonProcess.stdin.write('EDITOR_CONFIRMED\n');
      } catch (err) {
        console.error('Failed to notify Python process:', err);
      }
      waitingForEditorConfirmation = false;

      // Close editor window
      if (editorWindow) {
        editorWindow.close();
      }

      // Remove handlers to avoid leaks
      ipcMain.removeListener('subtitles-saved', onSubtitlesSaved);
      ipcMain.removeListener('editor-cancelled', onEditorCancelled);
    };
    ipcMain.on('subtitles-saved', onSubtitlesSaved);

    // Handle editor cancellation (persistent handler)
    const onEditorCancelled = () => {
      if (!waitingForEditorConfirmation) {
        console.warn('Received editor-cancelled but not waiting');
        return;
      }
      waitingForEditorConfirmation = false;
      try {
        pythonProcess.kill();
      } catch (err) {
        console.error('Failed to kill Python process:', err);
      }
      reject({ success: false, error: 'Processing cancelled by user' });

      // Remove handlers
      ipcMain.removeListener('subtitles-saved', onSubtitlesSaved);
      ipcMain.removeListener('editor-cancelled', onEditorCancelled);
    };
    ipcMain.on('editor-cancelled', onEditorCancelled);

    pythonProcess.stderr.on('data', (data) => {
      errorData += data.toString();
    });

    pythonProcess.on('close', (code) => {
      if (code === 0) {
        // Fallback: parse success message from aggregated output if not captured live
        if (!successMessage && outputData) {
          const match = outputData.match(/SUCCESS_MESSAGE::(.+)/);
          if (match && match[1]) {
            successMessage = match[1].trim();
          }
        }
        resolve({ success: true, output: outputData, successMessage });
      } else {
        reject({ success: false, error: errorData });
      }
    });

    pythonProcess.on('error', (error) => {
      reject({ success: false, error: error.message });
    });
  });
});

// Convert subtitles array to SRT format
function convertToSRT(subtitles) {
  let srt = '';
  
  subtitles.forEach((sub, index) => {
    srt += `${index + 1}\n`;
    srt += `${formatSRTTime(sub.start)} --> ${formatSRTTime(sub.end)}\n`;
    srt += `${sub.text}\n\n`;
  });
  
  return srt;
}

function formatSRTTime(seconds) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  const millis = Math.floor((seconds % 1) * 1000);
  
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')},${String(millis).padStart(3, '0')}`;
}

function ensureDirExists(dirPath) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
  }
}

function prepareFontResource(font, fontStoreDir) {
  if (!font || !font.path) return null;
  try {
    if (!fs.existsSync(font.path)) {
      console.warn('Font file missing on disk:', font.path);
      return null;
    }
    ensureDirExists(fontStoreDir);
    const fontName = font.family || path.basename(font.path, path.extname(font.path));
    const targetPath = path.join(fontStoreDir, path.basename(font.path));
    fs.copyFileSync(font.path, targetPath);
    return { fontName, fontDir: fontStoreDir };
  } catch (err) {
    console.error('Failed to prepare font resource:', err);
    return null;
  }
}