#!/usr/bin/env python3
"""
Telegram Movie Uploader with Cloudscraper & 240p Compression
"""

import os
import sys
import time
import json
import subprocess
import shutil
import asyncio
import tempfile
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
        "yt-dlp>=2024.12.08",  # Latest version
        "requests>=2.31.0",
        "tqdm>=4.66.0",
        "cloudscraper>=1.2.71",
        "browser_cookie3>=0.19.1",
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
import cloudscraper
from tqdm import tqdm
import browser_cookie3

app = None

# ===== TELEGRAM SETUP =====
async def setup_telegram():
    global app
    
    print("="*50)
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

def get_cookies_from_browser():
    """Try to get cookies from browser to bypass protection"""
    try:
        # Try Chrome first
        cj = browser_cookie3.chrome(domain_name='vidoba.org')
        cookies_dict = {}
        for cookie in cj:
            cookies_dict[cookie.name] = cookie.value
        
        if cookies_dict:
            print(f"🍪 Found {len(cookies_dict)} cookies from browser")
            return cookies_dict
    except:
        pass
    
    return None

def create_cookie_file(cookies_dict):
    """Create a cookie file from cookies dict"""
    if not cookies_dict:
        return None
    
    cookie_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt')
    
    # Write cookies in Netscape format
    for name, value in cookies_dict.items():
        cookie_file.write(f"{name}\t{value}\t/\tvidoba.org\tFALSE\t/\tFALSE\n")
    
    cookie_file.close()
    return cookie_file.name

def download_with_cloudscraper(url, output_path):
    """Download using cloudscraper to bypass Cloudflare"""
    print(f"🛡️ Using cloudscraper to bypass protection...")
    
    try:
        # Create cloudscraper instance
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False,
                'desktop': True,
            }
        )
        
        # Try to get page
        response = scraper.get(url, timeout=30)
        
        if response.status_code != 200:
            print(f"⚠️ Cloudscraper failed with status: {response.status_code}")
            return False
        
        print(f"✅ Cloudscraper accessed page successfully")
        return True
        
    except Exception as e:
        print(f"❌ Cloudscraper failed: {e}")
        return False

def download_video_with_ytdlp(url, output_path):
    """Download video using yt-dlp with enhanced settings"""
    print(f"📥 Starting download...")
    
    try:
        # Get cookies from browser if possible
        cookies_dict = get_cookies_from_browser()
        cookie_file = create_cookie_file(cookies_dict)
        
        # Enhanced headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://vidoba.org/',
            'Origin': 'https://vidoba.org',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'DNT': '1',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Custom progress hook
        last_update = [0]
        
        def progress_hook(d):
            if d['status'] == 'downloading':
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
                
                current_time = time.time()
                if current_time - last_update[0] > 0.5:  # Update every 0.5 seconds
                    if total:
                        percent = (downloaded / total) * 100
                        speed = d.get('speed', 0)
                        if speed:
                            speed_mb = speed / (1024 * 1024)
                            print(f"📥 Downloading: {percent:.1f}% | Speed: {speed_mb:.1f} MB/s", end='\r')
                        else:
                            print(f"📥 Downloading: {percent:.1f}%", end='\r')
                    else:
                        print(f"📥 Downloading: {downloaded:,} bytes", end='\r')
                    last_update[0] = current_time
            
            elif d['status'] == 'finished':
                print(f"\n✅ Download completed!")
        
        # yt-dlp options
        ydl_opts = {
            'format': 'best[height<=720]',
            'outtmpl': output_path,
            'quiet': False,
            'no_warnings': False,
            'progress_hooks': [progress_hook],
            'user_agent': headers['User-Agent'],
            'retries': 20,
            'fragment_retries': 20,
            'skip_unavailable_fragments': True,
            'concurrent_fragment_downloads': 10,
            'http_headers': headers,
            'socket_timeout': 60,
            'extractor_args': {
                'generic': {
                    'player_skip': ['all'],
                    'ignore_no_formats_error': True,
                }
            },
            'cookiefile': cookie_file if cookie_file else None,
        }
        
        start_time = time.time()
        
        # Try multiple extractors
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # First try with generic extractor
                info = ydl.extract_info(url, download=False)
            except Exception as e:
                print(f"⚠️ First extraction failed: {e}")
                # Try with force_generic_extractor
                ydl_opts['force_generic_extractor'] = True
                ydl = yt_dlp.YoutubeDL(ydl_opts)
                info = ydl.extract_info(url, download=False)
            
            if info:
                duration = info.get('duration', 0)
                if duration:
                    hours = duration // 3600
                    minutes = (duration % 3600) // 60
                    seconds = duration % 60
                    print(f"⏱️ Video duration: {hours:02d}:{minutes:02d}:{seconds:02d}")
                
                print(f"📊 Available formats: {len(info.get('formats', []))}")
                
                # Start download
                print("🚀 Starting download process...")
                ydl.download([url])
        
        elapsed = time.time() - start_time
        
        # Clean up cookie file
        if cookie_file and os.path.exists(cookie_file):
            os.unlink(cookie_file)
        
        # Check result
        if os.path.exists(output_path):
            size = os.path.getsize(output_path) / (1024 * 1024)
            print(f"✅ Download successful: {size:.1f}MB in {elapsed:.1f}s")
            return True
        
        # Check alternative extensions
        base, _ = os.path.splitext(output_path)
        for ext in ['.mp4', '.mkv', '.webm', '.ts', '.m4a', '.flv']:
            alt_path = base + ext
            if os.path.exists(alt_path):
                shutil.move(alt_path, output_path)
                size = os.path.getsize(output_path) / (1024 * 1024)
                print(f"✅ Downloaded as {ext}: {size:.1f}MB")
                return True
        
        return False
        
    except Exception as e:
        print(f"\n❌ Download failed: {str(e)[:200]}")
        return False

def compress_to_240p_with_progress(input_file, output_file):
    """Compress video to 240p with progress display"""
    if not os.path.exists(input_file):
        print(f"❌ Input file not found")
        return False
    
    original_size = os.path.getsize(input_file) / (1024 * 1024)
    print(f"🎬 Starting compression to 240p...")
    print(f"📊 Original size: {original_size:.1f}MB")
    
    # Get duration for progress
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
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            print(f"⏱️ Duration: {minutes}:{seconds:02d}")
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
        
        if duration > 0:
            # With progress display
            process = subprocess.Popen(
                cmd,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )
            
            last_percent = 0
            for line in process.stderr:
                if 'time=' in line:
                    try:
                        time_str = line.split('time=')[1].split()[0]
                        h, m, s = time_str.split(':')
                        current_time = float(h) * 3600 + float(m) * 60 + float(s)
                        percent = min(99, (current_time / duration) * 100)
                        
                        if percent - last_percent >= 1:  # Update every 1%
                            elapsed = time.time() - start_time
                            eta = (duration - current_time) * (elapsed / current_time) if current_time > 0 else 0
                            print(f"🎬 Compressing: {percent:.1f}% | ETA: {eta:.0f}s", end='\r')
                            last_percent = percent
                    except:
                        pass
            
            process.wait()
            returncode = process.returncode
        else:
            # Without progress
            result = subprocess.run(cmd, capture_output=True, text=True)
            returncode = result.returncode
        
        if returncode == 0 and os.path.exists(output_file):
            new_size = os.path.getsize(output_file) / (1024 * 1024)
            elapsed = time.time() - start_time
            reduction = ((original_size - new_size) / original_size) * 100
            
            print(f"\n✅ Compression completed in {elapsed:.1f}s")
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
        
        # Try to get video duration first
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
        
        # Take thumbnail from 10% of video duration
        if duration > 0:
            thumbnail_time = duration * 0.1
            hours = int(thumbnail_time // 3600)
            minutes = int((thumbnail_time % 3600) // 60)
            seconds = int(thumbnail_time % 60)
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            time_str = "00:05:00"  # Default 5 minutes
        
        cmd = [
            'ffmpeg',
            '-i', input_file,
            '-ss', time_str,
            '-vframes', '1',
            '-s', '320x180',
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

async def upload_video_with_progress(file_path, caption, thumbnail_path=None):
    """Upload video to Telegram with progress"""
    if not os.path.exists(file_path):
        return False
    
    file_size = os.path.getsize(file_path) / (1024 * 1024)
    print(f"☁️ Preparing upload: {file_size:.1f}MB")
    
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
        
        # Progress tracking
        start_time = time.time()
        last_update = [0]
        
        def progress(current, total):
            current_time = time.time()
            if current_time - last_update[0] > 1:  # Update every second
                percent = (current / total) * 100
                elapsed = current_time - start_time
                speed = current / elapsed / 1024 if elapsed > 0 else 0  # KB/s
                eta = (total - current) / (speed * 1024) if speed > 0 else 0
                
                print(f"📤 Uploading: {percent:.1f}% | Speed: {speed:.0f} KB/s | ETA: {eta:.0f}s", end='\r')
                last_update[0] = current_time
        
        upload_params['progress'] = progress
        
        await app.send_video(**upload_params)
        
        elapsed = time.time() - start_time
        print(f"\n✅ Upload completed in {elapsed:.1f}s")
        return True
        
    except FloodWait as e:
        print(f"\n⏳ Flood wait: {e.value}s")
        await asyncio.sleep(e.value)
        return await upload_video_with_progress(file_path, caption, thumbnail_path)
    except Exception as e:
        print(f"\n❌ Upload failed: {e}")
        return False

async def main():
    print("="*60)
    print("🎬 TELEGRAM MOVIE UPLOADER v2.0")
    print("="*60)
    print("📺 Resolution: 240p | 🛡️ Cloudscraper Enabled")
    print("="*60)
    
    # Install system dependencies
    print("\n🔧 Checking system dependencies...")
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("✅ ffmpeg is available")
    except:
        print("📦 Installing ffmpeg...")
        subprocess.run(['sudo', 'apt-get', 'update', '-y'], capture_output=True)
        subprocess.run(['sudo', 'apt-get', 'install', '-y', 'ffmpeg'], capture_output=True)
        print("✅ ffmpeg installed")
    
    # Setup Telegram
    if not await setup_telegram():
        return
    
    # Load config
    config_file = "movie_config.json"
    if not os.path.exists(config_file):
        print(f"❌ Config file not found")
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
    print(f"🔗 Source: {video_url[:100]}...")
    print(f"📺 Target: 240p")
    
    # Create working directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    work_dir = f"work_{timestamp}"
    os.makedirs(work_dir, exist_ok=True)
    
    original_file = os.path.join(work_dir, "original.mp4")
    compressed_file = os.path.join(work_dir, "compressed_240p.mp4")
    thumbnail_file = os.path.join(work_dir, "thumbnail.jpg")
    
    try:
        # Step 1: Try to bypass protection
        print(f"\n" + "="*60)
        print("🛡️ STEP 1: BYPASSING PROTECTION")
        print("="*60)
        
        if not download_with_cloudscraper(video_url, original_file):
            print("⚠️ Cloudscraper failed, trying direct download...")
        
        # Step 2: Download video
        print(f"\n" + "="*60)
        print("📥 STEP 2: DOWNLOADING VIDEO")
        print("="*60)
        
        if not download_video_with_ytdlp(video_url, original_file):
            print("❌ Download failed after all attempts")
            return
        
        # Step 3: Create thumbnail
        print(f"\n" + "="*60)
        print("🖼️ STEP 3: CREATING THUMBNAIL")
        print("="*60)
        
        create_thumbnail(original_file, thumbnail_file)
        
        # Step 4: Compress to 240p
        print(f"\n" + "="*60)
        print("🎬 STEP 4: COMPRESSING TO 240p")
        print("="*60)
        
        if not compress_to_240p_with_progress(original_file, compressed_file):
            print("⚠️ Compression failed, using original")
            compressed_file = original_file
        
        # Step 5: Upload
        print(f"\n" + "="*60)
        print("☁️ STEP 5: UPLOADING TO TELEGRAM")
        print("="*60)
        
        caption = f"<b>{movie_name_arabic}</b>"
        if movie_name_english:
            caption += f"\n<code>{movie_name_english}</code>"
        
        thumb = thumbnail_file if os.path.exists(thumbnail_file) else None
        
        if await upload_video_with_progress(compressed_file, caption, thumb):
            print(f"\n" + "="*60)
            print("✅ SUCCESS: MOVIE UPLOADED SUCCESSFULLY!")
            print("="*60)
            print(f"🎬 Movie: {movie_name_arabic}")
            print(f"📺 Quality: 240p")
            print(f"📢 Channel: {TELEGRAM_CHANNEL}")
            print(f"⏰ Completed at: {datetime.now().strftime('%H:%M:%S')}")
            print("="*60)
        else:
            print(f"\n" + "="*60)
            print("❌ FAILED: UPLOAD UNSUCCESSFUL")
            print("="*60)
            
    except Exception as e:
        print(f"\n" + "="*60)
        print("💥 ERROR OCCURRED")
        print("="*60)
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
