// Check if electronAPI is available
if (!window.electronAPI) {
  console.error('FATAL: electronAPI not available!');
  alert('Editor initialization failed: electronAPI not available');
}

// State management
let subtitles = [];
let selectedSubtitleIndex = null;
let videoDuration = 0;
let zoomLevel = 1;
let pixelsPerSecond = 100;
let isDragging = false;
let isResizing = false;
let dragStartX = 0;
let dragStartTime = 0;
let resizeHandle = null;
let historyStack = [];
let historyIndex = -1;
let currentFont = { family: 'Arial', path: null };

// DOM elements
const videoPlayer = document.getElementById('videoPlayer');
const playPauseBtn = document.getElementById('playPauseBtn');
const seekBar = document.getElementById('seekBar');
const currentTimeDisplay = document.getElementById('currentTime');
const durationDisplay = document.getElementById('duration');
const muteBtn = document.getElementById('muteBtn');
const volumeSlider = document.getElementById('volumeSlider');
const timelineTracks = document.getElementById('timelineTracks');
const timelineRuler = document.getElementById('timelineRuler');
const playhead = document.getElementById('playhead');
const subtitleEditor = document.getElementById('subtitleEditor');
const editModal = document.getElementById('editModal');
const zoomInBtn = document.getElementById('zoomInBtn');
const zoomOutBtn = document.getElementById('zoomOutBtn');
const undoBtn = document.getElementById('undoBtn');
const redoBtn = document.getElementById('redoBtn');
const saveBtn = document.getElementById('saveBtn');
const cancelBtn = document.getElementById('cancelBtn');
const addSubtitleBtn = document.getElementById('addSubtitleBtn');
const fontFileInput = document.getElementById('fontFile');
const fontNameLabel = document.getElementById('fontNameLabel');

// Subtitle overlay
const subtitleOverlay = document.getElementById('subtitleOverlay');

// Modal elements
const subtitleTextInput = document.getElementById('subtitleText');
const subtitleStartInput = document.getElementById('subtitleStart');
const subtitleEndInput = document.getElementById('subtitleEnd');
const subtitleDurationInput = document.getElementById('subtitleDuration');
const saveEditBtn = document.getElementById('saveEditBtn');
const cancelEditBtn = document.getElementById('cancelEditBtn');
const deleteSubtitleBtn = document.getElementById('deleteSubtitleBtn');

// Formatting buttons
const boldBtn = document.getElementById('boldBtn');
const italicBtn = document.getElementById('italicBtn');
const emphasizeBtn = document.getElementById('emphasizeBtn');
const clearFormatBtn = document.getElementById('clearFormatBtn');

// Check if all elements are found
const elements = {
  videoPlayer, playPauseBtn, seekBar, currentTimeDisplay, durationDisplay,
  muteBtn, volumeSlider, timelineTracks, timelineRuler, playhead,
  subtitleEditor, editModal, zoomInBtn, zoomOutBtn, undoBtn, redoBtn,
  saveBtn, cancelBtn, addSubtitleBtn, subtitleOverlay,
  subtitleTextInput, subtitleStartInput, subtitleEndInput, subtitleDurationInput,
  saveEditBtn, cancelEditBtn, deleteSubtitleBtn,
  boldBtn, italicBtn, emphasizeBtn, clearFormatBtn,
  fontFileInput, fontNameLabel
};

for (const [name, element] of Object.entries(elements)) {
  if (!element) {
    console.error(`FATAL: Element not found: ${name}`);
  }
}

console.log('All DOM elements loaded successfully');

// Initialize - receive data from main process
console.log('Editor script loaded, waiting for initialization...');

// Set initial font on load
function applySubtitleFont(family) {
  const safeFamily = family || 'Arial';
  document.documentElement.style.setProperty('--subtitle-font', `'${safeFamily}'`);
  subtitleOverlay.style.fontFamily = `'${safeFamily}', sans-serif`;
}

applySubtitleFont(currentFont.family);

// Handle custom font upload
if (fontFileInput) {
  fontFileInput.addEventListener('change', async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const family = file.name.replace(/\.(ttf|otf)$/i, '') || 'CustomFont';
    try {
      const data = await file.arrayBuffer();
      const fontFace = new FontFace(family, data);
      await fontFace.load();
      document.fonts.add(fontFace);
      currentFont = { family, path: file.path || null };
      applySubtitleFont(family);
      if (fontNameLabel) {
        fontNameLabel.textContent = `Using: ${family}`;
      }
      console.log(`Loaded custom font: ${family} (${file.path || 'buffer'})`);
    } catch (err) {
      console.error('Failed to load font', err);
      if (fontNameLabel) {
        fontNameLabel.textContent = 'Font load failed';
      }
    }
  });
}

window.electronAPI.onEditorInit((data) => {
  console.log('Editor initializing with data:', data);
  
  if (!data || !data.videoPath) {
    console.error('No video path provided!');
    alert('Error: No video path provided to editor');
    return;
  }
  
  if (!data.subtitles || data.subtitles.length === 0) {
    console.warn('No subtitles provided, starting with empty array');
    subtitles = [];
  } else {
    subtitles = data.subtitles;
    console.log('Loaded', subtitles.length, 'subtitles');
  }
  
  // Set video source
  const videoPath = data.videoPath;
  console.log('Setting video source:', videoPath);
  
  // Try to set the source and handle errors
  try {
    videoPlayer.src = videoPath;
  } catch (error) {
    console.error('Error setting video source:', error);
    alert(`Failed to set video source: ${error.message}`);
  }
  
  videoPlayer.addEventListener('loadedmetadata', () => {
    videoDuration = videoPlayer.duration;
    durationDisplay.textContent = formatTime(videoDuration);
    seekBar.max = 100;
    
    console.log('✓ Video loaded successfully');
    console.log('  Duration:', videoDuration, 'seconds');
    console.log('  Video source:', videoPlayer.src);
    console.log('  Rendering', subtitles.length, 'subtitle blocks');
    
    // Render timeline and subtitles
    renderTimeline();
    renderSubtitleList();
    saveHistory();
    
    console.log('✓ Timeline and subtitles rendered');
  });
  
  videoPlayer.addEventListener('error', (e) => {
    console.error('Video loading error:', e);
    console.error('Video error code:', videoPlayer.error?.code);
    console.error('Video error message:', videoPlayer.error?.message);
    console.error('Video src:', videoPlayer.src);
    console.error('Video currentSrc:', videoPlayer.currentSrc);
    
    const errorMessages = {
      1: 'MEDIA_ERR_ABORTED - The video loading was aborted',
      2: 'MEDIA_ERR_NETWORK - A network error occurred',
      3: 'MEDIA_ERR_DECODE - The video is corrupted or not supported',
      4: 'MEDIA_ERR_SRC_NOT_SUPPORTED - The video source is not supported or file not found'
    };
    
    const errorMsg = errorMessages[videoPlayer.error?.code] || 'Unknown error';
    alert(`Failed to load video.\n\nError: ${errorMsg}\n\nPath: ${videoPlayer.src}\n\nPlease check:\n1. The video file exists\n2. The file path is correct\n3. The video format is supported`);
  });
  
  videoPlayer.addEventListener('canplay', () => {
    console.log('✓ Video can play');
  });
  
  // Fallback: if video metadata is already loaded
  if (videoPlayer.readyState >= 1) {
    console.log('Video metadata already available, initializing now');
    videoDuration = videoPlayer.duration;
    durationDisplay.textContent = formatTime(videoDuration);
    renderTimeline();
    renderSubtitleList();
    saveHistory();
  }
});

// Video controls
videoPlayer.addEventListener('timeupdate', () => {
  if (videoDuration > 0) {
    const percent = (videoPlayer.currentTime / videoDuration) * 100;
    seekBar.value = percent;
    currentTimeDisplay.textContent = formatTime(videoPlayer.currentTime);
    updatePlayhead();
    updateSubtitleOverlay();
  }
});

playPauseBtn.addEventListener('click', () => {
  if (videoPlayer.paused) {
    videoPlayer.play();
    playPauseBtn.textContent = '⏸️';
  } else {
    videoPlayer.pause();
    playPauseBtn.textContent = '▶️';
  }
});

seekBar.addEventListener('input', (e) => {
  const time = (e.target.value / 100) * videoDuration;
  videoPlayer.currentTime = time;
});

muteBtn.addEventListener('click', () => {
  videoPlayer.muted = !videoPlayer.muted;
  muteBtn.textContent = videoPlayer.muted ? '🔇' : '🔊';
});

volumeSlider.addEventListener('input', (e) => {
  videoPlayer.volume = e.target.value / 100;
});

// Zoom controls
zoomInBtn.addEventListener('click', () => {
  zoomLevel = Math.min(zoomLevel * 1.5, 10);
  updateZoom();
});

zoomOutBtn.addEventListener('click', () => {
  zoomLevel = Math.max(zoomLevel / 1.5, 0.5);
  updateZoom();
});

function updateZoom() {
  pixelsPerSecond = 100 * zoomLevel;
  document.querySelector('.zoom-level').textContent = `${Math.round(zoomLevel * 100)}%`;
  renderTimeline();
}

// Timeline rendering
function renderTimeline() {
  if (!videoDuration || videoDuration === 0) {
    console.warn('Cannot render timeline: video duration is 0');
    return;
  }
  
  const totalWidth = videoDuration * pixelsPerSecond;
  timelineRuler.style.width = `${totalWidth}px`;
  timelineTracks.style.width = `${totalWidth}px`;
  
  // Render ruler markings
  timelineRuler.innerHTML = '';
  const interval = zoomLevel < 1 ? 10 : (zoomLevel > 2 ? 1 : 5);
  
  for (let i = 0; i <= videoDuration; i += interval) {
    const mark = document.createElement('div');
    mark.style.position = 'absolute';
    mark.style.left = `${i * pixelsPerSecond}px`;
    mark.style.top = '0';
    mark.style.width = '1px';
    mark.style.height = '100%';
    mark.style.background = '#555';
    
    const label = document.createElement('span');
    label.textContent = formatTime(i);
    label.style.position = 'absolute';
    label.style.left = `${i * pixelsPerSecond + 5}px`;
    label.style.top = '5px';
    label.style.fontSize = '0.75em';
    label.style.color = '#999';
    
    timelineRuler.appendChild(mark);
    timelineRuler.appendChild(label);
  }
  
  renderSubtitleBlocks();
}

function renderSubtitleBlocks() {
  timelineTracks.innerHTML = '';
  
  console.log(`Rendering ${subtitles.length} subtitle blocks on timeline`);
  
  if (subtitles.length === 0) {
    const emptyMessage = document.createElement('div');
    emptyMessage.style.cssText = 'position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: #666; font-size: 1em;';
    emptyMessage.textContent = 'No subtitles yet. Click "+ Add Subtitle" to create one.';
    timelineTracks.appendChild(emptyMessage);
    return;
  }
  
  subtitles.forEach((sub, index) => {
    const block = document.createElement('div');
    block.className = 'subtitle-block';
    if (index === selectedSubtitleIndex) {
      block.classList.add('selected');
    }
    
    const left = sub.start * pixelsPerSecond;
    const width = (sub.end - sub.start) * pixelsPerSecond;
    
    block.style.left = `${left}px`;
    block.style.width = `${width}px`;
    block.textContent = sub.text;
    block.dataset.index = index;
    
    if (index === 0) {
      console.log(`First subtitle block: left=${left}px, width=${width}px, text="${sub.text.substring(0, 30)}..."`);
    }
    
    // Add resize handles
    const leftHandle = document.createElement('div');
    leftHandle.className = 'subtitle-block-resize left';
    const rightHandle = document.createElement('div');
    rightHandle.className = 'subtitle-block-resize right';
    
    block.appendChild(leftHandle);
    block.appendChild(rightHandle);
    
    // Event listeners
    block.addEventListener('click', (e) => {
      if (!isDragging && !isResizing) {
        selectSubtitle(index);
      }
    });
    
    block.addEventListener('dblclick', () => {
      openEditModal(index);
    });
    
    // Drag to move
    block.addEventListener('mousedown', (e) => {
      if (e.target.classList.contains('subtitle-block-resize')) {
        startResize(e, index);
      } else {
        startDrag(e, index);
      }
    });
    
    timelineTracks.appendChild(block);
  });
}

// Helper function to check if a time range overlaps with other subtitles
function getOverlapConstraints(index, proposedStart, proposedEnd) {
  let maxStart = 0;
  let minEnd = videoDuration;
  
  subtitles.forEach((sub, i) => {
    if (i === index) return; // Skip the subtitle being moved
    
    // Check if proposed range would overlap with this subtitle
    if (proposedEnd > sub.start && proposedStart < sub.end) {
      // There would be an overlap
      if (proposedStart < sub.start) {
        // We're moving from left, can't go past the start of this subtitle
        minEnd = Math.min(minEnd, sub.start);
      } else {
        // We're moving from right, can't go before the end of this subtitle
        maxStart = Math.max(maxStart, sub.end);
      }
    }
  });
  
  return { maxStart, minEnd };
}

function startDrag(e, index) {
  isDragging = true;
  dragStartX = e.clientX;
  dragStartTime = subtitles[index].start;
  selectedSubtitleIndex = index;
  
  const onMouseMove = (e) => {
    if (!isDragging) return;
    
    const deltaX = e.clientX - dragStartX;
    const deltaTime = deltaX / pixelsPerSecond;
    let newStart = Math.max(0, dragStartTime + deltaTime);
    const duration = subtitles[index].end - subtitles[index].start;
    let newEnd = newStart + duration;
    
    // Check for overlaps and constrain movement
    const constraints = getOverlapConstraints(index, newStart, newEnd);
    
    // Apply constraints
    if (newStart < constraints.maxStart) {
      newStart = constraints.maxStart;
      newEnd = newStart + duration;
    }
    if (newEnd > constraints.minEnd) {
      newEnd = constraints.minEnd;
      newStart = newEnd - duration;
    }
    
    // Final bounds check
    newStart = Math.max(0, newStart);
    newEnd = Math.min(videoDuration, newEnd);
    
    subtitles[index].start = newStart;
    subtitles[index].end = newEnd;
    
    renderSubtitleBlocks();
    renderSubtitleList();
  };
  
  const onMouseUp = () => {
    if (isDragging) {
      isDragging = false;
      saveHistory();
    }
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
  };
  
  document.addEventListener('mousemove', onMouseMove);
  document.addEventListener('mouseup', onMouseUp);
}

function startResize(e, index) {
  e.stopPropagation();
  isResizing = true;
  resizeHandle = e.target.classList.contains('left') ? 'left' : 'right';
  dragStartX = e.clientX;
  const sub = subtitles[index];
  const originalStart = sub.start;
  const originalEnd = sub.end;
  
  const onMouseMove = (e) => {
    if (!isResizing) return;
    
    const deltaX = e.clientX - dragStartX;
    const deltaTime = deltaX / pixelsPerSecond;
    
    if (resizeHandle === 'left') {
      let newStart = Math.max(0, originalStart + deltaTime);
      
      // Check for overlaps with previous subtitle
      const constraints = getOverlapConstraints(index, newStart, originalEnd);
      newStart = Math.max(newStart, constraints.maxStart);
      
      // Ensure minimum duration
      if (newStart < originalEnd - 0.1) {
        subtitles[index].start = newStart;
      }
    } else {
      let newEnd = Math.min(videoDuration, originalEnd + deltaTime);
      
      // Check for overlaps with next subtitle
      const constraints = getOverlapConstraints(index, originalStart, newEnd);
      newEnd = Math.min(newEnd, constraints.minEnd);
      
      // Ensure minimum duration
      if (newEnd > originalStart + 0.1) {
        subtitles[index].end = newEnd;
      }
    }
    
    renderSubtitleBlocks();
    renderSubtitleList();
  };
  
  const onMouseUp = () => {
    if (isResizing) {
      isResizing = false;
      saveHistory();
    }
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
  };
  
  document.addEventListener('mousemove', onMouseMove);
  document.addEventListener('mouseup', onMouseUp);
}

function updatePlayhead() {
  const position = videoPlayer.currentTime * pixelsPerSecond;
  playhead.style.left = `${position}px`;
}

function updateSubtitleOverlay() {
  const currentTime = videoPlayer.currentTime;
  
  // Find the subtitle that should be displayed at current time
  const currentSubtitle = subtitles.find(sub => 
    currentTime >= sub.start && currentTime <= sub.end
  );
  
  if (currentSubtitle) {
    // Display subtitle with formatting
    let displayText = currentSubtitle.text;
    
    // Convert ~~text~~ to emphasized (must be before italic to avoid conflicts)
    displayText = displayText.replace(/~~(.*?)~~/g, '<span class="emphasized">$1</span>');
    
    // Convert **text** to bold
    displayText = displayText.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Convert *text* to italic
    displayText = displayText.replace(/\*(.*?)\*/g, '<em>$1</em>');
    
    subtitleOverlay.innerHTML = displayText;
    subtitleOverlay.classList.add('visible');
  } else {
    subtitleOverlay.classList.remove('visible');
  }
}

function selectSubtitle(index) {
  selectedSubtitleIndex = index;
  renderSubtitleBlocks();
  renderSubtitleList();
  videoPlayer.currentTime = subtitles[index].start;
}

// Subtitle list rendering
function renderSubtitleList() {
  if (subtitles.length === 0) {
    subtitleEditor.innerHTML = '<div class="subtitle-placeholder">No subtitles yet. Add one using the + button.</div>';
    return;
  }
  
  subtitleEditor.innerHTML = '';
  
  subtitles.forEach((sub, index) => {
    const item = document.createElement('div');
    item.className = 'subtitle-item';
    if (index === selectedSubtitleIndex) {
      item.classList.add('selected');
    }
    
    const time = document.createElement('div');
    time.className = 'subtitle-item-time';
    time.textContent = `${formatTime(sub.start)} → ${formatTime(sub.end)}`;
    
    const text = document.createElement('div');
    text.className = 'subtitle-item-text';
    text.textContent = sub.text;
    
    item.appendChild(time);
    item.appendChild(text);
    
    item.addEventListener('click', () => selectSubtitle(index));
    item.addEventListener('dblclick', () => openEditModal(index));
    
    subtitleEditor.appendChild(item);
  });
}

// Edit modal
function openEditModal(index) {
  selectedSubtitleIndex = index;
  const sub = subtitles[index];
  
  subtitleTextInput.value = sub.text;
  subtitleStartInput.value = sub.start.toFixed(2);
  subtitleEndInput.value = sub.end.toFixed(2);
  updateDuration();
  
  editModal.style.display = 'flex';
}

subtitleStartInput.addEventListener('input', updateDuration);
subtitleEndInput.addEventListener('input', updateDuration);

function updateDuration() {
  const start = parseFloat(subtitleStartInput.value) || 0;
  const end = parseFloat(subtitleEndInput.value) || 0;
  subtitleDurationInput.value = (end - start).toFixed(2) + 's';
}

saveEditBtn.addEventListener('click', () => {
  if (selectedSubtitleIndex === null) return;
  
  const text = subtitleTextInput.value;
  const start = parseFloat(subtitleStartInput.value);
  const end = parseFloat(subtitleEndInput.value);
  
  if (start >= end || start < 0 || end > videoDuration) {
    alert('Invalid time values');
    return;
  }
  
  subtitles[selectedSubtitleIndex] = { text, start, end };
  renderSubtitleBlocks();
  renderSubtitleList();
  saveHistory();
  updateSubtitleOverlay();
  editModal.style.display = 'none';
});

cancelEditBtn.addEventListener('click', () => {
  editModal.style.display = 'none';
});

deleteSubtitleBtn.addEventListener('click', () => {
  if (selectedSubtitleIndex === null) return;
  
  if (confirm('Delete this subtitle?')) {
    subtitles.splice(selectedSubtitleIndex, 1);
    selectedSubtitleIndex = null;
    renderSubtitleBlocks();
    renderSubtitleList();
    saveHistory();
    editModal.style.display = 'none';
  }
});

// Add new subtitle
addSubtitleBtn.addEventListener('click', () => {
  const newSubtitle = {
    text: 'New subtitle',
    start: videoPlayer.currentTime,
    end: videoPlayer.currentTime + 2
  };
  
  subtitles.push(newSubtitle);
  subtitles.sort((a, b) => a.start - b.start);
  
  const newIndex = subtitles.findIndex(s => s === newSubtitle);
  selectedSubtitleIndex = newIndex;
  
  renderSubtitleBlocks();
  renderSubtitleList();
  saveHistory();
  openEditModal(newIndex);
});

// History management
function saveHistory() {
  historyStack = historyStack.slice(0, historyIndex + 1);
  historyStack.push(JSON.parse(JSON.stringify(subtitles)));
  historyIndex++;
  
  undoBtn.disabled = historyIndex <= 0;
  redoBtn.disabled = true;
}

undoBtn.addEventListener('click', () => {
  if (historyIndex > 0) {
    historyIndex--;
    subtitles = JSON.parse(JSON.stringify(historyStack[historyIndex]));
    renderSubtitleBlocks();
    renderSubtitleList();
    
    undoBtn.disabled = historyIndex <= 0;
    redoBtn.disabled = false;
  }
});

redoBtn.addEventListener('click', () => {
  if (historyIndex < historyStack.length - 1) {
    historyIndex++;
    subtitles = JSON.parse(JSON.stringify(historyStack[historyIndex]));
    renderSubtitleBlocks();
    renderSubtitleList();
    
    undoBtn.disabled = false;
    redoBtn.disabled = historyIndex >= historyStack.length - 1;
  }
});

// Save and cancel
saveBtn.addEventListener('click', () => {
  window.electronAPI.saveSubtitles({ subtitles, font: currentFont });
});

cancelBtn.addEventListener('click', () => {
  if (confirm('Discard all changes?')) {
    window.electronAPI.cancelEditor();
  }
});

// Utility functions
function formatTime(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
    // Allow formatting shortcuts in textarea
    if (e.target === subtitleTextInput && e.ctrlKey) {
      if (e.key === 'b' || e.key === 'B') {
        e.preventDefault();
        boldBtn.click();
      } else if (e.key === 'i' || e.key === 'I') {
        e.preventDefault();
        italicBtn.click();
      } else if (e.key === 'e' || e.key === 'E') {
        e.preventDefault();
        emphasizeBtn.click();
      }
    }
    return;
  }
  
  if (e.key === ' ') {
    e.preventDefault();
    playPauseBtn.click();
  } else if (e.key === 'Delete' && selectedSubtitleIndex !== null) {
    subtitles.splice(selectedSubtitleIndex, 1);
    selectedSubtitleIndex = null;
    renderSubtitleBlocks();
    renderSubtitleList();
    saveHistory();
  } else if (e.ctrlKey && e.key === 'z') {
    e.preventDefault();
    undoBtn.click();
  } else if (e.ctrlKey && e.key === 'y') {
    e.preventDefault();
    redoBtn.click();
  }
});

// Formatting functions
function wrapSelectedText(prefix, suffix) {
  const textarea = subtitleTextInput;
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  const selectedText = textarea.value.substring(start, end);
  
  if (selectedText) {
    const wrappedText = prefix + selectedText + suffix;
    textarea.value = textarea.value.substring(0, start) + wrappedText + textarea.value.substring(end);
    // Restore selection
    textarea.selectionStart = start;
    textarea.selectionEnd = start + wrappedText.length;
  } else {
    // If no text selected, just insert the markers
    const placeholder = prefix + 'text' + suffix;
    textarea.value = textarea.value.substring(0, start) + placeholder + textarea.value.substring(end);
    // Select the placeholder text
    textarea.selectionStart = start + prefix.length;
    textarea.selectionEnd = start + prefix.length + 4; // 'text'.length
  }
  textarea.focus();
}

function removeFormatting(text) {
  // Remove all formatting markers
  return text.replace(/\*\*(.*?)\*\*/g, '$1')
             .replace(/\*(.*?)\*/g, '$1')
             .replace(/~~(.*?)~~/g, '$1');
}

// Formatting button handlers
boldBtn.addEventListener('click', () => {
  wrapSelectedText('**', '**');
});

italicBtn.addEventListener('click', () => {
  wrapSelectedText('*', '*');
});

emphasizeBtn.addEventListener('click', () => {
  wrapSelectedText('~~', '~~');
});

clearFormatBtn.addEventListener('click', () => {
  subtitleTextInput.value = removeFormatting(subtitleTextInput.value);
  subtitleTextInput.focus();
});