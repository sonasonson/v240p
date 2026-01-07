#!/usr/bin/env python3
"""
Telegram Movie Downloader & Uploader - Enhanced Version
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

# Improved headers to bypass 403 errors
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
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
from pyrogram.errors import FloodWait
import yt_dlp
import cloudscraper
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

# ===== VIDEO EXTRACTION WITH CLOUDSCRAPER =====
def extract_video_url(watch_url):
    """Extract video URL using cloudscraper to bypass protection"""
    print(f"🔗 Extracting video from: {watch_url}")
    
    # Initialize cloudscraper
    scraper = cloudscraper.create_scraper()
    
    # Method 1: Try to find direct video URL with cloudscraper
    print("🔄 Method 1: Using cloudscraper to bypass protection...")
    try:
        # Get the page content
        response = scraper.get(watch_url, headers=HEADERS, timeout=30)
        
        if response.status_code != 200:
            print(f"⚠️ HTTP {response.status_code} from cloudscraper")
        else:
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for video sources
            video_sources = []
            
            # Check video tags
            for video in soup.find_all('video'):
                src = video.get('src')
                if src:
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        parsed = urlparse(watch_url)
                        src = f'{parsed.scheme}://{parsed.netloc}{src}'
                    video_sources.append(src)
                    print(f"🎬 Found video src: {src[:100]}...")
                
                # Check source tags inside video
                for source in video.find_all('source'):
                    src = source.get('src')
                    if src:
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif src.startswith('/'):
                            parsed = urlparse(watch_url)
                            src = f'{parsed.scheme}://{parsed.netloc}{src}'
                        video_sources.append(src)
                        print(f"🎬 Found source src: {src[:100]}...")
            
            # Check for iframes
            for iframe in soup.find_all('iframe'):
                src = iframe.get('src')
                if src and ('video' in src.lower() or 'embed' in src.lower()):
                    print(f"📺 Found iframe: {src}")
                    # Try to follow iframe
                    try:
                        iframe_response = scraper.get(src, headers=HEADERS, timeout=15)
                        iframe_soup = BeautifulSoup(iframe_response.text, 'html.parser')
                        
                        # Look for video in iframe
                        for iframe_video in iframe_soup.find_all('video'):
                            iframe_src = iframe_video.get('src')
                            if iframe_src:
                                video_sources.append(iframe_src)
                                print(f"🎬 Found video in iframe: {iframe_src[:100]}...")
                    except:
                        pass
            
            # Check for JavaScript variables with video URLs
            script_patterns = [
                r'file["\']?\s*[:=]\s*["\']([^"\']+\.mp4[^"\']*)["\']',
                r'src["\']?\s*[:=]\s*["\']([^"\']+\.mp4[^"\']*)["\']',
                r'video["\']?\s*[:=]\s*["\']([^"\']+\.mp4[^"\']*)["\']',
                r'url["\']?\s*[:=]\s*["\']([^"\']+\.mp4[^"\']*)["\']',
                r'"(https?://[^"]+\.m3u8[^"]*)"',
            ]
            
            for script in soup.find_all('script'):
                if script.string:
                    for pattern in script_patterns:
                        matches = re.findall(pattern, script.string, re.IGNORECASE)
                        for url in matches:
                            url = url.replace('\\/', '/')
                            if url.startswith('http'):
                                video_sources.append(url)
                                print(f"🎬 Found URL in script: {url[:100]}...")
                            elif url.startswith('//'):
                                video_sources.append('https:' + url)
                                print(f"🎬 Found URL in script: https:{url[:100]}...")
            
            # Filter unique sources
            unique_sources = []
            for src in video_sources:
                if src and src not in unique_sources:
                    unique_sources.append(src)
            
            if unique_sources:
                # Return the best source (prefer mp4)
                for src in unique_sources:
                    if '.mp4' in src.lower():
                        return src, "✅ Found MP4 URL via cloudscraper"
                return unique_sources[0], "✅ Found video URL via cloudscraper"
    except Exception as e:
        print(f"⚠️ Cloudscraper method failed: {e}")
    
    # Method 2: Try yt-dlp with cloudscraper cookies
    print("🔄 Method 2: Trying yt-dlp with custom settings...")
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'user_agent': USER_AGENT,
            'referer': watch_url,
            'http_headers': HEADERS,
            'extractor_args': {
                'generic': {'player_skip': ['all']}
            }
        }
        
        # Try to use cookies from cloudscraper
        try:
            session = scraper
            # Try to get cookies
            if hasattr(session, 'cookies'):
                ydl_opts['cookiefile'] = 'cookies.txt'
                # Save cookies temporarily
                import http.cookiejar
                jar = http.cookiejar.MozillaCookieJar('cookies.txt')
                for cookie in session.cookies:
                    jar.set_cookie(cookie)
                jar.save()
        except:
            pass
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(watch_url, download=False)
            
            if 'url' in info:
                return info['url'], "✅ URL extracted via yt-dlp"
            
            if 'formats' in info:
                formats = info['formats']
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
    
    # Method 3: Try alternative approach for specific sites
    print("🔄 Method 3: Trying alternative approach...")
    try:
        # For embed sites, try to find the actual video file
        if 'embed' in watch_url.lower():
            # Try to extract video ID and construct direct URL
            patterns = [
                r'embed-([a-zA-Z0-9]+)',
                r'embed/([a-zA-Z0-9]+)',
                r'e/([a-zA-Z0-9]+)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, watch_url)
                if match:
                    video_id = match.group(1)
                    # Try common video hosting patterns
                    possible_urls = [
                        f"https://{urlparse(watch_url).netloc.replace('embed', 'video')}/{video_id}.mp4",
                        f"https://{urlparse(watch_url).netloc}/videos/{video_id}.mp4",
                        f"https://{urlparse(watch_url).netloc}/files/{video_id}.mp4",
                    ]
                    
                    for test_url in possible_urls:
                        try:
                            response = scraper.head(test_url, headers=HEADERS, timeout=10)
                            if response.status_code == 200:
                                return test_url, "✅ Found direct video URL"
                        except:
                            pass
    except Exception as e:
        print(f"⚠️ Alternative approach failed: {e}")
    
    return None, "❌ Could not extract video URL"

def download_video(url, output_path):
    """Download video using yt-dlp with improved settings"""
    try:
        ydl_opts = {
            'format': 'best[height<=720]/best',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'user_agent': USER_AGENT,
            'referer': url,
            'http_headers': HEADERS,
            'retries': 10,
            'fragment_retries': 10,
            'skip_unavailable_fragments': True,
            'socket_timeout': 30,
            'concurrent_fragment_downloads': 3,
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
        
        # Try direct download as fallback
        print("🔄 Trying direct download with cloudscraper...")
        try:
            scraper = cloudscraper.create_scraper()
            response = scraper.get(url, headers=HEADERS, stream=True, timeout=60)
            
            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    start = time.time()
                    
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                    
                elapsed = time.time() - start
                
                if os.path.exists(output_path):
                    size = os.path.getsize(output_path) / (1024*1024)
                    print(f"✅ Direct download completed in {elapsed:.1f}s ({size:.1f}MB)")
                    return True
        except Exception as e2:
            print(f"❌ Direct download failed: {e2}")
        
        return False

# باقي الدوال تبقى كما هي مع تعديلات بسيطة
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
    print("🎬 Telegram Movie Uploader (Enhanced)")
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
