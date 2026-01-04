#!/usr/bin/env python3
"""
Universal Video Downloader & Uploader - Complete Version
Works with any video website
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
    elif len(STRING_SESSION) < 200:
        errors.append(f"❌ STRING_SESSION seems too short ({len(STRING_SESSION)} chars)")
    
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
        "beautifulsoup4>=4.12.0",
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
from pyrogram.errors import FloodWait, AuthKeyUnregistered, SessionPasswordNeeded
import yt_dlp
from bs4 import BeautifulSoup

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
    print(f"🔗 Session length: {len(STRING_SESSION)} characters")
    
    try:
        cleaned_session = STRING_SESSION.strip()
        
        print(f"🔧 Creating client with cleaned session ({len(cleaned_session)} chars)...")
        
        app = Client(
            name="github_uploader",
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
        print(f"📞 Phone: {me.phone_number}")
        
        # التحقق من القناة
        try:
            chat = await app.get_chat(TELEGRAM_CHANNEL)
            print(f"📢 Channel found: {chat.title}")
            
            try:
                member = await app.get_chat_member(TELEGRAM_CHANNEL, me.id)
                print(f"👤 Role: {member.status}")
                
                if hasattr(member.status, 'value'):
                    role = member.status.value
                else:
                    role = str(member.status)
                
                if role not in ["creator", "administrator", "member", "owner"]:
                    print("⚠️ Warning: You may not have upload permissions")
                    
            except:
                print("⚠️ Warning: Cannot check channel permissions")
                
            return True
            
        except Exception as e:
            print(f"❌ Cannot access channel: {e}")
            print("⚠️ Make sure:")
            print("  1. The channel exists")
            print("  2. Your account is a member")
            print("  3. You have permission to send messages")
            return False
            
    except AuthKeyUnregistered:
        print("❌ STRING_SESSION is invalid or expired")
        print("💡 Generate a new one with:")
        print("   python generate_session.py")
        return False
        
    except SessionPasswordNeeded:
        print("❌ Account has 2FA enabled")
        print("💡 Disable 2FA or use a different account")
        return False
        
    except Exception as e:
        print(f"❌ Connection failed: {type(e).__name__}")
        print(f"📝 Error details: {str(e)[:100]}")
        
        print("\n🔧 Troubleshooting tips:")
        print("1. Check STRING_SESSION length (should be ~350 chars)")
        print("2. Regenerate session with generate_session.py")
        print("3. Verify API_ID and API_HASH")
        print("4. Check if account is banned")
        return False

# ===== VIDEO PROCESSING FUNCTIONS =====

def extract_video_url(video_page_url):
    """Extract video URL from any website using multiple methods"""
    try:
        parsed_url = urlparse(video_page_url)
        domain = parsed_url.netloc
        
        print(f"🌐 Extracting from: {domain}")
        
        # Method 1: Try yt-dlp first (supports 1000+ sites)
        print("🔍 Trying yt-dlp extraction...")
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_page_url, download=False)
                
                if info:
                    # Try to get the best quality URL
                    if 'url' in info:
                        video_url = info['url']
                        print(f"✅ Found direct URL via yt-dlp")
                        return video_url, "✅ URL extracted via yt-dlp"
                    
                    # Check for formats
                    elif 'formats' in info:
                        formats = info['formats']
                        if formats:
                            # Prefer formats with both video and audio
                            best_format = None
                            for fmt in formats:
                                if fmt.get('vcodec') != 'none' and fmt.get('acodec') != 'none':
                                    best_format = fmt
                                    break
                            
                            if best_format:
                                video_url = best_format['url']
                                print(f"✅ Found format via yt-dlp")
                                return video_url, "✅ URL extracted via yt-dlp"
                            else:
                                # Fallback to first format
                                video_url = formats[0]['url']
                                print(f"✅ Found format via yt-dlp")
                                return video_url, "✅ URL extracted via yt-dlp"
        except Exception as e:
            print(f"⚠️ yt-dlp extraction failed: {e}")
        
        # Method 2: Try to find iframe/video sources in HTML
        print("🔍 Trying HTML extraction...")
        try:
            headers = HEADERS.copy()
            headers['Referer'] = f'https://{domain}/'
            
            response = requests.get(video_page_url, headers=headers, timeout=30)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for video tags
                video_tags = soup.find_all(['video', 'iframe', 'source'])
                
                for tag in video_tags:
                    src = None
                    
                    if tag.name == 'video':
                        # Check for src attribute
                        if tag.get('src'):
                            src = tag['src']
                        # Check for source tags inside video
                        elif tag.find('source'):
                            source_tag = tag.find('source')
                            if source_tag.get('src'):
                                src = source_tag['src']
                    
                    elif tag.name == 'iframe':
                        src = tag.get('src')
                    
                    elif tag.name == 'source':
                        src = tag.get('src')
                    
                    if src:
                        # Make absolute URL
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif src.startswith('/'):
                            src = f'https://{domain}' + src
                        elif not src.startswith('http'):
                            src = f'https://{domain}/{src}'
                        
                        print(f"✅ Found video source: {src[:100]}...")
                        return src, "✅ URL extracted from HTML"
                
                # Look for common video patterns in scripts
                script_patterns = [
                    r'["\'](https?://[^"\']+\.mp4[^"\']*)["\']',
                    r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']',
                    r'["\'](https?://[^"\']+\.webm[^"\']*)["\']',
                    r'src:\s*["\'](https?://[^"\']+\.mp4[^"\']*)["\']',
                    r'file:\s*["\'](https?://[^"\']+\.mp4[^"\']*)["\']',
                ]
                
                for pattern in script_patterns:
                    matches = re.findall(pattern, response.text)
                    if matches:
                        video_url = matches[0]
                        print(f"✅ Found video URL via pattern: {video_url[:100]}...")
                        return video_url, "✅ URL extracted from script"
        
        except Exception as e:
            print(f"⚠️ HTML extraction failed: {e}")
        
        # Method 3: For myvidplay.com specifically
        if 'myvidplay.com' in domain:
            print("🔍 Trying myvidplay.com specific extraction...")
            try:
                response = requests.get(video_page_url, headers=HEADERS, timeout=30)
                
                # Look for iframe
                iframe_match = re.search(r'<iframe[^>]+src="([^"]+)"', response.text)
                if iframe_match:
                    iframe_url = iframe_match.group(1)
                    
                    # Follow iframe
                    iframe_response = requests.get(iframe_url, headers=HEADERS, timeout=30)
                    
                    # Look for video source
                    video_match = re.search(r'"file":"([^"]+)"', iframe_response.text)
                    if video_match:
                        video_url = video_match.group(1).replace('\\/', '/')
                        print(f"✅ Found myvidplay video URL")
                        return video_url, "✅ URL extracted from myvidplay"
            
            except Exception as e:
                print(f"⚠️ myvidplay extraction failed: {e}")
        
        return None, "❌ Could not extract video URL"
        
    except requests.exceptions.Timeout:
        return None, "⏰ Timeout"
    except Exception as e:
        return None, f"❌ Error: {str(e)}"

def download_video(url, output_path):
    """Download video using yt-dlp with best quality"""
    try:
        ydl_opts = {
            'format': 'best[height<=1080]/best',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'user_agent': USER_AGENT,
            'http_headers': HEADERS,
            'retries': 10,
            'fragment_retries': 10,
            'skip_unavailable_fragments': True,
            'socket_timeout': 30,
            'noprogress': True,
        }
        
        print(f"📥 Downloading from: {url[:100]}...")
        start = time.time()
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        elapsed = time.time() - start
        
        if os.path.exists(output_path):
            size = os.path.getsize(output_path) / (1024*1024)
            print(f"✅ Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
            return True
        
        # Try different extensions
        base = os.path.splitext(output_path)[0]
        for ext in ['.mp4', '.mkv', '.webm', '.avi', '.flv', '.mov']:
            alt_file = base + ext
            if os.path.exists(alt_file):
                shutil.move(alt_file, output_path)
                size = os.path.getsize(output_path) / (1024*1024)
                print(f"✅ Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
                return True
        
        return False
        
    except Exception as e:
        print(f"❌ Download error: {e}")
        return False

def compress_video(input_file, output_file):
    """Compress video to 480p (good quality for movies)"""
    if not os.path.exists(input_file):
        print(f"❌ File not found: {input_file}")
        return False
    
    original_size = os.path.getsize(input_file) / (1024 * 1024)
    print(f"🎬 Compressing video...")
    print(f"📊 Original: {original_size:.1f}MB")
    
    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-vf', 'scale=-2:480',
        '-c:v', 'libx264',
        '-crf', '26',  # Lower CRF for better quality
        '-preset', 'fast',
        '-c:a', 'aac',
        '-b:a', '128k',  # Better audio for movies
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
            if result.stderr:
                print(f"Error: {result.stderr[:200]}")
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
            '-ss', '00:01:00',  # Middle of video for movies
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
        
        # Try earlier if middle doesn't work
        cmd[4] = '00:00:30'
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
    
    return 854, 480  # Default for 480p

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
            if percent - last_percent >= 10 or percent == 100:
                speed = current / (time.time() - start_time) / 1024 if (time.time() - start_time) > 0 else 0
                print(f"📤 {percent:.0f}% - {speed:.0f}KB/s")
                last_percent = percent
        
        upload_params['progress'] = progress
        
        # Upload
        try:
            await app.send_video(**upload_params)
            elapsed = time.time() - start_time
            print(f"✅ Uploaded in {elapsed:.1f}s")
            print(f"🎬 Streaming: Enabled")
            return True
            
        except FloodWait as e:
            print(f"⏳ Flood wait: {e.value}s")
            await asyncio.sleep(e.value)
            return await upload_video(file_path, caption, thumbnail_path)
            
        except Exception as e:
            print(f"❌ Upload error: {e}")
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

async def process_video(video_url, video_title, download_dir, index=1):
    """Process a single video"""
    print(f"\n{'─'*50}")
    print(f"🎬 Movie: {video_title}")
    print(f"{'─'*50}")
    
    temp_file = os.path.join(download_dir, f"temp_{index:02d}.mp4")
    final_file = os.path.join(download_dir, f"final_{index:02d}.mp4")
    thumbnail_file = os.path.join(download_dir, f"thumb_{index:02d}.jpg")
    
    # Clean old files
    for f in [temp_file, final_file, thumbnail_file]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except:
                pass
    
    try:
        # 1. Extract direct video URL
        print("🔍 Extracting video URL...")
        direct_video_url, message = extract_video_url(video_url)
        
        if not direct_video_url:
            return False, f"URL extraction failed: {message}"
        
        print(f"{message}")
        print(f"📎 Direct URL: {direct_video_url[:100]}...")
        
        # 2. Download
        print("📥 Downloading video...")
        if not download_video(direct_video_url, temp_file):
            # Try with the original URL if direct download fails
            print("🔄 Trying with original URL...")
            if not download_video(video_url, temp_file):
                return False, "Download failed"
        
        # 3. Create thumbnail
        print("🖼️ Creating thumbnail...")
        create_thumbnail(temp_file, thumbnail_file)
        
        # 4. Compress (optional, skip if file is already small)
        file_size_mb = os.path.getsize(temp_file) / (1024 * 1024)
        
        if file_size_mb > 100:  # Only compress if > 100MB
            print("🎬 Compressing video...")
            if not compress_video(temp_file, final_file):
                print("⚠️ Compression failed, using original")
                shutil.copy2(temp_file, final_file)
        else:
            print(f"📊 File size is small ({file_size_mb:.1f}MB), skipping compression")
            shutil.copy2(temp_file, final_file)
        
        # 5. Upload
        caption = video_title
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
            return True, "✅ Uploaded and cleaned"
        else:
            return False, "❌ Upload failed"
        
    except Exception as e:
        print(f"❌ Processing error: {e}")
        return False, str(e)

# ===== MAIN FUNCTION =====

async def main():
    """Main function"""
    print("="*50)
    print("🎬 Universal Video Processor v3.0")
    print("="*50)
    
    # Check dependencies
    print("\n🔍 Checking dependencies...")
    
    # Check ffmpeg
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ ffmpeg is installed")
            
            version_match = re.search(r'ffmpeg version (\S+)', result.stdout)
            if version_match:
                print(f"  Version: {version_match.group(1)}")
        else:
            print("❌ ffmpeg not found, installing...")
            subprocess.run(['sudo', 'apt-get', 'update', '-y'], capture_output=True)
            subprocess.run(['sudo', 'apt-get', 'install', '-y', 'ffmpeg'], capture_output=True)
            print("✅ ffmpeg installed")
    except:
        print("❌ Cannot check ffmpeg")
    
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
                    "url": "https://myvidplay.com/e/14skdyhzt904",
                    "title": "اسم الفيلم"
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
        print("❌ No videos found in config")
        return
    
    # Create working directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    download_dir = f"downloads_{timestamp}"
    os.makedirs(download_dir, exist_ok=True)
    
    print(f"\n{'='*50}")
    print("🚀 Starting Video Processing")
    print('='*50)
    print(f"🎬 Total videos: {len(videos)}")
    print(f"📁 Working dir: {download_dir}")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Process videos
    successful = 0
    failed = []
    total = len(videos)
    
    for index, video in enumerate(videos, 1):
        video_url = video.get("url", "").strip()
        video_title = video.get("title", "").strip()
        
        if not video_url or not video_title:
            print(f"⚠️ Skipping video {index}: Missing URL or title")
            failed.append(index)
            continue
        
        print(f"\n[Video {index}/{total}] Processing: {video_title}")
        print(f"🔗 URL: {video_url}")
        print("─" * 50)
        
        start_time = time.time()
        success, message = await process_video(video_url, video_title, download_dir, index)
        
        elapsed = time.time() - start_time
        
        if success:
            successful += 1
            print(f"✅ Video {index}: {message}")
            print(f"   ⏱️ Processing time: {elapsed:.1f} seconds")
        else:
            failed.append((index, video_title, message))
            print(f"❌ Video {index}: {message}")
        
        # Wait between videos (to avoid rate limits)
        if index < total:
            wait_time = 5
            print(f"⏳ Waiting {wait_time} seconds before next video...")
            await asyncio.sleep(wait_time)
    
    # Results summary
    print(f"\n{'='*50}")
    print("📊 Processing Summary")
    print('='*50)
    print(f"✅ Successful: {successful}/{total}")
    print(f"❌ Failed: {len(failed)}")
    
    if successful == total:
        print("🎉 All videos processed successfully!")
    elif successful > 0:
        print(f"⚠️ Partially successful ({successful}/{total})")
    else:
        print("💥 All videos failed!")
    
    if failed:
        print(f"\n📝 Failed videos:")
        for fail in failed:
            if isinstance(fail, tuple):
                print(f"  ❌ Video {fail[0]}: {fail[1]} - {fail[2]}")
            else:
                print(f"  ❌ Video {fail}")
        print("💡 You can rerun the workflow for failed videos only")
    
    # Cleanup empty directory
    try:
        if os.path.exists(download_dir) and not os.listdir(download_dir):
            os.rmdir(download_dir)
            print(f"\n🗑️ Cleaned empty directory: {download_dir}")
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
