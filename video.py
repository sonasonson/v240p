#!/usr/bin/env python3
"""
VK Video Downloader - Ultimate Version
Uses browser-like requests with full headers simulation
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
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
    
    accept_languages = [
        'en-US,en;q=0.9',
        'ar,en-US;q=0.9,en;q=0.8',
        'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7'
    ]
    
    return {
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': random.choice(accept_languages),
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
        'Referer': 'https://vk.com/',
        'Origin': 'https://vk.com/',
    }

async def setup_telegram():
    """Setup Telegram client"""
    global app
    print("\n🔐 Setting up Telegram...")
    
    try:
        app = Client(
            "vk_ultimate",
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

def extract_vk_video_direct(url):
    """Direct extraction from VK using multiple techniques"""
    print("🎯 Direct VK video extraction...")
    
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
        
        # Method 1: Try to get the page with session
        session = requests.Session()
        headers = generate_headers()
        
        print("🔄 Method 1: Direct page request...")
        response = session.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Failed to load page: {response.status_code}")
            return None
        
        html = response.text
        
        # Look for video URLs in the page
        video_patterns = [
            r'"url(?:240|360|480|720|1080)?"\s*:\s*"([^"]+)"',
            r'"mp4(?:_src)?"\s*:\s*"([^"]+)"',
            r'file\s*:\s*"([^"]+)"',
            r'src\s*:\s*"([^"]+)"',
            r'"hls"\s*:\s*"([^"]+)"',
            r'videoSrc\s*:\s*"([^"]+)"',
            r'https?://[^"\']+\.mp4[^"\']*',
            r'https?://[^"\']+\.m3u8[^"\']*',
        ]
        
        for pattern in video_patterns:
            matches = re.findall(pattern, html)
            for match in matches:
                if match and 'http' in match:
                    video_url = match.replace('\\/', '/')
                    print(f"✅ Found video URL: {video_url[:100]}...")
                    
                    # If it's m3u8, try to get actual video segments
                    if '.m3u8' in video_url:
                        print("🔍 Processing m3u8 playlist...")
                        m3u8_content = download_m3u8_content(video_url, headers)
                        if m3u8_content:
                            # Look for actual video segments
                            segment_match = re.search(r'https?://[^\s]+\.(mp4|ts|m4s)', m3u8_content)
                            if segment_match:
                                return segment_match.group(0)
                    
                    return video_url
        
        # Method 2: Try to find in script tags
        print("🔄 Method 2: Script tag search...")
        script_patterns = [
            r'<script[^>]*>([^<]+)</script>',
            r'window\.videoData\s*=\s*({[^;]+});',
        ]
        
        for pattern in script_patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches:
                if 'mp4' in match or 'm3u8' in match:
                    # Try to extract URL from script
                    url_match = re.search(r'https?://[^"\'\s]+\.(mp4|m3u8)[^"\'\s]*', match)
                    if url_match:
                        video_url = url_match.group(0)
                        print(f"✅ Found in script: {video_url[:100]}...")
                        return video_url
        
        # Method 3: Try iframe approach
        print("🔄 Method 3: Iframe detection...")
        iframe_match = re.search(r'iframe[^>]+src="([^"]+)"', html)
        if iframe_match:
            iframe_url = iframe_match.group(1)
            if iframe_url.startswith('//'):
                iframe_url = 'https:' + iframe_url
            
            print(f"📺 Found iframe: {iframe_url}")
            try:
                iframe_response = session.get(iframe_url, headers=headers, timeout=20)
                iframe_html = iframe_response.text
                
                # Search for video in iframe
                for pattern in video_patterns:
                    iframe_matches = re.findall(pattern, iframe_html)
                    for iframe_match in iframe_matches:
                        if iframe_match and 'http' in iframe_match:
                            video_url = iframe_match.replace('\\/', '/')
                            print(f"✅ Found in iframe: {video_url[:100]}...")
                            return video_url
            except:
                pass
        
        print("❌ Could not extract video URL")
        return None
        
    except Exception as e:
        print(f"❌ Extraction error: {e}")
        return None

def download_m3u8_content(m3u8_url, headers):
    """Download and parse m3u8 content"""
    try:
        session = requests.Session()
        response = session.get(m3u8_url, headers=headers, timeout=20)
        
        if response.status_code == 200:
            return response.text
        else:
            print(f"❌ Failed to download m3u8: {response.status_code}")
            return None
    except:
        return None

def download_video_segments(video_url, output_path):
    """Download video by segments if needed"""
    print("🎬 Downloading video segments...")
    
    try:
        session = requests.Session()
        headers = generate_headers()
        
        # Check if it's a playlist or direct video
        if '.m3u8' in video_url:
            print("📋 Processing m3u8 playlist...")
            
            # Get playlist content
            response = session.get(video_url, headers=headers, timeout=30)
            if response.status_code != 200:
                print(f"❌ Failed to get playlist: {response.status_code}")
                return False
            
            playlist = response.text
            lines = playlist.split('\n')
            
            # Create temp directory for segments
            temp_dir = "segments_temp"
            os.makedirs(temp_dir, exist_ok=True)
            
            segment_files = []
            segment_count = 0
            
            # Download video segments
            base_url = '/'.join(video_url.split('/')[:-1])
            
            for line in lines:
                if line and not line.startswith('#') and ('.ts' in line or '.m4s' in line):
                    segment_count += 1
                    print(f"📥 Downloading segment {segment_count}...")
                    
                    # Construct segment URL
                    if line.startswith('http'):
                        segment_url = line
                    else:
                        segment_url = f"{base_url}/{line}"
                    
                    # Download segment
                    segment_file = os.path.join(temp_dir, f"segment_{segment_count:04d}.ts")
                    
                    try:
                        seg_response = session.get(segment_url, headers=headers, timeout=30, stream=True)
                        with open(segment_file, 'wb') as f:
                            for chunk in seg_response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        
                        segment_files.append(segment_file)
                        
                    except Exception as e:
                        print(f"⚠️ Failed to download segment {segment_count}: {e}")
            
            if segment_files:
                print(f"✅ Downloaded {len(segment_files)} segments")
                
                # Combine segments using ffmpeg
                print("🔗 Combining segments...")
                
                # Create file list for ffmpeg
                list_file = os.path.join(temp_dir, "segments.txt")
                with open(list_file, 'w') as f:
                    for seg_file in segment_files:
                        f.write(f"file '{seg_file}'\n")
                
                # Use ffmpeg to combine
                cmd = [
                    'ffmpeg',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', list_file,
                    '-c', 'copy',
                    '-y',
                    output_path
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                
                # Cleanup
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass
                
                if result.returncode == 0 and os.path.exists(output_path):
                    file_size = os.path.getsize(output_path) / (1024 * 1024)
                    print(f"✅ Combined successfully: {file_size:.1f} MB")
                    return True
                else:
                    print(f"❌ Failed to combine segments: {result.stderr[:200]}")
                    return False
            else:
                print("❌ No segments downloaded")
                return False
        
        else:
            # Direct video download
            print("🔗 Direct video download...")
            return download_direct_video(video_url, output_path)
            
    except Exception as e:
        print(f"❌ Segment download error: {e}")
        return False

def download_direct_video(video_url, output_path):
    """Download direct video file"""
    try:
        session = requests.Session()
        headers = generate_headers()
        
        print(f"📥 Downloading: {video_url[:100]}...")
        
        response = session.get(video_url, headers=headers, timeout=60, stream=True)
        
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
                    
                    # Show progress every 5MB
                    if downloaded % (5 * 1024 * 1024) < 8192:
                        elapsed = time.time() - start_time
                        speed = downloaded / elapsed / 1024 if elapsed > 0 else 0
                        print(f"📥 {downloaded / (1024*1024):.1f} MB - {speed:.0f} KB/s")
        
        elapsed = time.time() - start_time
        final_size = os.path.getsize(output_path) / (1024 * 1024)
        print(f"✅ Download complete: {final_size:.1f} MB in {elapsed:.1f}s")
        
        return final_size > 0.1  # At least 100KB
        
    except Exception as e:
        print(f"❌ Direct download error: {e}")
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
    temp_dir = f"vk_temp_{timestamp}"
    os.makedirs(temp_dir, exist_ok=True)
    
    temp_file = os.path.join(temp_dir, "video.mp4")
    final_file = os.path.join(temp_dir, "video_240p.mp4")
    
    max_attempts = 3
    current_attempt = 1
    
    while current_attempt <= max_attempts:
        print(f"\n🔄 Attempt {current_attempt}/{max_attempts}")
        
        try:
            # Step 1: Extract video URL
            print("1️⃣ Extracting video URL...")
            video_url = extract_vk_video_direct(url)
            
            if not video_url:
                print("❌ Failed to extract video URL")
                current_attempt += 1
                time.sleep(2)
                continue
            
            print(f"✅ Extracted URL: {video_url[:150]}...")
            
            # Step 2: Download
            print("2️⃣ Downloading...")
            
            if '.m3u8' in video_url:
                if not download_video_segments(video_url, temp_file):
                    print("❌ Segment download failed")
                    current_attempt += 1
                    time.sleep(2)
                    continue
            else:
                if not download_direct_video(video_url, temp_file):
                    print("❌ Direct download failed")
                    current_attempt += 1
                    time.sleep(2)
                    continue
            
            # Check file
            if not os.path.exists(temp_file) or os.path.getsize(temp_file) < 1024:
                print("❌ Downloaded file is invalid")
                current_attempt += 1
                time.sleep(2)
                continue
            
            # Step 3: Compress
            print("3️⃣ Compressing...")
            if not compress_to_240p(temp_file, final_file):
                final_file = temp_file
            
            # Step 4: Upload
            print("4️⃣ Uploading...")
            if not await upload_to_telegram(final_file, title):
                print("❌ Upload failed")
                current_attempt += 1
                time.sleep(2)
                continue
            
            # Success!
            try:
                shutil.rmtree(temp_dir)
                print("🗑️ Cleaned temp files")
            except:
                pass
            
            return True, "✅ Success"
            
        except Exception as e:
            print(f"❌ Attempt {current_attempt} failed: {e}")
            current_attempt += 1
            time.sleep(3)
    
    # All attempts failed
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except:
        pass
    
    return False, "❌ All attempts failed"

async def main():
    """Main function"""
    print("="*60)
    print("🎬 VK Ultimate Downloader v3.0")
    print("🌐 Browser-like requests with segment downloading")
    print("🔄 Multiple attempts with different approaches")
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
