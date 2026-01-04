#!/usr/bin/env python3
"""
Universal Video Uploader - For Movies
Simple version that works with VK.com and other sites
"""

import os
import sys
import re
import time
import json
import requests
import subprocess
import shutil
import asyncio
from datetime import datetime

# ===== CONFIGURATION =====
TELEGRAM_API_ID = os.environ.get("API_ID", "")
TELEGRAM_API_HASH = os.environ.get("API_HASH", "")
TELEGRAM_CHANNEL = os.environ.get("CHANNEL", "")
STRING_SESSION = os.environ.get("STRING_SESSION", "")

def validate_env():
    """Validate environment variables"""
    print("🔍 Validating environment variables...")
    
    errors = []
    if not TELEGRAM_API_ID:
        errors.append("❌ API_ID is missing")
    if not TELEGRAM_API_HASH:
        errors.append("❌ API_HASH is missing")
    if not TELEGRAM_CHANNEL:
        errors.append("❌ CHANNEL is missing")
    if not STRING_SESSION:
        errors.append("❌ STRING_SESSION is missing")
    
    if errors:
        for error in errors:
            print(error)
        return False
    
    print("✅ Environment variables validated")
    return True

if not validate_env():
    sys.exit(1)

TELEGRAM_API_ID = int(TELEGRAM_API_ID)

# Install requirements
print("📦 Installing requirements...")
requirements = ["pyrogram", "tgcrypto", "yt-dlp", "requests", "beautifulsoup4"]
for req in requirements:
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", req, "--quiet"])
        print(f"  ✅ {req}")
    except:
        print(f"  ❌ {req}")

from pyrogram import Client
from pyrogram.errors import FloodWait
import yt_dlp

app = None

async def setup_telegram():
    """Setup Telegram client"""
    global app
    print("\n🔐 Setting up Telegram...")
    
    try:
        app = Client(
            "movie_uploader",
            api_id=TELEGRAM_API_ID,
            api_hash=TELEGRAM_API_HASH,
            session_string=STRING_SESSION.strip(),
            in_memory=True
        )
        
        await app.start()
        me = await app.get_me()
        print(f"✅ Connected as: {me.first_name}")
        return True
    except Exception as e:
        print(f"❌ Telegram setup failed: {e}")
        return False

def extract_video_url(url):
    """Extract direct video URL"""
    print(f"🔍 Extracting from: {url}")
    
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'worst[height<=240]/worst',
            'socket_timeout': 30,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info and 'url' in info:
                video_url = info['url']
                print(f"✅ Found video URL")
                return video_url
    except Exception as e:
        print(f"❌ Extraction failed: {e}")
    
    return None

def download_video(url, output_path):
    """Download video"""
    print(f"📥 Downloading: {url[:100]}...")
    
    try:
        ydl_opts = {
            'format': 'worst[height<=240]/worst',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 30,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        if os.path.exists(output_path):
            size = os.path.getsize(output_path) / (1024*1024)
            print(f"✅ Downloaded: {size:.1f}MB")
            return True
    except Exception as e:
        print(f"❌ Download failed: {e}")
    
    return False

async def upload_to_telegram(file_path, caption):
    """Upload to Telegram channel"""
    print(f"☁️ Uploading: {os.path.basename(file_path)}")
    
    try:
        await app.send_video(
            chat_id=TELEGRAM_CHANNEL,
            video=file_path,
            caption=caption,
            supports_streaming=True
        )
        print("✅ Uploaded successfully")
        return True
    except FloodWait as e:
        print(f"⏳ Flood wait: {e.value}s")
        await asyncio.sleep(e.value)
        return await upload_to_telegram(file_path, caption)
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return False

async def process_movie(video_url, video_title):
    """Process a single movie"""
    print(f"\n{'─'*50}")
    print(f"🎬 Processing: {video_title}")
    print(f"🔗 URL: {video_url}")
    print(f"{'─'*50}")
    
    # Create temp directory
    temp_dir = "temp_movie_" + datetime.now().strftime('%H%M%S')
    os.makedirs(temp_dir, exist_ok=True)
    output_file = os.path.join(temp_dir, "movie.mp4")
    
    try:
        # Step 1: Extract URL
        print("1. Extracting video URL...")
        direct_url = extract_video_url(video_url)
        if not direct_url:
            return False, "URL extraction failed"
        
        # Step 2: Download
        print("2. Downloading video...")
        if not download_video(direct_url, output_file):
            return False, "Download failed"
        
        # Step 3: Upload
        print("3. Uploading to Telegram...")
        if not await upload_to_telegram(output_file, video_title):
            return False, "Upload failed"
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
        return True, "✅ Movie processed successfully"
        
    except Exception as e:
        # Cleanup on error
        shutil.rmtree(temp_dir, ignore_errors=True)
        return False, f"Error: {str(e)}"

async def main():
    """Main function"""
    print("="*50)
    print("🎬 Movie Uploader v1.0")
    print("="*50)
    
    # Setup Telegram
    if not await setup_telegram():
        print("❌ Cannot continue without Telegram")
        return
    
    # Check config
    config_file = "video_config.json"
    if not os.path.exists(config_file):
        print("❌ Config file not found, creating sample...")
        sample_config = {
            "videos": [{
                "url": "https://vk.com/video_ext.php?oid=791768803&id=456249035",
                "title": "اكس مراتي - الفيلم الكامل"
            }]
        }
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(sample_config, f, ensure_ascii=False, indent=2)
        print("⚠️ Please edit video_config.json and run again")
        return
    
    # Load config
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Error reading config: {e}")
        return
    
    videos = config.get("videos", [])
    if not videos:
        print("❌ No videos in config")
        return
    
    # Process videos
    successful = 0
    for index, video in enumerate(videos, 1):
        url = video.get("url", "").strip()
        title = video.get("title", "").strip()
        
        if not url or not title:
            print(f"⚠️ Skipping video {index}: Missing data")
            continue
        
        print(f"\n[Video {index}/{len(videos)}] {title}")
        success, message = await process_movie(url, title)
        
        if success:
            successful += 1
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
        
        # Wait between videos
        if index < len(videos):
            await asyncio.sleep(2)
    
    # Summary
    print(f"\n{'='*50}")
    print(f"📊 Result: {successful}/{len(videos)} successful")
    print("🏁 Processing complete")
    
    # Cleanup
    if app:
        await app.stop()
        print("🔌 Disconnected from Telegram")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Stopped by user")
    except Exception as e:
        print(f"\n💥 Error: {e}")
        sys.exit(1)
