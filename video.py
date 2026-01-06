#!/usr/bin/env python3
"""
VK Video Downloader - Fixed URL Filtering
Filters out tracking URLs and focuses on real video URLs
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
from urllib.parse import urlparse, parse_qs, quote, unquote
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
requirements = ["pyrogram", "tgcrypto", "requests"]
for req in requirements:
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", req, "--quiet"])
        print(f"  ✅ {req}")
    except:
        print(f"  ⚠️ Failed to install {req}")

from pyrogram import Client
from pyrogram.errors import FloodWait

app = None

# Generate random browser-like headers
def generate_headers():
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]
    
    return {
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
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
            "vk_fixed",
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

def is_video_url(url):
    """Check if URL is a real video URL (not tracking)"""
    if not url or 'http' not in url:
        return False
    
    # List of tracking/analytics patterns to EXCLUDE
    tracking_patterns = [
        'video_mediascope',
        'mediascope',
        'analytics',
        'tracking',
        'event_name=',
        'statistics',
        'metrics',
        'beacon',
        'pixel',
        'log',
    ]
    
    # List of video patterns to INCLUDE
    video_patterns = [
        '.mp4',
        '.m3u8',
        '.ts',
        'okcdn.ru',
        'vkvd',
        '1vid.online',
        'cdnz.quest',
        '/video/',
        'video.m3u8',
        'index.m3u8',
        'hls',
        'stream',
    ]
    
    # Exclude tracking URLs
    for pattern in tracking_patterns:
        if pattern in url.lower():
            return False
    
    # Include video URLs
    for pattern in video_patterns:
        if pattern in url.lower():
            return True
    
    return False

def extract_vk_video_smart(url):
    """Smart extraction focusing on real video URLs"""
    print("🎯 Smart VK video extraction...")
    
    try:
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
        
        # Method 1: Try with browser-like session
        session = requests.Session()
        headers = generate_headers()
        
        print("🔄 Loading VK page...")
        response = session.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Failed to load page: {response.status_code}")
            return None
        
        html = response.text
        
        # Try to find JSON data with video info
        print("🔍 Searching for video data in JSON...")
        
        # Look for common JSON patterns in VK
        json_patterns = [
            r'var\s+playerParams\s*=\s*({[^;]+});',
            r'videoPlayerInit\s*\(\s*({[^}]+})',
            r'window\.videoData\s*=\s*({[^;]+});',
            r'"videoData"\s*:\s*({[^}]+})',
            r'<script[^>]*data-video="([^"]+)"',
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches:
                try:
                    # Clean the JSON string
                    json_str = match.replace('\\/', '/').replace('\\"', '"')
                    if json_str.startswith('{'):
                        data = json.loads(json_str)
                        
                        # Search for video URLs in the JSON
                        def search_video_urls(obj, path=""):
                            urls = []
                            if isinstance(obj, dict):
                                for key, value in obj.items():
                                    if isinstance(value, str) and is_video_url(value):
                                        urls.append(value)
                                    elif isinstance(value, (dict, list)):
                                        urls.extend(search_video_urls(value, f"{path}.{key}"))
                            elif isinstance(obj, list):
                                for i, item in enumerate(obj):
                                    urls.extend(search_video_urls(item, f"{path}[{i}]"))
                            return urls
                        
                        found_urls = search_video_urls(data)
                        if found_urls:
                            print(f"✅ Found {len(found_urls)} video URLs in JSON")
                            for found_url in found_urls:
                                print(f"  • {found_url[:80]}...")
                            return found_urls[0]  # Return first valid video URL
                            
                except json.JSONDecodeError:
                    # If not JSON, check if it's a direct URL
                    if is_video_url(match):
                        print(f"✅ Found direct URL: {match[:80]}...")
                        return match
                except Exception as e:
                    continue
        
        # Method 2: Look for specific VK video patterns
        print("🔄 Searching for VK-specific patterns...")
        
        vk_video_patterns = [
            r'"url\d+"\s*:\s*"([^"]+)"',
            r'"hls"\s*:\s*"([^"]+)"',
            r'"mp4_src"\s*:\s*"([^"]+)"',
            r'"file"\s*:\s*"([^"]+)"',
            r'src\s*:\s*"([^"]+)"',
        ]
        
        for pattern in vk_video_patterns:
            matches = re.findall(pattern, html)
            for match in matches:
                if is_video_url(match):
                    video_url = match.replace('\\/', '/')
                    print(f"✅ Found VK video URL: {video_url[:80]}...")
                    return video_url
        
        # Method 3: Look for common video hosting domains
        print("🔄 Searching for video hosting domains...")
        
        video_hosting_patterns = [
            r'https?://[^"\']+\.okcdn\.ru/[^"\']+',
            r'https?://vkvd[0-9]+\.okcdn\.ru/[^"\']+',
            r'https?://[^"\']+\.1vid\.online/[^"\']+',
            r'https?://[^"\']+\.cdnz\.quest/[^"\']+',
        ]
        
        for pattern in video_hosting_patterns:
            matches = re.findall(pattern, html)
            for match in matches:
                if is_video_url(match):
                    print(f"✅ Found video hosting URL: {match[:80]}...")
                    return match
        
        # Method 4: Try to find m3u8 URLs
        print("🔄 Searching for m3u8 URLs...")
        m3u8_patterns = [
            r'https?://[^"\']+\.m3u8[^"\']*',
            r'\.m3u8\?[^"\']*',
        ]
        
        for pattern in m3u8_patterns:
            matches = re.findall(pattern, html)
            for match in matches:
                if is_video_url(match):
                    print(f"✅ Found m3u8 URL: {match[:80]}...")
                    return match
        
        print("❌ No valid video URLs found")
        return None
        
    except Exception as e:
        print(f"❌ Extraction error: {e}")
        return None

def download_video_with_retry(video_url, output_path, max_retries=3):
    """Download video with retry mechanism"""
    for attempt in range(max_retries):
        print(f"🔄 Download attempt {attempt + 1}/{max_retries}...")
        
        try:
            session = requests.Session()
            headers = generate_headers()
            
            # Add specific headers for VK CDN
            if 'okcdn.ru' in video_url:
                headers['Referer'] = 'https://vk.com/'
                headers['Origin'] = 'https://vk.com/'
            
            print(f"📥 Downloading: {video_url[:100]}...")
            
            # Try HEAD request first to check availability
            try:
                head_response = session.head(video_url, headers=headers, timeout=10, allow_redirects=True)
                print(f"📊 Status: {head_response.status_code}")
                
                if head_response.status_code != 200:
                    print(f"⚠️ HEAD request failed: {head_response.status_code}")
                    time.sleep(2)
                    continue
            except:
                pass  # Continue anyway
            
            # Download the video
            response = session.get(video_url, headers=headers, timeout=60, stream=True)
            
            if response.status_code != 200:
                print(f"❌ Download failed: {response.status_code}")
                time.sleep(2)
                continue
            
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
                            percent = (downloaded / total_size) * 100 if total_size > 0 else 0
                            print(f"📥 {percent:.1f}% - {downloaded / (1024*1024):.1f} MB - {speed:.0f} KB/s")
            
            elapsed = time.time() - start_time
            final_size = os.path.getsize(output_path) / (1024 * 1024)
            
            if final_size > 0.5:  # At least 500KB
                print(f"✅ Download complete: {final_size:.1f} MB in {elapsed:.1f}s")
                return True
            else:
                print(f"⚠️ File too small: {final_size:.1f} MB")
                os.remove(output_path)  # Remove small file
                time.sleep(2)
                continue
                
        except Exception as e:
            print(f"❌ Download error: {e}")
            time.sleep(2)
    
    return False

def compress_to_240p(input_path, output_path):
    """Compress video to 240p"""
    print("🎬 Compressing to 240p...")
    
    if not os.path.exists(input_path):
        return False
    
    input_size = os.path.getsize(input_path) / (1024 * 1024)
    print(f"📊 Input size: {input_size:.1f} MB")
    
    # Check current quality
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
        # Step 1: Extract REAL video URL (not tracking)
        print("1️⃣ Extracting real video URL...")
        video_url = extract_vk_video_smart(url)
        
        if not video_url:
            print("❌ Failed to extract video URL")
            return False, "Extraction failed"
        
        print(f"✅ Extracted REAL video URL: {video_url[:150]}...")
        
        # Step 2: Download
        print("2️⃣ Downloading video...")
        if not download_video_with_retry(video_url, temp_file, max_retries=3):
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
    print("🎬 VK Smart Downloader v4.0")
    print("🔍 Filters out tracking URLs, focuses on real video URLs")
    print("🎯 Specialized for VK.com video extraction")
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
