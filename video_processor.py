from http import client
import sys
import os
import subprocess
import boto3
import time
import json
from pathlib import Path

os.environ['PYTHONIOENCODING'] = 'utf-8'

def get_script_directory():
    """Get the directory where the script/exe is located, works for both dev and packaged."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return Path(sys.executable).parent
    else:
        # Running as script
        return Path(__file__).resolve().parent

def load_dotenv_simple():
    try:
        script_dir = get_script_directory()
        env_path = script_dir / '.env'
        if not env_path.exists():
            return
        for line in env_path.read_text(encoding='utf-8', errors='ignore').splitlines():
            s = line.strip()
            if not s or s.startswith('#'):
                continue
            if '=' in s:
                key, val = s.split('=', 1)
                key = key.strip()
                val = val.strip().strip('"')
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass

try:
    from dotenv import load_dotenv as _load_dotenv
    _DOTENV_AVAILABLE = True
except Exception:
    _load_dotenv = None
    _DOTENV_AVAILABLE = False

def load_env():
    try:
        script_dir = get_script_directory()
        env_path = script_dir / '.env'
        
        # Debug output
        print(f"DEBUG - Script directory: {script_dir}", flush=True)
        print(f"DEBUG - Looking for .env at: {env_path}", flush=True)
        print(f"DEBUG - .env exists: {env_path.exists()}", flush=True)
        
        if _DOTENV_AVAILABLE and _load_dotenv:
            _load_dotenv(dotenv_path=env_path)
        else:
            load_dotenv_simple()
    except Exception as e:
        print(f"DEBUG - Error loading .env: {e}", flush=True)
        load_dotenv_simple()

def get_aws_credentials():
    """Get AWS credentials from environment variables."""
    creds = {
        'aws_access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
        'aws_secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
        'region_name': os.getenv('AWS_DEFAULT_REGION', 'eu-central-1')
    }
    
    # Debug output (hide most of the keys for security)
    print(f"DEBUG - AWS Access Key loaded: {creds['aws_access_key_id'][:8] if creds['aws_access_key_id'] else 'None'}...", flush=True)
    print(f"DEBUG - AWS Secret Key loaded: {'Yes' if creds['aws_secret_access_key'] else 'No'}", flush=True)
    print(f"DEBUG - AWS Region: {creds['region_name']}", flush=True)
    
    return creds

def print_progress(message):
    if isinstance(message, bytes):
        message = message.decode('utf-8', errors='ignore')
    print(message, flush=True)
def success_message():
    import random
    aws_creds = get_aws_credentials()
    client = boto3.client('bedrock-runtime', **aws_creds)
    model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"

    # Randomize the prompt style for more variety
    prompt_styles = [
        "Create a charming success message announcing that a video has been subtitled. Keep it sweet romantic and poetic. Avoid names like 'my love' or 'my darling' I prefer calling her that myself. Maximum 20 words. Just output the message, nothing else.",
        "Write a heartfelt message celebrating that subtitles are ready for a video. Make it romantic and poetic, avoiding generic endearments. 20 words max. Message only.",
        "Generate a sweet, poetic announcement that video subtitling is complete. Keep it romantic without using 'my love' or 'darling'. Maximum 20 words. Just the message.",
        "Compose a tender success message for completed video subtitles. Be romantic and poetic, but skip common pet names. 20 words maximum. Output only the message.",
        "Craft a loving message about video subtitles being finished. Make it poetic and sweet, avoiding 'my love' or 'my darling'. Max 20 words. Message only.",
    ]
    
    prompt = random.choice(prompt_styles)
    
    messages = [
        {
            "role": "user",
            "content": [{"text": prompt}]
        }
    ]
    
    system = [
        {
            "text": "You are a helpful assistant that creates charming, concise success messages. Keep responses short and direct."
        }
    ]
    
    response = client.converse(
        modelId=model_id,
        messages=messages,
        system=system,
        inferenceConfig={
            "maxTokens": 300, 
            "temperature": 1.0,  
            "topP": 0.9          
        },
    )
    
    # Extract the response text from the converse API response
    return response['output']['message']['content'][0]['text']
def transcribe_to_translate_lang(transcribe_code):
    base_lang = transcribe_code.split('-')[0]
    if transcribe_code == 'zh-CN':
        return 'zh'
    elif transcribe_code == 'zh-TW':
        return 'zh-TW'
    return base_lang

def parse_srt_file(filepath):
    """Parse SRT file and return list of subtitle objects"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    subtitles = []
    blocks = content.strip().split('\n\n')
    
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            # Parse time
            time_line = lines[1]
            start_str, end_str = time_line.split(' --> ')
            
            def parse_time(time_str):
                time_str = time_str.replace(',', '.')
                parts = time_str.split(':')
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = float(parts[2])
                return hours * 3600 + minutes * 60 + seconds
            
            start = parse_time(start_str)
            end = parse_time(end_str)
            text = '\n'.join(lines[2:])
            
            subtitles.append({
                'text': text,
                'start': start,
                'end': end
            })
    
    return subtitles


def ff_safe(path_str: str) -> str:
    """Escape Windows paths for ffmpeg filter args."""
    return (
        path_str
        .replace('\\', '/')
        .replace(':', '\\:')
        .replace("'", "\\'")
    )


def ff_quote(val: str) -> str:
    """Quote a value for ffmpeg filter args with single quotes."""
    safe = val.replace("'", "\\'")
    return f"'{safe}'"

def main():
    if len(sys.argv) != 5:
        print("ERROR: Invalid arguments. Usage: video_processor.py <input_video> <output_video> <origin_lang> <destination_lang>", file=sys.stderr)
        sys.exit(1)
    
    input_video = sys.argv[1]
    output_video = sys.argv[2]
    origin_lang = sys.argv[3]
    destination_lang = sys.argv[4]
    
    try:
        load_env()
        print_progress("Starting video processing...")
        
        # Step 1: Extract audio
        print_progress("Extracting audio from video...")
        output_audio = "temp_audio.mp3"
        subprocess.run([
            "ffmpeg", "-i", input_video, "-vn", "-acodec", "libmp3lame",
            "-b:a", "128k", "-ar", "16000", "-ac", "1", "-y", output_audio
        ], check=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')
        
        # Step 2: Transcribe
        print_progress("Transcribing audio...")
        aws_creds = get_aws_credentials()
        region = aws_creds['region_name']
        transcriber = boto3.client('transcribe', **aws_creds)
        
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        job_name = f"transcription_job_{timestamp}"
        
        try:
            transcriber.delete_transcription_job(TranscriptionJobName="transcription_job")
        except:
            pass
            
        s3 = boto3.client('s3', **aws_creds)
        bucket_name = "mozhis-video-translator-bucket"
        s3_key = "input_audio.mp3"
        
        try:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': region}
            )
        except s3.exceptions.BucketAlreadyOwnedByYou:
            pass
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
        
        print_progress("Waiting for transcription to complete...")
        while True:
            status = transcriber.get_transcription_job(TranscriptionJobName=job_name)
            job_status = status['TranscriptionJob']['TranscriptionJobStatus']
            
            if job_status == 'COMPLETED':
                break
            elif job_status == 'FAILED':
                failure_reason = status['TranscriptionJob'].get('FailureReason', 'Unknown reason')
                raise Exception(f"Transcription failed: {failure_reason}")
            
            time.sleep(5)
        
        print_progress("Retrieving transcription...")
        transcript_key = f"{job_name}.json"
        s3.download_file(bucket_name, transcript_key, 'temp_transcript.json')
        
        with open('temp_transcript.json', 'r', encoding='utf-8') as f:
            transcript_data = json.load(f)
        
        transcription_text = transcript_data['results']['transcripts'][0]['transcript']
        
        # Step 3: Create subtitle segments with original timestamps first
        print_progress("Creating subtitle segments from transcription...")
        items = transcript_data['results']['items']

        subtitles = []
        current_words = []
        current_start = None
        current_end = None

        for item in items:
            if item['type'] == 'pronunciation':
                word = item['alternatives'][0]['content']
                start_time = float(item['start_time'])
                end_time = float(item['end_time'])
                
                if current_start is None:
                    current_start = start_time
                
                current_words.append(word)
                current_end = end_time
                
                if len(current_words) >= 12:
                    subtitles.append({
                        'start': current_start,
                        'end': current_end,
                        'words': ' '.join(current_words)
                    })
                    current_words = []
                    current_start = None
            
            elif item['type'] == 'punctuation' and current_words:
                punctuation = item['alternatives'][0]['content']
                current_words[-1] += punctuation
                
                if punctuation in ['.', '!', '?'] and current_words:
                    subtitles.append({
                        'start': current_start,
                        'end': current_end,
                        'words': ' '.join(current_words)
                    })
                    current_words = []
                    current_start = None

        if current_words:
            subtitles.append({
                'start': current_start,
                'end': current_end,
                'words': ' '.join(current_words)
            })
        
        print_progress(f"Created {len(subtitles)} subtitle segments")
        
        # Step 4: Translate text in one pass (faster than per-segment)
        translate_source_lang = transcribe_to_translate_lang(origin_lang)
        translation_skipped = translate_source_lang == destination_lang
        
        if translation_skipped:
            print_progress("Source and target languages are the same, skipping translation...")
            translated_text = '\n'.join([s['words'] for s in subtitles])
        else:
            # Combine segments with newlines to preserve structure
            full_text = '\n'.join([s['words'] for s in subtitles])
            print_progress(f"Translating text to {destination_lang} using AWS Translate...")
            
            translator = boto3.client('translate', **aws_creds)
            response = translator.translate_text(
                Text=full_text,
                SourceLanguageCode=translate_source_lang,
                TargetLanguageCode=destination_lang
            )
            translated_text = response.get('TranslatedText')
        
        print_progress("Translation complete. Preparing preview...")
        
        # Prepare subtitle data for editor
        subtitle_data_for_editor = []
        translated_segments = translated_text.split('\n')
        for i, subtitle in enumerate(subtitles):
            if i < len(translated_segments):
                text = translated_segments[i].strip()
            else:
                text = subtitle['words']
            
            subtitle_data_for_editor.append({
                'text': text,
                'start': float(subtitle['start']),
                'end': float(subtitle['end'])
            })
        
        # Write initial SRT file for editor (SRT is simpler for editing)
        subtitle_file = "temp_subtitles.srt"
        with open(subtitle_file, 'w', encoding='utf-8') as f:
            for i, sub in enumerate(subtitle_data_for_editor):
                def format_time(seconds):
                    hours = int(seconds // 3600)
                    minutes = int((seconds % 3600) // 60)
                    secs = int(seconds % 60)
                    millis = int((seconds % 1) * 1000)
                    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
                
                f.write(f"{i + 1}\n")
                f.write(f"{format_time(sub['start'])} --> {format_time(sub['end'])}\n")
                f.write(f"{sub['text']}\n\n")
        
        # Send editor request
        editor_payload = {
            'subtitles': subtitle_data_for_editor,
            'subtitleFile': subtitle_file
        }
        
        sys.stdout.flush()
        print(f"EDITOR_REQUEST::{json.dumps(editor_payload)}", flush=True)
        sys.stdout.flush()
        
        print_progress("Waiting for subtitle editing confirmation...")
        confirmation = input()
        
        if confirmation != "EDITOR_CONFIRMED":
            raise Exception("Subtitle editing was not confirmed or was cancelled")
        
        print_progress("Editor confirmed, processing final video...")
        
        # Read edited subtitles from the first editor session
        subtitle_data = parse_srt_file(subtitle_file)
        
        # Convert to SRT with formatting (using ASS override tags for bold)
        def format_subtitle_text(text, is_rtl=False):
            import re
            # FFmpeg's subtitles filter supports ASS override tags in SRT files
            # Tags must appear as literal backslashes in the file: {\fs32}
            # ASS color format is BGR: &HBBGGRR& so yellow RGB(255,215,0) = &H00D7FF&
            
            # Convert ~~emphasis~~ to emphasized text: larger, yellow, with glow
            # Using raw string r'...' for replacement with \\ for literal backslash and \1 for backreference
            text = re.sub(
                r'~~(.+?)~~',
                r'{\\fs32\\1c&H00D7FF&\\3c&H00A5FF&\\bord3\\shad2\\b1}\1{\\r}',
                text
            )
            # Convert **bold** to colored bold text
            text = re.sub(
                r'\*\*(.+?)\*\*',
                r'{\\c&H00D7FF&\\b1}\1{\\b0\\c&HFFFFFF&}',
                text
            )
            # Convert *italic* to italic text
            text = re.sub(
                r'\*(.+?)\*',
                r'{\\i1}\1{\\i0}',
                text
            )
            if is_rtl:
                text = '\u200F' + text
            return text
        
        rtl_languages = ['ar', 'fa', 'he', 'ur']
        is_rtl = destination_lang in rtl_languages
        
        subtitle_offset = float(os.getenv('SUBTITLE_OFFSET_SECONDS', '-0.30'))

        def apply_offset(start_val, end_val):
            s = max(0.0, start_val + subtitle_offset)
            e = max(s + 0.01, end_val + subtitle_offset)
            return s, e

        # Get custom font info before writing ASS file
        font_info_path = os.getenv("FONT_INFO_PATH")
        font_name = "Arial"
        fonts_dir = ""
        if font_info_path and os.path.exists(font_info_path):
            try:
                with open(font_info_path, 'r', encoding='utf-8') as f:
                    info = json.load(f)
                font_name = info.get('fontName', font_name)
                fonts_dir = info.get('fontDir', '') or ''
                print_progress(f"Using custom font: {font_name}")
                print_progress(f"Font directory: {fonts_dir}")
            except Exception as font_err:
                print_progress(f"Warning: could not load font info ({font_err}), falling back to Arial")
                fonts_dir = ""
                font_name = "Arial"
        
        # Sanitize font name for ASS (remove commas which break the format)
        font_name_safe = (font_name or "Arial").strip().replace(',', ' ')

        # Convert to ASS format (which properly supports ASS override tags)
        ass_file = "temp_subtitles.ass"
        with open(ass_file, 'w', encoding='utf-8') as f:
            # Write ASS header
            f.write("[Script Info]\n")
            f.write("ScriptType: v4.00+\n")
            f.write("PlayResX: 384\n")
            f.write("PlayResY: 288\n")
            f.write("WrapStyle: 0\n\n")
            
            f.write("[V4+ Styles]\n")
            f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
            # Use custom font in the Default style
            f.write(f"Style: Default,{font_name_safe},24,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,2,10,10,10,1\n\n")
            
            f.write("[Events]\n")
            f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
            
            for i, sub in enumerate(subtitle_data):
                subtitle_text = format_subtitle_text(sub['text'], is_rtl)
                adj_start, adj_end = apply_offset(sub['start'], sub['end'])
                
                # Debug: Print first subtitle to verify formatting
                if i == 0:
                    print_progress(f"DEBUG - First subtitle formatted text: {repr(subtitle_text)}")
                
                def format_ass_time(seconds):
                    hours = int(seconds // 3600)
                    minutes = int((seconds % 3600) // 60)
                    secs = seconds % 60
                    # ASS format uses H:MM:SS.CS where CS is centiseconds (1/100 of a second)
                    return f"{hours}:{minutes:02d}:{secs:05.2f}"
                
                f.write(f"Dialogue: 0,{format_ass_time(adj_start)},{format_ass_time(adj_end)},Default,,0,0,0,,{subtitle_text}\n")
        
        # Use ASS file instead of SRT for FFmpeg
        subtitle_file = ass_file
        
        # Step 5: Add subtitles to video with custom font directory
        subtitle_arg = ff_safe(subtitle_file)
        fontsdir_opt = f":fontsdir={ff_quote(ff_safe(fonts_dir))}" if fonts_dir else ""
        
        print_progress(f"DEBUG - Fonts directory option: {fontsdir_opt}")

        # ASS files don't need force_style, they have their own style definitions
        ffmpeg_filter = f"subtitles={ff_quote(subtitle_arg)}{fontsdir_opt}"
        
        print_progress(f"DEBUG - FFmpeg filter: {ffmpeg_filter}")

        print_progress("Adding subtitles to video...")
        subprocess.run([
            'ffmpeg', '-i', input_video,
            '-vf', ffmpeg_filter,
            '-c:a', 'copy',
            output_video,
            '-y'
        ], check=True)
        
        # Cleanup
        print_progress("Cleaning up temporary files...")
        if os.path.exists(output_audio):
            os.remove(output_audio)
        if os.path.exists('temp_transcript.json'):
            os.remove('temp_transcript.json')
        if os.path.exists(subtitle_file):
            os.remove(subtitle_file)
        
        print_progress("Cleaning up S3 resources...")
        try:
            # Empty all objects in the bucket first
            paginator = s3.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=bucket_name)
            for page in pages:
                if 'Contents' in page:
                    objects = [{'Key': obj['Key']} for obj in page['Contents']]
                    if objects:
                        s3.delete_objects(Bucket=bucket_name, Delete={'Objects': objects})
                        print_progress(f"Deleted {len(objects)} objects from S3")
            
            # Delete the bucket
            s3.delete_bucket(Bucket=bucket_name)
            print_progress("S3 bucket deleted successfully")
        except Exception as cleanup_error:
            print_progress(f"Warning: S3 cleanup error (non-critical): {str(cleanup_error)}")
        
        # Generate and emit custom success message using Bedrock
        try:
            bedrock_msg = success_message()
            msg = f"{bedrock_msg}\n\nSaved to: {output_video}"
        except Exception as e:
            print_progress(f"Note: Could not generate custom message ({str(e)}), using default")
            msg = f"✨ Your subtitled video is ready! ✨\n\nSaved to: {output_video}"
        
        print(f"SUCCESS_MESSAGE::{msg}", flush=True)

        print_progress("Video processing complete!")
        sys.exit(0)
        
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()