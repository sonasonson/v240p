#!/usr/bin/env python3
"""
Video Uploader - Focused on vidspeed.org
Download minimum quality then compress to 240p
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
import cloudscraper
from datetime import datetime
from urllib.parse import urlparse

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
requirements = ["pyrogram", "tgcrypto", "requests", "cloudscraper"]
for req in requirements:
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", req, "--quiet"])
        print(f"  ✅ {req}")
    except:
        print(f"  ❌ {req}")

from pyrogram import Client
from pyrogram.errors import FloodWait

app = None

# Headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
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

def extract_vidspeed_hls(url):
    """Extract HLS URL from vidspeed using direct curl approach"""
    print("🔍 Extracting HLS from vidspeed...")
    
    try:
        # First, try to get the page with cloudscraper
        scraper = cloudscraper.create_scraper()
        
        headers = HEADERS.copy()
        headers['Referer'] = 'https://vidspeed.org/'
        
        print("🌐 Fetching page with cloudscraper...")
        response = scraper.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"⚠️ HTTP {response.status_code} with cloudscraper")
            return None
        
        content = response.text
        
        # Save page for debugging
        with open('vidspeed_page.html', 'w', encoding='utf-8') as f:
            f.write(content)
        print("📝 Saved page content")
        
        # Look for m3u8 URL patterns
        patterns = [
            r'https?://[^"\'\s]+\.m3u8[^"\'\s]*',
            r'"file"\s*:\s*"([^"]+\.m3u8[^"]*)"',
            r'"sources"\s*:\s*\[[^\]]*"([^"]+\.m3u8[^"]*)"[^\]]*\]',
            r'//[^"\'\s]+\.m3u8[^"\'\s]*',
        ]
        
        all_urls = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, str):
                    url_clean = match.strip('"\'')
                    if url_clean.startswith('//'):
                        url_clean = 'https:' + url_clean
                    if '.m3u8' in url_clean and url_clean not in all_urls:
                        all_urls.append(url_clean)
        
        print(f"📊 Found {len(all_urls)} potential HLS URLs")
        
        # Filter for vidspeed CDN URLs
        cdn_urls = [u for u in all_urls if 'cdnz.quest' in u or 'vsped-' in u]
        
        if cdn_urls:
            print("🔗 Potential CDN URLs:")
            for i, hls_url in enumerate(cdn_urls[:3]):
                print(f"  {i+1}. {hls_url[:80]}...")
            
            # Try the first one
            hls_url = cdn_urls[0]
            print(f"🎯 Trying: {hls_url[:80]}...")
            
            # Test the URL
            test_headers = headers.copy()
            test_headers['Referer'] = url
            
            try:
                test_response = requests.head(hls_url, headers=test_headers, timeout=10, allow_redirects=True)
                if test_response.status_code == 200:
                    print(f"✅ HLS URL works!")
                    return hls_url
                else:
                    print(f"⚠️ URL returned HTTP {test_response.status_code}")
            except Exception as e:
                print(f"⚠️ Error testing URL: {e}")
        
        # If no URLs found in page, try to construct from video ID
        print("🔄 Trying to construct URL from video ID...")
        video_id = url.split('/')[-1].replace('.html', '').replace('embed-', '')
        print(f"🎯 Video ID: {video_id}")
        
        # Based on network logs pattern
        constructed_urls = [
            f"https://vsped-fs11-u3z.cdnz.quest/hls2/04/00177/{video_id}_,l,n,.urlset/master.m3u8",
            f"https://vsped-fs11-u3z.cdnz.quest/hls2/04/00177/{video_id}_/master.m3u8",
        ]
        
        for const_url in constructed_urls:
            print(f"🔗 Testing constructed URL: {const_url}")
            try:
                test_headers = headers.copy()
                test_headers['Referer'] = url
                test_response = requests.head(const_url, headers=test_headers, timeout=10)
                if test_response.status_code == 200:
                    print(f"✅ Constructed URL works!")
                    return const_url
            except:
                continue
        
        return None
        
    except Exception as e:
        print(f"⚠️ Extraction error: {e}")
        import traceback
        traceback.print_exc()
        return None

def download_hls_with_ffmpeg(hls_url, output_path):
    """Download HLS stream using ffmpeg"""
    print("📥 Downloading HLS with ffmpeg...")
    
    try:
        # Build ffmpeg command
        cmd = [
            'ffmpeg',
            '-user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            '-referer', 'https://vidspeed.org/',
            '-i', hls_url,
            '-c', 'copy',
            '-bsf:a', 'aac_adtstoasc',
            '-y',
            output_path
        ]
        
        print(f"🔄 Running: ffmpeg -i [HLS_URL] -c copy {output_path}")
        
        # Run with timeout
        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # 30 minutes
        
        elapsed = time.time() - start_time
        
        if result.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path) / (1024 * 1024)
            print(f"✅ Download complete in {elapsed:.1f}s: {file_size:.1f} MB")
            return True
        else:
            print(f"❌ FFmpeg failed with code {result.returncode}")
            if result.stderr:
                print(f"Error: {result.stderr[:200]}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Download timed out after 30 minutes")
        return False
    except Exception as e:
        print(f"❌ Download error: {e}")
        return False

def compress_to_240p(input_path, output_path):
    """Compress video to 240p"""
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
    
    print("🔄 Starting compression...")
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
    
    return 426, 240

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
    """Upload to Telegram channel"""
    print(f"☁️ Uploading: {os.path.basename(file_path)}")
    
    file_size = os.path.getsize(file_path) / (1024*1024)
    print(f"📊 File size: {file_size:.1f} MB")
    
    try:
        width, height = get_video_dimensions(file_path)
        duration = get_video_duration(file_path)
        
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
            print(f"🖼️ Using thumbnail")
        
        print(f"📐 Dimensions: {width}x{height}")
        print(f"⏱️ Duration: {duration}s")
        
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
        print(f"✅ Uploaded in {elapsed:.1f}s")
        return True
        
    except FloodWait as e:
        print(f"⏳ Flood wait: {e.value}s")
        await asyncio.sleep(e.value)
        return await upload_to_telegram(file_path, caption, thumbnail_path)
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        try:
            if 'progress' in upload_params:
                upload_params.pop('progress')
            await app.send_video(**upload_params)
            print("✅ Upload successful (without progress)")
            return True
        except Exception as e2:
            print(f"❌ Retry failed: {e2}")
            return False

async def process_vidspeed_video(video_url, video_title):
    """Process a vidspeed video"""
    print(f"\n{'─'*50}")
    print(f"🎬 Processing: {video_title}")
    print(f"🔗 URL: {video_url}")
    print(f"{'─'*50}")
    
    timestamp = datetime.now().strftime('%H%M%S')
    temp_dir = f"temp_video_{timestamp}"
    os.makedirs(temp_dir, exist_ok=True)
    
    temp_file = os.path.join(temp_dir, "video.mp4")
    final_file = os.path.join(temp_dir, "video_240p.mp4")
    thumbnail_file = os.path.join(temp_dir, "thumbnail.jpg")
    
    try:
        # Step 1: Extract HLS URL
        print("1️⃣ Extracting HLS URL...")
        hls_url = extract_vidspeed_hls(video_url)
        
        if not hls_url:
            print("❌ Failed to extract HLS URL")
            return False, "HLS extraction failed"
        
        print(f"✅ Found HLS URL: {hls_url[:100]}...")
        
        # Step 2: Download with ffmpeg
        print("2️⃣ Downloading with ffmpeg...")
        if not download_hls_with_ffmpeg(hls_url, temp_file):
            print("❌ HLS download failed")
            return False, "Download failed"
        
        # Check file
        if not os.path.exists(temp_file) or os.path.getsize(temp_file) < 1024:
            print("❌ Downloaded file is invalid")
            return False, "Invalid file"
        
        # Step 3: Compress to 240p
        print("3️⃣ Checking quality...")
        try:
            cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', 
                   '-show_entries', 'stream=height', '-of', 'csv=p=0:nk=1', temp_file]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                height = result.stdout.strip()
                if height.isdigit():
                    print(f"📊 Downloaded video is {height}p")
                    
                    if int(height) <= 240:
                        print(f"✅ Video is already {height}p or lower")
                        final_file = temp_file
                    else:
                        print("🎬 Compressing to 240p...")
                        if not compress_to_240p(temp_file, final_file):
                            return False, "Compression failed"
        except:
            print("⚠️ Could not check height, trying compression...")
            if not compress_to_240p(temp_file, final_file):
                return False, "Compression failed"
        
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
            
        return True, "✅ Video processed successfully"
        
    except Exception as e:
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass
        return False, f"Error: {str(e)}"

async def main():
    """Main function"""
    print("="*50)
    print("🎬 Vidspeed Video Uploader v1.0")
    print("🎯 Strategy: Extract HLS → Download → Compress to 240p")
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
            "videos": [
                {
                    "url": "https://vidspeed.org/embed-vuwb2gl8mqyr.html",
                    "title": "فيلم تجريبي"
                }
            ]
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
        
        # Check if it's vidspeed
        if 'vidspeed.org' in url:
            success, message = await process_vidspeed_video(url, title)
        else:
            print(f"⚠️ Unsupported site: {url}")
            success = False
            message = "Unsupported site"
        
        if success:
            successful += 1
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
        
        # Wait between videos
        if index < len(videos):
            print("⏳ Waiting 5 seconds...")
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
