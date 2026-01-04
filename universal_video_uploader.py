#!/usr/bin/env python3
"""
Universal Video Downloader - Enhanced Version
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
        "cfscrape>=1.0.0",
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
import cfscrape

# ===== CONFIGURATION =====
TELEGRAM_API_ID = os.environ.get("API_ID", "")
TELEGRAM_API_HASH = os.environ.get("API_HASH", "")
TELEGRAM_CHANNEL = os.environ.get("CHANNEL", "")
STRING_SESSION = os.environ.get("STRING_SESSION", "")

app = None

# ===== ADVANCED VIDEO EXTRACTION =====

class VideoExtractor:
    """Advanced video extractor for any site"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # Initialize scrapers
        self.cloud_scraper = cs.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            }
        )
        
        try:
            self.cf_scraper = cfscrape.create_scraper()
        except:
            self.cf_scraper = None
    
    def extract_video_url(self, url):
        """Extract video URL using multiple methods"""
        print(f"🔍 Analyzing: {url}")
        
        methods = [
            self._try_ytdlp_direct,
            self._try_cloudscraper,
            self._try_iframe_extraction,
            self._try_javascript_extraction,
            self._try_video_tag_search,
            self._try_common_patterns,
        ]
        
        for method in methods:
            try:
                result = method(url)
                if result:
                    print(f"✅ Success with {method.__name__}")
                    return result
            except Exception as e:
                print(f"⚠️ {method.__name__} failed: {e}")
                continue
        
        return None
    
    def _try_ytdlp_direct(self, url):
        """Try yt-dlp extraction"""
        print("🔄 Method 1: yt-dlp direct extraction...")
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist',
            'force_generic_extractor': False,
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            'no_check_certificate': True,
            'ignoreerrors': True,
            'skip_download': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    # Try to get the best format URL
                    if 'url' in info:
                        return info['url']
                    
                    # For playlists/extracted videos
                    if 'entries' in info and info['entries']:
                        first_entry = info['entries'][0]
                        if 'url' in first_entry:
                            return first_entry['url']
                    
                    # Look for formats
                    if 'formats' in info:
                        for fmt in reversed(info['formats']):  # Start with best quality
                            if fmt.get('url'):
                                return fmt['url']
        except:
            pass
        
        return None
    
    def _try_cloudscraper(self, url):
        """Use CloudScraper to bypass protection"""
        print("🔄 Method 2: CloudScraper extraction...")
        
        try:
            response = self.cloud_scraper.get(url, timeout=30)
            if response.status_code == 200:
                return self._extract_from_html(response.text, url)
        except:
            pass
        
        return None
    
    def _try_iframe_extraction(self, url):
        """Extract video from iframes"""
        print("🔄 Method 3: Iframe extraction...")
        
        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find all iframes
                iframes = soup.find_all('iframe')
                for iframe in iframes:
                    src = iframe.get('src')
                    if src:
                        # Make absolute URL
                        if src.startswith('//'):
                            src = 'https:' + src
                        elif src.startswith('/'):
                            src = urljoin(url, src)
                        
                        # Check if it's a video iframe
                        if any(x in src for x in ['embed', 'video', 'player', 'watch']):
                            print(f"🔗 Found iframe: {src}")
                            
                            # Try to extract from iframe
                            iframe_result = self.extract_video_url(src)
                            if iframe_result:
                                return iframe_result
        except:
            pass
        
        return None
    
    def _try_javascript_extraction(self, url):
        """Extract video URLs from JavaScript"""
        print("🔄 Method 4: JavaScript extraction...")
        
        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                content = response.text
                
                # Common patterns for video URLs in JS
                patterns = [
                    r'(?:file|src|video|source|url)\s*[=:]\s*["\'](https?://[^"\']+\.(?:mp4|m3u8|mkv|webm)[^"\']*)["\']',
                    r'["\'](https?://[^"\']+\.(?:mp4|m3u8|mkv|webm)[^"\']*)["\']',
                    r'(?:file|src|video|source|url)\s*:\s*["\']([^"\']+)["\']',
                    r'jwplayer\([^)]+\)\.setup\(({[^}]+})',
                    r'videojs\([^)]+\)\.src\(["\']([^"\']+)["\']',
                    r'<script[^>]*>\s*[^<]*var\s+[^=]*=\s*["\']([^"\']+\.(?:mp4|m3u8))["\']',
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches:
                        if isinstance(match, str):
                            video_url = match
                            # Clean up JSON if needed
                            if '{' in video_url:
                                url_match = re.search(r'["\'](https?://[^"\']+)["\']', video_url)
                                if url_match:
                                    video_url = url_match.group(1)
                            
                            if video_url and any(x in video_url.lower() for x in ['.mp4', '.m3u8', '.mkv', '.webm']):
                                # Make absolute URL
                                if video_url.startswith('//'):
                                    video_url = 'https:' + video_url
                                elif video_url.startswith('/'):
                                    video_url = urljoin(url, video_url)
                                
                                return video_url
        except:
            pass
        
        return None
    
    def _try_video_tag_search(self, url):
        """Search for video tags in HTML"""
        print("🔄 Method 5: Video tag search...")
        
        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                return self._extract_from_html(response.text, url)
        except:
            pass
        
        return None
    
    def _try_common_patterns(self, url):
        """Try common video hosting patterns"""
        print("🔄 Method 6: Common patterns...")
        
        # Known video hosting patterns
        patterns = {
            'myvidplay': r'https?://[^/]+/e/[a-zA-Z0-9]+',
            'vidplay': r'https?://[^/]+/embed\.php\?[^"\']+',
            'streamtape': r'https?://[^/]+/e/[a-zA-Z0-9]+',
            'voe': r'https?://[^/]+/e/[a-zA-Z0-9]+',
            'dood': r'https?://[^/]+/e/[a-zA-Z0-9]+',
            'mp4upload': r'https?://[^/]+/embed-[^/]+\.html',
        }
        
        for site, pattern in patterns.items():
            if re.search(pattern, url):
                print(f"✅ Matched {site} pattern")
                return url
        
        return None
    
    def _extract_from_html(self, html, base_url):
        """Extract video from HTML content"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Check for video tags
        video_tags = soup.find_all('video')
        for video in video_tags:
            src = video.get('src')
            if src:
                return self._make_absolute_url(src, base_url)
            
            # Check source tags
            sources = video.find_all('source')
            for source in sources:
                src = source.get('src')
                if src:
                    return self._make_absolute_url(src, base_url)
        
        # Check for meta tags with video URLs
        meta_tags = soup.find_all('meta', {'property': ['og:video', 'og:video:url']})
        for meta in meta_tags:
            content = meta.get('content')
            if content and any(x in content for x in ['.mp4', '.m3u8']):
                return self._make_absolute_url(content, base_url)
        
        # Check for data-src attributes
        elements = soup.find_all(attrs={"data-src": True})
        for element in elements:
            src = element.get('data-src')
            if src and any(x in src for x in ['.mp4', '.m3u8']):
                return self._make_absolute_url(src, base_url)
        
        return None
    
    def _make_absolute_url(self, url, base_url):
        """Convert relative URL to absolute"""
        if url.startswith('//'):
            return 'https:' + url
        elif url.startswith('/'):
            return urljoin(base_url, url)
        elif not url.startswith('http'):
            return urljoin(base_url, url)
        return url

# ===== DOWNLOAD FUNCTION =====

def download_with_extractor(video_url, output_path):
    """Download video using the enhanced extractor"""
    try:
        print(f"🔗 URL: {video_url[:100]}...")
        
        # Initialize extractor
        extractor = VideoExtractor()
        
        # Extract video URL
        extracted_url = extractor.extract_video_url(video_url)
        
        if not extracted_url:
            return False, None, "Failed to extract video URL"
        
        print(f"✅ Extracted URL: {extracted_url[:100]}...")
        
        # Download with yt-dlp
        ydl_opts = {
            'format': 'best[height<=720]/best',
            'outtmpl': output_path,
            'quiet': False,  # Show progress
            'no_warnings': False,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'referer': video_url,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Referer': video_url,
                'Origin': urlparse(video_url).scheme + '://' + urlparse(video_url).netloc,
            },
            'retries': 50,
            'fragment_retries': 50,
            'skip_unavailable_fragments': True,
            'socket_timeout': 180,
            'extractor_args': {
                'generic': {
                    'headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Referer': video_url,
                    }
                }
            },
            'concurrent_fragment_downloads': 15,
            'continuedl': True,
            'noprogress': False,
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            'ignoreerrors': True,
            'no_check_certificate': True,
            'extract_flat': False,
            'force_generic_extractor': True,
            'allow_unplayable_formats': True,
            'sleep_interval': 2,
            'max_sleep_interval': 10,
        }
        
        print("📥 Starting download...")
        start = time.time()
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Get info
                info = ydl.extract_info(extracted_url, download=False)
                if info:
                    title = info.get('title', 'Unknown')
                    print(f"📝 Title: {title}")
                    
                    # Download
                    ydl.download([extracted_url])
                    actual_title = title
                else:
                    ydl.download([extracted_url])
                    actual_title = "Unknown"
        except Exception as e:
            print(f"⚠️ Download error: {e}")
            # Try with simpler options
            ydl_opts['quiet'] = True
            ydl_opts['no_warnings'] = True
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([extracted_url])
            actual_title = "Unknown"
        
        elapsed = time.time() - start
        
        # Check if file was created
        if os.path.exists(output_path):
            size = os.path.getsize(output_path) / (1024*1024)
            print(f"✅ Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
            return True, actual_title, "Download successful"
        
        # Try different extensions
        base = os.path.splitext(output_path)[0]
        for ext in ['.mp4', '.mkv', '.webm', '.avi', '.flv', '.mov', '.m4v', '.ts']:
            alt_file = base + ext
            if os.path.exists(alt_file):
                shutil.move(alt_file, output_path)
                size = os.path.getsize(output_path) / (1024*1024)
                print(f"✅ Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
                return True, actual_title, "Download successful"
        
        return False, None, "No file was created"
        
    except Exception as e:
        print(f"❌ Download error: {e}")
        return False, None, str(e)

# ===== TELEGRAM FUNCTIONS =====

async def setup_telegram():
    global app
    
    print("\n" + "="*50)
    print("🔐 Telegram Setup")
    print("="*50)
    
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH or not TELEGRAM_CHANNEL or not STRING_SESSION:
        print("❌ Missing environment variables")
        return False
    
    try:
        app = Client(
            "movie_uploader",
            api_id=int(TELEGRAM_API_ID),
            api_hash=TELEGRAM_API_HASH,
            session_string=STRING_SESSION.strip(),
            in_memory=True,
            device_model="GitHub Actions",
            app_version="2.0.0",
            system_version="Ubuntu 22.04"
        )
        
        print("🔌 Connecting to Telegram...")
        await app.start()
        
        me = await app.get_me()
        print(f"✅ Connected as: {me.first_name} (@{me.username})")
        
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
        
        await app.send_video(
            chat_id=TELEGRAM_CHANNEL,
            video=file_path,
            caption=caption,
            supports_streaming=True
        )
        return True
    except:
        return False

# ===== MAIN =====

async def main():
    # Check ffmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except:
        print("❌ ffmpeg not found")
        return
    
    # Setup Telegram
    if not await setup_telegram():
        return
    
    # Load config
    config_file = "video_config.json"
    if not os.path.exists(config_file):
        print(f"❌ Config file not found")
        return
    
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    videos = config.get("videos", [])
    
    for video in videos:
        url = video.get("url", "")
        title = video.get("title", "")
        
        if not url:
            continue
        
        print(f"\n🎬 Processing: {title}")
        
        # Create temp directory
        temp_dir = f"temp_{int(time.time())}"
        os.makedirs(temp_dir, exist_ok=True)
        
        temp_file = os.path.join(temp_dir, "video.mp4")
        final_file = os.path.join(temp_dir, "final.mp4")
        
        # Download
        success, actual_title, message = download_with_extractor(url, temp_file)
        
        if success:
            # Compress
            if compress_video(temp_file, final_file):
                upload_file = final_file
            else:
                upload_file = temp_file
            
            # Upload
            caption = f"🎬 {actual_title if actual_title != 'Unknown' else title}"
            if await upload_video(upload_file, caption):
                print(f"✅ Upload successful")
            else:
                print(f"❌ Upload failed")
        else:
            print(f"❌ {message}")
        
        # Cleanup
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
    
    if app:
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
