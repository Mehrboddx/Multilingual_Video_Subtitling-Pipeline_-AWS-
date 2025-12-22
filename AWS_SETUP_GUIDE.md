# AWS Setup Guide for Video Translator

## Step 1: Create an AWS Account
If you don't have one already:
1. Go to https://aws.amazon.com/
2. Click "Create an AWS Account"
3. Follow the registration process

## Step 2: Create IAM User with Programmatic Access

1. **Go to IAM Console**
   - Visit https://console.aws.amazon.com/iam/
   - Click "Users" in the left sidebar
   - Click "Add users"

2. **Configure User**
   - User name: `video-translator-user`
   - Access type: ✅ Select "Programmatic access"
   - Click "Next: Permissions"

3. **Set Permissions**
   - Click "Attach existing policies directly"
   - Search and select these policies:
     - ✅ `AmazonTranscribeFullAccess`
     - ✅ `TranslateFullAccess`
     - ✅ `AmazonS3FullAccess`
   - Click "Next: Tags" (optional, skip)
   - Click "Next: Review"
   - Click "Create user"

4. **Save Credentials** ⚠️ IMPORTANT
   - You'll see your **Access Key ID** and **Secret Access Key**
   - **Download the CSV** or copy them immediately
   - You won't be able to see the secret key again!

## Step 3: Enable Amazon Bedrock Access

Amazon Bedrock requires special access:

1. **Request Access to Models**
   - Go to https://console.aws.amazon.com/bedrock/
   - Click "Model access" in the left sidebar
   - Click "Manage model access"
   - Find **"Anthropic Claude 3.5 Sonnet"**
   - Check the box and click "Save changes"
   - Access is usually granted immediately

2. **Add Bedrock Permissions to Your User**
   - Go back to IAM Console
   - Click on your `video-translator-user`
   - Click "Add permissions" → "Attach policies"
   - Search for `AmazonBedrockFullAccess`
   - Select it and click "Attach policies"

## Step 4: Configure the Application

1. **Create .env file**
   - Copy `.env.example` to `.env` in the app folder
   - Open `.env` in a text editor

2. **Add Your Credentials**
   ```
   AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
   AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
   AWS_DEFAULT_REGION=eu-central-1
   ```

3. **Save the file**

## Step 5: Verify Setup

Run the application and try processing a short video. You should see:
- ✅ Audio extraction
- ✅ Transcription starting
- ✅ Translation working
- ✅ Success message from Bedrock

## Cost Estimates (as of 2025)

### Per 10-minute video:
- **Transcription**: ~$0.05
- **Translation**: ~$0.15 (depends on text length)
- **Bedrock (Claude)**: ~$0.02
- **S3 Storage**: < $0.01
- **Total**: ~$0.23 per video

### Free Tier:
- Transcribe: 60 minutes/month free for 12 months
- Translate: 2 million characters/month free for 12 months
- S3: 5GB storage, 20,000 requests/month free for 12 months

## Security Best Practices

### ✅ DO:
- Use IAM users (not root account)
- Enable MFA on your AWS account
- Rotate access keys regularly
- Keep `.env` file private (never commit to Git)
- Use least privilege permissions

### ❌ DON'T:
- Share your AWS credentials
- Commit `.env` file to version control
- Use root account credentials
- Leave unused resources running

## Troubleshooting

### "Access Denied" Errors
- Check if all required permissions are attached to your IAM user
- Verify Bedrock model access is approved
- Ensure credentials in `.env` are correct

### "Region Not Supported"
- Change `AWS_DEFAULT_REGION` in `.env` to a supported region:
  - `us-east-1` (N. Virginia)
  - `us-west-2` (Oregon)
  - `eu-central-1` (Frankfurt)
  - `ap-northeast-1` (Tokyo)

### Bedrock Not Working
- Confirm you requested and received model access
- Some regions don't have Bedrock - try `us-east-1`
- Check if your account is new (may take 24 hours for access)

## Additional Resources

- AWS IAM Documentation: https://docs.aws.amazon.com/iam/
- AWS Bedrock: https://aws.amazon.com/bedrock/
- AWS Free Tier: https://aws.amazon.com/free/
- Pricing Calculator: https://calculator.aws/

## Support

For AWS-specific issues:
- AWS Support: https://console.aws.amazon.com/support/
- AWS Forums: https://forums.aws.amazon.com/
