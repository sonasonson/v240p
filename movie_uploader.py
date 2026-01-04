#!/usr/bin/env python3
"""
Telegram Movie Uploader - Same Settings as Series
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
from urllib.parse import urlparse

# ===== CONFIGURATION =====
# Get from GitHub Secrets
TELEGRAM_API_ID = os.environ.get("API_ID", "")
TELEGRAM_API_HASH = os.environ.get("API_HASH", "")
TELEGRAM_CHANNEL = os.environ.get("CHANNEL", "")
STRING_SESSION = os.environ.get("STRING_SESSION", "")

# Validate environment variables
def validate_env():
    """Validate environment variables"""
    errors = []
    
    if not TELEGRAM_API_ID:
        errors.append("❌ API_ID is missing")
    elif not TELEGRAM_API_ID.isdigit():
        errors.append("❌ API_ID must be a number")
    
    if not TELEGRAM_API_HASH:
        errors.append("❌ API_HASH is missing")
    
    if not TELEGRAM_CHANNEL:
        errors.append("❌ CHANNEL is missing")
    
    if not STRING_SESSION:
        errors.append("❌ STRING_SESSION is missing")
    
    if errors:
        print("\n".join(errors))
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
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Referer': 'https://larooza.cfd/'  # إضافة Referer للموقع
}

# ===== IMPORTS =====
def install_requirements():
    """Install required packages"""
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
            print(f"  ✅ {req.split('>=')[0]}")
        except:
            print(f"  ❌ Failed to install {req}")
    
    print("✅ All requirements installed")

# Install packages
install_requirements()

from pyrogram import Client
from pyrogram.errors import FloodWait, AuthKeyUnregistered
import yt_dlp

app = None

# ===== TELEGRAM SETUP =====

async def setup_telegram():
    """Setup Telegram using string session"""
    global app
    
    print("\n" + "="*50)
    print("🔐 Telegram Setup")
    print("="*50)
    
    print(f"📱 API_ID: {TELEGRAM_API_ID}")
    print(f"🔑 API_HASH: {TELEGRAM_API_HASH[:10]}...")
    print(f"📢 Channel: {TELEGRAM_CHANNEL}")
    
    try:
        cleaned_session = STRING_SESSION.strip()
        
        app = Client(
            name="movie_uploader",
            api_id=TELEGRAM_API_ID,
            api_hash=TELEGRAM_API_HASH,
            session_string=cleaned_session,
            in_memory=True,
            device_model="GitHub Actions",
            app_version="2.0.0",
            system_version="Ubuntu 22.04"
        )
        
        print("🔌 Connecting to Telegram...")
        await app.start()
        
        me = await app.get_me()
        print(f"✅ Connected as: {me.first_name} (@{me.username})")
        
        # Verify channel
        try:
            chat = await app.get_chat(TELEGRAM_CHANNEL)
            print(f"📢 Channel found: {chat.title}")
            return True
        except Exception as e:
            print(f"❌ Cannot access channel: {e}")
            return False
            
    except AuthKeyUnregistered:
        print("❌ STRING_SESSION is invalid or expired")
        return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

# ===== VIDEO PROCESSING FUNCTIONS =====

def extract_direct_video_url(page_url):
    """Extract direct video URL from streaming pages"""
    try:
        print(f"🔍 Extracting video from: {page_url}")
        
        # Parse the URL to get domain
        parsed_url = urlparse(page_url)
        domain = parsed_url.netloc
        
        # Update referer based on domain
        headers = HEADERS.copy()
        headers['Referer'] = f"https://{domain}/"
        
        # Fetch the page
        response = requests.get(page_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return None, f"HTTP Error {response.status_code}"
        
        content = response.text
        
        # Look for common video sources
        patterns = [
            r'src=["\']([^"\']+\.mp4[^"\']*)["\']',
            r'file["\']?\s*:\s*["\']([^"\']+\.mp4[^"\']*)["\']',
            r'video["\']?\s*:\s*["\']([^"\']+\.mp4[^"\']*)["\']',
            r'source["\']?\s*:\s*["\']([^"\']+\.mp4[^"\']*)["\']',
            r'player\.load\({src: ["\']([^"\']+\.mp4[^"\']*)["\']',
            r'jwplayer\("([^"]+)"\)\.setup\({.*?file: ["\']([^"\']+\.mp4[^"\']*)["\']',
            r'hlsManifestUrl["\']?\s*:\s*["\']([^"\']+)["\']',
            r'm3u8["\']?\s*:\s*["\']([^"\']+)["\']',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
            if matches:
                for match in matches:
                    if isinstance(match, tuple):
                        video_url = match[1] if len(match) > 1 else match[0]
                    else:
                        video_url = match
                    
                    # Make URL absolute
                    if video_url.startswith('//'):
                        video_url = 'https:' + video_url
                    elif video_url.startswith('/'):
                        video_url = f"https://{domain}" + video_url
                    elif not video_url.startswith('http'):
                        video_url = f"https://{domain}/{video_url}"
                    
                    print(f"✅ Found video URL: {video_url[:80]}...")
                    return video_url, "Direct URL extracted"
        
        # If no direct URL found, return the original URL for yt-dlp to handle
        print("⚠️ No direct URL found, using original URL")
        return page_url, "Using original URL"
        
    except Exception as e:
        print(f"❌ Extraction error: {e}")
        return None, str(e)

def download_movie(video_url, output_path):
    """Download movie with improved error handling"""
    try:
        # First try to extract direct URL
        direct_url, message = extract_direct_video_url(video_url)
        if direct_url:
            video_url = direct_url
            print(f"✅ {message}")
        
        # Configure yt-dlp for better compatibility
        ydl_opts = {
            'format': 'best[height<=720]/best',
            'outtmpl': output_path,
            'quiet': False,
            'no_warnings': False,
            'user_agent': USER_AGENT,
            'referer': video_url,  # Use video URL as referer
            'http_headers': HEADERS,
            'retries': 20,
            'fragment_retries': 20,
            'skip_unavailable_fragments': True,
            'socket_timeout': 60,
            'extractor_args': {
                'generic': {
                    'headers': HEADERS
                }
            },
            'concurrent_fragment_downloads': 4,
            'continuedl': True,
            'noprogress': False,
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        }
        
        print(f"📥 Downloading movie...")
        print(f"🔗 URL: {video_url}")
        
        start = time.time()
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Try to get info first
            try:
                info = ydl.extract_info(video_url, download=False)
                if info:
                    title = info.get('title', 'Unknown')
                    duration = info.get('duration', 0)
                    print(f"📝 Title: {title}")
                    if duration > 0:
                        print(f"⏱️ Duration: {duration // 60}:{duration % 60:02d} minutes")
                    
                    # Download
                    print("⬇️ Starting download...")
                    ydl.download([video_url])
                    actual_title = title
                else:
                    ydl.download([video_url])
                    actual_title = "Unknown"
            except:
                # If info extraction fails, try direct download
                print("⚠️ Info extraction failed, trying direct download...")
                ydl.download([video_url])
                actual_title = "Unknown"
        
        elapsed = time.time() - start
        
        # Check if file exists
        if os.path.exists(output_path):
            size = os.path.getsize(output_path) / (1024*1024)
            print(f"✅ Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
            return True, actual_title
        
        # Try different extensions
        base = os.path.splitext(output_path)[0]
        for ext in ['.mp4', '.mkv', '.webm', '.avi', '.flv', '.mov', '.m4v', '.3gp']:
            alt_file = base + ext
            if os.path.exists(alt_file):
                shutil.move(alt_file, output_path)
                size = os.path.getsize(output_path) / (1024*1024)
                print(f"✅ Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
                return True, actual_title
        
        return False, None
        
    except Exception as e:
        print(f"❌ Download error: {e}")
        
        # Try alternative method with different settings
        print("🔄 Trying alternative download method...")
        return download_movie_alternative(video_url, output_path)

def download_movie_alternative(video_url, output_path):
    """Alternative download method"""
    try:
        # Simpler settings for problematic sites
        ydl_opts = {
            'format': 'best',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'referer': 'https://www.google.com/',
            'retries': 30,
            'fragment_retries': 30,
            'skip_unavailable_fragments': True,
            'socket_timeout': 120,
            'extract_flat': False,
            'ignoreerrors': True,
            'no_check_certificate': True,
        }
        
        print("🔄 Using alternative downloader...")
        start = time.time()
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        
        elapsed = time.time() - start
        
        if os.path.exists(output_path):
            size = os.path.getsize(output_path) / (1024*1024)
            print(f"✅ Alternative download successful in {elapsed:.1f}s ({size:.1f}MB)")
            return True, "Movie"
        
        return False, None
        
    except Exception as e:
        print(f"❌ Alternative download also failed: {e}")
        return False, None

def compress_video_to_240p(input_file, output_file, crf=28):
    """Compress video to 240p - Same as series"""
    if not os.path.exists(input_file):
        print(f"❌ File not found: {input_file}")
        return False
    
    original_size = os.path.getsize(input_file) / (1024 * 1024)
    print(f"🎬 Compressing to 240p...")
    print(f"📊 Original: {original_size:.1f}MB")
    print(f"⚙️ CRF: {crf} (same as series)")
    
    # Get video duration
    try:
        cmd = ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', 
               '-of', 'default=noprint_wrappers=1:nokey=1', input_file]
        result = subprocess.run(cmd, capture_output=True, text=True)
        duration = float(result.stdout.strip()) if result.returncode == 0 else 0
        if duration > 0:
            print(f"⏱️ Duration: {int(duration//3600)}:{int((duration%3600)//60):02d}:{int(duration%60):02d}")
    except:
        duration = 0
    
    # Same compression settings as series
    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-vf', 'scale=-2:240',  # 240p مثل المسلسلات
        '-c:v', 'libx264',
        '-crf', str(crf),  # نفس جودة المسلسلات
        '-preset', 'veryfast',  # نفس سرعة المسلسلات
        '-c:a', 'aac',
        '-b:a', '64k',  # نفس جودة صوت المسلسلات
        '-y',
        output_file
    ]
    
    try:
        start = time.time()
        print(f"⏳ Compression started...")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Simple progress
        for line in process.stdout:
            if 'time=' in line:
                time_match = re.search(r'time=(\d+:\d+:\d+\.\d+)', line)
                if time_match:
                    print(f"⏳ Processing: {time_match.group(1)}", end='\r')
        
        process.wait()
        
        if process.returncode == 0 and os.path.exists(output_file):
            new_size = os.path.getsize(output_file) / (1024 * 1024)
            elapsed = time.time() - start
            reduction = ((original_size - new_size) / original_size) * 100
            
            print(f"\n✅ Compressed in {elapsed:.1f}s")
            print(f"📊 New size: {new_size:.1f}MB (-{reduction:.1f}%)")
            print(f"🎬 Quality: 240p (same as series)")
            return True
        else:
            print(f"\n❌ Compression failed")
            return False
    except Exception as e:
        print(f"\n❌ Compression error: {e}")
        return False

def create_thumbnail(input_file, thumbnail_path):
    """Create thumbnail - Same as series"""
    try:
        print(f"🖼️ Creating thumbnail...")
        
        cmd = [
            'ffmpeg',
            '-i', input_file,
            '-ss', '00:00:10',  # نفس توقيت المسلسلات
            '-vframes', '1',
            '-s', '320x180',  # نفس حجم المسلسلات
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

def get_video_dimensions(input_file):
    """Get video dimensions"""
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'csv=p=0',
            input_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            dimensions = result.stdout.strip().split(',')
            if len(dimensions) == 2:
                return int(dimensions[0]), int(dimensions[1])
    except:
        pass
    
    return 426, 240  # Default for 240p

def get_video_duration(input_file):
    """Get video duration in seconds"""
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
            return int(float(result.stdout.strip()))
    except:
        pass
    
    return 0

async def upload_video(file_path, caption, thumbnail_path=None):
    """Upload video to Telegram channel"""
    try:
        if not app or not os.path.exists(file_path):
            return False
        
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path) / (1024*1024)
        
        print(f"☁️ Uploading: {filename}")
        print(f"📊 Size: {file_size:.1f}MB")
        
        # Get video dimensions
        width, height = get_video_dimensions(file_path)
        
        # Get duration
        duration = get_video_duration(file_path)
        
        # Prepare upload
        upload_params = {
            'chat_id': TELEGRAM_CHANNEL,
            'video': file_path,
            'caption': caption,
            'supports_streaming': True,
            'width': width,
            'height': height,
            'duration': duration,
        }
        
        if thumbnail_path and os.path.exists(thumbnail_path):
            upload_params['thumb'] = thumbnail_path
        
        # Upload with progress
        start_time = time.time()
        last_percent = 0
        
        def progress(current, total):
            nonlocal last_percent
            percent = (current / total) * 100
            if percent - last_percent >= 5 or percent == 100:
                speed = current / (time.time() - start_time) / 1024 if (time.time() - start_time) > 0 else 0
                print(f"📤 {percent:.1f}% - {speed:.0f}KB/s", end='\r')
                last_percent = percent
        
        upload_params['progress'] = progress
        
        # Upload
        try:
            await app.send_video(**upload_params)
            elapsed = time.time() - start_time
            print(f"\n✅ Uploaded in {elapsed:.1f}s")
            print(f"🎬 Streaming: Enabled")
            return True
            
        except FloodWait as e:
            print(f"\n⏳ Flood wait: {e.value}s")
            await asyncio.sleep(e.value)
            return await upload_video(file_path, caption, thumbnail_path)
            
        except Exception as e:
            print(f"\n❌ Upload error: {e}")
            # Try without progress callback
            try:
                upload_params.pop('progress', None)
                await app.send_video(**upload_params)
                print(f"✅ Upload successful")
                return True
            except Exception as e2:
                print(f"❌ Retry failed: {e2}")
                return False
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return False

async def process_movie(movie_url, movie_title, download_dir):
    """Process a single movie"""
    print(f"\n{'─'*50}")
    print(f"🎬 Movie: {movie_title}")
    print(f"{'─'*50}")
    
    # Create safe filename
    safe_title = re.sub(r'[^\w\-_\. ]', '_', movie_title)[:50]
    temp_file = os.path.join(download_dir, f"temp_{safe_title}.mp4")
    final_file = os.path.join(download_dir, f"{safe_title}.mp4")
    thumbnail_file = os.path.join(download_dir, f"thumb_{safe_title}.jpg")
    
    # Clean old files
    for f in [temp_file, final_file, thumbnail_file]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except:
                pass
    
    try:
        # 1. Download movie
        print("📥 Downloading movie...")
        download_success, actual_title = download_movie(movie_url, temp_file)
        
        if not download_success:
            return False, "Download failed"
        
        # Use actual title if available
        if actual_title and actual_title != 'Unknown' and actual_title != 'Movie':
            movie_title = actual_title
        
        # 2. Create thumbnail
        print("🖼️ Creating thumbnail...")
        create_thumbnail(temp_file, thumbnail_file)
        
        # 3. Compress to 240p (same as series)
        print("🎬 Compressing to 240p...")
        if not compress_video_to_240p(temp_file, final_file, crf=28):
            print("⚠️ Compression failed, using original")
            shutil.copy2(temp_file, final_file)
        
        # 4. Upload
        caption = f"🎬 {movie_title}"  # بدون سنة
        thumb = thumbnail_file if os.path.exists(thumbnail_file) else None
        
        if await upload_video(final_file, caption, thumb):
            # 5. Clean up
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
    """Main function for movie uploader"""
    print("="*50)
    print("🎬 Movie Uploader v2.0 - Same as Series")
    print("="*50)
    print("⚙️ Settings: 240p, CRF 28, 64k audio (same as series)")
    print("📝 Caption: 🎬 + Title only (no year)")
    
    # Check dependencies
    print("\n🔍 Checking dependencies...")
    
    # Check ffmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("✅ ffmpeg is installed")
    except:
        print("❌ ffmpeg not found, installing...")
        subprocess.run(['sudo', 'apt-get', 'update', '-y'], capture_output=True)
        subprocess.run(['sudo', 'apt-get', 'install', '-y', 'ffmpeg'], capture_output=True)
        print("✅ ffmpeg installed")
    
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
            "movies": [
                {
                    "url": "https://larooza.cfd/play.php?vid=956c7e520",
                    "title": "فيلم تجريبي"
                }
            ]
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(sample_config, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Created {config_file} with sample data")
        print("⚠️ Please edit the config file and run again")
        return
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Error reading config: {e}")
        return
    
    movies = config.get("movies", [])
    
    if not movies:
        print("❌ No movies found in configuration")
        return
    
    print(f"📋 Found {len(movies)} movie(s) to process")
    
    # Create working directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    download_dir = f"movies_{timestamp}"
    os.makedirs(download_dir, exist_ok=True)
    
    print(f"\n{'='*50}")
    print("🚀 Starting Movie Processing")
    print('='*50)
    print(f"⚙️ Quality: 240p (same as series)")
    print(f"📁 Working dir: {download_dir}")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Process movies
    successful = 0
    failed = []
    
    for index, movie in enumerate(movies, 1):
        movie_url = movie.get("url", "").strip()
        movie_title = movie.get("title", "").strip()
        
        if not movie_url:
            print(f"❌ Movie {index}: No URL provided")
            failed.append(f"Movie {index}: No URL")
            continue
        
        if not movie_title:
            movie_title = f"Movie {index}"
        
        print(f"\n[#{index}] 🎬 {movie_title}")
        print(f"   🔗 URL: {movie_url[:60]}...")
        
        start_time = time.time()
        success, message = await process_movie(
            movie_url, movie_title, download_dir
        )
        
        elapsed = time.time() - start_time
        
        if success:
            successful += 1
            print(f"✅ {movie_title}: {message}")
            print(f"   ⏱️ Time: {elapsed:.1f}s")
            print(f"   🎬 Quality: 240p (series settings)")
        else:
            failed.append(movie_title)
            print(f"❌ {movie_title}: {message}")
        
        # Wait between movies
        if index < len(movies):
            wait_time = 3
            print(f"⏳ Waiting {wait_time} seconds...")
            await asyncio.sleep(wait_time)
    
    # Results summary
    print(f"\n{'='*50}")
    print("📊 Processing Summary")
    print('='*50)
    print(f"✅ Successful: {successful}/{len(movies)}")
    print(f"❌ Failed: {len(failed)}")
    
    if successful == len(movies):
        print("🎉 All movies processed successfully!")
    elif successful > 0:
        print(f"⚠️ Partially successful ({successful}/{len(movies)})")
    else:
        print("💥 All movies failed!")
    
    if failed:
        print(f"📝 Failed movies: {failed}")
        print("💡 Tips for failed downloads:")
        print("   1. Try a different video URL")
        print("   2. Use direct .mp4 links if possible")
        print("   3. Check if the video is accessible")
    
    # Cleanup empty directory
    try:
        if os.path.exists(download_dir) and not os.listdir(download_dir):
            os.rmdir(download_dir)
            print(f"🗑️ Cleaned empty directory: {download_dir}")
    except:
        pass
    
    print(f"\n{'='*50}")
    print("🏁 Processing Complete")
    print(f"⏰ Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print('='*50)
    
    # Close Telegram connection
    if app:
        await app.stop()
        print("🔌 Telegram connection closed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️ Process stopped by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {type(e).__name__}")
        print(f"📝 Details: {e}")
        sys.exit(1)
