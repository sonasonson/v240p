#!/usr/bin/env python3
"""
VK Video Downloader - JavaScript Rendering Edition
Uses requests-html to render JavaScript and get video URLs
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
from urllib.parse import urlparse, parse_qs, unquote
import random

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

print("📦 Installing requirements...")
requirements = ["pyrogram", "tgcrypto", "requests", "requests-html", "beautifulsoup4"]
for req in requirements:
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", req, "--quiet"])
        print(f"  ✅ {req}")
    except:
        print(f"  ⚠️ Failed to install {req}")

from pyrogram import Client
from pyrogram.errors import FloodWait
from requests_html import HTMLSession
from bs4 import BeautifulSoup

app = None

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Referer': 'https://vk.com/',
    'Origin': 'https://vk.com/',
}

async def setup_telegram():
    """Setup Telegram client"""
    global app
    print("\n🔐 Setting up Telegram...")
    
    try:
        app = Client(
            "vk_js",
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

def extract_vk_video_with_js(url):
    """Extract VK video using JavaScript rendering"""
    print("🎯 Using JavaScript rendering for VK...")
    
    try:
        # Create HTML session with JavaScript support
        session = HTMLSession()
        
        # Load the page with JavaScript rendering
        print("🔄 Rendering VK page with JavaScript...")
        response = session.get(url, headers=HEADERS, timeout=30)
        
        # Render JavaScript (this will execute JS on the page)
        response.html.render(timeout=30, sleep=3)
        
        # Get the rendered HTML
        html = response.html.html
        print(f"✅ Page rendered successfully ({len(html)} characters)")
        
        # Save rendered HTML for debugging
        with open("debug_rendered.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("📝 Saved rendered HTML to debug_rendered.html")
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        # Method 1: Look for video element
        print("🔍 Searching for video elements...")
        video_elements = soup.find_all('video')
        for i, video in enumerate(video_elements):
            print(f"📺 Found video element #{i+1}")
            if video.get('src'):
                video_url = video['src']
                if video_url.startswith('//'):
                    video_url = 'https:' + video_url
                print(f"✅ Found video source: {video_url[:100]}...")
                return video_url
        
        # Method 2: Look for source tags inside video
        source_tags = soup.find_all('source')
        for i, source in enumerate(source_tags):
            src = source.get('src')
            if src and ('mp4' in src or 'm3u8' in src):
                video_url = src
                if video_url.startswith('//'):
                    video_url = 'https:' + video_url
                print(f"✅ Found source tag: {video_url[:100]}...")
                return video_url
        
        # Method 3: Look for iframe embeds
        print("🔍 Searching for iframe embeds...")
        iframe_tags = soup.find_all('iframe')
        for i, iframe in enumerate(iframe_tags):
            src = iframe.get('src')
            if src and 'video' in src:
                print(f"📺 Found iframe #{i+1}: {src[:100]}...")
                
                try:
                    # Try to extract from iframe
                    iframe_response = session.get(src, headers=HEADERS, timeout=20)
                    iframe_response.html.render(timeout=20, sleep=2)
                    iframe_html = iframe_response.html.html
                    
                    # Look for video in iframe
                    iframe_soup = BeautifulSoup(iframe_html, 'html.parser')
                    iframe_videos = iframe_soup.find_all('video')
                    for iframe_video in iframe_videos:
                        if iframe_video.get('src'):
                            video_url = iframe_video['src']
                            if video_url.startswith('//'):
                                video_url = 'https:' + video_url
                            print(f"✅ Found video in iframe: {video_url[:100]}...")
                            return video_url
                except:
                    continue
        
        # Method 4: Search for common VK video patterns in rendered content
        print("🔍 Searching for VK video patterns...")
        
        patterns = [
            r'"url(?:240|360|480|720|1080)?"\s*:\s*"([^"]+)"',
            r'"hls"\s*:\s*"([^"]+)"',
            r'"mp4(?:_src)?"\s*:\s*"([^"]+)"',
            r'file\s*:\s*"([^"]+)"',
            r'src\s*:\s*"([^"]+)"',
            r'https?://vkvd[0-9]+\.okcdn\.ru/[^"\']+',
            r'https?://[^"\']+\.m3u8[^"\']*',
            r'https?://[^"\']+\.mp4[^"\']*',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html)
            for match in matches:
                if match and 'http' in match:
                    video_url = match.replace('\\/', '/')
                    print(f"✅ Found pattern match: {video_url[:100]}...")
                    return video_url
        
        print("❌ No video URL found in rendered content")
        return None
        
    except Exception as e:
        print(f"❌ JavaScript rendering error: {e}")
        return None

def extract_vk_video_bypass(url):
    """Alternative method: Try to bypass VK protection"""
    print("🎯 Trying bypass method...")
    
    try:
        # Try mobile user agent
        mobile_headers = HEADERS.copy()
        mobile_headers['User-Agent'] = 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
        
        session = requests.Session()
        response = session.get(url, headers=mobile_headers, timeout=30)
        
        # Look for video URLs
        html = response.text
        
        # Try to find JSON data
        json_pattern = r'var\s+playerParams\s*=\s*({[^;]+});'
        match = re.search(json_pattern, html)
        if match:
            try:
                json_str = match.group(1)
                # Clean JSON
                json_str = json_str.replace('\\/', '/').replace('\\"', '"')
                data = json.loads(json_str)
                
                # Look for video URLs in JSON
                if 'hls' in data:
                    video_url = data['hls']
                    print(f"✅ Found hls in JSON: {video_url[:100]}...")
                    return video_url
                
                # Check for mp4 URLs
                for key in ['url240', 'url360', 'url480', 'url720', 'url1080', 'url']:
                    if key in data and data[key]:
                        video_url = data[key]
                        print(f"✅ Found {key} in JSON: {video_url[:100]}...")
                        return video_url
                        
            except:
                pass
        
        # Try alternative mobile API
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        oid = query.get('oid', [''])[0]
        vid = query.get('id', [''])[0]
        
        if oid and vid:
            mobile_api_url = f"https://vk.com/al_video.php?act=show&al=1&video={oid}_{vid}"
            mobile_response = session.get(mobile_api_url, headers=mobile_headers, timeout=30)
            
            # Look for video in API response
            api_html = mobile_response.text
            
            patterns = [
                r'"url\d+"\s*:\s*"([^"]+)"',
                r'"hls"\s*:\s*"([^"]+)"',
                r'https?://[^"\']+\.mp4[^"\']*',
                r'https?://[^"\']+\.m3u8[^"\']*',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, api_html)
                for match in matches:
                    if match and 'http' in match:
                        video_url = match.replace('\\/', '/')
                        print(f"✅ Found in mobile API: {video_url[:100]}...")
                        return video_url
        
        return None
        
    except Exception as e:
        print(f"❌ Bypass error: {e}")
        return None

def download_video(video_url, output_path):
    """Download video with proper headers"""
    print("📥 Downloading video...")
    
    try:
        session = requests.Session()
        headers = HEADERS.copy()
        
        # Set referer for VK
        if 'okcdn.ru' in video_url or 'vk.com' in video_url:
            headers['Referer'] = 'https://vk.com/'
        
        print(f"🔗 Downloading: {video_url[:150]}...")
        
        response = session.get(video_url, headers=headers, stream=True, timeout=60)
        
        if response.status_code != 200:
            print(f"❌ Download failed: {response.status_code}")
            return False
        
        total_size = int(response.headers.get('content-length', 0))
        
        if total_size > 0:
            print(f"📊 File size: {total_size / (1024*1024):.1f} MB")
        
        with open(output_path, 'wb') as f:
            downloaded = 0
            start_time = time.time()
            
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # Show progress every 2MB
                    if downloaded % (2 * 1024 * 1024) < 8192 and total_size > 0:
                        elapsed = time.time() - start_time
                        speed = downloaded / elapsed / 1024 if elapsed > 0 else 0
                        percent = (downloaded / total_size) * 100
                        print(f"📥 {percent:.1f}% - {downloaded / (1024*1024):.1f} MB - {speed:.0f} KB/s")
        
        elapsed = time.time() - start_time
        final_size = os.path.getsize(output_path) / (1024 * 1024)
        
        if final_size > 0.5:  # At least 500KB
            print(f"✅ Download complete: {final_size:.1f} MB in {elapsed:.1f}s")
            return True
        else:
            print(f"❌ File too small: {final_size:.1f} MB")
            return False
            
    except Exception as e:
        print(f"❌ Download error: {e}")
        return False

def compress_to_240p(input_path, output_path):
    """Compress video to 240p"""
    print("🎬 Compressing to 240p...")
    
    if not os.path.exists(input_path):
        return False
    
    input_size = os.path.getsize(input_path) / (1024 * 1024)
    print(f"📊 Input size: {input_size:.1f} MB")
    
    # Check if already low quality
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
    
    # Compress
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
        print(f"✅ Compression complete in {elapsed:.1f}s")
        print(f"📊 Output size: {output_size:.1f} MB")
        return True
    else:
        print("❌ Compression failed, using original")
        shutil.copy2(input_path, output_path)
        return True

async def upload_to_telegram(file_path, caption):
    """Upload video to Telegram"""
    print("☁️ Uploading to Telegram...")
    
    try:
        # Get video info
        try:
            cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                   '-show_entries', 'stream=width,height,duration',
                   '-of', 'json', file_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            info = json.loads(result.stdout)
            streams = info.get('streams', [])
            if streams:
                width = streams[0].get('width', 426)
                height = streams[0].get('height', 240)
                duration = int(float(streams[0].get('duration', 0)))
            else:
                width, height, duration = 426, 240, 0
        except:
            width, height, duration = 426, 240, 0
        
        # Upload
        upload_params = {
            'chat_id': TELEGRAM_CHANNEL,
            'video': file_path,
            'caption': caption,
            'supports_streaming': True,
            'width': width,
            'height': height,
            'duration': duration,
        }
        
        print(f"📐 Video: {width}x{height}, Duration: {duration}s")
        
        # Progress
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
        return await upload_to_telegram(file_path, caption)
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return False

async def process_vk_video(url, title):
    """Process VK video with multiple extraction methods"""
    print(f"\n{'='*60}")
    print(f"🎬 Processing: {title}")
    print(f"🔗 URL: {url}")
    print(f"{'='*60}")
    
    timestamp = datetime.now().strftime('%H%M%S')
    temp_dir = f"vk_{timestamp}"
    os.makedirs(temp_dir, exist_ok=True)
    
    temp_file = os.path.join(temp_dir, "video.mp4")
    final_file = os.path.join(temp_dir, "video_240p.mp4")
    
    try:
        # Step 1: Try JavaScript rendering first
        print("1️⃣ Extracting with JavaScript rendering...")
        video_url = extract_vk_video_with_js(url)
        
        # Step 2: If that fails, try bypass method
        if not video_url:
            print("2️⃣ Trying bypass method...")
            video_url = extract_vk_video_bypass(url)
        
        if not video_url:
            print("❌ Failed to extract video URL")
            return False, "Extraction failed"
        
        print(f"✅ Extracted URL: {video_url[:150]}...")
        
        # Step 3: Download
        print("3️⃣ Downloading video...")
        if not download_video(video_url, temp_file):
            return False, "Download failed"
        
        # Check file
        if not os.path.exists(temp_file) or os.path.getsize(temp_file) < 1024:
            return False, "Downloaded file is invalid"
        
        print(f"📊 File size: {os.path.getsize(temp_file) / (1024*1024):.1f} MB")
        
        # Step 4: Compress
        print("4️⃣ Compressing to 240p...")
        if not compress_to_240p(temp_file, final_file):
            final_file = temp_file
        
        # Step 5: Upload
        print("5️⃣ Uploading to Telegram...")
        if not await upload_to_telegram(final_file, title):
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
    print("🎬 VK JavaScript Downloader v6.0")
    print("🌐 Uses JavaScript rendering to bypass VK protection")
    print("🔍 Multiple extraction methods with fallbacks")
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
        success, message = await process_vk_video(url, title)
        
        if success:
            successful += 1
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
        
        if index < len(videos):
            print("⏳ Waiting 10 seconds...")
            await asyncio.sleep(10)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"📊 Result: {successful}/{len(videos)} successful")
    
    if successful > 0:
        print("✅ Processing complete")
    else:
        print("❌ All videos failed")
    
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
