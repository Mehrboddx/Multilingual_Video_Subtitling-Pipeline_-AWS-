const selectVideoBtn = document.getElementById('selectVideoBtn');
const selectOutputBtn = document.getElementById('selectOutputBtn');
const processBtn = document.getElementById('processBtn');
const videoPathInput = document.getElementById('videoPath');
const outputPathInput = document.getElementById('outputPath');
const sourceLangSelect = document.getElementById('sourceLang');
const targetLangSelect = document.getElementById('targetLang');
const progressSection = document.getElementById('progressSection');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const logSection = document.getElementById('logSection');
const logOutput = document.getElementById('logOutput');

let selectedVideoPath = null;
let selectedOutputPath = null;

// Select video file
selectVideoBtn.addEventListener('click', async () => {
  const path = await window.electronAPI.selectVideo();
  if (path) {
    selectedVideoPath = path;
    videoPathInput.value = path;
    selectOutputBtn.disabled = false;
    
    // Auto-suggest output path
    const outputPath = await window.electronAPI.selectOutput(path);
    if (outputPath) {
      selectedOutputPath = outputPath;
      outputPathInput.value = outputPath;
      processBtn.disabled = false;
    }
  }
});

// Select output location
selectOutputBtn.addEventListener('click', async () => {
  const path = await window.electronAPI.selectOutput(selectedVideoPath);
  if (path) {
    selectedOutputPath = path;
    outputPathInput.value = path;
    processBtn.disabled = false;
  }
});

// Process video
processBtn.addEventListener('click', async () => {
  if (!selectedVideoPath || !selectedOutputPath) return;

  // Disable controls
  processBtn.disabled = true;
  selectVideoBtn.disabled = true;
  selectOutputBtn.disabled = true;
  sourceLangSelect.disabled = true;
  targetLangSelect.disabled = true;

  // Show progress
  progressSection.style.display = 'block';
  logSection.style.display = 'block';
  logOutput.innerHTML = '';
  progressFill.style.width = '0%';

  try {
    const result = await window.electronAPI.processVideo({
      inputPath: selectedVideoPath,
      outputPath: selectedOutputPath,
      sourceLang: sourceLangSelect.value,
      targetLang: targetLangSelect.value
    });

    progressFill.style.width = '100%';
    progressText.textContent = '✅ Complete!';
    progressFill.style.backgroundColor = '#4caf50';
    
    addLog('✅ Video processing complete!', 'success');
    alert('Video translated successfully!');
    
  } catch (error) {
    progressText.textContent = '❌ Error occurred';
    progressFill.style.backgroundColor = '#f44336';
    addLog(`❌ Error: ${error.error || error.message}`, 'error');
    alert('An error occurred during processing. Check the log for details.');
  } finally {
    // Re-enable controls
    processBtn.disabled = false;
    selectVideoBtn.disabled = false;
    selectOutputBtn.disabled = false;
    sourceLangSelect.disabled = false;
    targetLangSelect.disabled = false;
  }
});

// Listen for progress updates
window.electronAPI.onProgress((message) => {
  addLog(message, 'info');
  
  // Simple progress estimation based on keywords
  if (message.includes('Extracting audio')) {
    progressFill.style.width = '20%';
    progressText.textContent = 'Extracting audio...';
  } else if (message.includes('Transcribing')) {
    progressFill.style.width = '40%';
    progressText.textContent = 'Transcribing audio...';
  } else if (message.includes('Translating')) {
    progressFill.style.width = '60%';
    progressText.textContent = 'Translating text...';
  } else if (message.includes('Creating subtitles')) {
    progressFill.style.width = '80%';
    progressText.textContent = 'Creating subtitles...';
  } else if (message.includes('Adding subtitles')) {
    progressFill.style.width = '90%';
    progressText.textContent = 'Adding subtitles to video...';
  }
});

function addLog(message, type = 'info') {
  const logEntry = document.createElement('div');
  logEntry.className = `log-entry log-${type}`;
  logEntry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
  logOutput.appendChild(logEntry);
  logOutput.scrollTop = logOutput.scrollHeight;
}

// Text preview modal handling
const textPreviewModal = document.getElementById('textPreviewModal');
const transcriptEditor = document.getElementById('transcriptEditor');
const confirmEditBtn = document.getElementById('confirmEditBtn');
const cancelEditBtn = document.getElementById('cancelEditBtn');

window.electronAPI.onShowTextPreview((text) => {
  transcriptEditor.value = text;
  textPreviewModal.style.display = 'flex';
  addLog('📝 Translation ready for review', 'info');
});

confirmEditBtn.addEventListener('click', () => {
  const editedText = transcriptEditor.value;
  window.electronAPI.sendEditedText(editedText);
  textPreviewModal.style.display = 'none';
  addLog('✅ Text confirmed, continuing processing...', 'success');
});

cancelEditBtn.addEventListener('click', () => {
  // Send original text back
  window.electronAPI.sendEditedText(transcriptEditor.value);
  textPreviewModal.style.display = 'none';
  addLog('↩️ Continuing with original text', 'info');
});