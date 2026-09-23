"""
Verification script for FFmpeg audio extraction and Whisper speech-to-text pipeline.
"""
import os
import sys
import glob
import time
import shutil
import subprocess

# Auto-locate FFmpeg
search_patterns = [
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\*\bin"),
    os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\*\ffmpeg*\bin"),
    r"C:\ffmpeg\bin",
    r"C:\Program Files\ffmpeg\bin",
]
for pattern in search_patterns:
    matches = glob.glob(pattern)
    for match in matches:
        if os.path.exists(os.path.join(match, "ffmpeg.exe")):
            os.environ["PATH"] = match + os.pathsep + os.environ.get("PATH", "")
            print(f"[OK] Added FFmpeg to PATH: {match}")
            break

print(f"[OK] FFmpeg binary: {shutil.which('ffmpeg')}")

# Locate sample video
media_dir = os.path.abspath("Media")
video_files = glob.glob(os.path.join(media_dir, "*.mp4"))
if not video_files:
    print("[ERROR] No sample video found in Media/")
    sys.exit(1)

video_path = video_files[0]
print(f"[OK] Test Video: {video_path} ({os.path.getsize(video_path)/(1024*1024):.2f} MB)")

# Step 1: Extract Audio with FFmpeg
os.makedirs("audio", exist_ok=True)
audio_output = os.path.abspath("audio/test_extracted.wav")
ffmpeg_cmd = [
    "ffmpeg", "-i", video_path,
    "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", "-y",
    audio_output
]
print("[Step 1] Running FFmpeg extraction...")
t0 = time.time()
res = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
t_ffmpeg = time.time() - t0

if res.returncode != 0:
    print(f"[ERROR] FFmpeg failed: {res.stderr}")
    sys.exit(1)

print(f"[OK] FFmpeg extracted WAV in {t_ffmpeg:.2f}s! Size: {os.path.getsize(audio_output)/(1024*1024):.2f} MB")

# Step 2: Whisper Transcription
print("[Step 2] Loading OpenAI Whisper 'tiny' model...")
t_load_start = time.time()
import whisper
model = whisper.load_model("tiny")
print(f"[OK] Whisper model loaded in {time.time() - t_load_start:.2f}s!")

print("[Step 3] Transcribing audio...")
t_whisper_start = time.time()
result = model.transcribe(audio_output, fp16=False, verbose=False)
t_whisper = time.time() - t_whisper_start

print(f"[OK] Transcription complete in {t_whisper:.2f}s!")
print(f"[Result] Detected language: {result.get('language')}")
print(f"[Result] Total segments: {len(result.get('segments', []))}")
print(f"[Result] Words: {len(result.get('text', '').split())}")
print("-" * 60)
print("[First 300 characters of Transcript]:")
print(result.get('text', '')[:300] + "...")
print("-" * 60)

# Clean up test audio
if os.path.exists(audio_output):
    os.remove(audio_output)
    print("[OK] Cleaned up temporary test WAV file.")

print("[SUCCESS] All pipeline steps passed flawlessly!")
