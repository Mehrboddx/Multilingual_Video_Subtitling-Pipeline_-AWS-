import sys
import os
import subprocess
import boto3
import time
import json

# Set environment variables for UTF-8 encoding
os.environ['PYTHONIOENCODING'] = 'utf-8'

def print_progress(message):
    """Print progress messages that will be captured by Electron"""
    # Ensure message is a string
    if isinstance(message, bytes):
        message = message.decode('utf-8', errors='ignore')
    print(message, flush=True)

def transcribe_to_translate_lang(transcribe_code):
    """Convert AWS Transcribe language code to AWS Translate language code"""
    # Extract base language code (e.g., 'en-US' -> 'en')
    base_lang = transcribe_code.split('-')[0]
    
    # Handle special cases
    if transcribe_code == 'zh-CN':
        return 'zh'  # Simplified Chinese
    elif transcribe_code == 'zh-TW':
        return 'zh-TW'  # Traditional Chinese
    
    return base_lang

def main():
    if len(sys.argv) != 5:
        print("Usage: video_processor.py <input_video> <output_video> <origin_lang> <destination_lang>")
        sys.exit(1)
    
    input_video = sys.argv[1]
    output_video = sys.argv[2]
    origin_lang = sys.argv[3]
    destination_lang = sys.argv[4]
    
    
    try:
        # ===== YOUR PIPELINE STARTS HERE =====
        
        print_progress("Starting video processing...")
        
        # Step 1: Extract audio from video
        print_progress("Extracting audio from video...")
        output_audio = "temp_audio.mp3"
        subprocess.run([
            "ffmpeg", 
            "-i", input_video, 
            "-vn",  # No video
            "-acodec", "libmp3lame",  # MP3 codec
            "-b:a", "128k",  # Audio bitrate (128k is good enough for transcription)
            "-ar", "16000",  # Sample rate 16kHz (sufficient for speech recognition)
            "-ac", "1",  # Mono audio (faster processing)
            "-y",  # Overwrite output file without asking
            output_audio
        ], check=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')
       
        
        # Step 2: Transcribe audio to text
        print_progress("Transcribing audio...")
        region = 'eu-central-1'
        transcriber = boto3.client('transcribe', region_name=region)
        
        # Use unique job name with timestamp to avoid conflicts
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        job_name = f"transcription_job_{timestamp}"
        
        # Delete old job if it exists (cleanup from previous runs)
        try:
            transcriber.delete_transcription_job(TranscriptionJobName="transcription_job")
        except:
            pass  # Job doesn't exist, continue
        s3 = boto3.client('s3', region_name=region)
        bucket_name = "mozhis-video-translator-bucket"
        s3_key = "input_audio.mp3"
        
        # Create bucket with location constraint for non us-east-1 regions
        try:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': region}
            )
        except s3.exceptions.BucketAlreadyOwnedByYou:
            pass  # Bucket already exists, continue
        except Exception as e:
            if 'BucketAlreadyExists' not in str(e):
                raise
        
        s3.upload_file(output_audio, bucket_name, s3_key)

        job_url = f"s3://{bucket_name}/{s3_key}"
        transcriber.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': job_url},
            MediaFormat='mp3',
            LanguageCode=origin_lang,
            OutputBucketName=bucket_name
        )
        
        # Wait for transcription job to complete
        print_progress("Waiting for transcription to complete...")
        while True:
            status = transcriber.get_transcription_job(TranscriptionJobName=job_name)
            job_status = status['TranscriptionJob']['TranscriptionJobStatus']
            
            if job_status == 'COMPLETED':
                break
            elif job_status == 'FAILED':
                raise Exception("Transcription job failed")
            
            time.sleep(5)  # Wait 5 seconds before checking again
        
        # Retrieve transcription result from S3
        print_progress("Retrieving transcription...")
        
        # Download the JSON file from S3
        transcript_key = f"{job_name}.json"
        s3.download_file(bucket_name, transcript_key, 'temp_transcript.json')
        
        # Parse the transcription
        with open('temp_transcript.json', 'r', encoding='utf-8') as f:
            transcript_data = json.load(f)
        
        transcription_text = transcript_data['results']['transcripts'][0]['transcript']
        
        # Step 3: Translate the transcription (skip if same language)
        # Convert Transcribe language code to Translate language code
        translate_source_lang = transcribe_to_translate_lang(origin_lang)
        
        if translate_source_lang == destination_lang:
            print_progress("Source and target languages are the same, skipping translation...")
            translated_text = transcription_text
        else:
            print_progress(f"Translating text to {destination_lang}...")
            translator = boto3.client('translate', region_name=region)
            response = translator.translate_text(
                Text=transcription_text,
                SourceLanguageCode=translate_source_lang,
                TargetLanguageCode=destination_lang
            )
            translated_text = response.get('TranslatedText')
        
        # Send translated text for user preview/editing
        # Format: PREVIEW_TEXT::<text>
        print(f"PREVIEW_TEXT::{translated_text}", flush=True)
        
        # Wait for edited text from user
        # Format expected: EDITED_TEXT::<text with **bold** markup>
        print_progress("Waiting for user to review and edit translated text...")
        edited_text = input()  # This will block until Electron sends the edited text
        
        if not edited_text.startswith("EDITED_TEXT::"):
            raise Exception("Invalid edited text format")
        
        edited_text = edited_text.replace("EDITED_TEXT::", "", 1)
        translated_text = edited_text  # Use the edited version
        
        # Step 4: Create subtitle file
        print_progress("Creating subtitles...")

        # Get word-level timestamps from transcription
        items = transcript_data['results']['items']
        
        # Group words into subtitle segments (every 5-10 words or by punctuation)
        subtitle_file = "temp_subtitles.srt"
        subtitles = []
        current_words = []
        current_start = None
        current_end = None
        subtitle_index = 1
        
        for item in items:
            if item['type'] == 'pronunciation':
                word = item['alternatives'][0]['content']
                start_time = float(item['start_time'])
                end_time = float(item['end_time'])
                
                if current_start is None:
                    current_start = start_time
                
                current_words.append(word)
                current_end = end_time
                
                # Create a subtitle segment every 10 words or at punctuation
                if len(current_words) >= 10:
                    subtitles.append({
                        'index': subtitle_index,
                        'start': current_start,
                        'end': current_end,
                        'words': ' '.join(current_words)
                    })
                    subtitle_index += 1
                    current_words = []
                    current_start = None
            
            elif item['type'] == 'punctuation' and current_words:
                # Add punctuation to current segment and close it
                punctuation = item['alternatives'][0]['content']
                current_words[-1] += punctuation
                
                if punctuation in ['.', '!', '?'] and current_words:
                    subtitles.append({
                        'index': subtitle_index,
                        'start': current_start,
                        'end': current_end,
                        'words': ' '.join(current_words)
                    })
                    subtitle_index += 1
                    current_words = []
                    current_start = None
        
        # Add remaining words
        if current_words:
            subtitles.append({
                'index': subtitle_index,
                'start': current_start,
                'end': current_end,
                'words': ' '.join(current_words)
            })
        
        # Split translated text into segments matching subtitle count
        translated_words = translated_text.split()
        words_per_subtitle = max(1, len(translated_words) // len(subtitles))
        
        # Convert **bold** markers to SRT bold tags <b></b>
        def format_subtitle_text(text, is_rtl=False):
            # Replace **text** with <b>text</b>
            import re
            text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
            
            # Add RTL marker for right-to-left languages
            if is_rtl:
                # Add Unicode RTL mark (U+200F) at the beginning
                text = '\u200F' + text
            
            return text
        
        # Check if target language is RTL
        rtl_languages = ['ar', 'fa', 'he', 'ur']  # Arabic, Persian, Hebrew, Urdu
        is_rtl = destination_lang in rtl_languages
        
        # Write SRT file
        with open(subtitle_file, 'w', encoding='utf-8') as f:
            start_idx = 0
            for i, subtitle in enumerate(subtitles):
                # Get corresponding translated words
                end_idx = min(start_idx + words_per_subtitle, len(translated_words))
                if i == len(subtitles) - 1:  # Last subtitle gets remaining words
                    end_idx = len(translated_words)
                
                subtitle_text = ' '.join(translated_words[start_idx:end_idx])
                subtitle_text = format_subtitle_text(subtitle_text, is_rtl)
                
                # Format time as HH:MM:SS,mmm
                def format_time(seconds):
                    hours = int(seconds // 3600)
                    minutes = int((seconds % 3600) // 60)
                    secs = int(seconds % 60)
                    millis = int((seconds % 1) * 1000)
                    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
                
                # Write SRT entry
                f.write(f"{subtitle['index']}\n")
                f.write(f"{format_time(subtitle['start'])} --> {format_time(subtitle['end'])}\n")
                f.write(f"{subtitle_text}\n\n")
                
                start_idx = end_idx
        
        # Step 5: Add subtitles to video
        print_progress("Adding subtitles to video...")
        
        # Use ffmpeg to burn subtitles into video (borderless style)
        subprocess.run([
            'ffmpeg', '-i', input_video,
            '-vf', f"subtitles={subtitle_file}:force_style='FontName=Arial,FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=0,Outline=0,Shadow=0'",
            '-c:a', 'copy',
            output_video,
            '-y'  # Overwrite output file if exists
        ], check=True)
        # Clean up temporary files
        print_progress("Cleaning up temporary files...")
        # Delete local temporary files
        if os.path.exists(output_audio):
            os.remove(output_audio)
        if os.path.exists('temp_transcript.json'):
            os.remove('temp_transcript.json')
        if os.path.exists(subtitle_file):
            os.remove(subtitle_file)
        
        # Clean up S3 resources
        print_progress("Cleaning up S3 resources...")
        try:
            # Delete uploaded audio file
            s3.delete_object(Bucket=bucket_name, Key=s3_key)
            
            # Delete transcription result file
            s3.delete_object(Bucket=bucket_name, Key=f"{job_name}.json")
            
            # Delete the S3 bucket (only works if empty)
            s3.delete_bucket(Bucket=bucket_name)
        except Exception as cleanup_error:
            print_progress(f"Warning: S3 cleanup error (non-critical): {str(cleanup_error)}")
        
        print_progress("Video processing complete!")
        
        # ===== YOUR PIPELINE ENDS HERE =====
        
        sys.exit(0)  # Success
        
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)  # Failure

if __name__ == "__main__":
    main()