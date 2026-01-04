#!/usr/bin/env python3
"""
Universal Video Downloader & Uploader - Complete Version
Works with any video website
Download in 240p quality
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
import base64
import json
from datetime import datetime
from urllib.parse import urlparse, parse_qs, unquote

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
    'Referer': 'https://filemoon.sx/',
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
        "lxml>=4.9.0",
        "cloudscraper>=1.2.71",
        "m3u8>=6.0.0",
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
import cloudscraper
import m3u8

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

def extract_from_filemoon_with_network(video_page_url):
    """Extract video from filemoon.sx by mimicking browser network requests"""
    try:
        scraper = cloudscraper.create_scraper()
        
        print("🌐 Fetching filemoon page...")
        response = scraper.get(video_page_url, headers=HEADERS, timeout=30)
        
        if response.status_code != 200:
            print(f"⚠️ HTTP {response.status_code}")
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Method 1: Look for jwplayer setup
        print("🔍 Searching for JW Player configuration...")
        
        # Look for script with jwplayer setup
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string:
                content = script.string
                
                # Look for setupConfig or similar
                if 'setup(' in content or 'jwplayer(' in content:
                    print("🎬 Found JW Player script")
                    
                    # Try to find sources array
                    sources_patterns = [
                        r'sources\s*:\s*(\[[^\]]+\])',
                        r'file\s*:\s*["\']([^"\']+)["\']',
                        r'"sources"\s*:\s*(\[[^\]]+\])',
                        r'"file"\s*:\s*["\']([^"\']+)["\']',
                    ]
                    
                    for pattern in sources_patterns:
                        matches = re.findall(pattern, content, re.DOTALL)
                        if matches:
                            for match in matches:
                                if match.startswith('['):
                                    # It's a JSON array
                                    try:
                                        sources = json.loads(match)
                                        for source in sources:
                                            if isinstance(source, dict) and 'file' in source:
                                                video_url = source['file']
                                                if video_url and '.m3u8' in video_url:
                                                    print(f"✅ Found HLS stream in sources")
                                                    return video_url
                                            elif isinstance(source, str) and '.m3u8' in source:
                                                print(f"✅ Found HLS stream")
                                                return source
                                    except:
                                        pass
                                elif '.m3u8' in match:
                                    print(f"✅ Found HLS stream")
                                    return match
        
        # Method 2: Look for m3u8 URLs in the page
        print("🔍 Searching for m3u8 URLs...")
        
        # Search for m3u8 patterns
        m3u8_patterns = [
            r'https?://[^\s"\']+\.m3u8[^\s"\']*',
            r'"([^"]+\.m3u8[^"]*)"',
            r"'([^']+\.m3u8[^']*)'",
        ]
        
        for pattern in m3u8_patterns:
            matches = re.findall(pattern, response.text)
            for match in matches:
                if 'master.m3u8' in match or 'index.m3u8' in match:
                    print(f"✅ Found m3u8 playlist: {match[:100]}...")
                    return match
        
        # Method 3: Check for common CDN patterns
        print("🔍 Searching for CDN patterns...")
        
        cdn_patterns = [
            r'https?://[^/]+/hls2/[^"\']+\.m3u8[^"\']*',
            r'https?://[^/]+/stream/[^"\']+\.m3u8[^"\']*',
            r'https?://[^/]+/video/[^"\']+\.m3u8[^"\']*',
        ]
        
        for pattern in cdn_patterns:
            matches = re.findall(pattern, response.text)
            if matches:
                print(f"✅ Found CDN stream: {matches[0][:100]}...")
                return matches[0]
        
        # Method 4: Look for iframe and check its content
        print("🔍 Checking iframes...")
        iframes = soup.find_all('iframe')
        for iframe in iframes:
            if iframe.get('src'):
                iframe_url = iframe['src']
                if iframe_url.startswith('//'):
                    iframe_url = 'https:' + iframe_url
                
                print(f"📺 Checking iframe: {iframe_url[:100]}...")
                
                try:
                    iframe_response = scraper.get(iframe_url, headers=HEADERS, timeout=30)
                    
                    # Search for m3u8 in iframe
                    for pattern in m3u8_patterns:
                        iframe_matches = re.findall(pattern, iframe_response.text)
                        for match in iframe_matches:
                            if '.m3u8' in match:
                                print(f"✅ Found m3u8 in iframe")
                                return match
                except:
                    continue
        
        return None
        
    except Exception as e:
        print(f"⚠️ filemoon extraction error: {e}")
        return None

def get_lowest_quality_m3u8(m3u8_url):
    """Get the lowest quality stream from m3u8 playlist (240p if available)"""
    try:
        print("🔍 Looking for lowest quality stream in m3u8...")
        
        response = requests.get(m3u8_url, headers=HEADERS, timeout=30)
        if response.status_code != 200:
            return m3u8_url
        
        m3u8_content = response.text
        
        # Check if this is a master playlist with multiple quality options
        if '#EXT-X-STREAM-INF' in m3u8_content:
            # Parse the master playlist
            lines = m3u8_content.split('\n')
            
            # Find all streams with their resolutions
            streams = []
            current_stream = {}
            
            for i, line in enumerate(lines):
                if line.startswith('#EXT-X-STREAM-INF'):
                    # Parse resolution from line
                    resolution_match = re.search(r'RESOLUTION=(\d+)x(\d+)', line)
                    if resolution_match:
                        width = int(resolution_match.group(1))
                        height = int(resolution_match.group(2))
                        current_stream = {'height': height, 'line_index': i}
                elif line and not line.startswith('#') and current_stream:
                    current_stream['url'] = line
                    
                    # Make relative URL absolute if needed
                    if not current_stream['url'].startswith('http'):
                        base_url = '/'.join(m3u8_url.split('/')[:-1])
                        current_stream['url'] = f"{base_url}/{current_stream['url']}"
                    
                    streams.append(current_stream.copy())
                    current_stream = {}
            
            if streams:
                # Sort by height (quality) - lowest first
                streams.sort(key=lambda x: x['height'])
                
                # Try to find 240p stream
                for stream in streams:
                    if stream['height'] == 240:
                        print(f"✅ Found 240p stream")
                        return stream['url']
                
                # If no 240p, get the lowest available
                print(f"✅ Using lowest available: {streams[0]['height']}p")
                return streams[0]['url']
        
        return m3u8_url
        
    except Exception as e:
        print(f"⚠️ Error parsing m3u8: {e}")
        return m3u8_url

def extract_video_url(video_page_url):
    """Extract video URL from any website using multiple methods"""
    try:
        parsed_url = urlparse(video_page_url)
        domain = parsed_url.netloc
        
        print(f"🌐 Extracting from: {domain}")
        
        # Special handling for filemoon.sx
        if 'filemoon.sx' in domain or 'filemoon' in domain:
            print("🔍 Using filemoon.sx specific extractor...")
            video_url = extract_from_filemoon_with_network(video_page_url)
            if video_url:
                # If it's a relative URL, make it absolute
                if video_url.startswith('//'):
                    video_url = 'https:' + video_url
                elif video_url.startswith('/'):
                    parsed = urlparse(video_page_url)
                    video_url = f'{parsed.scheme}://{parsed.netloc}{video_url}'
                
                # If it's an m3u8 URL, try to get lowest quality
                if '.m3u8' in video_url:
                    print("🎬 Found HLS stream, looking for 240p...")
                    video_url = get_lowest_quality_m3u8(video_url)
                
                # Add referer if not present
                if '?' not in video_url:
                    video_url += '?'
                if 'referer=' not in video_url:
                    video_url += '&referer=https://filemoon.sx/'
                
                print(f"✅ Found video URL: {video_url[:100]}...")
                return video_url, "✅ URL extracted from filemoon.sx"
        
        # Try yt-dlp for other sites with 240p preference
        print("🔍 Trying yt-dlp extraction (preferring 240p)...")
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'ignoreerrors': True,
                'user_agent': USER_AGENT,
                'http_headers': HEADERS,
                'referer': video_page_url,
                'format': 'best[height<=240]/worst',  # Prefer 240p or lower
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_page_url, download=False)
                
                if info:
                    # Get the format that was selected
                    if 'format_id' in info:
                        print(f"✅ Selected format: {info['format_id']}")
                    
                    # Get the URL
                    if 'url' in info:
                        video_url = info['url']
                        print(f"✅ Found direct URL via yt-dlp")
                        return video_url, "✅ URL extracted via yt-dlp (240p preferred)"
                    
                    # Check for formats
                    elif 'formats' in info:
                        formats = info['formats']
                        for fmt in formats:
                            if fmt.get('height', 0) <= 240:
                                video_url = fmt['url']
                                print(f"✅ Found 240p format via yt-dlp")
                                return video_url, "✅ URL extracted via yt-dlp (240p)"
                        
                        # Fallback to first format
                        if formats:
                            video_url = formats[0]['url']
                            print(f"✅ Found format via yt-dlp (fallback)")
                            return video_url, "✅ URL extracted via yt-dlp"
        except Exception as e:
            print(f"⚠️ yt-dlp extraction failed: {e}")
        
        # General HTML extraction
        print("🔍 Trying general HTML extraction...")
        try:
            scraper = cloudscraper.create_scraper()
            response = scraper.get(video_page_url, headers=HEADERS, timeout=30)
            
            if response.status_code != 200:
                return None, f"HTTP {response.status_code}"
            
            # Search for m3u8 patterns
            m3u8_patterns = [
                r'https?://[^\s"\']+\.m3u8[^\s"\']*',
                r'"([^"]+\.m3u8[^"]*)"',
                r"'([^']+\.m3u8[^']*)'",
            ]
            
            for pattern in m3u8_patterns:
                matches = re.findall(pattern, response.text)
                for match in matches:
                    if '.m3u8' in match:
                        video_url = match
                        # Make absolute URL if needed
                        if video_url.startswith('//'):
                            video_url = 'https:' + video_url
                        elif video_url.startswith('/'):
                            video_url = f'https://{domain}{video_url}'
                        
                        # Try to get lowest quality
                        if '.m3u8' in video_url:
                            video_url = get_lowest_quality_m3u8(video_url)
                        
                        print(f"✅ Found video stream: {video_url[:100]}...")
                        return video_url, "✅ URL extracted from HTML"
            
            # Look for video elements
            soup = BeautifulSoup(response.text, 'html.parser')
            video_tags = soup.find_all(['video', 'iframe', 'source'])
            
            for tag in video_tags:
                src = None
                
                if tag.name == 'video' and tag.get('src'):
                    src = tag['src']
                elif tag.name == 'iframe' and tag.get('src'):
                    src = tag['src']
                elif tag.name == 'source' and tag.get('src'):
                    src = tag['src']
                
                if src and ('.mp4' in src.lower() or '.m3u8' in src.lower()):
                    # Make absolute URL
                    if src.startswith('//'):
                        src = 'https:' + src
                    elif src.startswith('/'):
                        src = f'https://{domain}' + src
                    elif not src.startswith('http'):
                        src = f'https://{domain}/{src}'
                    
                    print(f"✅ Found video source: {src[:80]}...")
                    return src, "✅ URL extracted from HTML"
        
        except Exception as e:
            print(f"⚠️ HTML extraction failed: {e}")
        
        return None, "❌ Could not extract video URL"
        
    except Exception as e:
        return None, f"❌ Error: {str(e)}"

def download_hls_stream(m3u8_url, output_path):
    """Download HLS stream using ffmpeg with 240p output"""
    try:
        print(f"📥 Downloading HLS stream at 240p...")
        
        # Use ffmpeg to download and convert to 240p directly
        cmd = [
            'ffmpeg',
            '-i', m3u8_url,
            '-vf', 'scale=-2:240',  # Scale to 240p
            '-c:v', 'libx264',
            '-crf', '28',  # Good quality for 240p
            '-preset', 'fast',
            '-c:a', 'aac',
            '-b:a', '64k',  # Lower audio bitrate for 240p
            '-y',
            output_path
        ]
        
        start = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(output_path):
            elapsed = time.time() - start
            size = os.path.getsize(output_path) / (1024*1024)
            print(f"✅ HLS stream downloaded at 240p in {elapsed:.1f}s ({size:.1f}MB)")
            return True
        else:
            print(f"❌ HLS download failed")
            if result.stderr:
                print(f"Error: {result.stderr[:200]}")
            
            # Fallback: download and then compress
            print("🔄 Trying alternative method: download then compress...")
            temp_file = output_path + '.temp.mp4'
            
            # Download without processing
            cmd2 = [
                'ffmpeg',
                '-i', m3u8_url,
                '-c', 'copy',
                '-bsf:a', 'aac_adtstoasc',
                '-y',
                temp_file
            ]
            
            result2 = subprocess.run(cmd2, capture_output=True, text=True)
            if result2.returncode == 0 and os.path.exists(temp_file):
                # Now compress to 240p
                return compress_video(temp_file, output_path, is_temp=True)
            return False
            
    except Exception as e:
        print(f"❌ HLS download error: {e}")
        return False

def download_video(url, output_path):
    """Download video using appropriate method based on URL"""
    try:
        print(f"📥 Downloading from: {url[:100]}...")
        
        # Check if it's an HLS stream
        if '.m3u8' in url:
            return download_hls_stream(url, output_path)
        
        # Otherwise use yt-dlp with 240p preference
        ydl_opts = {
            'format': 'best[height<=240]/worst',  # Prefer 240p or lowest
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'user_agent': USER_AGENT,
            'http_headers': HEADERS,
            'retries': 5,
            'fragment_retries': 5,
            'skip_unavailable_fragments': True,
            'socket_timeout': 30,
            'noprogress': True,
            'referer': 'https://filemoon.sx/',
        }
        
        start = time.time()
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            print(f"❌ yt-dlp download failed: {e}")
            
            # Try direct download for non-streaming content
            if not url.endswith('.m3u8'):
                try:
                    response = requests.get(url, headers=HEADERS, stream=True, timeout=60)
                    if response.status_code == 200:
                        total_size = int(response.headers.get('content-length', 0))
                        
                        with open(output_path, 'wb') as f:
                            downloaded = 0
                            chunk_size = 8192
                            
                            for chunk in response.iter_content(chunk_size=chunk_size):
                                if chunk:
                                    f.write(chunk)
                                    downloaded += len(chunk)
                            
                            print(f"  ✅ Direct download complete")
                    else:
                        print(f"❌ Direct download failed: HTTP {response.status_code}")
                        return False
                except Exception as e2:
                    print(f"❌ Direct download error: {e2}")
                    return False
        
        elapsed = time.time() - start
        
        if os.path.exists(output_path):
            size = os.path.getsize(output_path) / (1024*1024)
            if size > 0.1:  # At least 100KB
                print(f"✅ Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
                return True
        
        # Try different extensions
        base = os.path.splitext(output_path)[0]
        for ext in ['.mp4', '.mkv', '.webm', '.avi', '.flv', '.mov']:
            alt_file = base + ext
            if os.path.exists(alt_file) and os.path.getsize(alt_file) > 1024:
                shutil.move(alt_file, output_path)
                size = os.path.getsize(output_path) / (1024*1024)
                print(f"✅ Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
                return True
        
        return False
        
    except Exception as e:
        print(f"❌ Download error: {e}")
        return False

def compress_video(input_file, output_file, is_temp=False):
    """Compress video to 240p (same as original script)"""
    if not os.path.exists(input_file):
        print(f"❌ File not found: {input_file}")
        return False
    
    file_size = os.path.getsize(input_file) / (1024 * 1024)
    print(f"📊 Original file size: {file_size:.1f}MB")
    
    if file_size < 1:  # Less than 1MB
        print("❌ File is too small (probably not a video)")
        return False
    
    # Check if it's actually a video file
    try:
        cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=codec_name,height', '-of', 'default=noprint_wrappers=1:nokey=1', input_file]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            output = result.stdout.strip()
            if output:
                parts = output.split('\n')
                if len(parts) >= 2:
                    height = int(parts[1]) if parts[1].isdigit() else 0
                    if height <= 240:
                        print(f"📊 File is already {height}p, copying without compression")
                        shutil.copy2(input_file, output_file)
                        if is_temp:
                            os.remove(input_file)
                        return True
    except:
        pass
    
    print(f"🎬 Compressing video to 240p...")
    
    # Use same settings as original script
    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-vf', 'scale=-2:240',  # Scale to 240p
        '-c:v', 'libx264',
        '-crf', '28',  # Same as original
        '-preset', 'veryfast',  # Same as original
        '-c:a', 'aac',
        '-b:a', '64k',  # Same as original
        '-y',
        output_file
    ]
    
    try:
        start = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(output_file):
            new_size = os.path.getsize(output_file) / (1024 * 1024)
            elapsed = time.time() - start
            
            if new_size > 1:  # At least 1MB
                reduction = ((file_size - new_size) / file_size) * 100 if file_size > 0 else 0
                print(f"✅ Compressed to 240p in {elapsed:.1f}s")
                print(f"📊 New size: {new_size:.1f}MB (-{reduction:.1f}%)")
                
                # Clean up temp file if needed
                if is_temp:
                    os.remove(input_file)
                return True
            else:
                print("❌ Compressed file is too small")
                shutil.copy2(input_file, output_file)
                if is_temp:
                    os.remove(input_file)
                return True
        else:
            print(f"❌ Compression failed, using original")
            shutil.copy2(input_file, output_file)
            if is_temp:
                os.remove(input_file)
            return True
    except Exception as e:
        print(f"❌ Compression error: {e}, using original")
        shutil.copy2(input_file, output_file)
        if is_temp:
            os.remove(input_file)
        return True

# ... [rest of the functions remain the same as previous version] ...

def create_thumbnail(input_file, thumbnail_path):
    """Create thumbnail from video"""
    try:
        print(f"🖼️ Creating thumbnail...")
        
        # First check if file is valid
        if not os.path.exists(input_file) or os.path.getsize(input_file) < 1024:
            print("❌ Video file is too small or invalid")
            return False
        
        # Try to get thumbnail from middle
        cmd = [
            'ffmpeg',
            '-i', input_file,
            '-ss', '00:01:00',
            '-vframes', '1',
            '-s', '320x180',  # Same as original
            '-f', 'image2',
            '-y',
            thumbnail_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and os.path.exists(thumbnail_path):
            size = os.path.getsize(thumbnail_path) / 1024
            if size > 1:  # At least 1KB
                print(f"✅ Thumbnail created ({size:.1f}KB)")
                return True
        
        # Try from beginning
        cmd[4] = '00:00:05'
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and os.path.exists(thumbnail_path):
            size = os.path.getsize(thumbnail_path) / 1024
            if size > 1:
                print(f"✅ Thumbnail created ({size:.1f}KB)")
                return True
        
        # Try from 30 seconds
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
    
    return 426, 240  # Default for 240p (same as original)

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
    print(f"🎯 Target quality: 240p")
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
        print("🔍 Extracting video URL (preferring 240p)...")
        direct_video_url, message = extract_video_url(video_url)
        
        if not direct_video_url:
            print(f"❌ {message}")
            
            # Try manual extraction for filemoon.sx
            if 'filemoon.sx' in video_url:
                print("🔄 Trying manual extraction for filemoon.sx...")
                
                # Try common patterns based on your network analysis
                video_id = video_url.split('/')[-1]
                possible_urls = [
                    f"https://be4235.rcr32.ams02.i8yz83pn.com/hls2/07/07294/{video_id}_h/master.m3u8",
                    f"https://be4235.rcr32.ams02.i8yz83pn.com/hls2/07/07294/{video_id}_h/index.m3u8",
                ]
                
                for test_url in possible_urls:
                    print(f"🔄 Testing: {test_url}")
                    try:
                        response = requests.head(test_url, headers=HEADERS, timeout=10)
                        if response.status_code == 200:
                            direct_video_url = test_url
                            print(f"✅ Found video URL manually")
                            break
                    except:
                        continue
            
            if not direct_video_url:
                return False, "URL extraction failed"
        
        print(f"✅ {message}")
        print(f"📎 Direct URL: {direct_video_url[:100]}...")
        
        # 2. Download
        print("📥 Downloading video at 240p...")
        if not download_video(direct_video_url, final_file):
            return False, "Download failed"
        
        # Check if download was successful
        if not os.path.exists(final_file) or os.path.getsize(final_file) < 1024:
            print("❌ Downloaded file is too small or doesn't exist")
            return False, "Downloaded file is invalid"
        
        # 3. Create thumbnail
        print("🖼️ Creating thumbnail...")
        create_thumbnail(final_file, thumbnail_file)
        
        # 4. Upload
        caption = video_title
        thumb = thumbnail_file if os.path.exists(thumbnail_file) else None
        
        print("☁️ Uploading to Telegram...")
        if await upload_video(final_file, caption, thumb):
            # 5. Clean up
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
    print("🎬 Universal Video Processor v5.0")
    print("🎯 Target quality: 240p")
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
                    "url": "https://filemoon.sx/e/swm1uivboqix",
                    "title": "اكس مراتي - الفيلم الكامل"
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
    print(f"🎯 Target quality: 240p")
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
        
        # Wait between videos
        if index < total:
            wait_time = 3
            print(f"⏳ Waiting {wait_time} seconds before next video...")
            await asyncio.sleep(wait_time)
    
    # Results summary
    print(f"\n{'='*50}")
    print("📊 Processing Summary")
    print('='*50)
    print(f"✅ Successful: {successful}/{total}")
    print(f"❌ Failed: {len(failed)}")
    
    if successful == total:
        print("🎉 All videos processed successfully at 240p!")
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
