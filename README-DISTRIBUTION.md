# Distribution Guide for Video Translator

## Prerequisites for Building

### 1. Install Dependencies
```bash
npm install
```

### 2. Create Python Standalone Package
You need to bundle Python with your dependencies. Two options:

#### Option A: Use PyInstaller (Recommended)
```bash
# Install PyInstaller in your venv
myVenv\Scripts\activate
pip install pyinstaller

# Create standalone executable
pyinstaller --onefile --name video_processor ^
  --hidden-import=boto3 ^
  --hidden-import=botocore ^
  --hidden-import=urllib3 ^
  --hidden-import=python-dotenv ^
  video_processor.py

# This creates dist/video_processor.exe
# Copy it to your project root or a python/ folder
```

#### Option B: Bundle Python Environment
- Copy your `myVenv` folder
- Rename it to `python_runtime`
- Include it in the build
- Update paths in your code to use the bundled Python

### 3. Prepare Icons (Optional)
- **Windows**: Create `icon.ico` (256x256px recommended)
- **Mac**: Create `icon.icns`
- Place in project root

## Building the Application

### For Windows
```bash
npm run build:win
```
This creates:
- `dist/Video Translator Setup.exe` - Installer
- Users can install to their preferred location

### For Mac (if on Mac)
```bash
npm run build:mac
```

### For Linux
```bash
npm run build:linux
```

## What Gets Packaged

✅ Electron app files (main.js, renderer.js, etc.)
✅ HTML/CSS/JS files
✅ FFmpeg binaries (from ffmpeg/ folder)
✅ Python script (video_processor.py)
✅ Node modules (automatically)

❌ Excluded:
- Development files (.git, .vscode, etc.)
- Virtual environment (myVenv/)
- Output folders
- Temporary files

## Important: AWS Credentials

⚠️ **DO NOT include AWS credentials in the packaged app!**

Users need to:
1. Create a `.env` file in the app's installation folder
2. Add their own AWS credentials:
   ```
   AWS_ACCESS_KEY_ID=their_key
   AWS_SECRET_ACCESS_KEY=their_secret
   AWS_DEFAULT_REGION=eu-central-1
   ```

### For Users Documentation
Create a `USER_SETUP.md` that explains:
1. Download and install the app
2. Create `.env` file with their AWS credentials
3. Ensure they have AWS Bedrock and Transcribe access
4. Grant necessary IAM permissions

## Distribution Options

### 1. **GitHub Releases** (Free)
- Create a GitHub repository
- Use GitHub Releases to upload the installer
- Users download and install

### 2. **Website Download**
- Host the installer on your own website
- Provide download link

### 3. **Microsoft Store** (Paid)
- Requires developer account ($19)
- Broader distribution

### 4. **Direct Distribution**
- Share the installer file directly
- Use cloud storage (Dropbox, Google Drive, etc.)

## Code Signing (Recommended for Production)

Windows/Mac will show warnings for unsigned apps. To avoid:

1. **Windows**: Get a code signing certificate ($50-300/year)
2. **Mac**: Join Apple Developer Program ($99/year)

Without signing, users will see "Unknown Publisher" warnings but can still install.

## Testing Before Distribution

1. Build the app: `npm run build:win`
2. Install it on a clean Windows machine (not your dev machine)
3. Test all features:
   - Video selection
   - Transcription
   - Translation
   - Subtitle editing
   - Video export
   - Custom fonts
4. Verify AWS credentials are loaded from `.env`

## File Size Expectations

- **With bundled Python**: ~300-500 MB
- **Without Python (users install separately)**: ~150-200 MB
- **Installer compressed**: Usually 30-40% smaller

## Alternative: Cloud-Based Solution

If the file size is too large, consider:
1. Keep Python/FFmpeg on a server
2. Make the Electron app a thin client
3. Process videos server-side
4. Reduces distribution size significantly

## Update Strategy

Use electron-updater for automatic updates:
```bash
npm install electron-updater
```

This allows pushing updates without users reinstalling.

## License Considerations

If distributing publicly:
- FFmpeg: LGPL/GPL (check your usage)
- AWS SDK: Apache 2.0
- Electron: MIT
- Your code: Choose your license

Ensure compliance with all dependency licenses.
