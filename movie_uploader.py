#!/usr/bin/env python3
"""
Telegram Movie Downloader & Uploader
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
from urllib.parse import urlparse, parse_qs

# ===== CONFIGURATION =====
TELEGRAM_API_ID = os.environ.get("API_ID", "")
TELEGRAM_API_HASH = os.environ.get("API_HASH", "")
TELEGRAM_CHANNEL = os.environ.get("CHANNEL", "")
STRING_SESSION = os.environ.get("STRING_SESSION", "")

# Validate environment variables
def validate_env():
    errors = []
    
    if not TELEGRAM_API_ID:
        errors.append("API_ID is missing")
    elif not TELEGRAM_API_ID.isdigit():
        errors.append("API_ID must be a number")
    
    if not TELEGRAM_API_HASH:
        errors.append("API_HASH is missing")
    
    if not TELEGRAM_CHANNEL:
        errors.append("CHANNEL is missing")
    
    if not STRING_SESSION:
        errors.append("STRING_SESSION is missing")
    
    if errors:
        for error in errors:
            print(f"❌ {error}")
        return False
    
    print("✅ Environment variables validated")
    return True

if not validate_env():
    sys.exit(1)

TELEGRAM_API_ID = int(TELEGRAM_API_ID)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
}

# ===== INSTALL REQUIREMENTS =====
def install_requirements():
    print("📦 Installing requirements...")
    
    requirements = [
        "pyrogram>=2.0.0",
        "tgcrypto>=1.2.0",
        "yt-dlp>=2024.4.9",
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.0",
        "lxml>=4.9.0",
    ]
    
    for req in requirements:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", req, "--quiet"])
            print(f"  ✅ {req.split('>=')[0]}")
        except:
            print(f"  ❌ Failed to install {req}")
    
    print("✅ All requirements installed")

install_requirements()

from pyrogram import Client
from pyrogram.errors import FloodWait
import yt_dlp
from bs4 import BeautifulSoup

app = None

# ===== TELEGRAM SETUP =====
async def setup_telegram():
    global app
    
    print("\n" + "="*50)
    print("🔐 Telegram Setup")
    print("="*50)
    
    try:
        app = Client(
            name="movie_uploader",
            api_id=TELEGRAM_API_ID,
            api_hash=TELEGRAM_API_HASH,
            session_string=STRING_SESSION.strip(),
            in_memory=True,
        )
        
        print("🔌 Connecting to Telegram...")
        await app.start()
        
        me = await app.get_me()
        print(f"✅ Connected as: {me.first_name}")
        
        try:
            chat = await app.get_chat(TELEGRAM_CHANNEL)
            print(f"📢 Channel found: {chat.title}")
            return True
        except Exception as e:
            print(f"❌ Cannot access channel: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Telegram setup failed: {e}")
        return False

# ===== VIDEO EXTRACTION =====
def extract_video_url(watch_url):
    """Extract video URL from watch URL"""
    print(f"🔗 Extracting video from: {watch_url}")
    
    # Try multiple methods
    
    # Method 1: Try yt-dlp
    print("🔄 Method 1: Trying yt-dlp...")
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'user_agent': USER_AGENT,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(watch_url, download=False)
            
            if 'url' in info:
                return info['url'], "✅ URL extracted via yt-dlp"
            
            if 'formats' in info:
                formats = info['formats']
                # Filter video formats
                video_formats = [f for f in formats if f.get('vcodec') != 'none']
                if video_formats:
                    # Try to find MP4 first
                    mp4_formats = [f for f in video_formats if f.get('ext') == 'mp4']
                    if mp4_formats:
                        best_format = max(mp4_formats, key=lambda x: x.get('height', 0))
                        return best_format['url'], f"✅ Found MP4 ({best_format.get('height', 'N/A')}p)"
                    
                    # Otherwise take best available
                    best_format = max(video_formats, key=lambda x: x.get('height', 0))
                    return best_format['url'], f"✅ Found best format ({best_format.get('height', 'N/A')}p)"
    except Exception as e:
        print(f"⚠️ yt-dlp extraction failed: {e}")
    
    # Method 2: Try direct HTML parsing
    print("🔄 Method 2: Trying direct HTML parsing...")
    try:
        response = requests.get(watch_url, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for video tags
            video_tags = soup.find_all('video')
            for video in video_tags:
                src = video.get('src')
                if src:
                    # Make absolute URL if relative
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        parsed = urlparse(watch_url)
                        src = f'{parsed.scheme}://{parsed.netloc}{src}'
                    return src, "✅ Found video tag"
            
            # Look for source tags inside video
            for video in video_tags:
                sources = video.find_all('source')
                for source in sources:
                    src = source.get('src')
                    if src:
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif src.startswith('/'):
                            parsed = urlparse(watch_url)
                            src = f'{parsed.scheme}://{parsed.netloc}{src}'
                        return src, "✅ Found source tag"
            
            # Look for iframes
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                src = iframe.get('src')
                if src and 'video' in src.lower():
                    # Try to extract from iframe
                    try:
                        iframe_response = requests.get(src, headers=HEADERS, timeout=15)
                        iframe_soup = BeautifulSoup(iframe_response.text, 'html.parser')
                        
                        # Look for video in iframe
                        iframe_videos = iframe_soup.find_all('video')
                        for iframe_video in iframe_videos:
                            iframe_src = iframe_video.get('src')
                            if iframe_src:
                                return iframe_src, "✅ Found URL in iframe"
                    except:
                        pass
    except Exception as e:
        print(f"⚠️ HTML parsing failed: {e}")
    
    return None, "❌ Could not extract video URL"

def download_video(url, output_path):
    """Download video using yt-dlp"""
    try:
        ydl_opts = {
            'format': 'best[height<=720]/best',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'user_agent': USER_AGENT,
            'retries': 10,
            'fragment_retries': 10,
            'skip_unavailable_fragments': True,
            'socket_timeout': 30,
        }
        
        print(f"📥 Downloading: {url[:100]}...")
        start = time.time()
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        elapsed = time.time() - start
        
        # Check if file was downloaded
        if os.path.exists(output_path):
            size = os.path.getsize(output_path) / (1024*1024)
            print(f"✅ Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
            return True
        
        # Check for files with different extensions
        base = os.path.splitext(output_path)[0]
        for ext in ['.mp4', '.mkv', '.webm', '.avi', '.flv']:
            alt_path = base + ext
            if os.path.exists(alt_path):
                shutil.move(alt_path, output_path)
                size = os.path.getsize(output_path) / (1024*1024)
                print(f"✅ Renamed {ext} to mp4 ({size:.1f}MB)")
                return True
        
        return False
        
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return False

def compress_video(input_file, output_file):
    """Compress video to 720p"""
    if not os.path.exists(input_file):
        print(f"❌ File not found: {input_file}")
        return False
    
    original_size = os.path.getsize(input_file) / (1024 * 1024)
    print(f"🎬 Compressing video...")
    print(f"📊 Original: {original_size:.1f}MB")
    
    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-vf', 'scale=-2:720',
        '-c:v', 'libx264',
        '-crf', '23',
        '-preset', 'medium',
        '-c:a', 'aac',
        '-b:a', '128k',
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
            '-ss', '00:01:00',
            '-vframes', '1',
            '-s', '1280x720',
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
    """Upload video to Telegram channel"""
    try:
        if not app or not os.path.exists(file_path):
            return False
        
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path) / (1024*1024)
        
        print(f"☁️ Uploading: {filename}")
        print(f"📊 Size: {file_size:.1f}MB")
        
        upload_params = {
            'chat_id': TELEGRAM_CHANNEL,
            'video': file_path,
            'caption': caption,
            'supports_streaming': True,
        }
        
        if thumbnail_path and os.path.exists(thumbnail_path):
            upload_params['thumb'] = thumbnail_path
        
        start_time = time.time()
        
        try:
            await app.send_video(**upload_params)
            elapsed = time.time() - start_time
            print(f"✅ Uploaded in {elapsed:.1f}s")
            return True
            
        except FloodWait as e:
            print(f"⏳ Flood wait: {e.value}s")
            await asyncio.sleep(e.value)
            return await upload_video(file_path, caption, thumbnail_path)
            
        except Exception as e:
            print(f"❌ Upload error: {e}")
            return False
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return False

async def process_movie(watch_url, movie_name_arabic, movie_name_english, download_dir):
    """Process a single movie"""
    print(f"\n{'─'*50}")
    print(f"🎬 Processing Movie")
    print(f"{'─'*50}")
    
    temp_file = os.path.join(download_dir, "temp_movie.mp4")
    final_file = os.path.join(download_dir, "final_movie.mp4")
    thumbnail_file = os.path.join(download_dir, "thumb_movie.jpg")
    
    # Clean old files
    for f in [temp_file, final_file, thumbnail_file]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except:
                pass
    
    try:
        # 1. Extract URL
        print("🔍 Extracting video URL...")
        video_url, message = extract_video_url(watch_url)
        
        if not video_url:
            return False, f"URL extraction failed: {message}"
        
        print(f"{message}")
        print(f"📊 Video URL: {video_url[:100]}...")
        
        # 2. Download
        print("📥 Downloading video...")
        if not download_video(video_url, temp_file):
            return False, "Download failed"
        
        # 3. Create thumbnail
        print("🖼️ Creating thumbnail...")
        create_thumbnail(temp_file, thumbnail_file)
        
        # 4. Compress
        print("🎬 Compressing video...")
        if not compress_video(temp_file, final_file):
            print("⚠️ Compression failed, using original")
            shutil.copy2(temp_file, final_file)
        
        # 5. Upload
        caption = f"{movie_name_arabic}"
        if movie_name_english:
            caption += f"\n{movie_name_english}"
        
        thumb = thumbnail_file if os.path.exists(thumbnail_file) else None
        
        if await upload_video(final_file, caption, thumb):
            # 6. Clean up
            for file_path in [temp_file, final_file, thumbnail_file]:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        print(f"🗑️ Deleted: {os.path.basename(file_path)}")
                    except:
                        pass
            return True, "✅ Movie uploaded and cleaned"
        else:
            return False, "❌ Upload failed"
        
    except Exception as e:
        print(f"❌ Processing error: {e}")
        return False, str(e)

# ===== MAIN FUNCTION =====
async def main():
    """Main function"""
    print("="*50)
    print("🎬 Telegram Movie Uploader")
    print("="*50)
    
    # Check dependencies
    print("\n🔍 Checking dependencies...")
    
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ ffmpeg is installed")
        else:
            print("❌ ffmpeg not found, trying to install...")
            subprocess.run(['sudo', 'apt-get', 'update', '-y'], capture_output=True)
            subprocess.run(['sudo', 'apt-get', 'install', '-y', 'ffmpeg'], capture_output=True)
            print("✅ ffmpeg installed")
    except:
        print("⚠️ Cannot check ffmpeg")
    
    # Setup Telegram
    print("\n" + "="*50)
    if not await setup_telegram():
        print("❌ Cannot continue without Telegram connection")
        return
    
    # Load configuration
    config_file = "movie_config.json"
    if not os.path.exists(config_file):
        print(f"❌ Config file not found: {config_file}")
        print("💡 Creating sample config...")
        
        sample_config = {
            "watch_url": "https://example.com/watch/movie",
            "movie_name_arabic": "اسم الفيلم",
            "movie_name_english": "Movie Name"
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(sample_config, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Created {config_file}")
        print("⚠️ Please edit the config file and run again")
        return
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Error reading config: {e}")
        return
    
    watch_url = config.get("watch_url", "").strip()
    movie_name_arabic = config.get("movie_name_arabic", "").strip()
    movie_name_english = config.get("movie_name_english", "").strip()
    
    if not watch_url:
        print("❌ Watch URL is required")
        return
    
    if not movie_name_arabic:
        print("❌ Arabic movie name is required")
        return
    
    # Create working directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    download_dir = f"movie_downloads_{timestamp}"
    os.makedirs(download_dir, exist_ok=True)
    
    print(f"\n{'='*50}")
    print("🚀 Starting Movie Processing")
    print('='*50)
    print(f"📽️ Arabic Name: {movie_name_arabic}")
    if movie_name_english:
        print(f"📽️ English Name: {movie_name_english}")
    print(f"🔗 Watch URL: {watch_url}")
    print(f"📁 Working dir: {download_dir}")
    
    # Process movie
    print(f"\n[Processing Movie]")
    print("─" * 50)
    
    start_time = time.time()
    success, message = await process_movie(watch_url, movie_name_arabic, movie_name_english, download_dir)
    
    elapsed = time.time() - start_time
    
    print(f"\n{'='*50}")
    print("📊 Processing Summary")
    print('='*50)
    
    if success:
        print(f"✅ Movie processed successfully!")
        print(f"⏱️ Processing time: {elapsed:.1f} seconds")
    else:
        print(f"❌ Movie processing failed: {message}")
    
    # Cleanup
    try:
        if os.path.exists(download_dir) and not os.listdir(download_dir):
            os.rmdir(download_dir)
    except:
        pass
    
    print(f"\n{'='*50}")
    print("🏁 Processing Complete")
    print('='*50)
    
    if app:
        await app.stop()
        print("🔌 Telegram connection closed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️ Process stopped by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)
