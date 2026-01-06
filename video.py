#!/usr/bin/env python3
"""
VK Video Downloader - Final Attempt
Combines cloudscraper, mobile API, and yt-dlp
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
requirements = ["pyrogram", "tgcrypto", "yt-dlp", "cloudscraper", "beautifulsoup4"]
for req in requirements:
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", req, "--quiet"])
        print(f"  ✅ {req}")
    except:
        print(f"  ⚠️ Failed to install {req}")

from pyrogram import Client
from pyrogram.errors import FloodWait
import yt_dlp
import cloudscraper
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
            "vk_final",
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

def extract_video_url_vk(url):
    """Extract video URL from VK using multiple methods"""
    print("🎯 Extracting VK video URL...")
    
    # Parse video ID
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    
    oid = query.get('oid', [''])[0]
    vid = query.get('id', [''])[0]
    
    if not oid or not vid:
        match = re.search(r'video(\d+)_(\d+)', url)
        if match:
            oid = match.group(1)
            vid = match.group(2)
    
    if not oid or not vid:
        print("❌ Could not extract video ID")
        return None
    
    video_id = f"{oid}_{vid}"
    print(f"📊 Video ID: {video_id}")
    
    # Method 1: Use cloudscraper to get page
    print("🔄 Method 1: Cloudscraper...")
    try:
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url, headers=HEADERS, timeout=30)
        
        if response.status_code == 200:
            html = response.text
            
            # Look for JSON data
            json_pattern = r'var\s+playerParams\s*=\s*({[^;]+});'
            match = re.search(json_pattern, html)
            if match:
                try:
                    json_str = match.group(1)
                    json_str = json_str.replace('\\/', '/').replace('\\"', '"')
                    data = json.loads(json_str)
                    
                    # Try to get hls or mp4 URLs
                    if 'hls' in data:
                        video_url = data['hls']
                        print(f"✅ Found hls URL: {video_url[:100]}...")
                        return video_url
                    
                    # Check for mp4 URLs
                    for key in ['url240', 'url360', 'url480', 'url720', 'url1080', 'url']:
                        if key in data and data[key]:
                            video_url = data[key]
                            print(f"✅ Found {key} URL: {video_url[:100]}...")
                            return video_url
                except:
                    pass
            
            # Look for video URLs directly
            patterns = [
                r'"url\d+"\s*:\s*"([^"]+)"',
                r'"hls"\s*:\s*"([^"]+)"',
                r'"mp4(?:_src)?"\s*:\s*"([^"]+)"',
                r'file\s*:\s*"([^"]+)"',
                r'https?://vkvd[0-9]+\.okcdn\.ru/[^"\']+',
                r'https?://[^"\']+\.m3u8[^"\']*',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, html)
                for match in matches:
                    if match and 'http' in match:
                        video_url = match.replace('\\/', '/')
                        print(f"✅ Found URL: {video_url[:100]}...")
                        return video_url
    except Exception as e:
        print(f"⚠️ Cloudscraper failed: {e}")
    
    # Method 2: Try mobile API
    print("🔄 Method 2: Mobile API...")
    try:
        mobile_url = f"https://vk.com/al_video.php?act=show&al=1&video={oid}_{vid}"
        scraper = cloudscraper.create_scraper()
        response = scraper.get(mobile_url, headers=HEADERS, timeout=30)
        
        if response.status_code == 200:
            html = response.text
            
            # Look for video URLs
            patterns = [
                r'"url\d+"\s*:\s*"([^"]+)"',
                r'"hls"\s*:\s*"([^"]+)"',
                r'https?://vkvd[0-9]+\.okcdn\.ru/[^"\']+',
                r'https?://[^"\']+\.m3u8[^"\']*',
                r'https?://[^"\']+\.mp4[^"\']*',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, html)
                for match in matches:
                    if match and 'http' in match:
                        video_url = match.replace('\\/', '/')
                        print(f"✅ Found mobile URL: {video_url[:100]}...")
                        return video_url
    except Exception as e:
        print(f"⚠️ Mobile API failed: {e}")
    
    # Method 3: Try yt-dlp
    print("🔄 Method 3: yt-dlp...")
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'force_generic_extractor': False,
            'http_headers': HEADERS,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if info and 'url' in info:
                video_url = info['url']
                print(f"✅ yt-dlp found URL: {video_url[:100]}...")
                return video_url
    except Exception as e:
        print(f"⚠️ yt-dlp failed: {e}")
    
    print("❌ All extraction methods failed")
    return None

def download_video_vk(video_url, output_path):
    """Download VK video"""
    print("📥 Downloading video...")
    
    try:
        # Use yt-dlp for downloading with proper headers
        ydl_opts = {
            'outtmpl': output_path,
            'format': 'worst[height>=240]/worst',
            'quiet': False,
            'no_warnings': False,
            'socket_timeout': 30,
            'retries': 10,
            'fragment_retries': 10,
            'skip_unavailable_fragments': True,
            'http_headers': HEADERS,
            'extractor_args': {
                'vk': ['--referer', 'https://vk.com/'],
            },
        }
        
        print(f"🔗 Downloading: {video_url[:150]}...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            
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
    """Process VK video"""
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
        # Step 1: Extract video URL
        print("1️⃣ Extracting video URL...")
        video_url = extract_video_url_vk(url)
        
        if not video_url:
            print("❌ Failed to extract video URL")
            return False, "Extraction failed"
        
        print(f"✅ Extracted URL: {video_url[:150]}...")
        
        # Step 2: Download
        print("2️⃣ Downloading video...")
        if not download_video_vk(video_url, temp_file):
            return False, "Download failed"
        
        # Check file
        if not os.path.exists(temp_file) or os.path.getsize(temp_file) < 1024:
            return False, "Downloaded file is invalid"
        
        print(f"📊 File size: {os.path.getsize(temp_file) / (1024*1024):.1f} MB")
        
        # Step 3: Compress
        print("3️⃣ Compressing to 240p...")
        if not compress_to_240p(temp_file, final_file):
            final_file = temp_file
        
        # Step 4: Upload
        print("4️⃣ Uploading to Telegram...")
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
    print("🎬 VK Video Downloader v7.0")
    print("🌐 Uses cloudscraper, mobile API, and yt-dlp")
    print("🔍 Multiple fallback methods for extraction")
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
            print("⏳ Waiting 5 seconds...")
            await asyncio.sleep(5)
    
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
