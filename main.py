#!/usr/bin/env python3
"""
Telegram Video Downloader & Uploader - Complete Version with Dynamic URL Support
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

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0',
    'Referer': 'https://3seq.cam/'
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
from pyrogram.errors import FloodWait, AuthKeyUnregistered, SessionPasswordNeeded
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
    print(f"🔗 Session length: {len(STRING_SESSION)} characters")
    
    try:
        # تنظيف STRING_SESSION من أي مسافات أو أسطر إضافية
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
        
        # بدء العميل
        await app.start()
        
        # التحقق من الاتصال
        me = await app.get_me()
        print(f"✅ Connected as: {me.first_name} (@{me.username})")
        print(f"📞 Phone: {me.phone_number}")
        
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
        
        # نصائح استكشاف الأخطاء
        print("\n🔧 Troubleshooting tips:")
        print("1. Check STRING_SESSION length (should be ~350 chars)")
        print("2. Regenerate session with generate_session.py")
        print("3. Verify API_ID and API_HASH")
        print("4. Check if account is banned")
        return False

# ===== VIDEO PROCESSING FUNCTIONS =====

def extract_video_url(episode_num, series_name, season_num):
    """Extract video URL from 3seq by following redirects"""
    try:
        # Construct initial URL without dynamic code
        if season_num > 0:
            base_url = f"https://z.3seq.cam/video/modablaj-{series_name}-episode-s{season_num:02d}e{episode_num:02d}"
        else:
            base_url = f"https://z.3seq.cam/video/modablaj-{series_name}-episode-{episode_num:02d}"
        
        print(f"🔗 Initial URL: {base_url}")
        
        # Create a session to handle cookies and redirects
        session = requests.Session()
        session.headers.update(HEADERS)
        
        # Disable SSL verification for some problematic sites
        session.verify = False
        
        # Make initial request and follow redirects
        response = session.get(base_url, timeout=30, allow_redirects=True)
        
        # Get the final URL after all redirects
        final_url = response.url
        print(f"🔄 Final URL after redirects: {final_url}")
        
        # Check if we got a valid response
        if response.status_code != 200:
            print(f"❌ HTTP Error: {response.status_code}")
            return None, f"HTTP {response.status_code}"
        
        # Add ?do=watch to the final URL if not already present
        if '?do=watch' not in final_url:
            # Ensure URL ends with /
            if not final_url.endswith('/'):
                final_url += '/'
            watch_url = final_url + '?do=watch'
        else:
            watch_url = final_url
        
        print(f"🔍 Watch URL: {watch_url}")
        
        # Now fetch the watch page
        watch_response = session.get(watch_url, timeout=30)
        
        if watch_response.status_code != 200:
            return None, f"Watch page error: HTTP {watch_response.status_code}"
        
        # Save HTML for debugging
        html_debug = watch_response.text[:2000]
        print(f"📄 HTML preview: {html_debug[:200]}...")
        
        # Try to find video iframe in multiple ways
        video_url = None
        
        # Method 1: Direct iframe extraction
        iframe_patterns = [
            r'<iframe[^>]+src="([^"]+)"',
            r'<iframe[^>]+src=\'([^\']+)\'',
            r'<iframe[^>]+src=([^ >]+)',
            r'src="(https?://[^"]+)"[^>]*></iframe>',
        ]
        
        for pattern in iframe_patterns:
            matches = re.findall(pattern, watch_response.text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                
                if 'vidsp.net' in match or 'streamtape' in match or 'dood.' in match:
                    video_url = match
                    print(f"✅ Found video iframe with pattern: {pattern[:30]}...")
                    break
            if video_url:
                break
        
        # Method 2: Look for video sources in script tags
        if not video_url:
            script_patterns = [
                r'src:\s*["\']([^"\']+)["\']',
                r'file:\s*["\']([^"\']+)["\']',
                r'url:\s*["\']([^"\']+)["\']',
                r'video_url:\s*["\']([^"\']+)["\']',
                r'embed_url:\s*["\']([^"\']+)["\']',
            ]
            
            for pattern in script_patterns:
                matches = re.findall(pattern, watch_response.text, re.IGNORECASE)
                for match in matches:
                    if 'http' in match and ('vidsp' in match or 'mp4' in match or 'm3u8' in match):
                        video_url = match
                        print(f"✅ Found video in script with pattern: {pattern[:30]}...")
                        break
                if video_url:
                    break
        
        # Method 3: Look for direct video links
        if not video_url:
            video_extensions = ['mp4', 'mkv', 'avi', 'mov', 'wmv', 'flv', 'webm', 'm3u8']
            for ext in video_extensions:
                pattern = rf'https?://[^"\'\s<>]+\.{ext}[^"\'\s<>]*'
                matches = re.findall(pattern, watch_response.text, re.IGNORECASE)
                if matches:
                    video_url = matches[0]
                    print(f"✅ Found direct video link with extension .{ext}")
                    break
        
        # Method 4: Look for common video hosting domains
        if not video_url:
            video_hosts = [
                r'https?://v\.vidsp\.net/[^"\'\s<>]+',
                r'https?://vidsp\.net/[^"\'\s<>]+',
                r'https?://streamtape\.com/[^"\'\s<>]+',
                r'https?://dood\.\w+/[^"\'\s<>]+',
                r'https?://mixdrop\.\w+/[^"\'\s<>]+',
                r'https?://videobin\.\w+/[^"\'\s<>]+',
                r'https?://embedo\.\w+/[^"\'\s<>]+',
            ]
            
            for pattern in video_hosts:
                matches = re.findall(pattern, watch_response.text, re.IGNORECASE)
                if matches:
                    video_url = matches[0]
                    print(f"✅ Found video on hosting domain: {pattern[:30]}...")
                    break
        
        if not video_url:
            # Try to find any iframe and check its content
            all_iframes = re.findall(r'<iframe[^>]+>', watch_response.text, re.IGNORECASE)
            for iframe in all_iframes:
                # Extract src attribute
                src_match = re.search(r'src=["\']([^"\']+)["\']', iframe)
                if src_match:
                    iframe_url = src_match.group(1)
                    # Try to fetch the iframe content
                    try:
                        if iframe_url.startswith('//'):
                            iframe_url = 'https:' + iframe_url
                        elif iframe_url.startswith('/'):
                            iframe_url = 'https://z.3seq.cam' + iframe_url
                        
                        print(f"🔄 Checking iframe: {iframe_url[:80]}...")
                        iframe_response = session.get(iframe_url, timeout=10)
                        
                        # Look for video in iframe
                        video_patterns = [
                            r'<video[^>]+src="([^"]+)"',
                            r'<source[^>]+src="([^"]+)"',
                            r'file:\s*["\']([^"\']+)["\']',
                        ]
                        
                        for pattern in video_patterns:
                            video_match = re.search(pattern, iframe_response.text, re.IGNORECASE)
                            if video_match:
                                video_url = video_match.group(1)
                                print(f"✅ Found video in iframe content")
                                break
                        
                        if video_url:
                            break
                    except:
                        continue
        
        if not video_url:
            return None, "❌ Could not find video source on the page"
        
        # Clean and normalize the URL
        if video_url.startswith('//'):
            video_url = 'https:' + video_url
        elif video_url.startswith('/'):
            # Try to determine the correct domain
            if 'vidsp.net' in watch_response.text:
                video_url = 'https://v.vidsp.net' + video_url
            else:
                # Try common domains
                domains = [
                    'https://v.vidsp.net',
                    'https://vidsp.net',
                    'https://streamtape.com',
                    'https://dood.wf',
                ]
                
                for domain in domains:
                    try:
                        test_url = domain + video_url
                        test_response = requests.head(test_url, headers=HEADERS, timeout=5)
                        if test_response.status_code < 400:
                            video_url = test_url
                            break
                    except:
                        continue
        
        print(f"✅ Extracted video URL: {video_url[:100]}...")
        return video_url, "✅ Successfully extracted video URL"
        
    except requests.exceptions.Timeout:
        return None, "⏰ Timeout connecting to server"
    except requests.exceptions.ConnectionError:
        return None, "🔌 Connection error"
    except Exception as e:
        print(f"📝 Debug error: {type(e).__name__}: {str(e)}")
        return None, f"❌ Error: {str(e)[:100]}"

def download_video(url, output_path):
    """Download video using yt-dlp"""
    try:
        ydl_opts = {
            'format': 'best[height<=720]/best',
            'outtmpl': output_path,
            'quiet': False,  # Changed to False to see progress
            'no_warnings': False,
            'user_agent': USER_AGENT,
            'referer': 'https://3seq.cam/',
            'http_headers': HEADERS,
            'retries': 10,
            'fragment_retries': 10,
            'skip_unavailable_fragments': True,
            'socket_timeout': 30,
            'extractor_args': {
                'generic': {
                    'no_check_certificate': True
                }
            }
        }
        
        print(f"📥 Downloading from: {url[:80]}...")
        start = time.time()
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        elapsed = time.time() - start
        
        # Check if file was downloaded
        if os.path.exists(output_path):
            size = os.path.getsize(output_path) / (1024*1024)
            print(f"✅ Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
            return True
        
        # Try to find the file (yt-dlp might add extension)
        base_name = os.path.splitext(output_path)[0]
        for ext in ['.mp4', '.mkv', '.webm', '.avi', '.flv', '']:
            test_file = base_name + ext
            if os.path.exists(test_file):
                if test_file != output_path:
                    shutil.move(test_file, output_path)
                size = os.path.getsize(output_path) / (1024*1024)
                print(f"✅ Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
                return True
        
        return False
        
    except Exception as e:
        print(f"❌ Download error: {str(e)[:100]}")
        return False

def compress_video(input_file, output_file):
    """Compress video to 240p"""
    if not os.path.exists(input_file):
        print(f"❌ File not found: {input_file}")
        return False
    
    original_size = os.path.getsize(input_file) / (1024 * 1024)
    print(f"🎬 Compressing video...")
    print(f"📊 Original: {original_size:.1f}MB")
    
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
            '-ss', '00:00:05',
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
                print(f"📤 {percent:.0f}% - {speed:.0f}KB/s")
                last_percent = percent
        
        upload_params['progress'] = progress
        
        # Upload
        try:
            await app.send_video(**upload_params)
            elapsed = time.time() - start_time
            print(f"✅ Uploaded in {elapsed:.1f}s")
            print(f"🎬 Streaming: Enabled (pauses on exit)")
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

async def process_episode(episode_num, series_name, series_name_arabic, season_num, download_dir):
    """Process a single episode"""
    print(f"\n{'─'*50}")
    print(f"🎬 Episode {episode_num:02d}")
    print(f"{'─'*50}")
    
    temp_file = os.path.join(download_dir, f"temp_{episode_num:02d}.mp4")
    final_file = os.path.join(download_dir, f"final_{episode_num:02d}.mp4")
    thumbnail_file = os.path.join(download_dir, f"thumb_{episode_num:02d}.jpg")
    
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
        video_url, message = extract_video_url(episode_num, series_name, season_num)
        
        if not video_url:
            return False, f"URL extraction failed: {message}"
        
        print(f"{message}")
        
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
        caption = f"{series_name_arabic} الموسم {season_num} الحلقة {episode_num}"
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

# ===== ALTERNATIVE EXTRACTION USING DIFFERENT APPROACH =====

def extract_video_url_direct(episode_num, series_name, season_num):
    """Direct approach: Try to access the page and parse the redirect"""
    try:
        # Start with basic URL
        base_url = f"https://z.3seq.cam/video/modablaj-{series_name}-episode-s{season_num:02d}e{episode_num:02d}"
        
        print(f"🔗 Trying direct access to: {base_url}")
        
        # Disable SSL warnings
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Create session with custom settings
        session = requests.Session()
        session.headers.update(HEADERS)
        session.verify = False
        
        # First request to get redirected URL
        response = session.get(base_url, timeout=30, allow_redirects=True)
        
        # Check response history for redirects
        if response.history:
            print(f"🔄 Redirect chain:")
            for i, resp in enumerate(response.history):
                print(f"  {i+1}. {resp.status_code} -> {resp.url}")
        
        final_url = response.url
        print(f"📍 Final URL: {final_url}")
        
        # Add watch parameter
        if not final_url.endswith('/'):
            final_url += '/'
        watch_url = final_url + '?do=watch'
        
        print(f"👀 Watch URL: {watch_url}")
        
        # Get watch page
        watch_response = session.get(watch_url, timeout=30)
        
        # Try to extract iframe using more aggressive parsing
        iframe_matches = re.findall(r'<iframe[^>]+>', watch_response.text, re.IGNORECASE)
        
        for iframe in iframe_matches:
            src_match = re.search(r'src=["\']([^"\']+)["\']', iframe)
            if src_match:
                iframe_src = src_match.group(1)
                
                # Clean iframe URL
                if iframe_src.startswith('//'):
                    iframe_src = 'https:' + iframe_src
                elif iframe_src.startswith('/'):
                    iframe_src = 'https://z.3seq.cam' + iframe_src
                
                print(f"🎬 Found iframe: {iframe_src[:80]}...")
                
                # Try to get the iframe content
                try:
                    iframe_response = session.get(iframe_src, timeout=15)
                    
                    # Look for video source in iframe
                    source_patterns = [
                        r'<source[^>]+src="([^"]+)"',
                        r'<video[^>]+src="([^"]+)"',
                        r'file:\s*["\']([^"\']+)["\']',
                        r'src:\s*["\']([^"\']+)["\']',
                    ]
                    
                    for pattern in source_patterns:
                        source_match = re.search(pattern, iframe_response.text, re.IGNORECASE)
                        if source_match:
                            video_url = source_match.group(1)
                            if video_url.startswith('//'):
                                video_url = 'https:' + video_url
                            
                            print(f"✅ Found video source: {video_url[:80]}...")
                            return video_url, "✅ Extracted from iframe"
                    
                    # If no video source found, check if iframe itself is a video
                    if 'video' in iframe_response.headers.get('Content-Type', '') or \
                       '.mp4' in iframe_src or '.m3u8' in iframe_src:
                        return iframe_src, "✅ Iframe is video"
                        
                except Exception as e:
                    print(f"⚠️ Could not fetch iframe: {str(e)[:50]}")
        
        # If no iframe found, try to find direct links
        direct_links = re.findall(r'https?://[^"\'\s<>]+\.(?:mp4|m3u8|mkv)[^"\'\s<>]*', watch_response.text, re.IGNORECASE)
        if direct_links:
            return direct_links[0], "✅ Found direct video link"
        
        return None, "❌ Could not extract video URL"
        
    except Exception as e:
        print(f"❌ Direct extraction error: {str(e)[:100]}")
        return None, f"❌ Error: {str(e)[:50]}"

# ===== MAIN FUNCTION =====

async def main():
    """Main function"""
    print("="*50)
    print("🎬 GitHub Video Processor v3.0 (Improved URL Extraction)")
    print("="*50)
    
    # Check dependencies
    print("\n🔍 Checking dependencies...")
    
    # Check ffmpeg
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ ffmpeg is installed")
            
            # Get ffmpeg version
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
    config_file = "series_config.json"
    if not os.path.exists(config_file):
        print(f"❌ Config file not found: {config_file}")
        print("💡 Creating sample config...")
        
        sample_config = {
            "series_name": "kiralik-ask",
            "series_name_arabic": "كيراليك اسك",
            "season_num": 1,
            "start_episode": 1,
            "end_episode": 10
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
    
    series_name = config.get("series_name", "").strip()
    series_name_arabic = config.get("series_name_arabic", "").strip()
    season_num = int(config.get("season_num", 1))
    start_ep = int(config.get("start_episode", 1))
    end_ep = int(config.get("end_episode", 1))
    
    if not series_name or not series_name_arabic:
        print("❌ Invalid series configuration")
        return
    
    if start_ep > end_ep:
        print("❌ Start episode must be less than end episode")
        return
    
    # Create working directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    download_dir = f"downloads_{timestamp}"
    os.makedirs(download_dir, exist_ok=True)
    
    print(f"\n{'='*50}")
    print("🚀 Starting Video Processing")
    print('='*50)
    print(f"📺 Series: {series_name_arabic}")
    print(f"🌐 English name: {series_name}")
    print(f"🎬 Season: {season_num}")
    print(f"📈 Episodes: {start_ep} to {end_ep} (total: {end_ep - start_ep + 1})")
    print(f"📁 Working dir: {download_dir}")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Process episodes
    successful = 0
    failed = []
    total = end_ep - start_ep + 1
    
    for episode_num in range(start_ep, end_ep + 1):
        current = episode_num - start_ep + 1
        
        print(f"\n[Episode {current}/{total}] Processing episode {episode_num:02d}")
        print("─" * 50)
        
        start_time = time.time()
        
        # Try multiple extraction methods
        video_url = None
        message = ""
        
        # Try method 1
        print("🔄 Method 1: Standard extraction...")
        video_url, message = extract_video_url(episode_num, series_name, season_num)
        
        # Try method 2 if method 1 fails
        if not video_url:
            print("🔄 Method 2: Direct extraction...")
            video_url, message = extract_video_url_direct(episode_num, series_name, season_num)
        
        if not video_url:
            print(f"❌ Episode {episode_num:02d}: {message}")
            failed.append(episode_num)
            continue
        
        # Process the episode with the found URL
        try:
            # 1. Download
            temp_file = os.path.join(download_dir, f"temp_{episode_num:02d}.mp4")
            final_file = os.path.join(download_dir, f"final_{episode_num:02d}.mp4")
            thumbnail_file = os.path.join(download_dir, f"thumb_{episode_num:02d}.jpg")
            
            print("📥 Downloading video...")
            if not download_video(video_url, temp_file):
                print(f"❌ Episode {episode_num:02d}: Download failed")
                failed.append(episode_num)
                continue
            
            # 2. Create thumbnail
            print("🖼️ Creating thumbnail...")
            create_thumbnail(temp_file, thumbnail_file)
            
            # 3. Compress
            print("🎬 Compressing video...")
            if not compress_video(temp_file, final_file):
                print("⚠️ Compression failed, using original")
                shutil.copy2(temp_file, final_file)
            
            # 4. Upload
            caption = f"{series_name_arabic} الموسم {season_num} الحلقة {episode_num}"
            thumb = thumbnail_file if os.path.exists(thumbnail_file) else None
            
            if await upload_video(final_file, caption, thumb):
                successful += 1
                
                # Clean up
                for file_path in [temp_file, final_file, thumbnail_file]:
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except:
                            pass
                
                elapsed = time.time() - start_time
                print(f"✅ Episode {episode_num:02d}: Uploaded successfully")
                print(f"   ⏱️ Processing time: {elapsed:.1f} seconds")
            else:
                failed.append(episode_num)
                print(f"❌ Episode {episode_num:02d}: Upload failed")
        
        except Exception as e:
            failed.append(episode_num)
            print(f"❌ Episode {episode_num:02d}: Processing error - {str(e)[:100]}")
        
        # Wait between episodes (to avoid rate limits)
        if episode_num < end_ep:
            wait_time = 3
            print(f"⏳ Waiting {wait_time} seconds before next episode...")
            await asyncio.sleep(wait_time)
    
    # Results summary
    print(f"\n{'='*50}")
    print("📊 Processing Summary")
    print('='*50)
    print(f"✅ Successful: {successful}/{total}")
    print(f"❌ Failed: {len(failed)}")
    
    if successful == total:
        print("🎉 All episodes processed successfully!")
    elif successful > 0:
        print(f"⚠️ Partially successful ({successful}/{total})")
    else:
        print("💥 All episodes failed!")
    
    if failed:
        print(f"📝 Failed episodes: {failed}")
        print("💡 You can rerun the workflow for failed episodes only")
    
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
