#!/usr/bin/env python3
"""
Universal Video Uploader - For Movies
Download 240p minimum quality then compress to 240p
Fixed URL issues with yt-dlp download
Enhanced upload settings
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
import threading
from datetime import datetime
from urllib.parse import urlparse, urljoin, quote

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
requirements = ["pyrogram", "tgcrypto", "yt-dlp", "requests", "beautifulsoup4", "cloudscraper"]
for req in requirements:
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", req, "--quiet"])
        print(f"  ✅ {req}")
    except:
        print(f"  ❌ {req}")

from pyrogram import Client
from pyrogram.errors import FloodWait
import yt_dlp
from bs4 import BeautifulSoup
import cloudscraper

app = None

# Headers for VK
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Referer': 'https://vk.com/',
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

def clean_vk_url(url):
    """Clean VK URL from escape characters and fix common issues"""
    if not url:
        return url
    
    # Remove backslashes first
    url = url.replace('\\/', '/').replace('\\\\', '\\')
    url = url.replace('\\"', '"').replace("\\'", "'")
    
    # Fix https://
    if url.startswith('https:\\/\\/'):
        url = url.replace('https:\\/\\/', 'https://')
    elif url.startswith('http:\\/\\/'):
        url = url.replace('http:\\/\\/', 'http://')
    
    # Fix double slashes in URL path (important fix)
    parsed = urlparse(url)
    
    # Reconstruct URL with proper slashes
    if parsed.netloc:
        # Fix path to remove double slashes
        path = parsed.path.replace('//', '/')
        # Reconstruct URL
        url = f"{parsed.scheme}://{parsed.netloc}{path}"
        if parsed.query:
            url += f"?{parsed.query}"
    
    # Remove trailing dot if present
    if url.endswith('.'):
        url = url[:-1]
    
    return url.strip()

def fix_cdn_url(url):
    """Fix CDN URLs that have incorrect formatting"""
    if not url:
        return url
    
    # Fix double slashes after domain
    if '//' in url:
        # Only fix after the protocol part
        parts = url.split('://')
        if len(parts) == 2:
            protocol = parts[0]
            rest = parts[1]
            # Fix multiple slashes in path
            rest = rest.replace('//', '/')
            url = f"{protocol}://{rest}"
    
    return url

def get_minimum_240p_m3u8(m3u8_url):
    """Get minimum 240p stream from m3u8 playlist (ignore 144p)"""
    print("🔍 Looking for minimum 240p quality in m3u8...")
    
    try:
        # Fix URL first
        m3u8_url = clean_vk_url(m3u8_url)
        m3u8_url = fix_cdn_url(m3u8_url)
        
        # Add referer header for VK
        headers = HEADERS.copy()
        headers['Referer'] = 'https://vk.com/'
        
        # Fetch the m3u8 playlist
        print(f"📥 Fetching playlist from: {m3u8_url[:100]}...")
        response = requests.get(m3u8_url, headers=headers, timeout=30)
        if response.status_code != 200:
            print(f"⚠️ Failed to fetch playlist: HTTP {response.status_code}")
            return m3u8_url
        
        m3u8_content = response.text
        
        # Check if this is a master playlist with multiple qualities
        if '#EXT-X-STREAM-INF' in m3u8_content:
            print("🎬 Found multiple qualities in master playlist")
            
            # Parse the playlist
            lines = m3u8_content.split('\n')
            streams = []
            current_stream = {}
            
            for i, line in enumerate(lines):
                if line.startswith('#EXT-X-STREAM-INF'):
                    # Extract resolution
                    res_match = re.search(r'RESOLUTION=(\d+)x(\d+)', line)
                    if res_match:
                        width = int(res_match.group(1))
                        height = int(res_match.group(2))
                        current_stream = {
                            'height': height,
                            'width': width,
                            'bandwidth': 0,
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
                # Sort by height (lowest first)
                streams.sort(key=lambda x: x['height'])
                
                print(f"📊 Available qualities:")
                for stream in streams:
                    quality = f"{stream['height']}p"
                    bandwidth_kbps = stream['bandwidth'] / 1000 if stream['bandwidth'] > 0 else 'N/A'
                    print(f"  • {quality} (Bandwidth: {bandwidth_kbps}kbps)")
                
                # Strategy: Find minimum 240p or higher, ignore 144p
                selected_stream = None
                
                # First, try to find 240p exactly
                for stream in streams:
                    if stream['height'] == 240:
                        selected_stream = stream
                        print(f"✅ Found exact 240p quality")
                        break
                
                # If no 240p, find the next higher quality (ignoring 144p)
                if not selected_stream:
                    for stream in streams:
                        if stream['height'] > 144:  # Ignore 144p
                            selected_stream = stream
                            print(f"⚠️ No 240p found, selecting {stream['height']}p (ignoring 144p)")
                            break
                
                # If still no stream found (only 144p available), take 144p
                if not selected_stream:
                    selected_stream = streams[0]  # This will be 144p
                    print(f"⚠️ Only 144p available, selecting it as last resort")
                
                print(f"✅ Selected: {selected_stream['height']}p")
                return selected_stream['url']
        
        return m3u8_url
        
    except Exception as e:
        print(f"⚠️ Error parsing m3u8: {e}")
        return m3u8_url

def extract_vk_video_url(video_page_url):
    """Extract video URL from VK.com specifically"""
    print("🔍 Using VK.com specific extractor...")
    
    try:
        # Create a scraper to bypass Cloudflare
        scraper = cloudscraper.create_scraper()
        
        # Fetch the page
        print("🌐 Fetching VK page...")
        response = scraper.get(video_page_url, headers=HEADERS, timeout=30)
        
        if response.status_code != 200:
            print(f"⚠️ HTTP {response.status_code}")
            return None
        
        # Look for JSON data with video URLs
        print("🔍 Searching for video URLs...")
        
        # Try to find video URLs in the page
        video_patterns = [
            r'"hls":"([^"]+)"',
            r'"url[0-9]+":"([^"]+)"',
            r'video_url":"([^"]+)"',
            r'src="([^"]+\.m3u8[^"]*)"',
            r'\\"url\\":\\"([^\\\\"]+)\\"',
        ]
        
        for pattern in video_patterns:
            matches = re.findall(pattern, response.text)
            for match in matches:
                if match and ('http' in match or '.m3u8' in match):
                    url = clean_vk_url(match)
                    url = fix_cdn_url(url)
                    
                    if url and '.m3u8' in url:
                        print(f"🔧 Found m3u8 URL: {url[:80]}...")
                        # Try to get minimum 240p quality from m3u8
                        video_url = get_minimum_240p_m3u8(url)
                        if video_url:
                            return video_url
        
        # Try to extract from iframe
        print("🔍 Searching for iframe...")
        soup = BeautifulSoup(response.text, 'html.parser')
        iframe = soup.find('iframe')
        
        if iframe and iframe.get('src'):
            iframe_url = iframe['src']
            if iframe_url.startswith('//'):
                iframe_url = 'https:' + iframe_url
            
            print(f"📺 Found iframe, checking content...")
            try:
                iframe_response = scraper.get(iframe_url, headers=HEADERS, timeout=30)
                
                # Search in iframe
                for pattern in video_patterns:
                    matches = re.findall(pattern, iframe_response.text)
                    for match in matches:
                        if match and ('http' in match or '.m3u8' in match):
                            url = clean_vk_url(match)
                            url = fix_cdn_url(url)
                            if url and '.m3u8' in url:
                                video_url = get_minimum_240p_m3u8(url)
                                if video_url:
                                    print(f"✅ Found URL in iframe")
                                    return video_url
            except Exception as e:
                print(f"⚠️ Iframe error: {e}")
        
        print("❌ No video URL found")
        return None
        
    except Exception as e:
        print(f"⚠️ VK extraction error: {e}")
        import traceback
        traceback.print_exc()
        return None

def extract_video_url(url):
    """Extract direct video URL with minimum 240p quality"""
    print(f"🔍 Extracting from: {url}")
    
    # Check if it's VK
    parsed_url = urlparse(url)
    if 'vk.com' in parsed_url.netloc or 'vkontakte' in parsed_url.netloc:
        return extract_vk_video_url(url)
    
    # For other sites, try yt-dlp with minimum 240p quality
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'worst[height>=240][height<=360]/worst[height>=240]/worst',
            'socket_timeout': 30,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info and 'url' in info:
                video_url = info['url']
                # Check if we got the right quality
                if 'height' in info and info['height']:
                    print(f"✅ Found {info['height']}p URL via yt-dlp")
                else:
                    print(f"✅ Found URL via yt-dlp (quality unknown)")
                return video_url
    except Exception as e:
        print(f"⚠️ yt-dlp failed: {e}")
    
    return None

def download_with_ytdlp(url, output_path):
    """Download video using yt-dlp with minimum 240p quality"""
    print("📥 Downloading with yt-dlp (minimum 240p)...")
    
    try:
        ydl_opts = {
            'outtmpl': output_path,
            'format': 'worst[height>=240][height<=360]/worst[height>=240]/worst',
            'quiet': False,
            'no_warnings': False,
            'socket_timeout': 30,
            'retries': 3,
            'fragment_retries': 3,
            'skip_unavailable_fragments': True,
            'http_headers': HEADERS,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"🔗 Downloading from: {url[:100]}...")
            info = ydl.extract_info(url, download=True)
            
            # Log the quality we downloaded
            if info and 'height' in info and info['height']:
                print(f"📊 Downloaded {info['height']}p quality")
            
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

def download_alternative(url, output_path):
    """Alternative download method using requests"""
    print("🔄 Using alternative download method...")
    
    try:
        headers = HEADERS.copy()
        response = requests.get(url, headers=headers, stream=True, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ HTTP {response.status_code}")
            return False
        
        total_size = int(response.headers.get('content-length', 0))
        
        print(f"📥 Downloading {total_size / (1024*1024):.1f} MB...")
        
        with open(output_path, 'wb') as f:
            downloaded = 0
            start_time = time.time()
            chunk_size = 8192
            
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # Update progress every 5MB
                    if downloaded % (5 * 1024 * 1024) < chunk_size:
                        elapsed = time.time() - start_time
                        speed = downloaded / elapsed / 1024 if elapsed > 0 else 0
                        
                        downloaded_mb = downloaded / (1024 * 1024)
                        print(f"📥 {downloaded_mb:.1f} MB - {speed:.0f} KB/s")
        
        elapsed = time.time() - start_time
        final_size = os.path.getsize(output_path) / (1024 * 1024)
        print(f"✅ Alternative download complete: {final_size:.1f} MB in {elapsed:.1f}s")
        
        return final_size > 1
        
    except Exception as e:
        print(f"❌ Alternative download failed: {e}")
        return False

def compress_to_240p(input_path, output_path):
    """Compress video to 240p with original settings"""
    print("🎬 Compressing to 240p...")
    
    if not os.path.exists(input_path):
        print("❌ Input file not found")
        return False
    
    input_size = os.path.getsize(input_path) / (1024 * 1024)
    print(f"📊 Input size: {input_size:.1f} MB")
    
    # Check if already 240p or lower
    try:
        cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', 
               '-show_entries', 'stream=height', '-of', 'csv=p=0:nk=1', input_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            height = result.stdout.strip()
            if height.isdigit() and int(height) <= 240:
                print(f"📊 Video is already {height}p, copying without compression")
                shutil.copy2(input_path, output_path)
                return True
    except:
        pass
    
    # Compress using same settings as original script
    cmd = [
        'ffmpeg',
        '-i', input_path,
        '-vf', 'scale=-2:240',  # Scale to 240p height
        '-c:v', 'libx264',
        '-crf', '28',  # Same as original
        '-preset', 'veryfast',  # Same as original
        '-c:a', 'aac',
        '-b:a', '64k',  # Same as original
        '-y',
        output_path
    ]
    
    print("🔄 Starting compression...")
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)  # 1 hour timeout
    
    elapsed = time.time() - start_time
    
    if result.returncode == 0 and os.path.exists(output_path):
        output_size = os.path.getsize(output_path) / (1024 * 1024)
        reduction = ((input_size - output_size) / input_size) * 100 if input_size > 0 else 0
        
        print(f"✅ Compression complete in {elapsed:.1f}s")
        print(f"📊 Output size: {output_size:.1f} MB (-{reduction:.1f}%)")
        
        # Verify output file
        if output_size < 1:  # Less than 1MB
            print("⚠️ Output file too small, using input file")
            shutil.copy2(input_path, output_path)
        
        return True
    else:
        print("❌ Compression failed, using original file")
        if result.stderr:
            print(f"Error: {result.stderr[:200]}")
        shutil.copy2(input_path, output_path)
        return True

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

async def upload_to_telegram(file_path, caption, thumbnail_path=None):
    """Upload to Telegram channel with enhanced settings"""
    print(f"☁️ Uploading: {os.path.basename(file_path)}")
    
    # Get file size
    file_size = os.path.getsize(file_path) / (1024*1024)
    print(f"📊 File size: {file_size:.1f} MB")
    
    try:
        # Get video dimensions
        width, height = get_video_dimensions(file_path)
        
        # Get duration
        duration = get_video_duration(file_path)
        
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
        
        # Add thumbnail if available
        if thumbnail_path and os.path.exists(thumbnail_path):
            upload_params['thumb'] = thumbnail_path
            print(f"🖼️ Using thumbnail: {os.path.basename(thumbnail_path)}")
        
        print(f"📐 Video dimensions: {width}x{height}")
        print(f"⏱️ Duration: {duration} seconds")
        print(f"🎬 Streaming: Enabled (pauses on exit)")
        
        # Upload with progress
        start_time = time.time()
        last_percent = 0
        
        def progress(current, total):
            nonlocal last_percent
            percent = (current / total) * 100
            if percent - last_percent >= 10 or percent == 100:
                speed = current / (time.time() - start_time) / 1024 if (time.time() - start_time) > 0 else 0
                print(f"📤 {percent:.0f}% - {speed:.0f} KB/s")
                last_percent = percent
        
        upload_params['progress'] = progress
        
        await app.send_video(**upload_params)
        
        elapsed = time.time() - start_time
        print(f"✅ Uploaded in {elapsed:.1f} seconds")
        return True
        
    except FloodWait as e:
        print(f"⏳ Flood wait: {e.value} seconds")
        await asyncio.sleep(e.value)
        return await upload_to_telegram(file_path, caption, thumbnail_path)
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        # Try without progress
        try:
            if 'progress' in upload_params:
                upload_params.pop('progress')
            await app.send_video(**upload_params)
            print("✅ Upload successful (without progress)")
            return True
        except Exception as e2:
            print(f"❌ Retry failed: {e2}")
            return False

async def process_movie(video_url, video_title):
    """Process a single movie - download minimum 240p then compress"""
    print(f"\n{'─'*50}")
    print(f"🎬 Processing: {video_title}")
    print(f"🎯 Strategy: Download minimum 240p → Compress to 240p")
    print(f"⚠️  Note: Will ignore 144p if 240p or higher is available")
    print(f"🔗 URL: {video_url}")
    print(f"{'─'*50}")
    
    # Create temp directory
    timestamp = datetime.now().strftime('%H%M%S')
    temp_dir = f"temp_movie_{timestamp}"
    os.makedirs(temp_dir, exist_ok=True)
    
    # Define file paths
    temp_file = os.path.join(temp_dir, "temp_video.mp4")
    final_file = os.path.join(temp_dir, "movie_240p.mp4")
    thumbnail_file = os.path.join(temp_dir, "thumbnail.jpg")
    
    try:
        # Step 1: Extract URL
        print("1️⃣ Extracting video URL (minimum 240p)...")
        direct_url = extract_video_url(video_url)
        
        if not direct_url:
            print("❌ Failed to extract video URL")
            return False, "URL extraction failed"
        
        print(f"✅ Found URL: {direct_url[:100]}...")
        
        # Step 2: Download using yt-dlp (minimum 240p)
        print("2️⃣ Downloading (minimum 240p quality)...")
        if not download_with_ytdlp(direct_url, temp_file):
            # Try alternative method
            print("🔄 Trying alternative download method...")
            if not download_alternative(direct_url, temp_file):
                return False, "Download failed"
        
        # Check downloaded file
        if not os.path.exists(temp_file) or os.path.getsize(temp_file) < 1024:
            return False, "Downloaded file is invalid"
        
        # Step 3: Check quality and compress to 240p if needed
        print("3️⃣ Checking video quality...")
        
        try:
            cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', 
                   '-show_entries', 'stream=height', '-of', 'csv=p=0:nk=1', temp_file]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                height = result.stdout.strip()
                if height.isdigit():
                    print(f"📊 Downloaded video is {height}p")
                    
                    if int(height) <= 240:
                        print(f"✅ Video is already {height}p or lower, no compression needed")
                        final_file = temp_file
                    else:
                        print("🎬 Compressing to 240p...")
                        if not compress_to_240p(temp_file, final_file):
                            return False, "Compression failed"
                else:
                    print("⚠️ Could not determine video height, trying compression...")
                    if not compress_to_240p(temp_file, final_file):
                        return False, "Compression failed"
            else:
                print("⚠️ Could not check video height, trying compression...")
                if not compress_to_240p(temp_file, final_file):
                    return False, "Compression failed"
        except:
            print("⚠️ Error checking video quality, trying compression...")
            if not compress_to_240p(temp_file, final_file):
                return False, "Compression failed"
        
        # Verify final file
        if not os.path.exists(final_file) or os.path.getsize(final_file) < 1024:
            print("⚠️ Final file issue, using temp file")
            final_file = temp_file
        
        # Step 4: Create thumbnail
        print("4️⃣ Creating thumbnail...")
        thumbnail_created = create_thumbnail(final_file, thumbnail_file)
        
        # Step 5: Upload
        print("5️⃣ Uploading to Telegram...")
        thumb = thumbnail_file if thumbnail_created and os.path.exists(thumbnail_file) else None
        
        if not await upload_to_telegram(final_file, video_title, thumb):
            return False, "Upload failed"
        
        # Cleanup
        try:
            shutil.rmtree(temp_dir)
            print("🗑️ Cleaned temp files")
        except:
            pass
            
        return True, "✅ Movie processed successfully"
        
    except Exception as e:
        # Cleanup on error
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass
        return False, f"Error: {str(e)}"

async def main():
    """Main function"""
    print("="*50)
    print("🎬 Movie Uploader v3.4")
    print("🎯 Strategy: Download Minimum 240p → Compress to 240p")
    print("⚠️  Ignores 144p when 240p or higher is available")
    print("🔧 Enhanced upload settings")
    print("="*50)
    
    # Check ffmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("✅ ffmpeg is installed")
    except:
        print("❌ ffmpeg not found, installing...")
        subprocess.run(['sudo', 'apt-get', 'install', '-y', 'ffmpeg'], capture_output=True)
    
    # Setup Telegram
    if not await setup_telegram():
        print("❌ Cannot continue without Telegram")
        return
    
    # Check config
    config_file = "video_config.json"
    if not os.path.exists(config_file):
        print("❌ Config file not found, creating sample...")
        sample_config = {
            "videos": [{
                "url": "https://vk.com/video_ext.php?oid=791768803&id=456249035",
                "title": "اكس مراتي - الفيلم الكامل"
            }]
        }
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(sample_config, f, ensure_ascii=False, indent=2)
        print("⚠️ Please edit video_config.json and run again")
        return
    
    # Load config
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
    
    print(f"\n📊 Found {len(videos)} video(s) to process")
    
    # Process videos
    successful = 0
    for index, video in enumerate(videos, 1):
        url = video.get("url", "").strip()
        title = video.get("title", "").strip()
        
        if not url or not title:
            print(f"⚠️ Skipping video {index}: Missing data")
            continue
        
        print(f"\n[🎬 Video {index}/{len(videos)}] {title}")
        success, message = await process_movie(url, title)
        
        if success:
            successful += 1
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
        
        # Wait between videos
        if index < len(videos):
            print("⏳ Waiting 5 seconds before next video...")
            await asyncio.sleep(5)
    
    # Summary
    print(f"\n{'='*50}")
    print(f"📊 Result: {successful}/{len(videos)} successful")
    
    if successful == len(videos):
        print("🎉 All videos processed successfully!")
    elif successful > 0:
        print(f"⚠️ Partially successful ({successful}/{len(videos)})")
    else:
        print("💥 All videos failed!")
    
    print("🏁 Processing complete")
    
    # Cleanup
    if app:
        await app.stop()
        print("🔌 Disconnected from Telegram")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Stopped by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
