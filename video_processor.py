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

def transcribe_to_translate_lang(transcribe_code):
    base_lang = transcribe_code.split('-')[0]
    if transcribe_code == 'zh-CN':
        return 'zh'
    elif transcribe_code == 'zh-TW':
        return 'zh-TW'
    return base_lang

def translate_with_bedrock(text, source_lang, target_lang):
    model_id = os.getenv('MODEL_ID')
    if not model_id:
        raise Exception('MODEL_ID is not set in .env')

    client = boto3.client('bedrock-runtime', region_name='eu-central-1')

    prompt = (
        f"Translate the following text from {source_lang} to {target_lang}. "
        f"Preserve meaning, punctuation, numerals, and any **bold** markers exactly. "
        f"This text is for subtitles; keep phrasing concise. Return only translated text.\n\n{text}"
    )

    messages = [{"role": "user", "content": [{"text": prompt}]}]

    resp = client.converse(
        modelId=model_id,
        messages=messages,
        inferenceConfig={"maxTokens": 4000, "temperature": 0.2}
    )

    output = resp.get('output', {})
    msg = output.get('message', {})
    content = msg.get('content', [])
    translated_parts = []
    for part in content:
        t = part.get('text')
        if t:
            translated_parts.append(t)
    translated = '\n'.join(translated_parts).strip()
    return translated or text

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

def main():
    if len(sys.argv) != 5:
        print("Usage: video_processor.py <input_video> <output_video> <origin_lang> <destination_lang>")
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
                raise Exception("Transcription job failed")
            
            time.sleep(5)
        
        print_progress("Retrieving transcription...")
        transcript_key = f"{job_name}.json"
        s3.download_file(bucket_name, transcript_key, 'temp_transcript.json')
        
        with open('temp_transcript.json', 'r', encoding='utf-8') as f:
            transcript_data = json.load(f)
        
        transcription_text = transcript_data['results']['transcripts'][0]['transcript']
        
        # Step 3: Translate
        translate_source_lang = transcribe_to_translate_lang(origin_lang)
        
        translation_skipped = translate_source_lang == destination_lang
        if translation_skipped:
            print_progress("Source and target languages are the same, skipping translation...")
            translated_text = transcription_text
        else:
            model_id = os.getenv('MODEL_ID', 'unset')
            print_progress(f"Translating text to {destination_lang} using Bedrock model {model_id}...")
            try:
                translated_text = translate_with_bedrock(
                    transcription_text,
                    translate_source_lang,
                    destination_lang
                )
            except Exception as bedrock_err:
                print_progress(f"Bedrock translation failed, falling back to AWS Translate: {bedrock_err}")
                translator = boto3.client('translate', region_name=region)
                response = translator.translate_text(
                    Text=transcription_text,
                    SourceLanguageCode=translate_source_lang,
                    TargetLanguageCode=destination_lang
                )
                translated_text = response.get('TranslatedText')
        
        # Translation complete - will be edited in the subtitle editor later
        print_progress(f"Translation complete. Text length: {len(translated_text)} characters")
        
        # Step 4: Create initial subtitles with timestamps
        print_progress("Creating subtitles with timestamps...")
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
        
        # Map translated text to subtitles
        translated_words = translated_text.split()
        words_per_subtitle = max(1, len(translated_words) // len(subtitles))
        
        subtitle_data = []
        start_idx = 0
        for i, subtitle in enumerate(subtitles):
            if translation_skipped:
                text = subtitle['words']
            else:
                end_idx = min(start_idx + words_per_subtitle, len(translated_words))
                if i == len(subtitles) - 1:
                    end_idx = len(translated_words)
                text = ' '.join(translated_words[start_idx:end_idx])
                start_idx = end_idx
            
            subtitle_data.append({
                'text': text,
                'start': float(subtitle['start']),
                'end': float(subtitle['end'])
            })
        
        print_progress(f"Prepared {len(subtitle_data)} subtitles for editor")
        
        # Send to editor
        subtitle_file = "temp_subtitles.srt"
        editor_payload = {
            'subtitles': subtitle_data,
            'subtitleFile': subtitle_file
        }
        
        # Write initial SRT file that editor will modify
        with open(subtitle_file, 'w', encoding='utf-8') as f:
            for i, sub in enumerate(subtitle_data):
                def format_time(seconds):
                    hours = int(seconds // 3600)
                    minutes = int((seconds % 3600) // 60)
                    secs = int(seconds % 60)
                    millis = int((seconds % 1) * 1000)
                    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
                
                f.write(f"{i + 1}\n")
                f.write(f"{format_time(sub['start'])} --> {format_time(sub['end'])}\n")
                f.write(f"{sub['text']}\n\n")
        
        print_progress("Sending subtitles to editor...")
        print(f"EDITOR_REQUEST::{json.dumps(editor_payload)}", flush=True)
        print_progress("Waiting for subtitle editing confirmation...")
        
        # Wait for editor confirmation
        confirmation = input()
        if confirmation != "EDITOR_CONFIRMED":
            raise Exception("Editor not confirmed")
        
        print_progress("Editor confirmed, processing final video...")
        
        # Read edited subtitles
        subtitle_data = parse_srt_file(subtitle_file)
        
        # Convert to SRT with formatting
        def format_subtitle_text(text, is_rtl=False):
            import re
            text = re.sub(r'\*\*(.+?)\*\*', r'<font color="#FFD700">\1</font>', text)
            if is_rtl:
                text = '\u200F' + text
            return text
        
        rtl_languages = ['ar', 'fa', 'he', 'ur']
        is_rtl = destination_lang in rtl_languages
        
        with open(subtitle_file, 'w', encoding='utf-8') as f:
            for i, sub in enumerate(subtitle_data):
                subtitle_text = format_subtitle_text(sub['text'], is_rtl)
                
                def format_time(seconds):
                    hours = int(seconds // 3600)
                    minutes = int((seconds % 3600) // 60)
                    secs = int(seconds % 60)
                    millis = int((seconds % 1) * 1000)
                    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
                
                f.write(f"{i + 1}\n")
                f.write(f"{format_time(sub['start'])} --> {format_time(sub['end'])}\n")
                f.write(f"{subtitle_text}\n\n")
        
        # Step 5: Add subtitles to video
        print_progress("Adding subtitles to video...")
        subprocess.run([
            'ffmpeg', '-i', input_video,
            '-vf', f"subtitles={subtitle_file}:force_style='FontName=Arial,FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=0,Outline=0,Shadow=0'",
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
            s3.delete_object(Bucket=bucket_name, Key=s3_key)
            s3.delete_object(Bucket=bucket_name, Key=f"{job_name}.json")
            s3.delete_bucket(Bucket=bucket_name)
        except Exception as cleanup_error:
            print_progress(f"Warning: S3 cleanup error (non-critical): {str(cleanup_error)}")
        
        print_progress("Video processing complete!")
        sys.exit(0)
        
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()