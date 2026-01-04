#!/usr/bin/env python3
"""
Universal Video Downloader - Fixed Version
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
from urllib.parse import urlparse, urljoin

# ===== IMPORTS =====
def install_requirements():
    print("📦 Installing requirements...")
    
    requirements = [
        "pyrogram>=2.0.0",
        "tgcrypto>=1.2.0",
        "yt-dlp>=2024.4.9",
        "requests>=2.31.0",
        "cloudscraper>=1.2.71",
        "beautifulsoup4>=4.12.0",
        "lxml>=4.9.0",
        "tldextract>=3.4.0",
    ]
    
    for req in requirements:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", req, "--quiet"])
            print(f"  ✅ {req.split('>=')[0]}")
        except:
            print(f"  ❌ Failed to install {req}")
    
    print("✅ All requirements installed")

install_requirements()

from pyrogram import Client
from pyrogram.errors import FloodWait, AuthKeyUnregistered
import yt_dlp
import cloudscraper as cs
from bs4 import BeautifulSoup
import tldextract

# ===== CONFIGURATION =====
TELEGRAM_API_ID = os.environ.get("API_ID", "")
TELEGRAM_API_HASH = os.environ.get("API_HASH", "")
TELEGRAM_CHANNEL = os.environ.get("CHANNEL", "")
STRING_SESSION = os.environ.get("STRING_SESSION", "")

app = None

# ===== SIMPLIFIED VIDEO EXTRACTOR =====

class SimpleVideoExtractor:
    """Simplified video extractor"""
    
    def __init__(self):
        self.scraper = cs.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            }
        )
    
    def extract_video(self, url):
        """Simple video extraction"""
        print(f"🔍 Extracting from: {url}")
        
        # Try yt-dlp first
        video_url = self._try_ytdlp(url)
        if video_url:
            return video_url
        
        # Try direct scraping
        video_url = self._try_scraping(url)
        if video_url:
            return video_url
        
        return url
    
    def _try_ytdlp(self, url):
        """Try yt-dlp extraction"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'force_generic_extractor': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info and 'url' in info:
                    return info['url']
        except:
            pass
        
        return None
    
    def _try_scraping(self, url):
        """Try to scrape video URL"""
        try:
            response = self.scraper.get(url, timeout=30)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for video sources
                sources = []
                
                # Video tags
                for video in soup.find_all('video'):
                    if video.get('src'):
                        sources.append(video['src'])
                    for source in video.find_all('source'):
                        if source.get('src'):
                            sources.append(source['src'])
                
                # Iframe tags
                for iframe in soup.find_all('iframe'):
                    src = iframe.get('src')
                    if src and any(x in src.lower() for x in ['embed', 'video', 'player']):
                        # Try to extract from iframe
                        iframe_url = self.extract_video(src)
                        if iframe_url:
                            return iframe_url
                
                # Script tags with video URLs
                scripts = soup.find_all('script')
                for script in scripts:
                    if script.string:
                        patterns = [
                            r'(https?://[^\s"\']+\.(?:mp4|m3u8|mkv|webm)[^\s"\']*)',
                            r'file["\']?\s*:\s*["\']([^"\']+)["\']',
                            r'src["\']?\s*:\s*["\']([^"\']+)["\']',
                        ]
                        
                        for pattern in patterns:
                            matches = re.findall(pattern, script.string, re.IGNORECASE)
                            for match in matches:
                                if any(x in match.lower() for x in ['.mp4', '.m3u8', '.mkv', '.webm']):
                                    return match
                
                # Return first valid source
                for source in sources:
                    if source:
                        # Make absolute URL
                        if source.startswith('//'):
                            source = 'https:' + source
                        elif source.startswith('/'):
                            source = urljoin(url, source)
                        
                        return source
        except:
            pass
        
        return None

# ===== DOWNLOAD FUNCTION =====

def download_video_simple(video_url, output_path):
    """Simple video download function"""
    try:
        print(f"📥 Downloading: {video_url[:100]}...")
        
        # Initialize extractor
        extractor = SimpleVideoExtractor()
        
        # Extract video URL
        extracted_url = extractor.extract_video(video_url)
        
        print(f"✅ Using URL: {extracted_url[:100]}...")
        
        # Simple yt-dlp options
        ydl_opts = {
            'format': 'best[height<=720]/best',
            'outtmpl': output_path,
            'quiet': False,
            'no_warnings': False,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'referer': video_url,
            'retries': 30,
            'fragment_retries': 30,
            'socket_timeout': 60,
            'concurrent_fragment_downloads': 8,
            'continuedl': True,
        }
        
        start = time.time()
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(extracted_url, download=False)
                if info:
                    title = info.get('title', 'Unknown')
                    print(f"📝 Title: {title}")
                    ydl.download([extracted_url])
                    actual_title = title
                else:
                    ydl.download([extracted_url])
                    actual_title = "Unknown"
        except Exception as e:
            print(f"⚠️ Error: {e}")
            # Try with simpler options
            ydl_opts['quiet'] = True
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([extracted_url])
            actual_title = "Unknown"
        
        elapsed = time.time() - start
        
        # Check if file exists
        if os.path.exists(output_path):
            size = os.path.getsize(output_path) / (1024*1024)
            print(f"✅ Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
            return True, actual_title
        else:
            # Try different extensions
            base = os.path.splitext(output_path)[0]
            for ext in ['.mp4', '.mkv', '.webm', '.avi']:
                alt_file = base + ext
                if os.path.exists(alt_file):
                    shutil.move(alt_file, output_path)
                    size = os.path.getsize(output_path) / (1024*1024)
                    print(f"✅ Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
                    return True, actual_title
        
        return False, None
        
    except Exception as e:
        print(f"❌ Download error: {e}")
        return False, None

# ===== TELEGRAM FUNCTIONS =====

async def setup_telegram():
    global app
    
    print("\n" + "="*50)
    print("🔐 Telegram Setup")
    print("="*50)
    
    if not all([TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_CHANNEL, STRING_SESSION]):
        print("❌ Missing environment variables")
        return False
    
    try:
        app = Client(
            "video_uploader",
            api_id=int(TELEGRAM_API_ID),
            api_hash=TELEGRAM_API_HASH,
            session_string=STRING_SESSION.strip(),
            in_memory=True
        )
        
        print("🔌 Connecting to Telegram...")
        await app.start()
        
        me = await app.get_me()
        print(f"✅ Connected as: {me.first_name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

def compress_video(input_file, output_file):
    """Compress video to 240p"""
    if not os.path.exists(input_file):
        return False
    
    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-vf', 'scale=-2:240',
        '-c:v', 'libx264',
        '-crf', '28',
        '-preset', 'veryfast',
        '-c:a', 'aac',
        '-b:a', '64k',
        '-y',
        output_file
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return True
    except:
        return False

async def upload_video(file_path, caption):
    """Upload video to Telegram"""
    try:
        if not app or not os.path.exists(file_path):
            return False
        
        file_size = os.path.getsize(file_path) / (1024*1024)
        print(f"☁️ Uploading: {file_size:.1f}MB")
        
        await app.send_video(
            chat_id=TELEGRAM_CHANNEL,
            video=file_path,
            caption=caption,
            supports_streaming=True
        )
        
        print("✅ Upload successful")
        return True
    except FloodWait as e:
        print(f"⏳ Flood wait: {e.value}s")
        await asyncio.sleep(e.value)
        return await upload_video(file_path, caption)
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return False

# ===== MAIN =====

async def main():
    # Check ffmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("✅ ffmpeg is installed")
    except:
        print("❌ ffmpeg not found, installing...")
        try:
            subprocess.run(['apt-get', 'update', '-y'], capture_output=True)
            subprocess.run(['apt-get', 'install', '-y', 'ffmpeg'], capture_output=True)
            print("✅ ffmpeg installed")
        except:
            print("❌ Failed to install ffmpeg")
            return
    
    # Setup Telegram
    if not await setup_telegram():
        return
    
    # Load config
    config_file = "video_config.json"
    if not os.path.exists(config_file):
        print(f"❌ Config file not found: {config_file}")
        return
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
    except:
        print(f"❌ Error reading config file")
        return
    
    videos = config.get("videos", [])
    
    if not videos:
        print("❌ No videos found in config")
        return
    
    print(f"📋 Found {len(videos)} video(s)")
    
    for video in videos:
        url = video.get("url", "")
        title = video.get("title", "Unknown")
        
        if not url:
            continue
        
        print(f"\n{'─'*50}")
        print(f"🎬 Processing: {title}")
        print(f"🔗 URL: {url[:80]}...")
        
        # Create temp directory
        temp_dir = f"temp_{int(time.time())}"
        os.makedirs(temp_dir, exist_ok=True)
        
        temp_file = os.path.join(temp_dir, "video.mp4")
        final_file = os.path.join(temp_dir, "final.mp4")
        
        # Download
        success, actual_title = download_video_simple(url, temp_file)
        
        if not success:
            print(f"❌ Download failed")
            shutil.rmtree(temp_dir, ignore_errors=True)
            continue
        
        # Compress
        if compress_video(temp_file, final_file):
            upload_file = final_file
        else:
            upload_file = temp_file
        
        # Upload
        caption = f"🎬 {actual_title if actual_title != 'Unknown' else title}"
        if await upload_video(upload_file, caption):
            print(f"✅ Process completed successfully")
        else:
            print(f"❌ Upload failed")
        
        # Cleanup
        try:
            shutil.rmtree(temp_dir)
            print(f"🗑️ Cleaned temp files")
        except:
            pass
    
    if app:
        await app.stop()
        print("🔌 Telegram connection closed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️ Stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
