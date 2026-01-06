#!/usr/bin/env python3
"""
Universal Video Uploader - Enhanced Version
Supports multiple sites including vidspeed.org
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
from urllib.parse import urlparse, urljoin, parse_qs, quote
from html import unescape

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
requirements = ["pyrogram", "tgcrypto", "yt-dlp", "requests", "beautifulsoup4", 
                "cloudscraper", "lxml", "cfscrape", "selenium-wire"]
for req in requirements:
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", req, "--quiet"])
        print(f"  ✅ {req}")
    except:
        print(f"  ⚠️ Failed to install {req}")

from pyrogram import Client
from pyrogram.errors import FloodWait
import yt_dlp
from bs4 import BeautifulSoup
import cloudscraper

app = None

# Enhanced headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0',
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

def normalize_url(url):
    """Normalize URL"""
    if not url:
        return url
    
    # Fix common URL issues
    url = url.strip()
    url = url.replace('\\/', '/')
    url = url.replace('\\\\', '\\')
    url = url.replace('\\"', '"')
    url = unescape(url)
    
    # Ensure protocol
    if url.startswith('//'):
        url = 'https:' + url
    elif not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    return url

def extract_vidspeed_video(url):
    """Extract video from vidspeed.org"""
    print("🔍 Extracting from vidspeed.org...")
    
    try:
        scraper = cloudscraper.create_scraper()
        
        # Fetch the page
        response = scraper.get(url, headers=HEADERS, timeout=30)
        
        if response.status_code != 200:
            print(f"⚠️ HTTP {response.status_code}")
            return None
        
        html = response.text
        
        # Method 1: Look for iframe sources
        iframe_patterns = [
            r'iframe[^>]*src=["\']([^"\']+)["\']',
            r'player\.setSource\s*\(\s*["\']([^"\']+)["\']',
            r'sources\s*:\s*\[\s*["\']([^"\']+)["\']',
        ]
        
        for pattern in iframe_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                video_url = normalize_url(match)
                if video_url and ('http' in video_url or '.mp4' in video_url or '.m3u8' in video_url):
                    print(f"✅ Found video URL in iframe: {video_url[:100]}...")
                    return video_url
        
        # Method 2: Look for video sources in script tags
        script_patterns = [
            r'file\s*:\s*["\']([^"\']+)["\']',
            r'src\s*:\s*["\']([^"\']+)["\']',
            r'video_url\s*:\s*["\']([^"\']+)["\']',
            r'url\s*:\s*["\']([^"\']+)["\']',
            r'mp4["\' ]*:["\' ]*([^"\'\s,]+)',
            r'"mp4":"([^"]+)"',
        ]
        
        for pattern in script_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                video_url = normalize_url(match)
                if video_url and ('mp4' in video_url or 'm3u8' in video_url):
                    print(f"✅ Found video URL in script: {video_url[:100]}...")
                    return video_url
        
        # Method 3: Look for video tags
        soup = BeautifulSoup(html, 'html.parser')
        video_tags = soup.find_all('video')
        for video in video_tags:
            source = video.find('source')
            if source and source.get('src'):
                video_url = normalize_url(source.get('src'))
                if video_url:
                    print(f"✅ Found video URL in video tag: {video_url[:100]}...")
                    return video_url
        
        # Method 4: Look for JSON data
        json_patterns = [
            r'playerConfig\s*=\s*({[^}]+})',
            r'config\s*=\s*({[^}]+})',
            r'videoData\s*=\s*({[^}]+})',
        ]
        
        for pattern in json_patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    json_str = match.group(1)
                    json_str = json_str.replace('\\"', '"').replace("\\'", "'")
                    data = json.loads(json_str)
                    
                    # Search for video URLs in JSON
                    def search_json(obj):
                        if isinstance(obj, dict):
                            for key, value in obj.items():
                                if isinstance(value, str) and ('mp4' in value or 'm3u8' in value):
                                    video_url = normalize_url(value)
                                    if video_url:
                                        return video_url
                                elif isinstance(value, (dict, list)):
                                    result = search_json(value)
                                    if result:
                                        return result
                        elif isinstance(obj, list):
                            for item in obj:
                                result = search_json(item)
                                if result:
                                    return result
                        return None
                    
                    video_url = search_json(data)
                    if video_url:
                        print(f"✅ Found video URL in JSON: {video_url[:100]}...")
                        return video_url
                except:
                    pass
        
        # Method 5: Look for base64 encoded data
        base64_patterns = [
            r'data-video=["\']([^"\']+)["\']',
            r'data-src=["\']([^"\']+)["\']',
            r'base64,[^"\']*',
        ]
        
        for pattern in base64_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                if len(match) > 100:  # Likely a video URL
                    video_url = normalize_url(match)
                    print(f"✅ Found video URL in data attribute: {video_url[:100]}...")
                    return video_url
        
        print("❌ Could not extract video URL from vidspeed")
        return None
        
    except Exception as e:
        print(f"⚠️ vidspeed extraction error: {e}")
        return None

def extract_streamtape_video(url):
    """Extract video from streamtape"""
    print("🔍 Extracting from streamtape...")
    
    try:
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url, headers=HEADERS, timeout=30)
        
        if response.status_code != 200:
            return None
        
        html = response.text
        
        # Look for the video URL pattern
        patterns = [
            r'ById\("videolink"\)\.innerHTML\s*=\s*["\']([^"\']+)["\']',
            r'getElementById\(["\']videolink["\']\)[^=]+=\s*["\']([^"\']+)["\']',
            r'video.src\s*=\s*["\']([^"\']+)["\']',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                video_url = match.group(1)
                video_url = normalize_url(video_url)
                if video_url.startswith('//'):
                    video_url = 'https:' + video_url
                print(f"✅ Found streamtape URL: {video_url[:100]}...")
                return video_url
        
        return None
    except Exception as e:
        print(f"⚠️ streamtape error: {e}")
        return None

def extract_doodstream_video(url):
    """Extract video from doodstream"""
    print("🔍 Extracting from doodstream...")
    
    try:
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url, headers=HEADERS, timeout=30)
        
        if response.status_code != 200:
            return None
        
        html = response.text
        
        # Look for the pass_md5 pattern
        match = re.search(r"/pass_md5/[^'\"]+", html)
        if match:
            base_url = match.group(0)
            # Get the token
            token_match = re.search(r"token=([^&'\"]+)", html)
            if token_match:
                token = token_match.group(1)
                video_url = f"https://dood.pm{base_url}/{token}"
                print(f"✅ Found doodstream URL: {video_url[:100]}...")
                return video_url
        
        return None
    except Exception as e:
        print(f"⚠️ doodstream error: {e}")
        return None

def extract_mp4upload_video(url):
    """Extract video from mp4upload"""
    print("🔍 Extracting from mp4upload...")
    
    try:
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url, headers=HEADERS, timeout=30)
        
        if response.status_code != 200:
            return None
        
        html = response.text
        
        # Look for the video URL
        match = re.search(r'src:\s*["\']([^"\']+\.mp4[^"\']*)["\']', html)
        if match:
            video_url = normalize_url(match.group(1))
            print(f"✅ Found mp4upload URL: {video_url[:100]}...")
            return video_url
        
        return None
    except Exception as e:
        print(f"⚠️ mp4upload error: {e}")
        return None

def extract_videobin_video(url):
    """Extract video from videobin.co"""
    print("🔍 Extracting from videobin...")
    
    try:
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url, headers=HEADERS, timeout=30)
        
        if response.status_code != 200:
            return None
        
        html = response.text
        
        # Look for video source
        patterns = [
            r'playerInstance\.setup\(\s*{[\s\S]*?sources\s*:\s*\[\s*{\s*file\s*:\s*["\']([^"\']+)["\']',
            r'src\s*:\s*["\']([^"\']+\.mp4[^"\']*)["\']',
            r'file["\' ]*:["\' ]*["\' ]*([^"\'\s,]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                video_url = normalize_url(match.group(1))
                if video_url:
                    print(f"✅ Found videobin URL: {video_url[:100]}...")
                    return video_url
        
        return None
    except Exception as e:
        print(f"⚠️ videobin error: {e}")
        return None

def extract_vk_video_enhanced(url):
    """Enhanced VK video extraction"""
    print("🔍 Enhanced VK extraction...")
    
    try:
        # Normalize VK URL
        if 'video_ext.php' not in url and 'vk.com/video' in url:
            match = re.match(r'.*vk\.com/video(\d+)_(\d+)', url)
            if match:
                oid = match.group(1)
                vid = match.group(2)
                url = f"https://vk.com/video_ext.php?oid={oid}&id={vid}"
        
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url, headers=HEADERS, timeout=30)
        
        if response.status_code != 200:
            return None
        
        html = response.text
        
        # Multiple extraction methods for VK
        patterns = [
            r'"url[0-9]*":"([^"]+)"',
            r'"hls":"([^"]+)"',
            r'video[^"]*"url":"([^"]+)"',
            r'src="([^"]+\.m3u8[^"]*)"',
            r'file":"([^"]+)"',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html)
            for match in matches:
                video_url = normalize_url(match)
                if video_url and ('mp4' in video_url or 'm3u8' in video_url):
                    print(f"✅ Found VK URL: {video_url[:100]}...")
                    
                    # If it's m3u8, get the lowest quality
                    if '.m3u8' in video_url:
                        # Simple m3u8 quality selection
                        try:
                            m3u8_response = requests.get(video_url, headers=HEADERS, timeout=10)
                            if m3u8_response.status_code == 200:
                                lines = m3u8_response.text.split('\n')
                                for line in lines:
                                    if line and not line.startswith('#') and '.m3u8' in line:
                                        if not line.startswith('http'):
                                            base = '/'.join(video_url.split('/')[:-1])
                                            line = f"{base}/{line}"
                                        return line
                        except:
                            pass
                    
                    return video_url
        
        return None
    except Exception as e:
        print(f"⚠️ VK enhanced error: {e}")
        return None

def extract_generic_embed(url):
    """Generic embed video extraction"""
    print("🔍 Generic embed extraction...")
    
    try:
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url, headers=HEADERS, timeout=30)
        
        if response.status_code != 200:
            return None
        
        html = response.text
        
        # Comprehensive patterns for various sites
        patterns = [
            # JavaScript patterns
            r'file["\']?\s*:\s*["\']([^"\']+)["\']',
            r'sources?\s*:\s*\[\s*{\s*file\s*:\s*["\']([^"\']+)["\']',
            r'player\.(?:load|setup)\([^)]*["\']([^"\']+\.(?:mp4|m3u8))["\']',
            r'video(?:URL|Src)\s*[=:]\s*["\']([^"\']+)["\']',
            
            # HTML patterns
            r'<source[^>]+src=["\']([^"\']+)["\']',
            r'video[^>]+src=["\']([^"\']+)["\']',
            r'iframe[^>]+src=["\']([^"\']+)["\']',
            
            # Data patterns
            r'data-(?:video|src|file)=["\']([^"\']+)["\']',
            
            # Direct URL patterns
            r'(https?://[^\s"\']+\.(?:mp4|m3u8|webm|avi|mkv|flv)[^\s"\']*)',
            r'(https?://[^\s"\']+/video/[^\s"\']+)',
            r'(https?://[^\s"\']+/v/[^\s"\']+)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                if isinstance(match, str):
                    video_url = normalize_url(match)
                    
                    # Filter out false positives
                    if (video_url and len(video_url) > 20 and 
                        any(ext in video_url.lower() for ext in ['.mp4', '.m3u8', '.webm', 'video', '/v/']) and
                        not any(bad in video_url.lower() for bad in ['google', 'facebook', 'twitter', 'script', '.js', '.css'])):
                        
                        print(f"✅ Found generic URL: {video_url[:100]}...")
                        
                        # If it's a relative URL, make it absolute
                        if video_url.startswith('//'):
                            video_url = 'https:' + video_url
                        elif video_url.startswith('/'):
                            parsed = urlparse(url)
                            video_url = f"{parsed.scheme}://{parsed.netloc}{video_url}"
                        
                        return video_url
        
        # Try to find iframe and extract from it
        soup = BeautifulSoup(html, 'html.parser')
        iframes = soup.find_all('iframe')
        for iframe in iframes:
            src = iframe.get('src', '')
            if src and 'http' in src:
                print(f"🔍 Found iframe: {src}")
                # Recursively extract from iframe
                nested_url = extract_video_url(src)
                if nested_url:
                    return nested_url
        
        return None
    except Exception as e:
        print(f"⚠️ Generic embed error: {e}")
        return None

def extract_with_ytdlp(url):
    """Extract video URL using yt-dlp"""
    print("🔍 Trying yt-dlp extractor...")
    
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 30,
            'extract_flat': False,
            'force_generic_extractor': True,
            'http_headers': HEADERS,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return None
            
            # Try to get direct URL
            if 'url' in info:
                video_url = info['url']
                print(f"✅ yt-dlp found direct URL: {video_url[:100]}...")
                return video_url
            
            # Try formats
            elif 'formats' in info and info['formats']:
                # Get the worst quality (for smaller file size)
                formats = [f for f in info['formats'] if f.get('vcodec') != 'none']
                if formats:
                    formats.sort(key=lambda x: x.get('height', 0))
                    selected = formats[0]
                    video_url = selected['url']
                    height = selected.get('height', 0)
                    print(f"✅ yt-dlp found {height}p URL")
                    return video_url
            
            return None
            
    except Exception as e:
        print(f"⚠️ yt-dlp extraction failed: {e}")
        return None

def extract_video_url(url):
    """Main video URL extraction function"""
    print(f"\n🎬 Extracting video from: {url}")
    
    # Normalize URL
    url = normalize_url(url)
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    
    # Site-specific extractors
    extractors = [
        # vidspeed and similar
        ('vidspeed.org', extract_vidspeed_video),
        ('streamtape.com', extract_streamtape_video),
        ('doodstream.com', extract_doodstream_video),
        ('dood.pm', extract_doodstream_video),
        ('mp4upload.com', extract_mp4upload_video),
        ('videobin.co', extract_videobin_video),
        ('vk.com', extract_vk_video_enhanced),
        ('vkontakte', extract_vk_video_enhanced),
    ]
    
    # Try site-specific extractor first
    for site_pattern, extractor in extractors:
        if site_pattern in domain:
            print(f"🔄 Using {site_pattern} extractor...")
            result = extractor(url)
            if result:
                return result
    
    # Try generic embed extractor
    print("🔄 Trying generic embed extractor...")
    result = extract_generic_embed(url)
    if result:
        return result
    
    # Try yt-dlp as fallback
    print("🔄 Trying yt-dlp as fallback...")
    result = extract_with_ytdlp(url)
    if result:
        return result
    
    # Last resort: direct URL (for some embedded players)
    print("🔄 Checking if URL is already direct video...")
    if any(ext in url.lower() for ext in ['.mp4', '.m3u8', '.webm', 'video/', '/v/']):
        print(f"✅ URL appears to be direct video")
        return url
    
    print("❌ All extraction methods failed")
    return None

def download_with_ytdlp(url, output_path):
    """Download video using yt-dlp with adaptive quality selection"""
    print("📥 Downloading with yt-dlp...")
    
    try:
        # Check if it's a direct video URL
        is_direct = any(ext in url.lower() for ext in ['.mp4', '.m3u8', '.webm', '.avi', '.mkv', '.flv'])
        
        if is_direct:
            print("🔗 Direct video URL detected")
            # Use ffmpeg for direct URLs
            cmd = [
                'ffmpeg',
                '-i', url,
                '-c', 'copy',
                '-bsf:a', 'aac_adtstoasc',
                '-y',
                output_path
            ]
            
            print(f"🔄 Downloading with ffmpeg...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            
            if result.returncode == 0 and os.path.exists(output_path):
                file_size = os.path.getsize(output_path) / (1024 * 1024)
                print(f"✅ FFmpeg download complete: {file_size:.1f} MB")
                return True
            else:
                print(f"⚠️ FFmpeg failed: {result.stderr[:200]}")
        
        # Use yt-dlp with adaptive quality selection
        ydl_opts = {
            'outtmpl': output_path,
            # Adaptive quality selection: worst quality but at least 240p if available
            'format': 'worst[height>=240]/worst',
            'quiet': False,
            'no_warnings': False,
            'socket_timeout': 30,
            'retries': 10,
            'fragment_retries': 10,
            'skip_unavailable_fragments': True,
            'http_headers': HEADERS,
            'extractor_args': {
                'generic': ['--referer', url],
            },
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
        }
        
        print(f"🎬 Downloading with yt-dlp...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            if info:
                height = info.get('height', 0)
                print(f"📊 Downloaded {height}p quality")
        
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path) / (1024 * 1024)
            print(f"✅ Download complete: {file_size:.1f} MB")
            return True
        else:
            print("❌ Download failed")
            return False
            
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return False

def download_fallback(url, output_path):
    """Fallback download method"""
    print("🔄 Using fallback download...")
    
    try:
        headers = HEADERS.copy()
        response = requests.get(url, headers=headers, stream=True, timeout=60)
        
        if response.status_code != 200:
            print(f"❌ HTTP {response.status_code}")
            return False
        
        total_size = int(response.headers.get('content-length', 0))
        print(f"📥 Downloading {total_size / (1024*1024):.1f} MB...")
        
        with open(output_path, 'wb') as f:
            downloaded = 0
            start_time = time.time()
            
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # Show progress every 10MB
                    if downloaded % (10 * 1024 * 1024) < 8192:
                        elapsed = time.time() - start_time
                        speed = downloaded / elapsed / 1024 if elapsed > 0 else 0
                        print(f"📥 {downloaded / (1024*1024):.1f} MB - {speed:.0f} KB/s")
        
        elapsed = time.time() - start_time
        final_size = os.path.getsize(output_path) / (1024 * 1024)
        print(f"✅ Fallback download complete: {final_size:.1f} MB in {elapsed:.1f}s")
        
        return final_size > 1
        
    except Exception as e:
        print(f"❌ Fallback download failed: {e}")
        return False

def compress_video(input_path, output_path):
    """Compress video to 240p"""
    print("🎬 Compressing video...")
    
    if not os.path.exists(input_path):
        print("❌ Input file not found")
        return False
    
    input_size = os.path.getsize(input_path) / (1024 * 1024)
    print(f"📊 Input size: {input_size:.1f} MB")
    
    # Check current resolution
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
    
    # Compress to 240p
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
        reduction = ((input_size - output_size) / input_size) * 100 if input_size > 0 else 0
        
        print(f"✅ Compression complete in {elapsed:.1f}s")
        print(f"📊 Output size: {output_size:.1f} MB (-{reduction:.1f}%)")
        return True
    else:
        print("❌ Compression failed")
        if result.stderr:
            print(f"Error: {result.stderr[:200]}")
        return False

def create_thumbnail(input_path, output_path):
    """Create thumbnail from video"""
    try:
        print("🖼️ Creating thumbnail...")
        
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-ss', '00:00:05',
            '-vframes', '1',
            '-s', '320x180',
            '-f', 'image2',
            '-y',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and os.path.exists(output_path):
            size = os.path.getsize(output_path) / 1024
            print(f"✅ Thumbnail created ({size:.1f}KB)")
            return True
        
        return False
    except:
        return False

async def upload_to_telegram(file_path, caption, thumbnail_path=None):
    """Upload video to Telegram"""
    print("☁️ Uploading to Telegram...")
    
    try:
        # Get video info
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,duration',
            '-of', 'json',
            file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            info = json.loads(result.stdout)
            streams = info.get('streams', [])
            if streams:
                width = streams[0].get('width', 426)
                height = streams[0].get('height', 240)
                duration = int(float(streams[0].get('duration', 0)))
            else:
                width, height, duration = 426, 240, 0
        else:
            width, height, duration = 426, 240, 0
        
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
        
        if thumbnail_path and os.path.exists(thumbnail_path):
            upload_params['thumb'] = thumbnail_path
        
        print(f"📐 Video: {width}x{height}, Duration: {duration}s")
        
        # Upload with progress
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
        return await upload_to_telegram(file_path, caption, thumbnail_path)
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return False

async def process_video(url, title):
    """Process a single video"""
    print(f"\n{'='*60}")
    print(f"🎬 Processing: {title}")
    print(f"🔗 URL: {url}")
    print(f"{'='*60}")
    
    # Create temp directory
    timestamp = datetime.now().strftime('%H%M%S')
    temp_dir = f"temp_{timestamp}"
    os.makedirs(temp_dir, exist_ok=True)
    
    temp_file = os.path.join(temp_dir, "video.mp4")
    final_file = os.path.join(temp_dir, "video_240p.mp4")
    thumbnail_file = os.path.join(temp_dir, "thumbnail.jpg")
    
    try:
        # Step 1: Extract video URL
        print("1️⃣ Extracting video URL...")
        video_url = extract_video_url(url)
        
        if not video_url:
            print("❌ Failed to extract video URL")
            return False, "Extraction failed"
        
        print(f"✅ Extracted URL: {video_url[:100]}...")
        
        # Step 2: Download
        print("2️⃣ Downloading...")
        if not download_with_ytdlp(video_url, temp_file):
            print("🔄 Trying fallback download...")
            if not download_fallback(video_url, temp_file):
                return False, "Download failed"
        
        # Check file
        if not os.path.exists(temp_file) or os.path.getsize(temp_file) < 1024:
            return False, "Downloaded file is invalid"
        
        # Step 3: Compress if needed
        print("3️⃣ Checking quality...")
        try:
            cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', 
                   '-show_entries', 'stream=height', '-of', 'csv=p=0:nk=1', temp_file]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                height = result.stdout.strip()
                if height.isdigit() and int(height) <= 240:
                    print(f"✅ Video is {height}p, no compression needed")
                    final_file = temp_file
                else:
                    print(f"📊 Video is {height}p, compressing to 240p...")
                    if not compress_video(temp_file, final_file):
                        print("⚠️ Compression failed, using original")
                        final_file = temp_file
            else:
                print("⚠️ Could not check height, trying compression...")
                if not compress_video(temp_file, final_file):
                    final_file = temp_file
        except:
            print("⚠️ Error checking quality, using original")
            final_file = temp_file
        
        # Verify final file
        if not os.path.exists(final_file):
            final_file = temp_file
        
        # Step 4: Create thumbnail
        print("4️⃣ Creating thumbnail...")
        create_thumbnail(final_file, thumbnail_file)
        
        # Step 5: Upload
        print("5️⃣ Uploading...")
        thumb = thumbnail_file if os.path.exists(thumbnail_file) else None
        
        if not await upload_to_telegram(final_file, title, thumb):
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
    print("🎬 Universal Video Uploader v5.0")
    print("🌐 Supports: vidspeed.org, streamtape, doodstream, mp4upload,")
    print("             videobin, VK, and many other sites")
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
        success, message = await process_video(url, title)
        
        if success:
            successful += 1
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
        
        # Wait between videos
        if index < len(videos):
            print("⏳ Waiting 3 seconds...")
            await asyncio.sleep(3)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"📊 Result: {successful}/{len(videos)} successful")
    
    if successful > 0:
        print("✅ Processing complete")
    else:
        print("❌ All videos failed")
    
    # Cleanup
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
