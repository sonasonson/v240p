#!/usr/bin/env python3
"""
Telegram Movie Uploader - Direct Extraction from Larooza
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
import cloudscraper
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# ===== CONFIGURATION =====
TELEGRAM_API_ID = os.environ.get("API_ID", "")
TELEGRAM_API_HASH = os.environ.get("API_HASH", "")
TELEGRAM_CHANNEL = os.environ.get("CHANNEL", "")
STRING_SESSION = os.environ.get("STRING_SESSION", "")

def validate_env():
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

# ===== IMPORTS =====
def install_requirements():
    print("📦 Installing requirements...")
    
    requirements = [
        "pyrogram>=2.0.0",
        "tgcrypto>=1.2.0",
        "yt-dlp>=2024.4.9",
        "requests>=2.31.0",
        "cloudscraper>=1.2.71",
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
from pyrogram.errors import FloodWait, AuthKeyUnregistered
import yt_dlp

app = None

# ===== TELEGRAM SETUP =====
async def setup_telegram():
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

# ===== EXTRACT VIDEO FROM LAROOZA =====
def extract_larooza_video(page_url):
    """Extract video URL from Larooza site"""
    try:
        print(f"🔍 Extracting from Larooza: {page_url}")
        
        # Use cloudscraper to bypass CloudFlare
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            }
        )
        
        # Get main page
        print("📄 Fetching main page...")
        response = scraper.get(page_url, timeout=30)
        
        if response.status_code != 200:
            return None, f"Failed to fetch page: {response.status_code}"
        
        # Find iframe
        iframe_match = re.search(r'<iframe[^>]+src="([^"]+)"', response.text)
        if not iframe_match:
            return None, "No iframe found"
        
        iframe_url = iframe_match.group(1)
        if iframe_url.startswith('//'):
            iframe_url = 'https:' + iframe_url
        
        print(f"🔗 Found iframe: {iframe_url}")
        
        # Get iframe content
        print("📄 Fetching iframe...")
        iframe_response = scraper.get(iframe_url, timeout=30)
        
        if iframe_response.status_code != 200:
            return None, f"Failed to fetch iframe: {iframe_response.status_code}"
        
        # Try to find direct video URL
        # Pattern 1: Look for jwplayer setup
        jwplayer_patterns = [
            r'file["\']?\s*:\s*["\']([^"\']+)["\']',
            r'sources\s*:\s*\[\s*{[^}]+file["\']?\s*:\s*["\']([^"\']+)["\']',
            r'jwplayer\([^)]+\)\.setup\(({[^}]+})',
        ]
        
        for pattern in jwplayer_patterns:
            matches = re.findall(pattern, iframe_response.text, re.DOTALL | re.IGNORECASE)
            for match in matches:
                if isinstance(match, str):
                    # Try to extract URL from JSON-like string
                    url_match = re.search(r'file["\']?\s*:\s*["\']([^"\']+)["\']', match)
                    if url_match:
                        video_url = url_match.group(1)
                        if video_url and ('m3u8' in video_url or 'mp4' in video_url):
                            print(f"✅ Found jwplayer URL: {video_url[:80]}...")
                            return video_url, "JWPlayer URL found"
        
        # Pattern 2: Look for m3u8 in script tags
        script_pattern = r'<script[^>]*>([^<]+)</script>'
        scripts = re.findall(script_pattern, iframe_response.text, re.DOTALL | re.IGNORECASE)
        
        for script in scripts:
            if 'm3u8' in script or 'master.m3u8' in script:
                # Look for URL in the script
                url_pattern = r'(https?://[^\s"\']+\.m3u8[^\s"\']*)'
                urls = re.findall(url_pattern, script)
                for url in urls:
                    if 'master.m3u8' in url or 'index.m3u8' in url:
                        print(f"✅ Found m3u8 in script: {url[:80]}...")
                        return url, "m3u8 URL found"
        
        # Pattern 3: Look for any video URL
        video_patterns = [
            r'(https?://[^\s"\']+\.m3u8[^\s"\']*)',
            r'(https?://[^\s"\']+\.mp4[^\s"\']*)',
            r'video["\']?\s*:\s*["\']([^"\']+)["\']',
            r'src["\']?\s*:\s*["\']([^"\']+)["\']',
        ]
        
        for pattern in video_patterns:
            matches = re.findall(pattern, iframe_response.text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, str):
                    video_url = match
                    if ('m3u8' in video_url or 'mp4' in video_url) and 'http' in video_url:
                        print(f"✅ Found video URL: {video_url[:80]}...")
                        return video_url, "Video URL found"
        
        # If no direct URL found, use yt-dlp on the iframe URL
        print("⚠️ No direct URL found, using yt-dlp on iframe")
        return iframe_url, "Using iframe URL"
        
    except Exception as e:
        print(f"❌ Extraction error: {e}")
        return None, str(e)

def download_with_ytdlp(video_url, output_path):
    """Download using yt-dlp with optimized settings"""
    try:
        # Configure yt-dlp
        ydl_opts = {
            'format': 'best[height<=720]/best',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'referer': video_url,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'video',
                'Sec-Fetch-Mode': 'no-cors',
                'Sec-Fetch-Site': 'cross-site',
            },
            'retries': 30,
            'fragment_retries': 30,
            'skip_unavailable_fragments': True,
            'socket_timeout': 120,
            'extractor_args': {
                'generic': {
                    'headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Referer': video_url,
                    }
                }
            },
            'concurrent_fragment_downloads': 10,
            'continuedl': True,
            'noprogress': True,
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            'ignoreerrors': True,
            'no_check_certificate': True,
            'extract_flat': False,
        }
        
        print(f"📥 Downloading with yt-dlp...")
        print(f"🔗 URL: {video_url[:100]}...")
        
        start = time.time()
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # Try to get info first
                info = ydl.extract_info(video_url, download=False)
                if info:
                    title = info.get('title', 'Unknown')
                    print(f"📝 Title: {title}")
                    
                    # Download
                    ydl.download([video_url])
                    actual_title = title
                else:
                    ydl.download([video_url])
                    actual_title = "Unknown"
            except Exception as e:
                print(f"⚠️ Info extraction failed: {e}")
                # Try direct download
                ydl.download([video_url])
                actual_title = "Unknown"
        
        elapsed = time.time() - start
        
        if os.path.exists(output_path):
            size = os.path.getsize(output_path) / (1024*1024)
            print(f"✅ Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
            return True, actual_title
        
        # Try different extensions
        base = os.path.splitext(output_path)[0]
        for ext in ['.mp4', '.mkv', '.webm', '.avi', '.flv', '.mov']:
            alt_file = base + ext
            if os.path.exists(alt_file):
                shutil.move(alt_file, output_path)
                size = os.path.getsize(output_path) / (1024*1024)
                print(f"✅ Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
                return True, actual_title
        
        return False, None
        
    except Exception as e:
        print(f"❌ Download error: {e}")
        return False, None

def download_movie_larooza(video_url, output_path):
    """Download movie from Larooza"""
    try:
        # Extract video URL
        extracted_url, message = extract_larooza_video(video_url)
        
        if not extracted_url:
            return False, None
        
        print(f"✅ {message}")
        
        # Download using yt-dlp
        return download_with_ytdlp(extracted_url, output_path)
        
    except Exception as e:
        print(f"❌ Larooza download error: {e}")
        return False, None

# ===== COMPRESSION (SAME AS SERIES) =====
def compress_video_240p(input_file, output_file, crf=28):
    """Same compression as series"""
    if not os.path.exists(input_file):
        print(f"❌ File not found: {input_file}")
        return False
    
    original_size = os.path.getsize(input_file) / (1024 * 1024)
    print(f"🎬 Compressing to 240p...")
    print(f"📊 Original: {original_size:.1f}MB")
    print(f"⚙️ CRF: {crf} (same as series)")
    
    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-vf', 'scale=-2:240',
        '-c:v', 'libx264',
        '-crf', str(crf),
        '-preset', 'veryfast',
        '-c:a', 'aac',
        '-b:a', '64k',
        '-y',
        output_file
    ]
    
    try:
        start = time.time()
        print("⏳ Compression started...")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
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
            print(f"🎬 Quality: 240p (series settings)")
            return True
        else:
            print(f"\n❌ Compression failed")
            return False
    except Exception as e:
        print(f"\n❌ Compression error: {e}")
        return False

def create_thumbnail(input_file, thumbnail_path):
    """Same thumbnail as series"""
    try:
        print(f"🖼️ Creating thumbnail...")
        
        cmd = [
            'ffmpeg',
            '-i', input_file,
            '-ss', '00:00:10',
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

async def upload_video(file_path, caption, thumbnail_path=None):
    """Upload video to Telegram"""
    try:
        if not app or not os.path.exists(file_path):
            return False
        
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path) / (1024*1024)
        
        print(f"☁️ Uploading: {filename}")
        print(f"📊 Size: {file_size:.1f}MB")
        
        # Get video dimensions
        try:
            cmd = ['ffprobe', '-v', 'quiet', '-select_streams', 'v:0', 
                   '-show_entries', 'stream=width,height', '-of', 'csv=p=0', file_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                w, h = result.stdout.strip().split(',')
                width, height = int(w), int(h)
            else:
                width, height = 426, 240
        except:
            width, height = 426, 240
        
        # Get duration
        try:
            cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
                   '-of', 'default=noprint_wrappers=1:nokey=1', file_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            duration = int(float(result.stdout.strip())) if result.returncode == 0 else 0
        except:
            duration = 0
        
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
        
        try:
            await app.send_video(**upload_params)
            elapsed = time.time() - start_time
            print(f"\n✅ Uploaded in {elapsed:.1f}s")
            return True
            
        except FloodWait as e:
            print(f"\n⏳ Flood wait: {e.value}s")
            await asyncio.sleep(e.value)
            return await upload_video(file_path, caption, thumbnail_path)
            
        except Exception as e:
            print(f"\n❌ Upload error: {e}")
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
        # 1. Download
        print("📥 Downloading movie...")
        
        # Check if it's Larooza
        if 'larooza' in movie_url or 'larozavideo' in movie_url:
            download_success, actual_title = download_movie_larooza(movie_url, temp_file)
        else:
            # Use standard download
            download_success, actual_title = download_with_ytdlp(movie_url, temp_file)
        
        if not download_success:
            return False, "Download failed"
        
        if actual_title and actual_title != 'Unknown':
            movie_title = actual_title
        
        # 2. Create thumbnail
        print("🖼️ Creating thumbnail...")
        create_thumbnail(temp_file, thumbnail_file)
        
        # 3. Compress to 240p
        print("🎬 Compressing to 240p...")
        if not compress_video_240p(temp_file, final_file, crf=28):
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
    print("="*50)
    print("🎬 Movie Uploader - Larooza Special")
    print("="*50)
    print("⚙️ Same settings as series: 240p, CRF 28")
    print("📝 Caption: Title only (no year)")
    
    # Check dependencies
    print("\n🔍 Checking dependencies...")
    
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
                    "url": "https://q.larozavideo.net/play.php?vid=956c7e520",
                    "title": "x مراتي"
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
        success, message = await process_movie(movie_url, movie_title, download_dir)
        
        elapsed = time.time() - start_time
        
        if success:
            successful += 1
            print(f"✅ {movie_title}: {message}")
            print(f"   ⏱️ Time: {elapsed:.1f}s")
        else:
            failed.append(movie_title)
            print(f"❌ {movie_title}: {message}")
        
        # Wait between movies
        if index < len(movies):
            wait_time = 3
            print(f"⏳ Waiting {wait_time} seconds...")
            await asyncio.sleep(wait_time)
    
    # Results
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
        print("\n💡 Possible solutions:")
        print("1. Try a different movie URL")
        print("2. The site might be blocking GitHub Actions")
        print("3. Try running locally on your computer")
        print("4. Use a VPN or proxy service")
    
    # Cleanup
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
