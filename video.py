#!/usr/bin/env python3
"""
Universal Video Uploader - Enhanced Version with Improved m3u8 Support
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
from urllib.parse import urlparse, urljoin, parse_qs, unquote
from html import unescape

# ===== CONFIGURATION =====
TELEGRAM_API_ID = os.environ.get("API_ID", "")
TELEGRAM_API_HASH = os.environ.get("API_HASH", "")
TELEGRAM_CHANNEL = os.environ.get("CHANNEL", "")
STRING_SESSION = os.environ.get("STRING_SESSION", "")

def validate_env():
    """Validate environment variables"""
    print("🔍 Validating environment variables...")
    
    errors = []
    if not TELEGRAM_API_ID:
        errors.append("❌ API_ID is missing")
    if not TELEGRAM_API_HASH:
        errors.append("❌ API_HASH is missing")
    if not TELEGRAM_CHANNEL:
        errors.append("❌ CHANNEL is missing")
    if not STRING_SESSION:
        errors.append("❌ STRING_SESSION is missing")
    
    if errors:
        for error in errors:
            print(error)
        return False
    
    print("✅ Environment variables validated")
    return True

if not validate_env():
    sys.exit(1)

TELEGRAM_API_ID = int(TELEGRAM_API_ID)

# Install requirements
print("📦 Installing requirements...")
requirements = ["pyrogram", "tgcrypto", "yt-dlp", "requests", "beautifulsoup4", 
                "cloudscraper", "lxml", "m3u8"]
for req in requirements:
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", req, "--quiet"])
        print(f"  ✅ {req}")
    except:
        print(f"  ⚠️ Failed to install {req}")

from pyrogram import Client
from pyrogram.errors import FloodWait
import yt_dlp
from bs4 import BeautifulSoup
import cloudscraper

app = None

# Enhanced headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
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
}

async def setup_telegram():
    """Setup Telegram client"""
    global app
    print("\n🔐 Setting up Telegram...")
    
    try:
        app = Client(
            "movie_uploader",
            api_id=TELEGRAM_API_ID,
            api_hash=TELEGRAM_API_HASH,
            session_string=STRING_SESSION.strip(),
            in_memory=True,
            device_model="GitHub Actions",
            app_version="2.0.0",
            system_version="Ubuntu 22.04"
        )
        
        await app.start()
        me = await app.get_me()
        print(f"✅ Connected as: {me.first_name} (@{me.username if me.username else 'N/A'})")
        
        # Verify channel access
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

def normalize_url(url):
    """Normalize URL"""
    if not url:
        return url
    
    # Fix common URL issues
    url = url.strip()
    url = url.replace('\\/', '/')
    url = url.replace('\\\\', '\\')
    url = url.replace('\\"', '"')
    url = unescape(url)
    
    # Ensure protocol
    if url.startswith('//'):
        url = 'https:' + url
    elif not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    return url

def get_m3u8_headers(url):
    """Get appropriate headers for m3u8 URLs based on domain"""
    headers = HEADERS.copy()
    
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    
    # Add Referer based on domain
    if 'vkvd' in domain or 'okcdn.ru' in domain:
        headers['Referer'] = 'https://vk.com/'
        headers['Origin'] = 'https://vk.com/'
    elif '1vid.online' in domain:
        headers['Referer'] = 'https://vk.com/'
        headers['Origin'] = 'https://vk.com/'
    elif 'cdnz.quest' in domain:
        headers['Referer'] = 'https://vk.com/'
        headers['Origin'] = 'https://vk.com/'
    
    return headers

def clean_m3u8_url(url):
    """Clean m3u8 URL by removing problematic parameters"""
    if not url or '.m3u8' not in url:
        return url
    
    parsed = urlparse(url)
    
    # Keep only essential parameters
    essential_params = ['t', 's', 'e', 'v', 'f', 'i', 'sp']
    query_params = parse_qs(parsed.query)
    
    # Filter parameters
    filtered_params = {}
    for param in essential_params:
        if param in query_params:
            filtered_params[param] = query_params[param][0]
    
    # Reconstruct URL
    new_query = '&'.join([f"{k}={v}" for k, v in filtered_params.items()])
    
    if new_query:
        cleaned_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"
    else:
        cleaned_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    
    print(f"🧹 Cleaned m3u8 URL: {cleaned_url[:150]}...")
    return cleaned_url

def get_best_m3u8_quality(m3u8_url):
    """Get the best available quality from m3u8 playlist"""
    print("🔍 Analyzing m3u8 playlist...")
    
    try:
        headers = get_m3u8_headers(m3u8_url)
        response = requests.get(m3u8_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Failed to fetch m3u8: HTTP {response.status_code}")
            return m3u8_url
        
        content = response.text
        
        # Check if this is a master playlist
        if '#EXT-X-STREAM-INF' in content:
            print("📊 Master playlist detected, finding available qualities...")
            
            lines = content.split('\n')
            streams = []
            current_stream = {}
            
            for line in lines:
                if line.startswith('#EXT-X-STREAM-INF'):
                    # Extract resolution
                    res_match = re.search(r'RESOLUTION=(\d+)x(\d+)', line)
                    if res_match:
                        width = int(res_match.group(1))
                        height = int(res_match.group(2))
                        current_stream = {
                            'height': height,
                            'width': width,
                            'url': None
                        }
                        
                        # Extract bandwidth if available
                        bw_match = re.search(r'BANDWIDTH=(\d+)', line)
                        if bw_match:
                            current_stream['bandwidth'] = int(bw_match.group(1))
                
                elif line and not line.startswith('#') and current_stream:
                    current_stream['url'] = line.strip()
                    
                    # Make URL absolute if relative
                    if not current_stream['url'].startswith('http'):
                        base_url = '/'.join(m3u8_url.split('/')[:-1])
                        current_stream['url'] = f"{base_url}/{current_stream['url']}"
                    
                    streams.append(current_stream.copy())
                    current_stream = {}
            
            if streams:
                # Sort by height (lowest first, but ignore too low qualities)
                streams.sort(key=lambda x: x['height'])
                
                print(f"📊 Available qualities:")
                for stream in streams:
                    quality = f"{stream['height']}p"
                    print(f"  • {quality}")
                
                # Strategy: Find minimum 240p or closest to it
                target_quality = 240
                selected_stream = None
                
                # Try to find exact 240p
                for stream in streams:
                    if stream['height'] == target_quality:
                        selected_stream = stream
                        print(f"✅ Found exact {target_quality}p quality")
                        break
                
                # If not found, find the closest higher quality
                if not selected_stream:
                    for stream in streams:
                        if stream['height'] >= target_quality:
                            selected_stream = stream
                            print(f"⚠️ No {target_quality}p found, selecting {stream['height']}p")
                            break
                
                # If still not found, take the lowest available
                if not selected_stream:
                    selected_stream = streams[0]
                    print(f"⚠️ Only {selected_stream['height']}p available")
                
                print(f"✅ Selected: {selected_stream['height']}p")
                
                # Clean the selected URL
                selected_url = clean_m3u8_url(selected_stream['url'])
                return selected_url
        
        # If not a master playlist or parsing failed, return cleaned original URL
        return clean_m3u8_url(m3u8_url)
        
    except Exception as e:
        print(f"⚠️ Error analyzing m3u8: {e}")
        return clean_m3u8_url(m3u8_url)

def extract_vk_video_enhanced(url):
    """Enhanced VK video extraction"""
    print("🔍 Enhanced VK extraction...")
    
    try:
        # Normalize VK URL
        if 'video_ext.php' not in url and 'vk.com/video' in url:
            match = re.match(r'.*vk\.com/video(\d+)_(\d+)', url)
            if match:
                oid = match.group(1)
                vid = match.group(2)
                url = f"https://vk.com/video_ext.php?oid={oid}&id={vid}"
        
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url, headers=HEADERS, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ HTTP {response.status_code}")
            return None
        
        html = response.text
        
        # First try to find mp4 URLs
        mp4_patterns = [
            r'"url(?:240|360|480|720|1080)?"\s*:\s*"([^"]+\.mp4[^"]*)"',
            r'"mp4(?:_url)?"\s*:\s*"([^"]+)"',
            r'file\s*:\s*"([^"]+\.mp4)"',
        ]
        
        for pattern in mp4_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                video_url = normalize_url(match)
                if video_url and '.mp4' in video_url:
                    print(f"✅ Found MP4 URL: {video_url[:100]}...")
                    return video_url
        
        # If no mp4 found, look for m3u8
        m3u8_patterns = [
            r'"hls"\s*:\s*"([^"]+)"',
            r'src\s*:\s*"([^"]+\.m3u8[^"]*)"',
            r'file\s*:\s*"([^"]+\.m3u8)"',
            r'https?://[^"\']+\.m3u8[^"\']*',
        ]
        
        for pattern in m3u8_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                video_url = normalize_url(match)
                if video_url and '.m3u8' in video_url:
                    print(f"✅ Found m3u8 URL: {video_url[:100]}...")
                    
                    # Clean and get best quality
                    cleaned_url = clean_m3u8_url(video_url)
                    best_url = get_best_m3u8_quality(cleaned_url)
                    
                    return best_url
        
        # Try to find in iframes
        soup = BeautifulSoup(html, 'html.parser')
        iframes = soup.find_all('iframe')
        for iframe in iframes:
            src = iframe.get('src', '')
            if src and 'http' in src:
                print(f"🔍 Found iframe: {src[:100]}...")
                iframe_url = normalize_url(src)
                # Recursive extraction from iframe
                try:
                    iframe_response = scraper.get(iframe_url, headers=HEADERS, timeout=30)
                    iframe_html = iframe_response.text
                    
                    # Look for m3u8 in iframe
                    for pattern in m3u8_patterns:
                        iframe_matches = re.findall(pattern, iframe_html, re.IGNORECASE)
                        for iframe_match in iframe_matches:
                            video_url = normalize_url(iframe_match)
                            if video_url and '.m3u8' in video_url:
                                print(f"✅ Found m3u8 in iframe: {video_url[:100]}...")
                                cleaned_url = clean_m3u8_url(video_url)
                                return cleaned_url
                except:
                    pass
        
        return None
    except Exception as e:
        print(f"⚠️ VK enhanced error: {e}")
        return None

def extract_video_url(url):
    """Main video URL extraction function"""
    print(f"\n🎬 Extracting video from: {url}")
    
    # Normalize URL
    url = normalize_url(url)
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    
    # Check if it's already a direct video URL
    if any(ext in url.lower() for ext in ['.mp4', '.m3u8', '.webm', '.avi', '.mkv']):
        print("✅ URL appears to be direct video")
        
        # If it's m3u8, clean it and get best quality
        if '.m3u8' in url.lower():
            print("🔄 Processing m3u8 URL...")
            cleaned_url = clean_m3u8_url(url)
            best_url = get_best_m3u8_quality(cleaned_url)
            return best_url
        return url
    
    # Site-specific extractors
    if 'vk.com' in domain or 'vkontakte' in domain:
        print("🔄 Using VK extractor...")
        return extract_vk_video_enhanced(url)
    
    # Generic extraction for other sites
    print("🔄 Trying generic extraction...")
    try:
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url, headers=HEADERS, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ HTTP {response.status_code}")
            return None
        
        html = response.text
        
        # Look for video URLs
        patterns = [
            r'src=["\']([^"\']+\.mp4[^"\']*)["\']',
            r'src=["\']([^"\']+\.m3u8[^"\']*)["\']',
            r'file\s*:\s*["\']([^"\']+)["\']',
            r'video\s*:\s*["\']([^"\']+)["\']',
            r'https?://[^"\']+\.mp4[^"\']*',
            r'https?://[^"\']+\.m3u8[^"\']*',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                video_url = normalize_url(match)
                if video_url:
                    print(f"✅ Found URL: {video_url[:100]}...")
                    
                    # If it's m3u8, process it
                    if '.m3u8' in video_url.lower():
                        cleaned_url = clean_m3u8_url(video_url)
                        best_url = get_best_m3u8_quality(cleaned_url)
                        return best_url
                    
                    return video_url
        
        return None
    except Exception as e:
        print(f"⚠️ Generic extraction failed: {e}")
        return None

def download_with_ytdlp(url, output_path):
    """Download video using yt-dlp with enhanced m3u8 support"""
    print("📥 Downloading with yt-dlp...")
    
    try:
        # Get appropriate headers for the URL
        headers = get_m3u8_headers(url)
        
        # Check if it's m3u8
        is_m3u8 = '.m3u8' in url.lower()
        
        if is_m3u8:
            print("🎬 Processing m3u8 stream...")
            
            # Use yt-dlp with specific options for m3u8
            ydl_opts = {
                'outtmpl': output_path,
                'format': 'bestvideo[height<=480]+bestaudio/best[height<=480]',
                'quiet': False,
                'no_warnings': False,
                'socket_timeout': 30,
                'retries': 10,
                'fragment_retries': 10,
                'skip_unavailable_fragments': True,
                'http_headers': headers,
                'extractor_args': {
                    'generic': {
                        'no_check_certificate': True,
                    }
                },
                'postprocessor_args': {
                    'ffmpeg': [
                        '-c', 'copy',
                        '-bsf:a', 'aac_adtstoasc',
                    ]
                },
            }
        else:
            # For direct URLs or other formats
            ydl_opts = {
                'outtmpl': output_path,
                'format': 'worst[height>=240]/worst',
                'quiet': False,
                'no_warnings': False,
                'socket_timeout': 30,
                'retries': 10,
                'fragment_retries': 10,
                'skip_unavailable_fragments': True,
                'http_headers': headers,
            }
        
        print(f"🎬 Downloading from: {url[:150]}...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            if info:
                height = info.get('height', 0)
                print(f"📊 Downloaded {height}p quality")
        
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path) / (1024 * 1024)
            print(f"✅ Download complete: {file_size:.1f} MB")
            return True
        else:
            print("❌ Download failed - file not created")
            return False
            
    except Exception as e:
        print(f"❌ yt-dlp download failed: {e}")
        return False

def download_fallback(url, output_path):
    """Fallback download method for m3u8"""
    print("🔄 Using ffmpeg fallback for m3u8...")
    
    try:
        headers = get_m3u8_headers(url)
        
        # Build ffmpeg command with headers
        cmd = [
            'ffmpeg',
            '-headers', f"User-Agent: {headers.get('User-Agent', HEADERS['User-Agent'])}",
        ]
        
        # Add Referer if available
        if 'Referer' in headers:
            cmd.extend(['-headers', f"Referer: {headers['Referer']}"])
        
        cmd.extend([
            '-i', url,
            '-c', 'copy',
            '-bsf:a', 'aac_adtstoasc',
            '-y',
            output_path
        ])
        
        print(f"🔄 Running ffmpeg with headers...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        
        if result.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path) / (1024 * 1024)
            print(f"✅ FFmpeg download complete: {file_size:.1f} MB")
            return True
        else:
            print(f"❌ FFmpeg failed: {result.stderr[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ FFmpeg fallback failed: {e}")
        return False

def compress_video(input_path, output_path):
    """Compress video to 240p"""
    print("🎬 Compressing video...")
    
    if not os.path.exists(input_path):
        print("❌ Input file not found")
        return False
    
    input_size = os.path.getsize(input_path) / (1024 * 1024)
    print(f"📊 Input size: {input_size:.1f} MB")
    
    # Check current resolution
    try:
        cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', 
               '-show_entries', 'stream=height', '-of', 'csv=p=0:nk=1', input_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            height = result.stdout.strip()
            if height.isdigit() and int(height) <= 240:
                print(f"📊 Video is already {height}p, no compression needed")
                shutil.copy2(input_path, output_path)
                return True
    except:
        pass
    
    # Compress to 240p
    cmd = [
        'ffmpeg',
        '-i', input_path,
        '-vf', 'scale=-2:240',
        '-c:v', 'libx264',
        '-crf', '28',
        '-preset', 'veryfast',
        '-c:a', 'aac',
        '-b:a', '64k',
        '-y',
        output_path
    ]
    
    print("🔄 Compressing...")
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    elapsed = time.time() - start_time
    
    if result.returncode == 0 and os.path.exists(output_path):
        output_size = os.path.getsize(output_path) / (1024 * 1024)
        reduction = ((input_size - output_size) / input_size) * 100 if input_size > 0 else 0
        
        print(f"✅ Compression complete in {elapsed:.1f}s")
        print(f"📊 Output size: {output_size:.1f} MB (-{reduction:.1f}%)")
        return True
    else:
        print("❌ Compression failed")
        if result.stderr:
            print(f"Error: {result.stderr[:200]}")
        return False

def create_thumbnail(input_path, output_path):
    """Create thumbnail from video"""
    try:
        print("🖼️ Creating thumbnail...")
        
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-ss', '00:00:05',
            '-vframes', '1',
            '-s', '320x180',
            '-f', 'image2',
            '-y',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and os.path.exists(output_path):
            size = os.path.getsize(output_path) / 1024
            print(f"✅ Thumbnail created ({size:.1f}KB)")
            return True
        
        return False
    except:
        return False

async def upload_to_telegram(file_path, caption, thumbnail_path=None):
    """Upload video to Telegram"""
    print("☁️ Uploading to Telegram...")
    
    try:
        # Get video info
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,duration',
            '-of', 'json',
            file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            info = json.loads(result.stdout)
            streams = info.get('streams', [])
            if streams:
                width = streams[0].get('width', 426)
                height = streams[0].get('height', 240)
                duration = int(float(streams[0].get('duration', 0)))
            else:
                width, height, duration = 426, 240, 0
        else:
            width, height, duration = 426, 240, 0
        
        # Prepare upload parameters
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
        
        print(f"📐 Video: {width}x{height}, Duration: {duration}s")
        
        # Upload with progress
        start_time = time.time()
        last_update = 0
        
        def progress(current, total):
            nonlocal last_update
            now = time.time()
            if now - last_update > 5 or current == total:
                percent = (current / total) * 100
                speed = current / (now - start_time) / 1024 if (now - start_time) > 0 else 0
                print(f"📤 Upload: {percent:.1f}% ({speed:.0f} KB/s)")
                last_update = now
        
        upload_params['progress'] = progress
        
        await app.send_video(**upload_params)
        
        elapsed = time.time() - start_time
        print(f"✅ Uploaded in {elapsed:.1f}s")
        return True
        
    except FloodWait as e:
        print(f"⏳ Flood wait: {e.value}s")
        await asyncio.sleep(e.value)
        return await upload_to_telegram(file_path, caption, thumbnail_path)
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return False

async def process_video(url, title):
    """Process a single video"""
    print(f"\n{'='*60}")
    print(f"🎬 Processing: {title}")
    print(f"🔗 URL: {url}")
    print(f"{'='*60}")
    
    # Create temp directory
    timestamp = datetime.now().strftime('%H%M%S')
    temp_dir = f"temp_{timestamp}"
    os.makedirs(temp_dir, exist_ok=True)
    
    temp_file = os.path.join(temp_dir, "video.mp4")
    final_file = os.path.join(temp_dir, "video_240p.mp4")
    thumbnail_file = os.path.join(temp_dir, "thumbnail.jpg")
    
    try:
        # Step 1: Extract video URL
        print("1️⃣ Extracting video URL...")
        video_url = extract_video_url(url)
        
        if not video_url:
            print("❌ Failed to extract video URL")
            return False, "Extraction failed"
        
        print(f"✅ Extracted URL: {video_url[:150]}...")
        
        # Step 2: Download
        print("2️⃣ Downloading...")
        
        # Try yt-dlp first
        if not download_with_ytdlp(video_url, temp_file):
            # If yt-dlp fails, try ffmpeg fallback for m3u8
            if '.m3u8' in video_url.lower():
                print("🔄 Trying ffmpeg fallback for m3u8...")
                if not download_fallback(video_url, temp_file):
                    return False, "Download failed"
            else:
                return False, "Download failed"
        
        # Check file
        if not os.path.exists(temp_file) or os.path.getsize(temp_file) < 1024:
            return False, "Downloaded file is invalid"
        
        # Step 3: Compress if needed
        print("3️⃣ Checking quality...")
        try:
            cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', 
                   '-show_entries', 'stream=height', '-of', 'csv=p=0:nk=1', temp_file]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                height = result.stdout.strip()
                if height.isdigit() and int(height) <= 240:
                    print(f"✅ Video is {height}p, no compression needed")
                    final_file = temp_file
                else:
                    print(f"📊 Video is {height}p, compressing to 240p...")
                    if not compress_video(temp_file, final_file):
                        print("⚠️ Compression failed, using original")
                        final_file = temp_file
            else:
                print("⚠️ Could not check height, trying compression...")
                if not compress_video(temp_file, final_file):
                    final_file = temp_file
        except:
            print("⚠️ Error checking quality, using original")
            final_file = temp_file
        
        # Verify final file
        if not os.path.exists(final_file):
            final_file = temp_file
        
        # Step 4: Create thumbnail
        print("4️⃣ Creating thumbnail...")
        create_thumbnail(final_file, thumbnail_file)
        
        # Step 5: Upload
        print("5️⃣ Uploading...")
        thumb = thumbnail_file if os.path.exists(thumbnail_file) else None
        
        if not await upload_to_telegram(final_file, title, thumb):
            return False, "Upload failed"
        
        # Cleanup
        try:
            shutil.rmtree(temp_dir)
            print("🗑️ Cleaned temp files")
        except:
            pass
        
        return True, "✅ Success"
        
    except Exception as e:
        # Cleanup on error
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass
        return False, f"Error: {str(e)}"

async def main():
    """Main function"""
    print("="*60)
    print("🎬 Universal Video Uploader v6.0")
    print("🌐 Enhanced m3u8 support with quality selection")
    print("🔧 Automatic parameter cleaning and header management")
    print("="*60)
    
    # Check ffmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("✅ ffmpeg is installed")
    except:
        print("❌ ffmpeg not found")
        return
    
    # Setup Telegram
    if not await setup_telegram():
        print("❌ Cannot continue without Telegram")
        return
    
    # Load config
    config_file = "video_config.json"
    if not os.path.exists(config_file):
        print("❌ Config file not found")
        return
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Error reading config: {e}")
        return
    
    videos = config.get("videos", [])
    if not videos:
        print("❌ No videos in config")
        return
    
    print(f"\n📊 Found {len(videos)} video(s)")
    
    # Process videos
    successful = 0
    for index, video in enumerate(videos, 1):
        url = video.get("url", "").strip()
        title = video.get("title", "").strip()
        
        if not url or not title:
            print(f"⚠️ Skipping video {index}: Missing data")
            continue
        
        print(f"\n[🎬 {index}/{len(videos)}] {title}")
        success, message = await process_video(url, title)
        
        if success:
            successful += 1
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
        
        # Wait between videos
        if index < len(videos):
            print("⏳ Waiting 3 seconds...")
            await asyncio.sleep(3)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"📊 Result: {successful}/{len(videos)} successful")
    
    if successful > 0:
        print("✅ Processing complete")
    else:
        print("❌ All videos failed")
    
    # Cleanup
    if app:
        await app.stop()
        print("🔌 Disconnected")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Stopped")
    except Exception as e:
        print(f"\n💥 Error: {e}")
        import traceback
        traceback.print_exc()
