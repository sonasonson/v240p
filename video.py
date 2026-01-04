#!/usr/bin/env python3
"""
Universal Video Uploader - For Movies
Download lowest quality then compress to 240p
Fixed URL issues
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
            in_memory=True
        )
        
        await app.start()
        me = await app.get_me()
        print(f"✅ Connected as: {me.first_name}")
        return True
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
    
    # Remove double slashes after domain (except after https://)
    url = re.sub(r'(https?://[^/]+)//+', r'\1/', url)
    
    # Remove trailing dot if present
    if url.endswith('.'):
        url = url[:-1]
    
    # Fix common VK URL patterns
    if 'vkuser.net' in url:
        # Fix URLs with double slashes in path
        url = re.sub(r'//+', '/', url)
        # Ensure proper URL structure
        if not url.endswith('.m3u8') and not url.endswith('.mp4'):
            # Try to find the actual video file
            url = url.rstrip('/')
    
    return url.strip()

def fix_vk_m3u8_url(url):
    """Fix VK m3u8 URLs that have formatting issues"""
    print("🔧 Fixing VK m3u8 URL...")
    
    # If it's already a clean m3u8 URL, return it
    if 'video.m3u8' in url and '?' in url:
        return url
    
    # Try to extract the actual m3u8 URL from parameters
    if 'expires=' in url:
        # This looks like a VK video URL with parameters
        # Extract base URL and parameters
        base_match = re.search(r'(https?://[^/]+)/', url)
        if base_match:
            base_url = base_match.group(1)
            
            # Extract common VK parameters
            params = {}
            param_patterns = [
                r'expires/(\d+)',
                r'srcIp/([^/]+)',
                r'pr/(\d+)',
                r'srcAg/([^/]+)',
                r'ch/([^/]+)',
                r'ms/([^/]+)',
                r'mid/(\d+)',
                r'type/(\d+)',
                r'sig/([^/]+)',
                r'ct/(\d+)',
                r'urls/([^/]+)',
                r'clientType/(\d+)',
                r'zs/(\d+)',
                r'id/(\d+)',
            ]
            
            for pattern in param_patterns:
                match = re.search(pattern, url)
                if match:
                    param_name = pattern.split('/')[0]
                    param_value = match.group(1)
                    params[param_name] = param_value
            
            # Construct proper query string
            if params:
                query_params = []
                for key, value in params.items():
                    query_params.append(f"{key}={value}")
                
                query_string = '&'.join(query_params)
                fixed_url = f"{base_url}/video.m3u8?{query_string}"
                print(f"✅ Fixed URL: {fixed_url[:100]}...")
                return fixed_url
    
    return url

def get_lowest_quality_m3u8(m3u8_url):
    """Get the lowest quality stream from m3u8 playlist"""
    print("🔍 Looking for lowest quality in m3u8...")
    
    try:
        # Fix URL first
        m3u8_url = clean_vk_url(m3u8_url)
        m3u8_url = fix_vk_m3u8_url(m3u8_url)
        
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
                
                # Get the lowest quality (preferably <= 240p)
                selected_stream = streams[0]
                for stream in streams:
                    if stream['height'] <= 240:
                        selected_stream = stream
                        break
                
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
        
        # Method 1: Look for JSON data
        print("🔍 Searching for JSON data...")
        
        # Common patterns in VK
        patterns = [
            r'"hls"\s*:\s*"([^"]+)"',
            r'"url[0-9]+"\s*:\s*"([^"]+)"',
            r'videoPlayerInit\s*\(\s*({[^}]+})',
            r'var\s+videoData\s*=\s*({[^;]+});',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, response.text, re.DOTALL)
            if matches:
                for match in matches:
                    if isinstance(match, str) and ('http' in match or '.mp4' in match or '.m3u8' in match):
                        url = clean_vk_url(match)
                        if url and '.m3u8' in url:
                            print(f"🔧 Found m3u8 URL, processing...")
                            # Try to get lowest quality from m3u8
                            url = get_lowest_quality_m3u8(url)
                        if url:
                            print(f"✅ Found URL with pattern: {pattern[:30]}...")
                            return url
        
        # Method 2: Try to extract from iframe
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
                for pattern in patterns:
                    matches = re.findall(pattern, iframe_response.text)
                    for match in matches:
                        if isinstance(match, str) and ('http' in match or '.mp4' in match or '.m3u8' in match):
                            url = clean_vk_url(match)
                            if url:
                                print(f"✅ Found URL in iframe")
                                return url
            except Exception as e:
                print(f"⚠️ Iframe error: {e}")
        
        return None
        
    except Exception as e:
        print(f"⚠️ VK extraction error: {e}")
        return None

def extract_video_url(url):
    """Extract direct video URL"""
    print(f"🔍 Extracting from: {url}")
    
    # Check if it's VK
    parsed_url = urlparse(url)
    if 'vk.com' in parsed_url.netloc or 'vkontakte' in parsed_url.netloc:
        return extract_vk_video_url(url)
    
    # For other sites, try yt-dlp with lowest quality
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'worst[height<=360]/worst',  # Lowest quality <= 360p
            'socket_timeout': 30,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info and 'url' in info:
                video_url = info['url']
                print(f"✅ Found lowest quality URL via yt-dlp")
                return video_url
    except Exception as e:
        print(f"⚠️ yt-dlp failed: {e}")
    
    return None

def test_url_access(url):
    """Test if URL is accessible"""
    print("🔗 Testing URL accessibility...")
    
    try:
        headers = HEADERS.copy()
        response = requests.head(url, headers=headers, timeout=10)
        print(f"📡 HTTP Status: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"⚠️ URL test failed: {e}")
        return False

def download_with_ffmpeg(url, output_path):
    """Download using ffmpeg"""
    print("🎬 Starting download with ffmpeg...")
    
    try:
        # Test URL first
        if not test_url_access(url):
            print("❌ URL is not accessible")
            return False
        
        # Prepare ffmpeg command
        cmd = [
            'ffmpeg',
            '-i', url,
            '-c', 'copy',  # Copy without re-encoding for speed
            '-bsf:a', 'aac_adtstoasc',
            '-y',
            output_path
        ]
        
        print(f"🔄 Running command: ffmpeg -i [URL] -c copy {output_path}")
        
        # Track progress
        progress_info = {
            'downloaded': 0,
            'finished': False,
            'last_update': time.time()
        }
        
        def track_progress():
            """Track file size progress"""
            while not progress_info['finished']:
                if os.path.exists(output_path):
                    current_size = os.path.getsize(output_path)
                    current_time = time.time()
                    
                    # Update every 5 seconds
                    if current_time - progress_info['last_update'] >= 5:
                        size_mb = current_size / (1024 * 1024)
                        print(f"📥 Downloaded: {size_mb:.1f} MB")
                        progress_info['last_update'] = current_time
                        progress_info['downloaded'] = current_size
                
                time.sleep(1)
        
        # Start progress thread
        progress_thread = threading.Thread(target=track_progress)
        progress_thread.daemon = True
        progress_thread.start()
        
        # Start download with timeout
        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # 30 minutes timeout
        
        # Mark as finished
        progress_info['finished'] = True
        progress_thread.join(timeout=5)
        
        elapsed = time.time() - start_time
        
        if result.returncode == 0 and os.path.exists(output_path):
            final_size = os.path.getsize(output_path) / (1024 * 1024)
            print(f"✅ Download complete: {final_size:.1f} MB in {elapsed:.1f} seconds")
            
            # Check if file is valid
            if final_size < 1:  # Less than 1MB
                print("⚠️ File seems too small")
                return False
            
            return True
        else:
            print(f"❌ Download failed with code: {result.returncode}")
            if result.stderr:
                # Show relevant error lines
                error_lines = [line for line in result.stderr.split('\n') if 'Error' in line or 'error' in line]
                if error_lines:
                    print("📝 Error details:")
                    for line in error_lines[-5:]:  # Last 5 error lines
                        print(f"  {line}")
            
            # Try alternative method if ffmpeg fails
            print("🔄 Trying alternative download method...")
            return download_alternative(url, output_path)
            
    except subprocess.TimeoutExpired:
        print("⏰ Download timed out after 30 minutes")
        return False
    except Exception as e:
        print(f"❌ Download error: {e}")
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

async def upload_to_telegram(file_path, caption):
    """Upload to Telegram channel"""
    print(f"☁️ Uploading: {os.path.basename(file_path)}")
    
    # Get file size
    file_size = os.path.getsize(file_path) / (1024*1024)
    print(f"📊 File size: {file_size:.1f} MB")
    
    try:
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
        
        await app.send_video(
            chat_id=TELEGRAM_CHANNEL,
            video=file_path,
            caption=caption,
            supports_streaming=True,
            progress=progress
        )
        
        elapsed = time.time() - start_time
        print(f"✅ Uploaded in {elapsed:.1f} seconds")
        return True
        
    except FloodWait as e:
        print(f"⏳ Flood wait: {e.value} seconds")
        await asyncio.sleep(e.value)
        return await upload_to_telegram(file_path, caption)
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        # Try without progress
        try:
            await app.send_video(
                chat_id=TELEGRAM_CHANNEL,
                video=file_path,
                caption=caption,
                supports_streaming=True
            )
            print("✅ Upload successful (without progress)")
            return True
        except Exception as e2:
            print(f"❌ Retry failed: {e2}")
            return False

async def process_movie(video_url, video_title):
    """Process a single movie - download low quality then compress"""
    print(f"\n{'─'*50}")
    print(f"🎬 Processing: {video_title}")
    print(f"🎯 Strategy: Download low quality → Compress to 240p")
    print(f"🔗 URL: {video_url}")
    print(f"{'─'*50}")
    
    # Create temp directory
    timestamp = datetime.now().strftime('%H%M%S')
    temp_dir = f"temp_movie_{timestamp}"
    os.makedirs(temp_dir, exist_ok=True)
    
    # Define file paths
    temp_file = os.path.join(temp_dir, "temp_video.mp4")
    final_file = os.path.join(temp_dir, "movie_240p.mp4")
    
    try:
        # Step 1: Extract URL (lowest quality)
        print("1️⃣ Extracting video URL (lowest quality)...")
        direct_url = extract_video_url(video_url)
        
        if not direct_url:
            return False, "URL extraction failed"
        
        print(f"✅ Found URL: {direct_url[:100]}...")
        
        # Step 2: Download (low quality)
        print("2️⃣ Downloading (lowest quality available)...")
        if not download_with_ffmpeg(direct_url, temp_file):
            return False, "Download failed"
        
        # Check downloaded file
        if not os.path.exists(temp_file) or os.path.getsize(temp_file) < 1024:
            return False, "Downloaded file is invalid"
        
        # Step 3: Compress to 240p
        print("3️⃣ Compressing to 240p...")
        if not compress_to_240p(temp_file, final_file):
            return False, "Compression failed"
        
        # Verify final file
        if not os.path.exists(final_file) or os.path.getsize(final_file) < 1024:
            print("⚠️ Final file issue, using temp file")
            final_file = temp_file
        
        # Step 4: Upload
        print("4️⃣ Uploading to Telegram...")
        if not await upload_to_telegram(final_file, video_title):
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
    print("🎬 Movie Uploader v3.1")
    print("🎯 Strategy: Download Low Quality → Compress to 240p")
    print("🔧 Fixed URL issues")
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
