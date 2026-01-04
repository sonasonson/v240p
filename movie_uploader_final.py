#!/usr/bin/env python3
"""
Telegram Movie Uploader - Same as Series Method
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
import random
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

# Rotating User Agents to avoid blocking
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Edge/120.0.0.0",
]

def get_random_headers(referer=None):
    """Get random headers to avoid blocking"""
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-User': '?1',
    }
    
    if referer:
        headers['Referer'] = referer
    else:
        headers['Referer'] = 'https://www.google.com/'
    
    return headers

# ===== IMPORTS =====
def install_requirements():
    print("📦 Installing requirements...")
    
    requirements = [
        "pyrogram>=2.0.0",
        "tgcrypto>=1.2.0",
        "yt-dlp>=2024.4.9",
        "requests>=2.31.0",
        "brotli",
        "cloudscraper",
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
import cloudscraper

app = None
scraper = None

# ===== CLOUDSCRAPER SETUP =====
def setup_scraper():
    """Setup cloudscraper to bypass CloudFlare"""
    global scraper
    print("🛡️ Setting up CloudScraper...")
    try:
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            }
        )
        print("✅ CloudScraper ready")
        return True
    except Exception as e:
        print(f"❌ CloudScraper error: {e}")
        return False

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

# ===== VIDEO URL EXTRACTION =====
def extract_movie_url(page_url):
    """Extract movie URL using same method as series"""
    try:
        print(f"🔍 Extracting from: {page_url}")
        
        # Parse URL to get base domain
        parsed = urlparse(page_url)
        base_domain = f"{parsed.scheme}://{parsed.netloc}"
        
        # Get video ID from URL
        query_params = parse_qs(parsed.query)
        vid = query_params.get('vid', [None])[0]
        
        if not vid:
            print("❌ No video ID found in URL")
            return None, "No video ID"
        
        print(f"📹 Video ID: {vid}")
        
        # Try different patterns for direct video URL
        patterns = [
            f"{base_domain}/videos/{vid}.mp4",
            f"{base_domain}/v/{vid}.mp4",
            f"{base_domain}/video/{vid}.mp4",
            f"{base_domain}/files/{vid}.mp4",
            f"{base_domain}/stream/{vid}.m3u8",
            f"{base_domain}/hls/{vid}.m3u8",
            f"{base_domain}/{vid}.mp4",
        ]
        
        # Try to fetch the page first
        try:
            headers = get_random_headers(referer=base_domain)
            response = requests.get(page_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                content = response.text
                
                # Look for video sources in the page
                video_patterns = [
                    r'src=["\']([^"\']+\.mp4[^"\']*)["\']',
                    r'file["\']?\s*:\s*["\']([^"\']+\.mp4[^"\']*)["\']',
                    r'video["\']?\s*:\s*["\']([^"\']+\.mp4[^"\']*)["\']',
                    r'videoSrc["\']?\s*:\s*["\']([^"\']+\.mp4[^"\']*)["\']',
                    r'source["\']?\s*:\s*["\']([^"\']+\.mp4[^"\']*)["\']',
                    r'data-video=["\']([^"\']+)["\']',
                ]
                
                for pattern in video_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches:
                        if isinstance(match, tuple):
                            video_url = match[0] if len(match) > 0 else None
                        else:
                            video_url = match
                        
                        if video_url:
                            # Make URL absolute
                            if video_url.startswith('//'):
                                video_url = 'https:' + video_url
                            elif video_url.startswith('/'):
                                video_url = base_domain + video_url
                            elif not video_url.startswith('http'):
                                video_url = base_domain + '/' + video_url
                            
                            print(f"✅ Found video URL in page: {video_url[:80]}...")
                            return video_url, "Found in page"
        except Exception as e:
            print(f"⚠️ Page fetch failed: {e}")
        
        # Try direct patterns
        for pattern in patterns:
            try:
                headers = get_random_headers(referer=base_domain)
                response = requests.head(pattern, headers=headers, timeout=10, allow_redirects=True)
                
                if response.status_code in [200, 302, 307]:
                    print(f"✅ Found direct URL: {pattern}")
                    return pattern, "Direct URL found"
            except:
                continue
        
        # Try with CloudScraper if available
        if scraper:
            try:
                print("🛡️ Trying CloudScraper...")
                response = scraper.get(page_url, timeout=30)
                if response.status_code == 200:
                    content = response.text
                    
                    # Look for m3u8 or mpd files
                    m3u8_patterns = [
                        r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']',
                        r'["\'](https?://[^"\']+\.mpd[^"\']*)["\']',
                        r'hlsManifestUrl["\']?\s*:\s*["\']([^"\']+)["\']',
                        r'dashManifestUrl["\']?\s*:\s*["\']([^"\']+)["\']',
                    ]
                    
                    for pattern in m3u8_patterns:
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        for match in matches:
                            if match:
                                print(f"✅ Found streaming URL: {match[:80]}...")
                                return match, "Streaming URL found"
            except Exception as e:
                print(f"❌ CloudScraper failed: {e}")
        
        return None, "Could not extract video URL"
        
    except Exception as e:
        print(f"❌ Extraction error: {e}")
        return None, str(e)

def download_movie(video_url, output_path):
    """Download movie with improved method"""
    try:
        # First extract direct URL
        direct_url, message = extract_movie_url(video_url)
        
        if not direct_url:
            print("❌ Could not extract direct URL")
            return False, None
        
        print(f"✅ {message}")
        print(f"🔗 Using URL: {direct_url[:80]}...")
        
        # Configure yt-dlp with better settings
        ydl_opts = {
            'format': 'best[height<=720]/best',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'user_agent': random.choice(USER_AGENTS),
            'referer': video_url,
            'http_headers': get_random_headers(referer=video_url),
            'retries': 30,
            'fragment_retries': 30,
            'skip_unavailable_fragments': True,
            'socket_timeout': 60,
            'extractor_args': {
                'generic': {
                    'headers': get_random_headers()
                }
            },
            'concurrent_fragment_downloads': 8,
            'continuedl': True,
            'noprogress': True,
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            'extract_flat': False,
            'ignoreerrors': True,
            'no_check_certificate': True,
            'sleep_interval': 1,
            'max_sleep_interval': 5,
            'windows_filenames': True,
        }
        
        print("📥 Downloading movie...")
        start = time.time()
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(direct_url, download=False)
                if info:
                    title = info.get('title', 'Unknown')
                    duration = info.get('duration', 0)
                    print(f"📝 Title: {title}")
                    if duration > 0:
                        mins = duration // 60
                        secs = duration % 60
                        print(f"⏱️ Duration: {mins}:{secs:02d}")
                    
                    # Download
                    ydl.download([direct_url])
                    actual_title = title
                else:
                    ydl.download([direct_url])
                    actual_title = "Unknown"
        except:
            # Direct download if extraction fails
            print("⚠️ Info extraction failed, direct download...")
            ydl_opts['quiet'] = False
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([direct_url])
            actual_title = "Unknown"
        
        elapsed = time.time() - start
        
        # Check if file exists
        if os.path.exists(output_path):
            size = os.path.getsize(output_path) / (1024*1024)
            print(f"✅ Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
            return True, actual_title
        
        # Try different extensions
        base = os.path.splitext(output_path)[0]
        for ext in ['.mp4', '.mkv', '.webm', '.avi', '.flv', '.mov', '.m4v']:
            alt_file = base + ext
            if os.path.exists(alt_file):
                shutil.move(alt_file, output_path)
                size = os.path.getsize(output_path) / (1024*1024)
                print(f"✅ Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
                return True, actual_title
        
        return False, None
        
    except Exception as e:
        print(f"❌ Download error: {e}")
        
        # Alternative: Try direct download with requests if it's a direct link
        if direct_url and (direct_url.endswith('.mp4') or '.m3u8' in direct_url):
            print("🔄 Trying alternative download method...")
            return download_direct(direct_url, output_path)
        
        return False, None

def download_direct(video_url, output_path):
    """Direct download for .mp4 or .m3u8"""
    try:
        print("🔄 Direct download...")
        headers = get_random_headers(referer=video_url)
        
        if '.m3u8' in video_url:
            # Use yt-dlp for m3u8
            ydl_opts = {
                'format': 'best',
                'outtmpl': output_path,
                'quiet': False,
                'http_headers': headers,
                'retries': 20,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
        else:
            # Direct download for mp4
            response = requests.get(video_url, headers=headers, stream=True, timeout=60)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(f"⬇️ {percent:.1f}%", end='\r')
            
            print(f"\n✅ Direct download complete")
        
        if os.path.exists(output_path):
            size = os.path.getsize(output_path) / (1024*1024)
            print(f"📊 Size: {size:.1f}MB")
            return True, "Movie"
        
        return False, None
    except Exception as e:
        print(f"❌ Direct download failed: {e}")
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
        
        # Get video info
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
        download_success, actual_title = download_movie(movie_url, temp_file)
        
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
    print("🎬 Movie Uploader - Fixed Version")
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
    
    # Setup CloudScraper
    setup_scraper()
    
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
            wait_time = 5
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
        print("\n💡 Solutions for 403 error:")
        print("1. Try a different video source")
        print("2. Use direct .mp4 or .m3u8 links")
        print("3. The site may block GitHub IPs")
        print("4. Try another movie URL")
    
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
