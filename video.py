#!/usr/bin/env python3
"""
Universal Video Uploader - For Movies
Works with VK.com and other sites
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
from datetime import datetime
from urllib.parse import urlparse, parse_qs

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
    """Clean VK URL from escape characters"""
    if not url:
        return url
    
    # Remove backslashes
    url = url.replace('\\/', '/').replace('\\\\', '\\')
    url = url.replace('\\"', '"').replace("\\'", "'")
    
    # Fix https://
    if url.startswith('https:\\/\\/'):
        url = url.replace('https:\\/\\/', 'https://')
    elif url.startswith('http:\\/\\/'):
        url = url.replace('http:\\/\\/', 'http://')
    
    return url.strip()

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
                        if url:
                            print(f"✅ Found URL with pattern: {pattern[:30]}...")
                            return url
        
        # Method 2: Look for iframe
        print("🔍 Searching for iframe...")
        soup = BeautifulSoup(response.text, 'html.parser')
        iframe = soup.find('iframe')
        
        if iframe and iframe.get('src'):
            iframe_url = iframe['src']
            if iframe_url.startswith('//'):
                iframe_url = 'https:' + iframe_url
            
            print(f"📺 Found iframe: {iframe_url[:100]}...")
            
            # Fetch iframe content
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
            except:
                pass
        
        # Method 3: Look for direct video URLs
        print("🔍 Searching for direct video URLs...")
        direct_patterns = [
            r'https?://[^\s"\']+\.m3u8[^\s"\']*',
            r'https?://vkvd[0-9]+\.okcdn\.ru/[^\s"\']+',
            r'https?://cs[0-9]+\.vk\.me/[^\s"\']+',
        ]
        
        for pattern in direct_patterns:
            matches = re.findall(pattern, response.text)
            for match in matches:
                url = clean_vk_url(match)
                if url:
                    print(f"✅ Found direct URL: {url[:100]}...")
                    return url
        
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
    
    # For other sites, try yt-dlp
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'worst[height<=240]/worst',
            'socket_timeout': 30,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info and 'url' in info:
                video_url = info['url']
                print(f"✅ Found video URL via yt-dlp")
                return video_url
    except Exception as e:
        print(f"⚠️ yt-dlp failed: {e}")
    
    return None

def download_video(url, output_path):
    """Download video"""
    print(f"📥 Downloading: {url[:100]}...")
    
    # Clean URL if it's from VK
    url = clean_vk_url(url)
    
    try:
        # Check if it's an m3u8 stream
        if '.m3u8' in url:
            print("🎬 Detected HLS stream, using ffmpeg...")
            
            cmd = [
                'ffmpeg',
                '-i', url,
                '-c', 'copy',
                '-bsf:a', 'aac_adtstoasc',
                '-y',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and os.path.exists(output_path):
                size = os.path.getsize(output_path) / (1024*1024)
                print(f"✅ Downloaded HLS stream: {size:.1f}MB")
                return True
            else:
                print(f"❌ HLS download failed")
                return False
        
        # For regular downloads, use yt-dlp
        ydl_opts = {
            'format': 'worst[height<=240]/worst',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 30,
            'user_agent': HEADERS['User-Agent'],
            'http_headers': HEADERS,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        if os.path.exists(output_path):
            size = os.path.getsize(output_path) / (1024*1024)
            print(f"✅ Downloaded: {size:.1f}MB")
            return True
            
    except Exception as e:
        print(f"❌ Download failed: {e}")
    
    return False

async def upload_to_telegram(file_path, caption):
    """Upload to Telegram channel"""
    print(f"☁️ Uploading: {os.path.basename(file_path)}")
    
    # Get file size
    file_size = os.path.getsize(file_path) / (1024*1024)
    print(f"📊 File size: {file_size:.1f}MB")
    
    try:
        # First try with progress
        def progress(current, total):
            percent = (current / total) * 100
            print(f"📤 {percent:.0f}%")
        
        await app.send_video(
            chat_id=TELEGRAM_CHANNEL,
            video=file_path,
            caption=caption,
            supports_streaming=True,
            progress=progress
        )
        print("✅ Uploaded successfully")
        return True
        
    except FloodWait as e:
        print(f"⏳ Flood wait: {e.value}s")
        await asyncio.sleep(e.value)
        return await upload_to_telegram(file_path, caption)
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        # Try without progress callback
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
            print(f"❌ Retry also failed: {e2}")
            return False

async def process_movie(video_url, video_title):
    """Process a single movie"""
    print(f"\n{'─'*50}")
    print(f"🎬 Processing: {video_title}")
    print(f"🔗 URL: {video_url}")
    print(f"{'─'*50}")
    
    # Create temp directory
    timestamp = datetime.now().strftime('%H%M%S')
    temp_dir = f"temp_movie_{timestamp}"
    os.makedirs(temp_dir, exist_ok=True)
    output_file = os.path.join(temp_dir, "movie.mp4")
    
    try:
        # Step 1: Extract URL
        print("1️⃣ Extracting video URL...")
        direct_url = extract_video_url(video_url)
        if not direct_url:
            print("❌ URL extraction failed, trying alternative method...")
            
            # Try alternative method for VK
            if 'vk.com' in video_url:
                # Try to construct URL manually
                # Extract video ID from URL
                match = re.search(r'oid=(\d+)&id=(\d+)', video_url)
                if match:
                    oid = match.group(1)
                    vid = match.group(2)
                    # Try common VK CDN pattern
                    test_url = f"https://vkvd651.okcdn.ru/video.m3u8?oid={oid}&id={vid}"
                    print(f"🔄 Testing: {test_url[:100]}...")
                    
                    # Check if URL exists
                    try:
                        response = requests.head(test_url, headers=HEADERS, timeout=10)
                        if response.status_code == 200:
                            direct_url = test_url
                            print("✅ Found alternative URL")
                    except:
                        pass
            
            if not direct_url:
                return False, "URL extraction failed"
        
        print(f"✅ Found URL: {direct_url[:100]}...")
        
        # Step 2: Download
        print("2️⃣ Downloading video...")
        if not download_video(direct_url, output_file):
            return False, "Download failed"
        
        # Step 3: Upload
        print("3️⃣ Uploading to Telegram...")
        if not await upload_to_telegram(output_file, video_title):
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
    print("🎬 Movie Uploader v2.0")
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
            print("⏳ Waiting 3 seconds before next video...")
            await asyncio.sleep(3)
    
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
