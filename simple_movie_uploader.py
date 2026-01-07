#!/usr/bin/env python3
"""
Telegram Movie Uploader with HLS Support
"""

import os
import sys
import time
import json
import subprocess
import shutil
import asyncio
from datetime import datetime

# ===== CONFIGURATION =====
TELEGRAM_API_ID = os.environ.get("API_ID", "")
TELEGRAM_API_HASH = os.environ.get("API_HASH", "")
TELEGRAM_CHANNEL = os.environ.get("CHANNEL", "")
STRING_SESSION = os.environ.get("STRING_SESSION", "")

if not all([TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_CHANNEL, STRING_SESSION]):
    print("❌ Missing environment variables")
    sys.exit(1)

TELEGRAM_API_ID = int(TELEGRAM_API_ID)

# ===== INSTALL REQUIREMENTS =====
def install_requirements():
    print("📦 Installing requirements...")
    
    requirements = [
        "pyrogram>=2.0.0",
        "tgcrypto>=1.2.0",
        "yt-dlp>=2024.4.9",
        "requests>=2.31.0",
    ]
    
    for req in requirements:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", req, "--quiet"])
        except:
            pass
    
    print("✅ Requirements installed")

install_requirements()

from pyrogram import Client
from pyrogram.errors import FloodWait
import yt_dlp
import requests

app = None

# ===== TELEGRAM SETUP =====
async def setup_telegram():
    global app
    
    print("🔐 Setting up Telegram...")
    
    try:
        app = Client(
            name="movie_uploader",
            api_id=TELEGRAM_API_ID,
            api_hash=TELEGRAM_API_HASH,
            session_string=STRING_SESSION.strip(),
            in_memory=True,
        )
        
        await app.start()
        me = await app.get_me()
        print(f"✅ Connected as: {me.first_name}")
        
        chat = await app.get_chat(TELEGRAM_CHANNEL)
        print(f"📢 Channel: {chat.title}")
        return True
        
    except Exception as e:
        print(f"❌ Telegram setup failed: {e}")
        return False

def download_hls_with_ytdlp(url, output_path):
    """Download HLS/m3u8 using yt-dlp"""
    print(f"📥 Downloading HLS stream: {url[:80]}...")
    
    try:
        # Options for HLS/m3u8
        ydl_opts = {
            'format': 'best[height<=720]',
            'outtmpl': output_path,
            'quiet': False,
            'no_warnings': False,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'retries': 10,
            'fragment_retries': 10,
            'skip_unavailable_fragments': True,
            'concurrent_fragment_downloads': 5,
            'http_headers': {
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://vidoba.org/',
                'Origin': 'https://vidoba.org',
            },
            'extractor_args': {
                'hls': {
                    'live_duration': 86400,
                }
            }
        }
        
        start = time.time()
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # First get info about the stream
            info = ydl.extract_info(url, download=False)
            print(f"📊 Stream info: {info.get('title', 'Unknown')}")
            print(f"📊 Duration: {info.get('duration', 0)} seconds")
            print(f"📊 Formats: {len(info.get('formats', []))}")
            
            # Download the video
            ydl.download([url])
        
        elapsed = time.time() - start
        
        # Check for downloaded file
        if os.path.exists(output_path):
            size = os.path.getsize(output_path) / (1024*1024)
            print(f"✅ Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
            return True
        
        # Check with different extensions
        base, _ = os.path.splitext(output_path)
        for ext in ['.mp4', '.mkv', '.webm', '.ts', '.m4a']:
            alt_path = base + ext
            if os.path.exists(alt_path):
                shutil.move(alt_path, output_path)
                size = os.path.getsize(output_path) / (1024*1024)
                print(f"✅ Downloaded as {ext} in {elapsed:.1f}s ({size:.1f}MB)")
                return True
        
        return False
        
    except Exception as e:
        print(f"❌ yt-dlp download failed: {e}")
        
        # Try alternative method with ffmpeg
        print("🔄 Trying alternative method with ffmpeg...")
        try:
            return download_hls_with_ffmpeg(url, output_path)
        except Exception as e2:
            print(f"❌ Alternative method failed: {e2}")
            return False

def download_hls_with_ffmpeg(url, output_path):
    """Alternative method using ffmpeg directly"""
    print("🔄 Using ffmpeg for HLS download...")
    
    temp_file = output_path + '.ts'
    
    cmd = [
        'ffmpeg',
        '-i', url,
        '-c', 'copy',
        '-bsf:a', 'aac_adtstoasc',
        '-f', 'mp4',
        '-y',
        temp_file
    ]
    
    try:
        start = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0 and os.path.exists(temp_file):
            # Convert to proper mp4 if needed
            if temp_file != output_path:
                cmd2 = [
                    'ffmpeg',
                    '-i', temp_file,
                    '-c', 'copy',
                    '-y',
                    output_path
                ]
                subprocess.run(cmd2, capture_output=True)
                os.remove(temp_file)
            
            if os.path.exists(output_path):
                size = os.path.getsize(output_path) / (1024*1024)
                elapsed = time.time() - start
                print(f"✅ HLS downloaded via ffmpeg in {elapsed:.1f}s ({size:.1f}MB)")
                return True
    except Exception as e:
        print(f"❌ ffmpeg download failed: {e}")
    
    return False

def compress_video(input_file, output_file):
    """Compress video to 480p for better Telegram compatibility"""
    if not os.path.exists(input_file):
        print(f"❌ File not found: {input_file}")
        return False
    
    original_size = os.path.getsize(input_file) / (1024 * 1024)
    print(f"🎬 Compressing video...")
    print(f"📊 Original: {original_size:.1f}MB")
    
    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-vf', 'scale=-2:480',
        '-c:v', 'libx264',
        '-crf', '25',
        '-preset', 'fast',
        '-c:a', 'aac',
        '-b:a', '96k',
        '-movflags', '+faststart',
        '-y',
        output_file
    ]
    
    try:
        start = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(output_file):
            new_size = os.path.getsize(output_file) / (1024 * 1024)
            elapsed = time.time() - start
            reduction = ((original_size - new_size) / original_size) * 100
            
            print(f"✅ Compressed in {elapsed:.1f}s")
            print(f"📊 New size: {new_size:.1f}MB (-{reduction:.1f}%)")
            return True
        else:
            print(f"❌ Compression failed")
            if result.stderr:
                error_lines = result.stderr.split('\n')
                for line in error_lines[-5:]:
                    if line.strip():
                        print(f"   {line}")
            return False
    except Exception as e:
        print(f"❌ Compression error: {e}")
        return False

def create_thumbnail(input_file, thumbnail_path):
    """Create thumbnail from video"""
    try:
        print(f"🖼️ Creating thumbnail...")
        
        cmd = [
            'ffmpeg',
            '-i', input_file,
            '-ss', '00:05:00',
            '-vframes', '1',
            '-vf', 'scale=320:-1',
            '-f', 'image2',
            '-y',
            thumbnail_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and os.path.exists(thumbnail_path):
            size = os.path.getsize(thumbnail_path) / 1024
            print(f"✅ Thumbnail created ({size:.1f}KB)")
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ Thumbnail error: {e}")
        return False

async def upload_video(file_path, caption, thumbnail_path=None):
    """Upload video to Telegram"""
    if not os.path.exists(file_path):
        return False
    
    file_size = os.path.getsize(file_path) / (1024*1024)
    print(f"☁️ Uploading: {file_size:.1f}MB")
    
    try:
        upload_params = {
            'chat_id': TELEGRAM_CHANNEL,
            'video': file_path,
            'caption': caption,
            'supports_streaming': True,
            'parse_mode': 'HTML',
        }
        
        if thumbnail_path and os.path.exists(thumbnail_path):
            upload_params['thumb'] = thumbnail_path
        
        start_time = time.time()
        
        await app.send_video(**upload_params)
        
        elapsed = time.time() - start_time
        print(f"✅ Uploaded in {elapsed:.1f}s")
        return True
        
    except FloodWait as e:
        print(f"⏳ Flood wait: {e.value}s")
        await asyncio.sleep(e.value)
        return await upload_video(file_path, caption, thumbnail_path)
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return False

async def main():
    print("="*50)
    print("🎬 Telegram Movie Uploader (HLS Version)")
    print("="*50)
    
    # Install ffmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True)
        print("✅ ffmpeg available")
    except:
        print("📦 Installing ffmpeg...")
        subprocess.run(['sudo', 'apt-get', 'update', '-y'], capture_output=True)
        subprocess.run(['sudo', 'apt-get', 'install', '-y', 'ffmpeg'], capture_output=True)
    
    if not await setup_telegram():
        return
    
    # Load config
    config_file = "movie_config.json"
    if not os.path.exists(config_file):
        print(f"❌ Config file not found: {config_file}")
        return
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    video_url = config.get("watch_url", "").strip()
    movie_name_arabic = config.get("movie_name_arabic", "").strip()
    movie_name_english = config.get("movie_name_english", "").strip()
    
    if not video_url:
        print("❌ Video URL is required")
        return
    
    if not movie_name_arabic:
        print("❌ Arabic movie name is required")
        return
    
    print(f"\n📽️ Movie: {movie_name_arabic}")
    if movie_name_english:
        print(f"🌐 English: {movie_name_english}")
    print(f"🔗 URL: {video_url[:100]}...")
    
    # Create working directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    work_dir = f"movie_{timestamp}"
    os.makedirs(work_dir, exist_ok=True)
    
    original_file = os.path.join(work_dir, "original.mp4")
    compressed_file = os.path.join(work_dir, "compressed.mp4")
    thumbnail_file = os.path.join(work_dir, "thumbnail.jpg")
    
    try:
        # 1. Download HLS stream
        print(f"\n{'─'*50}")
        print("📥 Step 1: Downloading video...")
        
        if not download_hls_with_ytdlp(video_url, original_file):
            print("❌ Download failed")
            return
        
        # 2. Create thumbnail
        print(f"\n{'─'*50}")
        print("🖼️ Step 2: Creating thumbnail...")
        create_thumbnail(original_file, thumbnail_file)
        
        # 3. Compress video
        print(f"\n{'─'*50}")
        print("🎬 Step 3: Compressing video...")
        
        if not compress_video(original_file, compressed_file):
            print("⚠️ Using original file (not compressed)")
            compressed_file = original_file
        
        # 4. Upload to Telegram
        print(f"\n{'─'*50}")
        print("☁️ Step 4: Uploading to Telegram...")
        
        caption = f"<b>{movie_name_arabic}</b>"
        if movie_name_english:
            caption += f"\n<code>{movie_name_english}</code>"
        
        thumb = thumbnail_file if os.path.exists(thumbnail_file) else None
        
        if await upload_video(compressed_file, caption, thumb):
            print(f"\n{'='*50}")
            print("✅ SUCCESS: Movie uploaded successfully!")
            print(f"{'='*50}")
        else:
            print(f"\n{'='*50}")
            print("❌ FAILED: Upload failed")
            print(f"{'='*50}")
            
    except Exception as e:
        print(f"\n💥 ERROR: {e}")
        
    finally:
        # Cleanup
        try:
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir)
                print(f"🗑️ Cleaned working directory")
        except:
            pass
    
    if app:
        await app.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️ Process stopped by user")
    except Exception as e:
        print(f"\n💥 Fatal error: {e}")
        sys.exit(1)
