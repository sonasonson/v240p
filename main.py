#!/usr/bin/env python3
"""
Telegram Video Downloader & Uploader - Modified for 3seq.cam
Supports redirects with random suffixes like -avxn
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
import argparse
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

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Referer': 'https://z.3seq.cam/',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
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

# ===== URL PROCESSING FUNCTIONS =====

def extract_season_episode_from_url(url):
    """
    Extract season and episode numbers from 3seq URL
    Supports formats:
    - https://z.3seq.cam/video/modablaj-kiralik-ask-episode-s01e89
    - https://z.3seq.cam/video/modablaj-kiralik-ask-episode-s01e89-avxn/
    - https://z.3seq.cam/video/modablaj-series-name-episode-s02e15
    """
    print(f"🔗 Parsing URL: {url}")
    
    # Parse the URL
    parsed_url = urlparse(url)
    path_parts = parsed_url.path.split('/')
    
    if len(path_parts) < 3:
        return None, None, "Invalid URL format"
    
    video_slug = path_parts[-1]
    
    # Try to extract season and episode using regex patterns
    # Pattern 1: s01e89 format (with optional random suffix like -avxn)
    season_episode_match = re.search(r's(\d+)e(\d+)', video_slug, re.IGNORECASE)
    
    if season_episode_match:
        season_num = int(season_episode_match.group(1))
        episode_num = int(season_episode_match.group(2))
        
        # Extract series name (remove -avxn or similar random suffix)
        clean_slug = re.sub(r'-[a-z]{4}$', '', video_slug)  # Remove 4-letter suffix like -avxn
        series_match = re.search(r'modablaj-([a-z0-9-]+)-episode', clean_slug, re.IGNORECASE)
        if series_match:
            series_name = series_match.group(1)
        else:
            # Fallback: extract from URL path
            series_name = clean_slug.split('-episode-')[0].replace('modablaj-', '')
        
        return season_num, episode_num, series_name
    
    # Pattern 2: Just episode number (assume season 1)
    episode_match = re.search(r'-episode-(\d+)(?:-[a-z]{4})?$', video_slug)
    if episode_match:
        season_num = 1
        episode_num = int(episode_match.group(1))
        
        # Extract series name
        clean_slug = re.sub(r'-[a-z]{4}$', '', video_slug)  # Remove random suffix
        series_match = re.search(r'modablaj-([a-z0-9-]+)-episode', clean_slug)
        if series_match:
            series_name = series_match.group(1)
        else:
            series_name = clean_slug.split('-episode-')[0].replace('modablaj-', '')
        
        return season_num, episode_num, series_name
    
    return None, None, "Cannot extract season/episode from URL"

def get_arabic_series_name(english_name):
    """
    Map English series names to Arabic names
    Can be extended with more series
    """
    series_mapping = {
        "kiralik-ask": "حب للايجار",
        "the-protector": "المحافظ",
        "dirilis-ertugrul": "قيامة ارطغرل",
        "kurulus-osman": "تأسيس عثمان",
        "yargi": "قضاء",
        "ramo": "رامو",
        "son-yaz": "آخر كتابة",
        "sadakatsiz": "الخائن",
        "sen-calka": "أنت رقصت",
        "icerde": "في الداخل"
    }
    
    # Try exact match first
    if english_name in series_mapping:
        return series_mapping[english_name]
    
    # Try partial match
    for key, arabic_name in series_mapping.items():
        if key in english_name:
            return arabic_name
    
    # Return the English name if no match found
    return english_name.replace('-', ' ').title()

def extract_video_url_from_page(url):
    """
    Extract video URL from 3seq.cam page - UPDATED VERSION
    Handles redirects and random URL suffixes like -avxn
    """
    try:
        print(f"🌐 Fetching page (may redirect): {url}")
        
        # Allow redirects to follow the random suffix link
        session = requests.Session()
        session.headers.update(HEADERS)
        
        response = session.get(url, timeout=30, allow_redirects=True)
        
        if response.status_code != 200:
            return None, f"HTTP {response.status_code}"
        
        # Get the FINAL URL after all redirects
        final_url = response.url
        print(f"✅ Final URL after redirects: {final_url}")
        
        # Check if we need to add ?do=watch
        # If not already present, add it to the final URL
        if '?do=watch' not in final_url:
            if '?' in final_url:
                watch_url = final_url + '&do=watch'
            else:
                watch_url = final_url.rstrip('/') + '/?do=watch'
        else:
            watch_url = final_url
        
        print(f"🔍 Checking watch page: {watch_url}")
        
        # Now fetch the watch page to find the actual video
        watch_response = session.get(watch_url, timeout=30)
        
        # Use BeautifulSoup for better HTML parsing
        soup = BeautifulSoup(watch_response.text, 'html.parser')
        
        video_url = None
        
        # METHOD 1: Look for iframe embed (most common)
        iframes = soup.find_all('iframe')
        for iframe in iframes:
            src = iframe.get('src', '')
            if src and any(domain in src for domain in ['vidsp.net', 'youtube.com', 'dailymotion.com', 'vimeo.com', 'cloudemb.com']):
                video_url = src
                if video_url.startswith('//'):
                    video_url = 'https:' + video_url
                print(f"🎬 Found embedded video URL (iframe): {video_url}")
                break
        
        # METHOD 2: Look for video tags with src attribute
        if not video_url:
            video_tags = soup.find_all('video')
            for video in video_tags:
                src = video.get('src', '')
                if src and any(ext in src for ext in ['.mp4', '.m3u8', '.webm', '.ogg']):
                    video_url = src
                    print(f"🎬 Found video tag URL: {video_url}")
                    break
                
                # Check for source tags inside video tag
                source_tags = video.find_all('source')
                for source in source_tags:
                    src = source.get('src', '')
                    if src and any(ext in src for ext in ['.mp4', '.m3u8', '.webm', '.ogg']):
                        video_url = src
                        print(f"🎬 Found source tag URL: {video_url}")
                        break
                if video_url:
                    break
        
        # METHOD 3: Look for JavaScript variables containing video URLs
        if not video_url:
            script_tags = soup.find_all('script')
            for script in script_tags:
                if script.string:
                    js_content = script.string
                    # Look for common video URL patterns in JavaScript
                    patterns = [
                        r'file["\']?\s*:\s*["\'](https?://[^"\']+\.mp4[^"\']*)["\']',
                        r'src["\']?\s*:\s*["\'](https?://[^"\']+\.mp4[^"\']*)["\']',
                        r'video_url["\']?\s*:\s*["\'](https?://[^"\']+\.mp4[^"\']*)["\']',
                        r'url["\']?\s*:\s*["\'](https?://[^"\']+\.mp4[^"\']*)["\']',
                        r'(https?://[^"\']+vidsp\.net[^"\']+)',
                        r'(https?://[^"\']+\.m3u8[^"\']*)'
                    ]
                    
                    for pattern in patterns:
                        matches = re.findall(pattern, js_content, re.IGNORECASE)
                        for match in matches:
                            if match and any(ext in match for ext in ['.mp4', '.m3u8', 'vidsp.net']):
                                video_url = match
                                print(f"🎬 Found video URL in JavaScript: {video_url}")
                                break
                        if video_url:
                            break
                if video_url:
                    break
        
        # METHOD 4: Look for data-* attributes that might contain video URLs
        if not video_url:
            all_elements = soup.find_all(attrs={"data-src": True})
            for element in all_elements:
                data_src = element.get('data-src', '')
                if data_src and any(ext in data_src for ext in ['.mp4', '.m3u8', 'vidsp.net']):
                    video_url = data_src
                    print(f"🎬 Found video URL in data-src: {video_url}")
                    break
        
        # METHOD 5: Search the entire HTML for video URL patterns
        if not video_url:
            html_text = str(soup)
            video_patterns = [
                r'(https?://[^"\'\s<>]+vidsp\.net[^"\'\s<>]+)',
                r'(https?://[^"\'\s<>]+\.mp4[^"\'\s<>]*)',
                r'(https?://[^"\'\s<>]+\.m3u8[^"\'\s<>]*)',
                r'file["\']?\s*:\s*["\'](https?://[^"\']+)["\']',
                r'source["\']?\s*:\s*["\'](https?://[^"\']+)["\']'
            ]
            
            for pattern in video_patterns:
                matches = re.findall(pattern, html_text, re.IGNORECASE)
                for match in matches:
                    if match and any(ext in match for ext in ['.mp4', '.m3u8', 'vidsp.net', 'cloudemb.com']):
                        # Filter out common false positives
                        if not any(false_positive in match for false_positive in ['google-analytics', 'facebook.com', 'twitter.com', 'css', 'js']):
                            video_url = match
                            print(f"🎬 Found video URL via pattern matching: {video_url}")
                            break
                if video_url:
                    break
        
        if video_url:
            # Ensure the URL is complete
            if video_url.startswith('//'):
                video_url = 'https:' + video_url
            elif video_url.startswith('/'):
                video_url = 'https://z.3seq.cam' + video_url
            
            return video_url, f"✅ Video URL extracted from {final_url}"
        else:
            # For debugging: Save the page to see its structure
            debug_file = f"debug_page_{int(time.time())}.html"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(watch_response.text[:10000])  # First 10000 chars
            print(f"⚠️ Saved page snippet to {debug_file} for inspection")
            
            # Try one more method: Look for any URL with video-related terms
            all_urls = re.findall(r'https?://[^"\'\s<>]+', watch_response.text)
            for test_url in all_urls:
                if any(term in test_url.lower() for term in ['video', 'stream', 'embed', 'player', 'vid', 'watch']):
                    print(f"🔍 Potential video URL found: {test_url[:80]}...")
                    # Try to validate by checking if it's accessible
                    try:
                        test_resp = session.head(test_url, timeout=5)
                        if test_resp.status_code == 200:
                            content_type = test_resp.headers.get('content-type', '')
                            if any(video_type in content_type for video_type in ['video/', 'mp4', 'mpeg', 'x-mpegurl']):
                                print(f"✅ Validated as video URL: {test_url}")
                                return test_url, f"✅ Video URL found via validation"
                    except:
                        pass
            
            return None, f"❌ No video URL found in watch page. Check {debug_file}"
        
    except requests.exceptions.Timeout:
        return None, "⏰ Timeout fetching page"
    except requests.exceptions.TooManyRedirects:
        return None, "🔄 Too many redirects. Site structure may have changed."
    except Exception as e:
        return None, f"❌ Error: {str(e)[:100]}"

def generate_episode_urls(series_name, season_num, start_ep, end_ep):
    """
    Generate episode URLs for batch processing
    """
    urls = []
    
    for episode_num in range(start_ep, end_ep + 1):
        if season_num > 1:
            url = f"https://z.3seq.cam/video/modablaj-{series_name}-episode-s{season_num:02d}e{episode_num:02d}"
        else:
            url = f"https://z.3seq.cam/video/modablaj-{series_name}-episode-{episode_num:02d}"
        urls.append((episode_num, url))
    
    return urls

# ===== VIDEO PROCESSING FUNCTIONS =====

def download_video(url, output_path):
    """Download video using yt-dlp with enhanced settings"""
    try:
        ydl_opts = {
            'format': 'best[height<=720]/best',
            'outtmpl': output_path,
            'quiet': False,
            'no_warnings': False,
            'user_agent': USER_AGENT,
            'referer': 'https://z.3seq.cam/',
            'http_headers': HEADERS,
            'retries': 10,
            'fragment_retries': 10,
            'skip_unavailable_fragments': True,
            'socket_timeout': 30,
            'extractor_args': {
                'generic': ['--no-check-certificate']
            },
            'cookiesfrombrowser': ('chrome',),  # Try to use browser cookies if available
            'verbose': True,  # More detailed output for debugging
        }
        
        print(f"📥 Downloading from: {url}")
        start = time.time()
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
            except Exception as e:
                print(f"⚠️ yt-dlp extraction failed: {e}")
                print("🔄 Trying alternative download method...")
                
                # Fallback to direct download if yt-dlp fails
                session = requests.Session()
                session.headers.update(HEADERS)
                
                resp = session.get(url, stream=True, timeout=30)
                if resp.status_code == 200:
                    with open(output_path, 'wb') as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    print("✅ Downloaded via fallback method")
                else:
                    return False
        
        elapsed = time.time() - start
        
        # Check if file was downloaded
        if os.path.exists(output_path):
            size = os.path.getsize(output_path) / (1024*1024)
            print(f"✅ Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
            return True
        else:
            # Check for file with different extension
            base_name = os.path.splitext(output_path)[0]
            for ext in ['.mp4', '.mkv', '.webm', '.avi', '.flv', '.mov']:
                alt_file = base_name + ext
                if os.path.exists(alt_file):
                    shutil.move(alt_file, output_path)
                    size = os.path.getsize(output_path) / (1024*1024)
                    print(f"✅ Downloaded (renamed) in {elapsed:.1f}s ({size:.1f}MB)")
                    return True
        
        return False
        
    except Exception as e:
        print(f"❌ Download error: {e}")
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

async def process_single_url(url, download_dir):
    """
    Process a single URL with random suffix handling
    """
    print(f"\n{'─'*50}")
    print(f"🎬 Processing URL")
    print(f"📝 {url}")
    print(f"{'─'*50}")
    
    # Extract season and episode from URL
    season_num, episode_num, series_name = extract_season_episode_from_url(url)
    
    if season_num is None or episode_num is None:
        print("❌ Cannot extract season/episode information")
        return False, "Invalid URL format"
    
    # Get Arabic series name
    series_name_arabic = get_arabic_series_name(series_name)
    
    temp_file = os.path.join(download_dir, f"temp_s{season_num:02d}e{episode_num:02d}.mp4")
    final_file = os.path.join(download_dir, f"final_s{season_num:02d}e{episode_num:02d}.mp4")
    thumbnail_file = os.path.join(download_dir, f"thumb_s{season_num:02d}e{episode_num:02d}.jpg")
    
    # Clean old files
    for f in [temp_file, final_file, thumbnail_file]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except:
                pass
    
    try:
        # 1. Extract video URL from page (handles redirects and random suffixes)
        print("🔍 Extracting video URL from page...")
        video_url, message = extract_video_url_from_page(url)
        
        if not video_url:
            return False, f"URL extraction failed: {message}"
        
        print(f"{message}")
        print(f"🎬 Video URL: {video_url[:100]}...")
        
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
        # Try to clean up even on error
        for file_path in [temp_file, final_file, thumbnail_file]:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
        return False, str(e)

async def process_episode_batch(series_name, series_name_arabic, season_num, start_ep, end_ep, download_dir):
    """Process a batch of episodes"""
    successful = 0
    failed = []
    total = end_ep - start_ep + 1
    
    for episode_num in range(start_ep, end_ep + 1):
        current = episode_num - start_ep + 1
        
        print(f"\n[Episode {current}/{total}] Processing episode {episode_num:02d}")
        print("─" * 50)
        
        # Generate URL for this episode
        if season_num > 1:
            url = f"https://z.3seq.cam/video/modablaj-{series_name}-episode-s{season_num:02d}e{episode_num:02d}"
        else:
            url = f"https://z.3seq.cam/video/modablaj-{series_name}-episode-{episode_num:02d}"
        
        start_time = time.time()
        
        # Use the single URL processing function
        temp_file = os.path.join(download_dir, f"temp_s{season_num:02d}e{episode_num:02d}.mp4")
        final_file = os.path.join(download_dir, f"final_s{season_num:02d}e{episode_num:02d}.mp4")
        thumbnail_file = os.path.join(download_dir, f"thumb_s{season_num:02d}e{episode_num:02d}.jpg")
        
        # Clean old files
        for f in [temp_file, final_file, thumbnail_file]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass
        
        try:
            # Extract video URL from page (handles redirects and random suffixes)
            print(f"🔍 Fetching: {url}")
            video_url, message = extract_video_url_from_page(url)
            
            if not video_url:
                failed.append(episode_num)
                print(f"❌ Episode {episode_num:02d}: {message}")
                continue
            
            # Download
            if not download_video(video_url, temp_file):
                failed.append(episode_num)
                print(f"❌ Episode {episode_num:02d}: Download failed")
                continue
            
            # Create thumbnail
            create_thumbnail(temp_file, thumbnail_file)
            
            # Compress
            if not compress_video(temp_file, final_file):
                print("⚠️ Compression failed, using original")
                shutil.copy2(temp_file, final_file)
            
            # Upload
            caption = f"{series_name_arabic} الموسم {season_num} الحلقة {episode_num}"
            thumb = thumbnail_file if os.path.exists(thumbnail_file) else None
            
            if await upload_video(final_file, caption, thumb):
                successful += 1
                elapsed = time.time() - start_time
                print(f"✅ Episode {episode_num:02d}: Uploaded successfully")
                print(f"   ⏱️ Processing time: {elapsed:.1f} seconds")
            else:
                failed.append(episode_num)
                print(f"❌ Episode {episode_num:02d}: Upload failed")
            
            # Clean up
            for file_path in [temp_file, final_file, thumbnail_file]:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except:
                        pass
            
        except Exception as e:
            failed.append(episode_num)
            print(f"❌ Episode {episode_num:02d}: Error - {str(e)[:100]}")
            # Clean up on error
            for file_path in [temp_file, final_file, thumbnail_file]:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except:
                        pass
        
        # Wait between episodes
        if episode_num < end_ep:
            wait_time = 3
            print(f"⏳ Waiting {wait_time} seconds before next episode...")
            await asyncio.sleep(wait_time)
    
    return successful, failed, total

# ===== MAIN FUNCTION =====

async def main():
    """Main function"""
    print("="*50)
    print("🎬 GitHub Video Processor v3.1")
    print("   Handles random URL suffixes like -avxn")
    print("="*50)
    
    # Setup argument parser
    parser = argparse.ArgumentParser(description='Download and upload videos from 3seq.cam')
    parser.add_argument('--url', type=str, help='Single URL to process')
    parser.add_argument('--config', type=str, default='series_config.json', 
                       help='Config file for batch processing')
    parser.add_argument('--mode', type=str, choices=['single', 'batch'], default='batch',
                       help='Processing mode: single URL or batch')
    
    args = parser.parse_args()
    
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
    
    # Create working directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    download_dir = f"downloads_{timestamp}"
    os.makedirs(download_dir, exist_ok=True)
    
    # Process based on mode
    if args.mode == 'single' and args.url:
        print(f"\n{'='*50}")
        print("🚀 Processing Single URL")
        print('='*50)
        print(f"🔗 URL: {args.url}")
        
        # Extract info from URL for display
        season_num, episode_num, series_name = extract_season_episode_from_url(args.url)
        if season_num and episode_num:
            series_name_arabic = get_arabic_series_name(series_name)
            print(f"📺 Series: {series_name_arabic}")
            print(f"🌐 English name: {series_name}")
            print(f"🎬 Season: {season_num}")
            print(f"📺 Episode: {episode_num}")
        
        print(f"📁 Working dir: {download_dir}")
        print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        success, message = await process_single_url(args.url, download_dir)
        
        if success:
            print(f"\n✅ Success: {message}")
        else:
            print(f"\n❌ Failed: {message}")
    
    else:
        # Batch processing mode
        config_file = args.config
        
        if not os.path.exists(config_file):
            print(f"❌ Config file not found: {config_file}")
            print("💡 Creating sample config...")
            
            sample_config = {
                "series_name": "kiralik-ask",
                "series_name_arabic": "حب للايجار",
                "season_num": 1,
                "start_episode": 1,
                "end_episode": 89
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
        
        print(f"\n{'='*50}")
        print("🚀 Starting Batch Processing")
        print('='*50)
        print(f"📺 Series: {series_name_arabic}")
        print(f"🌐 English name: {series_name}")
        print(f"🎬 Season: {season_num}")
        print(f"📈 Episodes: {start_ep} to {end_ep} (total: {end_ep - start_ep + 1})")
        print(f"📁 Working dir: {download_dir}")
        print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Process episodes
        successful, failed, total = await process_episode_batch(
            series_name, series_name_arabic, season_num, start_ep, end_ep, download_dir
        )
        
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
