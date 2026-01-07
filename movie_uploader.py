#!/usr/bin/env python3
"""
Telegram Movie Downloader & Uploader - Complete Version
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
    'Referer': 'https://3seq.com/'
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

# Install packages
install_requirements()

from pyrogram import Client
from pyrogram.errors import FloodWait, AuthKeyUnregistered, SessionPasswordNeeded
import yt_dlp
import cloudscraper
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
        # تنظيف STRING_SESSION من أي مسافات أو أسطر إضافية
        cleaned_session = STRING_SESSION.strip()
        
        print(f"🔧 Creating client with cleaned session ({len(cleaned_session)} chars)...")
        
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
        
        # بدء العميل
        await app.start()
        
        # التحقق من الاتصال
        me = await app.get_me()
        print(f"✅ Connected as: {me.first_name} (@{me.username})")
        
        # التحقق من القناة
        try:
            chat = await app.get_chat(TELEGRAM_CHANNEL)
            print(f"📢 Channel found: {chat.title}")
            
            # التحقق من الصلاحيات
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
        return False
        
    except SessionPasswordNeeded:
        print("❌ Account has 2FA enabled")
        return False
        
    except Exception as e:
        print(f"❌ Connection failed: {type(e).__name__}")
        print(f"📝 Error details: {str(e)[:100]}")
        return False

# ===== VIDEO PROCESSING FUNCTIONS =====

def extract_video_url_from_watch_url(watch_url):
    """Extract video download URL from watch URL using network analysis approach"""
    try:
        print(f"🔗 Analyzing URL: {watch_url}")
        
        # Initialize cloudscraper to bypass Cloudflare
        scraper = cloudscraper.create_scraper()
        
        # Get initial page
        response = scraper.get(watch_url, headers=HEADERS, timeout=30)
        if response.status_code != 200:
            return None, f"HTTP {response.status_code}"
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # Strategy 1: Look for direct video sources
        video_sources = []
        
        # Find video tags
        for video_tag in soup.find_all('video'):
            for source in video_tag.find_all('source'):
                src = source.get('src')
                if src and ('mp4' in src or 'm3u8' in src or 'mkv' in src):
                    video_sources.append(src)
        
        # Find iframes with video sources
        for iframe in soup.find_all('iframe'):
            src = iframe.get('src')
            if src and ('youtube' not in src and 'vimeo' not in src):
                # Try to extract from iframe
                try:
                    iframe_response = scraper.get(src, headers=HEADERS, timeout=15)
                    iframe_soup = BeautifulSoup(iframe_response.text, 'lxml')
                    
                    # Look for video sources in iframe
                    for iframe_video in iframe_soup.find_all('video'):
                        for iframe_source in iframe_video.find_all('source'):
                            iframe_src = iframe_source.get('src')
                            if iframe_src:
                                video_sources.append(iframe_src)
                except:
                    pass
        
        # Strategy 2: Look for JavaScript variables containing video URLs
        script_patterns = [
            r'file["\']?\s*[:=]\s*["\']([^"\']+\.(?:mp4|mkv|webm|avi|m3u8))["\']',
            r'source["\']?\s*[:=]\s*["\']([^"\']+\.(?:mp4|mkv|webm|avi|m3u8))["\']',
            r'video["\']?\s*[:=]\s*["\']([^"\']+\.(?:mp4|mkv|webm|avi|m3u8))["\']',
            r'url["\']?\s*[:=]\s*["\']([^"\']+\.(?:mp4|mkv|webm|avi|m3u8))["\']',
            r'src["\']?\s*[:=]\s*["\']([^"\']+\.(?:mp4|mkv|webm|avi|m3u8))["\']',
        ]
        
        for script in soup.find_all('script'):
            if script.string:
                for pattern in script_patterns:
                    matches = re.findall(pattern, script.string, re.IGNORECASE)
                    for match in matches:
                        if match.startswith('http'):
                            video_sources.append(match)
                        elif match.startswith('//'):
                            video_sources.append('https:' + match)
                        elif match.startswith('/'):
                            parsed_url = urlparse(watch_url)
                            video_sources.append(f'{parsed_url.scheme}://{parsed_url.netloc}{match}')
        
        # Filter and prioritize video sources
        valid_sources = []
        for src in video_sources:
            if src.startswith('http'):
                valid_sources.append(src)
        
        if valid_sources:
            # Sort by quality indicators
            def quality_score(url):
                score = 0
                url_lower = url.lower()
                if '1080' in url_lower:
                    score += 10
                elif '720' in url_lower:
                    score += 8
                elif '480' in url_lower:
                    score += 6
                elif '360' in url_lower:
                    score += 4
                if 'mp4' in url_lower:
                    score += 5
                return score
            
            best_source = max(valid_sources, key=quality_score)
            print(f"✅ Found {len(valid_sources)} video sources")
            print(f"📊 Best source: {best_source[:100]}...")
            return best_source, "✅ Video URL extracted"
        
        # Strategy 3: Try yt-dlp as fallback
        try:
            print("🔄 Trying yt-dlp extraction...")
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'user_agent': USER_AGENT,
                'referer': watch_url,
                'http_headers': HEADERS,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(watch_url, download=False)
                if 'url' in info:
                    return info['url'], "✅ URL extracted via yt-dlp"
                elif 'formats' in info:
                    formats = info['formats']
                    video_formats = [f for f in formats if f.get('vcodec') != 'none']
                    if video_formats:
                        best_format = max(video_formats, key=lambda x: x.get('height', 0))
                        return best_format['url'], "✅ URL extracted via yt-dlp formats"
        except Exception as e:
            print(f"⚠️ yt-dlp extraction failed: {e}")
        
        return None, "❌ No video source found"
        
    except Exception as e:
        return None, f"❌ Error: {str(e)}"

def download_video(url, output_path):
    """Download video using yt-dlp"""
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
        
        print(f"📥 Downloading...")
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
        for ext in ['.mp4', '.mkv', '.webm', '.avi']:
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
    
    return 1280, 720

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
                print(f"📤 {percent:.0f}% - {speed:.0f}KB/s")
                last_percent = percent
        
        upload_params['progress'] = progress
        
        # Upload
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

async def process_movie(watch_url, movie_name_arabic, movie_name_english, download_dir):
    """Process a single movie"""
    print(f"\n{'─'*50}")
    print(f"🎬 Movie Processing")
    print(f"{'─'*50}")
    print(f"📽️ Arabic Name: {movie_name_arabic}")
    print(f"📽️ English Name: {movie_name_english}")
    print(f"🔗 Watch URL: {watch_url}")
    
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
        video_url, message = extract_video_url_from_watch_url(watch_url)
        
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
    print("🎬 GitHub Movie Processor v2.0")
    print("="*50)
    
    # Check dependencies
    print("\n🔍 Checking dependencies...")
    
    # Check ffmpeg
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ ffmpeg is installed")
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
    config_file = "movie_config.json"
    if not os.path.exists(config_file):
        print(f"❌ Config file not found: {config_file}")
        print("💡 Creating sample config...")
        
        sample_config = {
            "watch_url": "https://example.com/watch/movie",
            "movie_name_arabic": "اسم الفيلم بالعربي",
            "movie_name_english": "Movie Name in English"
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
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Process movie
    print(f"\n[Processing Movie]")
    print("─" * 50)
    
    start_time = time.time()
    success, message = await process_movie(watch_url, movie_name_arabic, movie_name_english, download_dir)
    
    elapsed = time.time() - start_time
    
    # Results summary
    print(f"\n{'='*50}")
    print("📊 Processing Summary")
    print('='*50)
    
    if success:
        print(f"✅ Movie processed successfully!")
        print(f"⏱️ Processing time: {elapsed:.1f} seconds")
    else:
        print(f"❌ Movie processing failed: {message}")
    
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
