#!/usr/bin/env python3
"""
Simple Telegram Movie Uploader for Direct MP4 Links
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
    ]
    
    for req in requirements:
        subprocess.check_call([sys.executable, "-m", "pip", "install", req, "--quiet"])
    
    print("✅ Requirements installed")

install_requirements()

from pyrogram import Client
from pyrogram.errors import FloodWait

app = None

# ===== TELEGRAM SETUP =====
async def setup_telegram():
    global app
    
    print("🔐 Setting up Telegram...")
    
    try:
        app = Client(
            name="simple_uploader",
            api_id=TELEGRAM_API_ID,
            api_hash=TELEGRAM_API_HASH,
            session_string=STRING_SESSION.strip(),
            in_memory=True,
        )
        
        await app.start()
        me = await app.get_me()
        print(f"✅ Connected as: {me.first_name}")
        
        await app.get_chat(TELEGRAM_CHANNEL)
        print("📢 Channel accessible")
        return True
        
    except Exception as e:
        print(f"❌ Telegram setup failed: {e}")
        return False

def download_video_direct(url, output_path):
    """Download video directly using wget"""
    print(f"📥 Downloading: {url}")
    
    try:
        # Use wget for reliable downloads
        cmd = [
            'wget', '-c',
            '--user-agent', 'Mozilla/5.0',
            '--timeout=60',
            '--tries=10',
            '-O', output_path,
            url
        ]
        
        start = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(output_path):
            size = os.path.getsize(output_path) / (1024*1024)
            elapsed = time.time() - start
            print(f"✅ Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
            return True
        else:
            print(f"❌ Download failed")
            return False
            
    except Exception as e:
        print(f"❌ Download error: {e}")
        return False

def compress_video(input_file, output_file):
    """Compress video to 240p (for Telegram)"""
    if not os.path.exists(input_file):
        return False
    
    original_size = os.path.getsize(input_file) / (1024 * 1024)
    print(f"🎬 Compressing: {original_size:.1f}MB → 240p")
    
    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-vf', 'scale=-2:240',
        '-c:v', 'libx264',
        '-crf', '28',
        '-preset', 'fast',
        '-c:a', 'aac',
        '-b:a', '64k',
        '-y',
        output_file
    ]
    
    try:
        start = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(output_file):
            new_size = os.path.getsize(output_file) / (1024 * 1024)
            elapsed = time.time() - start
            print(f"✅ Compressed in {elapsed:.1f}s ({new_size:.1f}MB)")
            return True
    except:
        pass
    
    return False

async def upload_video(file_path, caption):
    """Upload video to Telegram"""
    if not os.path.exists(file_path):
        return False
    
    file_size = os.path.getsize(file_path) / (1024*1024)
    print(f"☁️ Uploading: {file_size:.1f}MB")
    
    try:
        await app.send_video(
            chat_id=TELEGRAM_CHANNEL,
            video=file_path,
            caption=caption,
            supports_streaming=True
        )
        print("✅ Upload successful")
        return True
    except FloodWait as e:
        print(f"⏳ Flood wait: {e.value}s")
        await asyncio.sleep(e.value)
        return await upload_video(file_path, caption)
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return False

async def main():
    print("="*50)
    print("🎬 Simple Movie Uploader")
    print("="*50)
    
    # Check ffmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True)
        print("✅ ffmpeg available")
    except:
        print("📦 Installing ffmpeg...")
        subprocess.run(['sudo', 'apt-get', 'update', '-y'], capture_output=True)
        subprocess.run(['sudo', 'apt-get', 'install', '-y', 'ffmpeg', 'wget'], capture_output=True)
    
    if not await setup_telegram():
        return
    
    # Load config
    config_file = "movie_config.json"
    if not os.path.exists(config_file):
        print(f"❌ Config file not found")
        return
    
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    video_url = config.get("watch_url", "").strip()
    movie_name_arabic = config.get("movie_name_arabic", "").strip()
    movie_name_english = config.get("movie_name_english", "").strip()
    
    if not video_url:
        print("❌ Video URL is required")
        return
    
    if not movie_name_arabic:
        print("❌ Movie name is required")
        return
    
    print(f"\n📽️ Movie: {movie_name_arabic}")
    print(f"🔗 URL: {video_url}")
    
    # Create temp directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    temp_dir = f"temp_{timestamp}"
    os.makedirs(temp_dir, exist_ok=True)
    
    temp_file = os.path.join(temp_dir, "original.mp4")
    final_file = os.path.join(temp_dir, "compressed.mp4")
    
    try:
        # Download
        if not download_video_direct(video_url, temp_file):
            print("❌ Download failed")
            return
        
        # Compress
        if not compress_video(temp_file, final_file):
            print("⚠️ Using original file")
            final_file = temp_file
        
        # Upload
        caption = movie_name_arabic
        if movie_name_english:
            caption += f"\n{movie_name_english}"
        
        if await upload_video(final_file, caption):
            print("\n✅ Movie uploaded successfully!")
        else:
            print("\n❌ Upload failed")
            
    finally:
        # Cleanup
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"🗑️ Cleaned temp directory")
    
    if app:
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
