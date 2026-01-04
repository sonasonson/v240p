#!/usr/bin/env python3
"""
Universal Video Uploader - Works with Any Video Site
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
from urllib.parse import urlparse, parse_qs, urljoin

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
from pyrogram.errors import FloodWait, AuthKeyUnregistered
import yt_dlp
from bs4 import BeautifulSoup

app = None
scraper = None

# ===== CLOUDSCRAPER SETUP =====
def setup_scraper():
    """Setup cloudscraper to bypass protection"""
    global scraper
    print("🛡️ Setting up CloudScraper...")
    try:
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            },
            delay=10
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
            name="universal_uploader",
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

# ===== UNIVERSAL VIDEO EXTRACTION =====
def extract_video_url_advanced(page_url):
    """Extract video URL from any site using multiple methods"""
    try:
        print(f"🔍 Analyzing: {page_url}")
        parsed_url = urlparse(page_url)
        base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        # Method 1: Try yt-dlp first (works for most sites)
        print("🔄 Method 1: Trying yt-dlp...")
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'force_generic_extractor': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(page_url, download=False)
                if info and 'url' in info:
                    video_url = info['url']
                    print(f"✅ yt-dlp found URL: {video_url[:100]}...")
                    return video_url, "yt-dlp extraction"
        except:
            pass
        
        # Method 2: Use cloudscraper to fetch page
        print("🔄 Method 2: Using cloudscraper...")
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
            }
            
            if scraper:
                response = scraper.get(page_url, headers=headers, timeout=30)
            else:
                response = requests.get(page_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                content = response.text
                soup = BeautifulSoup(content, 'html.parser')
                
                # Look for video elements
                video_tags = soup.find_all(['video', 'iframe', 'embed', 'source'])
                
                for tag in video_tags:
                    src = None
                    if tag.name == 'video':
                        src = tag.get('src') or tag.find('source', {'src': True})
                        if src and hasattr(src, 'get'):
                            src = src.get('src')
                    elif tag.name == 'iframe':
                        src = tag.get('src')
                    elif tag.name == 'embed':
                        src = tag.get('src')
                    elif tag.name == 'source':
                        src = tag.get('src')
                    
                    if src:
                        # Make URL absolute
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif src.startswith('/'):
                            src = base_domain + src
                        elif not src.startswith('http'):
                            src = urljoin(base_domain, src)
                        
                        # Check if it's a video URL
                        if any(ext in src.lower() for ext in ['.mp4', '.m3u8', '.mkv', '.webm', '.avi', '.flv']):
                            print(f"✅ Found video URL in HTML: {src[:100]}...")
                            return src, "HTML extraction"
                
                # Look for video URLs in scripts
                scripts = soup.find_all('script', {'src': False})
                for script in scripts:
                    if script.string:
                        # Common video player patterns
                        patterns = [
                            r'["\'](https?://[^"\']+\.(?:mp4|m3u8|mkv|webm)[^"\']*)["\']',
                            r'file["\']?\s*:\s*["\']([^"\']+)["\']',
                            r'src["\']?\s*:\s*["\']([^"\']+)["\']',
                            r'video["\']?\s*:\s*["\']([^"\']+)["\']',
                            r'url["\']?\s*:\s*["\']([^"\']+)["\']',
                            r'source["\']?\s*:\s*["\']([^"\']+)["\']',
                            r'jwplayer\([^)]+\)\.setup\(({[^}]+})',
                            r'videojs\([^)]+\)\.src\(["\']([^"\']+)["\']',
                        ]
                        
                        for pattern in patterns:
                            matches = re.findall(pattern, script.string, re.IGNORECASE | re.DOTALL)
                            for match in matches:
                                if isinstance(match, str):
                                    video_url = match
                                    # Extract URL from JSON if needed
                                    if '{' in video_url:
                                        url_match = re.search(r'["\']file["\']?\s*:\s*["\']([^"\']+)["\']', video_url)
                                        if url_match:
                                            video_url = url_match.group(1)
                                    
                                    if video_url and any(ext in video_url.lower() for ext in ['.mp4', '.m3u8', '.mkv']):
                                        # Make URL absolute
                                        if video_url.startswith('//'):
                                            video_url = 'https:' + video_url
                                        elif video_url.startswith('/'):
                                            video_url = base_domain + video_url
                                        elif not video_url.startswith('http'):
                                            video_url = urljoin(base_domain, video_url)
                                        
                                        print(f"✅ Found video URL in script: {video_url[:100]}...")
                                        return video_url, "Script extraction"
        except Exception as e:
            print(f"⚠️ Cloudscraper method failed: {e}")
        
        # Method 3: Try common video hosting patterns
        print("🔄 Method 3: Trying common patterns...")
        common_patterns = [
            # Larooza pattern
            r'https?://[^/]+/hls2/\d+/\d+/[^/]+/master\.m3u8',
            # Okprime pattern
            r'https?://[^/]+/embed-[^/]+\.html',
            # Generic video patterns
            r'https?://[^/]+/videos?/[^"\']+\.(?:mp4|m3u8)',
            r'https?://[^/]+/stream/[^"\']+\.m3u8',
            r'https?://[^/]+/movie/[^"\']+',
        ]
        
        for pattern in common_patterns:
            if re.search(pattern, page_url):
                print(f"✅ Matched known pattern: {pattern}")
                return page_url, "Pattern matched"
        
        # Method 4: Try iframe extraction
        print("🔄 Method 4: Looking for iframes...")
        try:
            iframe_patterns = [
                r'<iframe[^>]+src=["\']([^"\']+)["\']',
                r'src=["\']([^"\']+embed[^"\']+)["\']',
                r'<embed[^>]+src=["\']([^"\']+)["\']',
            ]
            
            for pattern in iframe_patterns:
                matches = re.findall(pattern, content if 'content' in locals() else '', re.IGNORECASE)
                for iframe_url in matches:
                    if iframe_url and not iframe_url.startswith('javascript:'):
                        # Make URL absolute
                        if iframe_url.startswith('//'):
                            iframe_url = 'https:' + iframe_url
                        elif iframe_url.startswith('/'):
                            iframe_url = base_domain + iframe_url
                        elif not iframe_url.startswith('http'):
                            iframe_url = urljoin(base_domain, iframe_url)
                        
                        print(f"✅ Found iframe: {iframe_url[:100]}...")
                        # Recursively extract from iframe
                        nested_url, method = extract_video_url_advanced(iframe_url)
                        if nested_url:
                            return nested_url, f"Iframe -> {method}"
        except:
            pass
        
        # Method 5: Last resort - return original URL for yt-dlp to handle
        print("⚠️ No direct URL found, using original URL")
        return page_url, "Using original URL (yt-dlp will handle)"
        
    except Exception as e:
        print(f"❌ Extraction error: {e}")
        return None, str(e)

def download_video_universal(video_url, output_path):
    """Download video using multiple methods"""
    try:
        print(f"🔗 Processing URL: {video_url[:100]}...")
        
        # First extract the best video URL
        extracted_url, method = extract_video_url_advanced(video_url)
        
        if not extracted_url:
            return False, None, "Failed to extract video URL"
        
        print(f"✅ {method}")
        print(f"📥 Downloading from: {extracted_url[:100]}...")
        
        # Configure yt-dlp for universal download
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
                'Referer': video_url,
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
            'ignoreerrors': True,
            'no_check_certificate': True,
            'extract_flat': False,
            'force_generic_extractor': True,
        }
        
        start = time.time()
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(extracted_url, download=False)
                if info:
                    title = info.get('title', 'Unknown')
                    duration = info.get('duration', 0)
                    print(f"📝 Title: {title}")
                    
                    if duration > 0:
                        hours = duration // 3600
                        minutes = (duration % 3600) // 60
                        seconds = duration % 60
                        if hours > 0:
                            print(f"⏱️ Duration: {hours}:{minutes:02d}:{seconds:02d}")
                        else:
                            print(f"⏱️ Duration: {minutes}:{seconds:02d}")
                    
                    # Download
                    print("⬇️ Starting download...")
                    ydl.download([extracted_url])
                    actual_title = title
                else:
                    ydl.download([extracted_url])
                    actual_title = "Unknown"
        except Exception as e:
            print(f"⚠️ Download error: {e}")
            # Try without info extraction
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([extracted_url])
                actual_title = "Unknown"
            except:
                return False, None, f"Download failed: {e}"
        
        elapsed = time.time() - start
        
        # Check if file exists
        if os.path.exists(output_path):
            size = os.path.getsize(output_path) / (1024*1024)
            print(f"✅ Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
            return True, actual_title, "Download successful"
        
        # Try different extensions
        base = os.path.splitext(output_path)[0]
        for ext in ['.mp4', '.mkv', '.webm', '.avi', '.flv', '.mov', '.m4v', '.ts']:
            alt_file = base + ext
            if os.path.exists(alt_file):
                shutil.move(alt_file, output_path)
                size = os.path.getsize(output_path) / (1024*1024)
                print(f"✅ Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
                return True, actual_title, "Download successful"
        
        return False, None, "No file was created"
        
    except Exception as e:
        print(f"❌ Universal download error: {e}")
        return False, None, str(e)

# ===== COMPRESSION (240P - SAME AS SERIES) =====
def compress_video_240p(input_file, output_file):
    """Compress video to 240p with CRF 28 (same as series)"""
    if not os.path.exists(input_file):
        print(f"❌ File not found: {input_file}")
        return False
    
    original_size = os.path.getsize(input_file) / (1024 * 1024)
    print(f"🎬 Compressing to 240p...")
    print(f"📊 Original: {original_size:.1f}MB")
    print(f"⚙️ CRF: 28 (same as series settings)")
    
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
    """Create thumbnail from video"""
    try:
        print(f"🖼️ Creating thumbnail...")
        
        cmd = [
            'ffmpeg',
            '-i', input_file,
            '-ss', '00:05:00',
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
            if percent - last_percent >= 2 or percent == 100:
                speed = current / (time.time() - start_time) / 1024 if (time.time() - start_time) > 0 else 0
                print(f"📤 Upload: {percent:.1f}% ({speed:.0f}KB/s)", end='\r')
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

async def process_video(video_url, video_title, download_dir):
    """Process a single video"""
    print(f"\n{'─'*50}")
    print(f"🎬 Video: {video_title}")
    print(f"{'─'*50}")
    
    safe_title = re.sub(r'[^\w\-_\. ]', '_', video_title)[:50]
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
        # 1. Download video (universal method)
        print("📥 Downloading video...")
        download_success, actual_title, message = download_video_universal(video_url, temp_file)
        
        if not download_success:
            return False, f"Download failed: {message}"
        
        # Update title if we got a better one
        if actual_title and actual_title != 'Unknown':
            video_title = actual_title
        
        # 2. Create thumbnail
        print("🖼️ Creating thumbnail...")
        create_thumbnail(temp_file, thumbnail_file)
        
        # 3. Compress to 240p (same as series)
        print("🎬 Compressing to 240p...")
        if not compress_video_240p(temp_file, final_file):
            print("⚠️ Compression failed, using original")
            shutil.copy2(temp_file, final_file)
        
        # 4. Upload to Telegram
        caption = f"🎬 {video_title}"  # Title only, no year
        thumb = thumbnail_file if os.path.exists(thumbnail_file) else None
        
        if await upload_video(final_file, caption, thumb):
            # 5. Clean up files
            for file_path in [temp_file, final_file, thumbnail_file]:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        print(f"🗑️ Deleted: {os.path.basename(file_path)}")
                    except:
                        pass
            return True, "✅ Video uploaded and cleaned"
        else:
            return False, "❌ Upload failed"
        
    except Exception as e:
        print(f"❌ Processing error: {e}")
        return False, str(e)

# ===== MAIN FUNCTION =====
async def main():
    print("="*50)
    print("🎬 Universal Video Uploader")
    print("="*50)
    print("⚙️ Same settings as series: 240p, CRF 28")
    print("📝 Caption: Title only (no year)")
    print("🌐 Works with any video site")
    
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
    config_file = "video_config.json"
    if not os.path.exists(config_file):
        print(f"❌ Config file not found: {config_file}")
        print("💡 Creating sample config...")
        
        sample_config = {
            "videos": [
                {
                    "url": "https://q.larozavideo.net/play.php?vid=956c7e520",
                    "title": "x مراتي"
                },
                {
                    "url": "https://www.youtube.com/watch?v=EXAMPLE",
                    "title": "YouTube Video"
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
    
    videos = config.get("videos", [])
    
    if not videos:
        print("❌ No videos found in configuration")
        return
    
    print(f"📋 Found {len(videos)} video(s) to process")
    
    # Create working directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    download_dir = f"videos_{timestamp}"
    os.makedirs(download_dir, exist_ok=True)
    
    print(f"\n{'='*50}")
    print("🚀 Starting Video Processing")
    print('='*50)
    print(f"⚙️ Quality: 240p (same as series)")
    print(f"📁 Working dir: {download_dir}")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Process videos
    successful = 0
    failed = []
    
    for index, video in enumerate(videos, 1):
        video_url = video.get("url", "").strip()
        video_title = video.get("title", "").strip()
        
        if not video_url:
            print(f"❌ Video {index}: No URL provided")
            failed.append(f"Video {index}: No URL")
            continue
        
        if not video_title:
            video_title = f"Video {index}"
        
        print(f"\n[#{index}] 🎬 {video_title}")
        print(f"   🔗 URL: {video_url[:80]}...")
        
        start_time = time.time()
        success, message = await process_video(video_url, video_title, download_dir)
        
        elapsed = time.time() - start_time
        
        if success:
            successful += 1
            print(f"✅ {video_title}: {message}")
            print(f"   ⏱️ Total time: {elapsed:.1f}s")
            print(f"   🎬 Quality: 240p (series settings)")
        else:
            failed.append(video_title)
            print(f"❌ {video_title}: {message}")
        
        # Wait between videos
        if index < len(videos):
            wait_time = 5
            print(f"⏳ Waiting {wait_time} seconds...")
            await asyncio.sleep(wait_time)
    
    # Results summary
    print(f"\n{'='*50}")
    print("📊 Processing Summary")
    print('='*50)
    print(f"✅ Successful: {successful}/{len(videos)}")
    print(f"❌ Failed: {len(failed)}")
    
    if successful == len(videos):
        print("🎉 All videos processed successfully!")
    elif successful > 0:
        print(f"⚠️ Partially successful ({successful}/{len(videos)})")
    else:
        print("💥 All videos failed!")
    
    if failed:
        print(f"📝 Failed videos: {failed}")
        print("\n💡 Possible solutions:")
        print("   1. Try a different video URL")
        print("   2. Check if video is accessible")
        print("   3. Site might block automated downloads")
        print("   4. Try running locally")
    
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
