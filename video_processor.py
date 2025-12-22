from http import client
import sys
import os
import subprocess
import boto3
import time
import json
from pathlib import Path

os.environ['PYTHONIOENCODING'] = 'utf-8'

def load_dotenv_simple():
    try:
        script_dir = Path(__file__).resolve().parent
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
        script_dir = Path(__file__).resolve().parent
        env_path = script_dir / '.env'
        if _DOTENV_AVAILABLE and _load_dotenv:
            _load_dotenv(dotenv_path=env_path)
        else:
            load_dotenv_simple()
    except Exception:
        load_dotenv_simple()

def print_progress(message):
    if isinstance(message, bytes):
        message = message.decode('utf-8', errors='ignore')
    print(message, flush=True)
def success_message():
    client = boto3.client('bedrock-runtime', region_name='eu-central-1')
    model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"

    # Build the request body for chat
    prompt = "Create a charming success message announcing that a video has been subtitled. Keep it sweet romantic and poetic. Avoid names like 'my love' or 'my darling' I prefer calling her that myself. Maximum 20 words. Just output the message, nothing else."
    
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
            "temperature": 0.7, 
            "topP": 0.6
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
        region = 'eu-central-1'
        transcriber = boto3.client('transcribe', region_name=region)
        
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        job_name = f"transcription_job_{timestamp}"
        
        try:
            transcriber.delete_transcription_job(TranscriptionJobName="transcription_job")
        except:
            pass
            
        s3 = boto3.client('s3', region_name=region)
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
            
            translator = boto3.client('translate', region_name=region)
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
        
        # Write initial SRT file
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
            # Convert **bold** to ASS override tags for colored bold text
            text = re.sub(r'\*\*(.+?)\*\*', r'{\\c&H00D7FF&\\b1}\1{\\b0\\c}', text)
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

        with open(subtitle_file, 'w', encoding='utf-8') as f:
            for i, sub in enumerate(subtitle_data):
                subtitle_text = format_subtitle_text(sub['text'], is_rtl)
                adj_start, adj_end = apply_offset(sub['start'], sub['end'])
                
                def format_time(seconds):
                    hours = int(seconds // 3600)
                    minutes = int((seconds % 3600) // 60)
                    secs = int(seconds % 60)
                    millis = int((seconds % 1) * 1000)
                    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
                
                f.write(f"{i + 1}\n")
                f.write(f"{format_time(adj_start)} --> {format_time(adj_end)}\n")
                f.write(f"{subtitle_text}\n\n")
        
        # Step 5: Add subtitles to video
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
            except Exception as font_err:
                print_progress(f"Warning: could not load font info ({font_err}), falling back to Arial")
                fonts_dir = ""
                font_name = "Arial"

        subtitle_arg = ff_safe(subtitle_file)
        fontsdir_opt = f":fontsdir={ff_quote(ff_safe(fonts_dir))}" if fonts_dir else ""

        # Sanitize font name for force_style
        font_name_safe = (font_name or "Arial").strip()
        font_name_safe = font_name_safe.replace(',', ' ').replace("'", '').replace('  ', ' ')
        font_name_safe = font_name_safe.strip()

        force_style = (
            f"FontName={font_name_safe},"
            "FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=0,Outline=0,Shadow=0"
        )

        ffmpeg_filter = f"subtitles={ff_quote(subtitle_arg)}{fontsdir_opt}:force_style={ff_quote(force_style)}"

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