# Video Translator - Quick Start

## First Time Setup (Required!)

Before using the application, you need to configure your AWS credentials:

### Step 1: Create .env file
1. Open the installation folder where `Video Translator.exe` is located
2. Create a new file named `.env` (note the dot at the beginning)
3. Open it with Notepad

### Step 2: Add your AWS credentials
Copy this template into the `.env` file:

```
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_DEFAULT_REGION=eu-central-1
```

Replace `your_access_key_here` and `your_secret_key_here` with your actual AWS credentials.

### Step 3: Save and close
- Save the file
- Make sure it's named `.env` (not `.env.txt`)

### Step 4: Run the application
Double-click `Video Translator.exe` to start!

## Need AWS Credentials?

See `AWS_SETUP_GUIDE.md` for detailed instructions on getting AWS credentials.

## Troubleshooting

**"Access Denied" or AWS errors:**
- Check that your `.env` file is in the same folder as the .exe
- Verify your AWS credentials are correct
- Ensure there are no extra spaces or quotes around the values

**Can't find installation folder:**
- Right-click the shortcut → "Open file location"
- Default: `C:\Users\YourName\AppData\Local\Programs\video-translator\`
