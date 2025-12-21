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
    
    // Show celebration overlay instead of alert. Prefer custom success message from backend.
    const customMsg = (result && result.successMessage) ? result.successMessage : null;
    if (customMsg) {
      addLog(`🎉 Message: ${customMsg}`, 'success');
    } else {
      addLog('ℹ️ Using fallback success message', 'info');
    }
    const fallbackMsg = selectedOutputPath
      ? `Video saved to: ${selectedOutputPath}`
      : 'Your video has been translated successfully.';
    showCelebration('Translation Complete!', customMsg || fallbackMsg);
    
  } catch (error) {
    progressText.textContent = '❌ Error occurred';
    progressFill.style.backgroundColor = '#f44336';
    addLog(`❌ Error: ${error.error || error.message}`, 'error');
    // Keep alerts for errors for now; can be replaced with a toast later
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
// Celebration helpers
const celebrationOverlay = document.getElementById('celebrationOverlay');
const celebrationTitle = document.getElementById('celebrationTitle');
const celebrationMessage = document.getElementById('celebrationMessage');
const closeCelebrationBtn = document.getElementById('closeCelebrationBtn');

function showCelebration(title, message) {
  celebrationTitle.textContent = title || 'Done!';
  celebrationMessage.textContent = message || '';
  celebrationOverlay.style.display = 'flex';
  runConfetti(120);
}

function hideCelebration() {
  celebrationOverlay.style.display = 'none';
}

closeCelebrationBtn.addEventListener('click', hideCelebration);

function runConfetti(count = 80) {
  const colors = ['#ffd700', '#ff6b6b', '#4caf50', '#00bcd4', '#9c27b0', '#ff9800'];
  for (let i = 0; i < count; i++) {
    const piece = document.createElement('div');
    piece.className = 'confetti';
    piece.style.left = Math.random() * 100 + 'vw';
    piece.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
    piece.style.width = (6 + Math.random() * 6) + 'px';
    piece.style.height = (10 + Math.random() * 8) + 'px';
    piece.style.animationDuration = (2 + Math.random() * 2) + 's';
    piece.style.opacity = (0.7 + Math.random() * 0.3).toFixed(2);
    document.body.appendChild(piece);
    // Remove piece after animation completes
    setTimeout(() => piece.remove(), 4000);
  }
}

function addLog(message, type = 'info') {
  const logEntry = document.createElement('div');
  logEntry.className = `log-entry log-${type}`;
  logEntry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
  logOutput.appendChild(logEntry);
  logOutput.scrollTop = logOutput.scrollHeight;
}