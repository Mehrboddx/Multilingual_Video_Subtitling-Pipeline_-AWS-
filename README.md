# Video Translator (Electron + Python)

Desktop app for translating videos and burning editable subtitles into the final output.

The app uses:
- Electron for the desktop UI
- Python for media processing
- AWS Transcribe for speech-to-text
- AWS Translate for subtitle translation
- AWS Bedrock (optional-style feature in current code) for a short success message
- FFmpeg for audio extraction and subtitle burn-in

## Features

- Select a local video file (`.mp4`, `.avi`, `.mov`, `.mkv`, `.webm`)
- Choose source and target language
- Auto-generate subtitle segments from AWS Transcribe timestamps
- Open a timeline-based subtitle editor before export
- Edit subtitle timing/text and apply formatting
: `**bold**`, `*italic*`, `~~emphasis~~`
- Upload a custom `.ttf`/`.otf` font for subtitle rendering
- Export final video with hardcoded subtitles

## Project Structure

- `main.js`: Electron main process, IPC handlers, Python process orchestration
- `preload.js`: secure bridge between renderer and main process
- `index.html` + `renderer.js` + `styles.css`: main app UI
- `editor.html` + `editor_renderer.js` + `editor-styles.css`: subtitle timeline editor UI
- `video_processor.py`: end-to-end pipeline (FFmpeg + AWS + subtitle generation)
- `ffmpeg/`: bundled FFmpeg binaries/resources
- `README-DISTRIBUTION.md`: packaging/distribution workflow
- `QUICK_START.md`: end-user setup after installation
- `AWS_SETUP_GUIDE.md`: AWS credential and permission guidance

## Requirements

## 1) Runtime tools

- Node.js 18+ (recommended LTS)
- Python 3.10+ (3.11 recommended)
- Windows PowerShell (for commands below)

## 2) Python packages

Install in your virtual environment:

```powershell
myVenv\Scripts\Activate.ps1
pip install boto3 python-dotenv
```

Optional (for packaging Python into an `.exe`):

```powershell
pip install pyinstaller
```

## 3) AWS credentials

Create a `.env` file in the project root (or installed app directory in production):

```env
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=eu-central-1
```

Important notes from the current implementation:
- The code currently uses a fixed S3 bucket name: `mozhis-video-translator-bucket`
- Transcribe jobs upload temporary audio to S3 and clean up afterward
- If cleanup fails, temporary S3 data may remain

## Quick Start (Development)

1. Install Node dependencies

```powershell
npm install
```

2. Ensure Python env and packages are ready

```powershell
myVenv\Scripts\Activate.ps1
pip install boto3 python-dotenv
```

3. Run the Electron app

```powershell
npm start
```

4. In the app
- Select video
- Select output location
- Choose languages
- Click `Start Translation`
- Edit subtitles in the editor window
- Save and export

## Build and Distribution

Use Electron Builder scripts:

```powershell
npm run build:win
npm run build:mac
npm run build:linux
```

For full packaging details (including bundling `video_processor.exe`), see:
- `README-DISTRIBUTION.md`

For end-user credential setup, see:
- `QUICK_START.md`
- `AWS_SETUP_GUIDE.md`

## Processing Pipeline

The Python pipeline in `video_processor.py` does:

1. Extract mono 16k audio from input video using FFmpeg
2. Upload audio to S3
3. Start and poll AWS Transcribe job
4. Build subtitle segments from word timestamps
5. Translate segments via AWS Translate (unless source == target)
6. Send subtitles to Electron editor (`EDITOR_REQUEST::...`)
7. Wait for user confirmation from editor
8. Convert edited subtitles to ASS and burn into video with FFmpeg
9. Clean temporary local files and S3 bucket objects
10. Return success status/message to the UI

## Configuration and Behavior Notes

- Default subtitle timing offset comes from env var:
  - `SUBTITLE_OFFSET_SECONDS` (default: `-0.30`)
- Right-to-left formatting is applied for `ar`, `fa`, `he`, `ur`
- In development, Electron runs `python video_processor.py ...`
- In production, Electron runs bundled `video_processor.exe`

## Troubleshooting

## Python not found when running `npm start`

Cause: Electron main process calls `python` directly in dev mode.

Fix:
- Activate your venv before launch
- Ensure `python` is available in PATH

## AWS errors (AccessDenied, Missing credentials)

Fix:
- Verify `.env` location and values
- Check IAM permissions for Transcribe, Translate, S3, Bedrock
- Confirm region matches your service availability

## FFmpeg errors

Fix:
- Verify bundled binary exists at `ffmpeg/bin/ffmpeg.exe`
- Check input video codec support
- Confirm output file path is writable

## S3 bucket already exists / naming conflicts

Current code uses a fixed bucket name. If collisions happen across accounts/environments, make the bucket name configurable.

## Security Notes

- Never commit real `.env` credentials to source control
- Use least-privilege IAM permissions
- Consider replacing static bucket naming with per-user/per-run names
- Consider removing debug logs before public release

## Roadmap Ideas

- Make S3 bucket name configurable via `.env`
- Add retry logic and better error surfaces for AWS calls
- Add unit/integration tests for subtitle segmentation and formatting
- Add progress stages with percent derived from actual pipeline state
- Add localization for UI labels and logs

## License

Set your preferred license in this repository and ensure dependency license compliance (especially for FFmpeg distribution).