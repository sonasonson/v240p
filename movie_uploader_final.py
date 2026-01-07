#!/usr/bin/env python3
"""
Telegram Movie Uploader with Progress Bar and 240p Compression
"""

import os
import sys
import time
import json
import subprocess
import shutil
import asyncio
import math
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
        "tqdm>=4.66.0",  # For progress bars
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
from tqdm import tqdm

app = None

# ===== PROGRESS HANDLERS =====
class DownloadProgress:
    """Handle download progress with percentage"""
    
    def __init__(self, total_size=None):
        self.total_size = total_size
        self.downloaded = 0
        self.start_time = time.time()
        self.last_print = 0
        self.bar = None
        
    def __enter__(self):
        if self.total_size:
            self.bar = tqdm(
                total=self.total_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
                desc="📥 Downloading",
                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{percentage:.0f}%] {rate_fmt}'
            )
        return self
    
    def __exit__(self, *args):
        if self.bar:
            self.bar.close()
    
    def update(self, chunk_size):
        self.downloaded += chunk_size
        if self.bar:
            self.bar.update(chunk_size)
        else:
            current_time = time.time()
            if current_time - self.last_print > 1.0:  # Update every second
                if self.total_size:
                    percent = (self.downloaded / self.total_size) * 100
                    speed = self.downloaded / (current_time - self.start_time) / 1024
                    print(f"📥 Downloading: {percent:.1f}% ({speed:.1f} KB/s)", end='\r')
                self.last_print = current_time
    
    def finish(self):
        if self.bar:
            self.bar.close()
        elapsed = time.time() - self.start_time
        size_mb = self.downloaded / (1024 * 1024)
        print(f"\n✅ Downloaded: {size_mb:.1f}MB in {elapsed:.1f}s")

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

def download_hls_with_progress(url, output_path):
    """Download HLS with progress bar"""
    print(f"📥 Downloading HLS stream...")
    
    try:
        # Custom progress hook for yt-dlp
        def progress_hook(d):
            if d['status'] == 'downloading':
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
                
                if total:
                    percent = (downloaded / total) * 100
                    speed = d.get('speed', 0)
                    if speed:
                        speed_kb = speed / 1024
                        print(f"📥 Downloading: {percent:.1f}% | Speed: {speed_kb:.0f} KB/s", end='\r')
                    else:
                        print(f"📥 Downloading: {percent:.1f}%", end='\r')
                else:
                    print(f"📥 Downloading: {downloaded:,} bytes", end='\r')
            
            elif d['status'] == 'finished':
                print(f"\n✅ Download completed!")
        
        # yt-dlp options with progress hook
        ydl_opts = {
            'format': 'best[height<=720]',
            'outtmpl': output_path,
            'quiet': False,
            'no_warnings': False,
            'progress_hooks': [progress_hook],
            'user_agent': 'Mozilla/5.0',
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
        }
        
        start_time = time.time()
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Get info first
            info = ydl.extract_info(url, download=False)
            duration = info.get('duration', 0)
            if duration:
                minutes = duration // 60
                seconds = duration % 60
                print(f"⏱️ Video duration: {minutes}:{seconds:02d}")
            
            # Download with progress
            print("Starting download...")
            ydl.download([url])
        
        elapsed = time.time() - start_time
        
        # Check for downloaded file
        if os.path.exists(output_path):
            size = os.path.getsize(output_path) / (1024 * 1024)
            print(f"✅ Download complete: {size:.1f}MB in {elapsed:.1f}s")
            return True
        
        # Try alternative extensions
        base, _ = os.path.splitext(output_path)
        for ext in ['.mp4', '.mkv', '.webm', '.ts', '.m4a']:
            alt_path = base + ext
            if os.path.exists(alt_path):
                shutil.move(alt_path, output_path)
                size = os.path.getsize(output_path) / (1024 * 1024)
                print(f"✅ Downloaded as {ext}: {size:.1f}MB")
                return True
        
        return False
        
    except Exception as e:
        print(f"\n❌ Download failed: {e}")
        return False

def compress_video_240p(input_file, output_file):
    """Compress video to 240p with progress display"""
    if not os.path.exists(input_file):
        print(f"❌ File not found: {input_file}")
        return False
    
    original_size = os.path.getsize(input_file) / (1024 * 1024)
    print(f"🎬 Compressing to 240p...")
    print(f"📊 Original size: {original_size:.1f}MB")
    
    # First, get video duration for progress estimation
    duration = 0
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            input_file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            duration = float(result.stdout.strip())
    except:
        pass
    
    # Compression command
    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-vf', 'scale=-2:240',
        '-c:v', 'libx264',
        '-crf', '28',
        '-preset', 'veryfast',
        '-c:a', 'aac',
        '-b:a', '64k',
        '-y',
        output_file
    ]
    
    try:
        start_time = time.time()
        
        # Run with progress display
        print("⏳ Compression in progress...")
        
        if duration > 0:
            # Show progress bar for known duration
            process = subprocess.Popen(
                cmd,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Parse ffmpeg output for progress
            for line in process.stderr:
                if 'time=' in line:
                    time_str = line.split('time=')[1].split()[0]
                    try:
                        # Convert time to seconds
                        h, m, s = map(float, time_str.split(':'))
                        current_time = h * 3600 + m * 60 + s
                        if duration > 0:
                            percent = (current_time / duration) * 100
                            print(f"🎬 Compressing: {percent:.1f}%", end='\r')
                    except:
                        pass
            
            process.wait()
        else:
            # Just run without progress
            result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(output_file):
            new_size = os.path.getsize(output_file) / (1024 * 1024)
            elapsed = time.time() - start_time
            reduction = ((original_size - new_size) / original_size) * 100
            
            print(f"\n✅ Compressed in {elapsed:.1f}s")
            print(f"📊 New size: {new_size:.1f}MB ({reduction:.1f}% reduction)")
            print(f"📺 Resolution: 240p")
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
            '-ss', '00:02:30',  # Middle of the movie
            '-vframes', '1',
            '-s', '320x180',  # Thumbnail size
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
    """Upload video to Telegram with progress"""
    if not os.path.exists(file_path):
        return False
    
    file_size = os.path.getsize(file_path) / (1024 * 1024)
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
        
        # Progress callback
        start_time = time.time()
        last_percent = 0
        
        def progress(current, total):
            nonlocal last_percent
            percent = (current / total) * 100
            if percent - last_percent >= 5 or percent == 100:  # Update every 5%
                speed = current / (time.time() - start_time) / 1024 if (time.time() - start_time) > 0 else 0
                print(f"📤 Uploading: {percent:.0f}% | Speed: {speed:.0f} KB/s", end='\r')
                last_percent = percent
        
        upload_params['progress'] = progress
        
        await app.send_video(**upload_params)
        
        elapsed = time.time() - start_time
        print(f"\n✅ Uploaded in {elapsed:.1f}s")
        return True
        
    except FloodWait as e:
        print(f"\n⏳ Flood wait: {e.value}s")
        await asyncio.sleep(e.value)
        return await upload_video(file_path, caption, thumbnail_path)
    except Exception as e:
        print(f"\n❌ Upload failed: {e}")
        return False

async def main():
    print("="*50)
    print("🎬 Telegram Movie Uploader v1.0")
    print("="*50)
    print("📺 Resolution: 240p | ⏱️ Progress Tracking")
    print("="*50)
    
    # Check and install ffmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("✅ ffmpeg is available")
    except:
        print("📦 Installing ffmpeg...")
        subprocess.run(['sudo', 'apt-get', 'update', '-y'], capture_output=True)
        subprocess.run(['sudo', 'apt-get', 'install', '-y', 'ffmpeg'], capture_output=True)
        print("✅ ffmpeg installed")
    
    # Setup Telegram
    print("\n" + "="*50)
    if not await setup_telegram():
        return
    
    # Load config
    config_file = "movie_config.json"
    if not os.path.exists(config_file):
        print(f"❌ Config file not found: {config_file}")
        print("💡 Creating sample config...")
        
        sample_config = {
            "watch_url": "https://example.com/video.m3u8",
            "movie_name_arabic": "اسم الفيلم",
            "movie_name_english": "Movie Name"
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(sample_config, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Created {config_file}")
        print("⚠️ Please edit the config file and run again")
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
    print(f"🔗 Source: {video_url[:80]}...")
    print(f"📺 Target: 240p (Telegram optimized)")
    
    # Create working directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    work_dir = f"movie_work_{timestamp}"
    os.makedirs(work_dir, exist_ok=True)
    
    original_file = os.path.join(work_dir, "original.mp4")
    compressed_file = os.path.join(work_dir, "compressed_240p.mp4")
    thumbnail_file = os.path.join(work_dir, "thumbnail.jpg")
    
    try:
        # Step 1: Download
        print(f"\n{'='*50}")
        print("📥 STEP 1: DOWNLOADING VIDEO")
        print('='*50)
        
        if not download_hls_with_progress(video_url, original_file):
            print("❌ Download failed")
            return
        
        # Step 2: Create thumbnail
        print(f"\n{'='*50}")
        print("🖼️ STEP 2: CREATING THUMBNAIL")
        print('='*50)
        
        create_thumbnail(original_file, thumbnail_file)
        
        # Step 3: Compress to 240p
        print(f"\n{'='*50}")
        print("🎬 STEP 3: COMPRESSING TO 240p")
        print('='*50)
        
        if not compress_video_240p(original_file, compressed_file):
            print("⚠️ Compression failed, using original")
            compressed_file = original_file
            print("⚠️ Note: File may be too large for Telegram")
        
        # Step 4: Upload
        print(f"\n{'='*50}")
        print("☁️ STEP 4: UPLOADING TO TELEGRAM")
        print('='*50)
        
        caption = f"<b>{movie_name_arabic}</b>"
        if movie_name_english:
            caption += f"\n<code>{movie_name_english}</code>"
        
        thumb = thumbnail_file if os.path.exists(thumbnail_file) else None
        
        if await upload_video(compressed_file, caption, thumb):
            print(f"\n{'='*50}")
            print("✅ SUCCESS: MOVIE UPLOADED!")
            print('='*50)
            print(f"🎬 Movie: {movie_name_arabic}")
            print(f"📺 Quality: 240p")
            print(f"📢 Channel: {TELEGRAM_CHANNEL}")
            print(f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}")
            print('='*50)
        else:
            print(f"\n{'='*50}")
            print("❌ FAILED: UPLOAD UNSUCCESSFUL")
            print('='*50)
            
    except Exception as e:
        print(f"\n{'='*50}")
        print("💥 ERROR OCCURRED")
        print('='*50)
        print(f"Error: {e}")
        
    finally:
        # Cleanup
        try:
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir)
                print(f"\n🗑️ Cleaned working directory")
        except:
            pass
    
    if app:
        await app.stop()
        print("🔌 Telegram connection closed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️ Process stopped by user")
    except Exception as e:
        print(f"\n💥 Fatal error: {e}")
        sys.exit(1)
