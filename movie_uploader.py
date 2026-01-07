#!/usr/bin/env python3
"""
Telegram Movie Downloader & Uploader - Complete Version with VK Support
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
from urllib.parse import urlparse, parse_qs, unquote
import json as json_lib

# ===== CONFIGURATION =====
# Get from GitHub Secrets
TELEGRAM_API_ID = os.environ.get("API_ID", "")
TELEGRAM_API_HASH = os.environ.get("API_HASH", "")
TELEGRAM_CHANNEL = os.environ.get("CHANNEL", "")
STRING_SESSION = os.environ.get("STRING_SESSION", "")

# Validate environment variables
def validate_env():
    """Validate environment variables"""
    errors = []
    
    if not TELEGRAM_API_ID:
        errors.append("❌ API_ID is missing")
    elif not TELEGRAM_API_ID.isdigit():
        errors.append("❌ API_ID must be a number")
    
    if not TELEGRAM_API_HASH:
        errors.append("❌ API_HASH is missing")
    
    if not TELEGRAM_CHANNEL:
        errors.append("❌ CHANNEL is missing")
    
    if not STRING_SESSION:
        errors.append("❌ STRING_SESSION is missing")
    elif len(STRING_SESSION) < 200:
        errors.append(f"❌ STRING_SESSION seems too short ({len(STRING_SESSION)} chars)")
    
    if errors:
        print("\n".join(errors))
        return False
    
    print("✅ Environment variables validated")
    return True

if not validate_env():
    sys.exit(1)

TELEGRAM_API_ID = int(TELEGRAM_API_ID)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
}

# ===== IMPORTS =====
def install_requirements():
    """Install required packages"""
    print("📦 Installing requirements...")
    
    requirements = [
        "pyrogram>=2.0.0",
        "tgcrypto>=1.2.0",
        "yt-dlp>=2024.4.9",
        "requests>=2.31.0",
        "cloudscraper>=1.2.71",
        "beautifulsoup4>=4.12.0",
        "lxml>=4.9.0",
        "tls-client>=0.2.2",
    ]
    
    for req in requirements:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", req, "--quiet"])
            print(f"  ✅ {req.split('>=')[0]}")
        except:
            print(f"  ❌ Failed to install {req}")
    
    print("✅ All requirements installed")

# Install packages
install_requirements()

from pyrogram import Client
from pyrogram.errors import FloodWait, AuthKeyUnregistered, SessionPasswordNeeded
import yt_dlp
import cloudscraper
from bs4 import BeautifulSoup

app = None

# ===== TELEGRAM SETUP =====

async def setup_telegram():
    """Setup Telegram using string session"""
    global app
    
    print("\n" + "="*50)
    print("🔐 Telegram Setup")
    print("="*50)
    
    print(f"📱 API_ID: {TELEGRAM_API_ID}")
    print(f"🔑 API_HASH: {TELEGRAM_API_HASH[:10]}...")
    print(f"📢 Channel: {TELEGRAM_CHANNEL}")
    print(f"🔗 Session length: {len(STRING_SESSION)} characters")
    
    try:
        cleaned_session = STRING_SESSION.strip()
        
        print(f"🔧 Creating client with cleaned session ({len(cleaned_session)} chars)...")
        
        app = Client(
            name="movie_uploader",
            api_id=TELEGRAM_API_ID,
            api_hash=TELEGRAM_API_HASH,
            session_string=cleaned_session,
            in_memory=True,
            device_model="GitHub Actions",
            app_version="2.0.0",
            system_version="Ubuntu 22.04"
        )
        
        print("🔌 Connecting to Telegram...")
        await app.start()
        
        me = await app.get_me()
        print(f"✅ Connected as: {me.first_name} (@{me.username})")
        
        try:
            chat = await app.get_chat(TELEGRAM_CHANNEL)
            print(f"📢 Channel found: {chat.title}")
            
            try:
                member = await app.get_chat_member(TELEGRAM_CHANNEL, me.id)
                print(f"👤 Role: {member.status}")
            except:
                print("⚠️ Warning: Cannot check channel permissions")
                
            return True
            
        except Exception as e:
            print(f"❌ Cannot access channel: {e}")
            return False
            
    except AuthKeyUnregistered:
        print("❌ STRING_SESSION is invalid or expired")
        return False
        
    except SessionPasswordNeeded:
        print("❌ Account has 2FA enabled")
        return False
        
    except Exception as e:
        print(f"❌ Connection failed: {type(e).__name__}")
        print(f"📝 Error details: {str(e)[:100]}")
        return False

# ===== VK VIDEO EXTRACTION =====

def extract_vk_video_url(vk_url):
    """Extract VK video URL using multiple advanced methods"""
    print(f"🔗 Processing VK URL: {vk_url}")
    
    try:
        # Parse VK URL parameters
        parsed = urlparse(vk_url)
        params = parse_qs(parsed.query)
        
        oid = params.get('oid', [''])[0]
        video_id = params.get('id', [''])[0]
        
        if not oid or not video_id:
            return None, "❌ Invalid VK URL format"
        
        print(f"📊 VK Video ID: {video_id}, Owner ID: {oid}")
        
        # Method 1: Try to access the VK page directly
        print("🔄 Method 1: Direct page access with cloudscraper...")
        try:
            # Build VK player URL
            player_url = f"https://vk.com/video{oid}_{video_id}"
            print(f"🌐 Accessing: {player_url}")
            
            # Create a cloudscraper session to bypass anti-bot protection
            scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'mobile': False,
                    'desktop': True,
                }
            )
            
            # Add more headers to mimic real browser
            custom_headers = HEADERS.copy()
            custom_headers.update({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
                'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
            })
            
            response = scraper.get(player_url, headers=custom_headers, timeout=30)
            print(f"📄 Response status: {response.status_code}")
            
            if response.status_code == 200:
                content = response.text
                
                # Save response for debugging
                with open('vk_response.html', 'w', encoding='utf-8') as f:
                    f.write(content[:10000])
                print("💾 Saved response snippet to vk_response.html")
                
                # Try to find video URLs in the page
                # Pattern 1: Look for JSON data with video URLs
                json_patterns = [
                    r'"url([0-9]+)"\s*:\s*"([^"]+)"',
                    r'"hls"\s*:\s*"([^"]+)"',
                    r'"mp4"\s*:\s*"([^"]+)"',
                    r'video-src="([^"]+)"',
                    r'src="([^"]+mp4[^"]*)"',
                ]
                
                for pattern in json_patterns:
                    matches = re.findall(pattern, content)
                    for match in matches:
                        if isinstance(match, tuple):
                            quality, url = match
                            url = url.replace('\\/', '/')
                            if url.startswith('http'):
                                print(f"✅ Found video URL ({quality}p): {url[:100]}...")
                                return url, f"✅ Found {quality}p URL"
                        else:
                            url = match.replace('\\/', '/')
                            if url.startswith('http'):
                                print(f"✅ Found video URL: {url[:100]}...")
                                return url, "✅ Found video URL"
                
                # Pattern 2: Look for base64 encoded URLs
                base64_pattern = r'"url[0-9]*"\s*:\s*"([A-Za-z0-9+/=]+)"'
                matches = re.findall(base64_pattern, content)
                for match in matches:
                    try:
                        decoded = base64.b64decode(match).decode('utf-8')
                        if 'http' in decoded and ('mp4' in decoded or 'm3u8' in decoded):
                            print(f"✅ Found base64 encoded URL: {decoded[:100]}...")
                            return decoded, "✅ Found base64 decoded URL"
                    except:
                        pass
                
                # Pattern 3: Look for iframe sources
                iframe_pattern = r'<iframe[^>]+src="([^"]+)"'
                iframe_matches = re.findall(iframe_pattern, content)
                for iframe_src in iframe_matches:
                    if 'video' in iframe_src.lower():
                        print(f"📺 Found iframe: {iframe_src}")
                        # Try to extract from iframe
                        try:
                            iframe_response = scraper.get(iframe_src, headers=custom_headers, timeout=15)
                            iframe_content = iframe_response.text
                            
                            # Look for video sources in iframe
                            video_patterns = [
                                r'src="([^"]+\.mp4[^"]*)"',
                                r'<source[^>]+src="([^"]+)"',
                                r'file:\s*["\']([^"\']+)["\']',
                            ]
                            
                            for pattern in video_patterns:
                                video_matches = re.findall(pattern, iframe_content)
                                for video_url in video_matches:
                                    if video_url.startswith('http'):
                                        return video_url, "✅ Found URL in iframe"
                        except Exception as e:
                            print(f"⚠️ Iframe extraction failed: {e}")
                
                # Pattern 4: Look for m3u8 playlists
                m3u8_pattern = r'"(https?://[^"]+\.m3u8[^"]*)"'
                m3u8_matches = re.findall(m3u8_pattern, content)
                for m3u8_url in m3u8_matches:
                    print(f"🎬 Found m3u8 playlist: {m3u8_url[:100]}...")
                    return m3u8_url, "✅ Found m3u8 playlist"
                
                # Pattern 5: Try to find video config
                config_pattern = r'videoConfig\s*=\s*({[^}]+})'
                config_matches = re.findall(config_pattern, content)
                for config_str in config_matches:
                    try:
                        config = json_lib.loads(config_str)
                        if 'url' in config:
                            return config['url'], "✅ Found URL in videoConfig"
                        if 'sources' in config:
                            for source in config['sources']:
                                if 'file' in source:
                                    return source['file'], "✅ Found URL in sources"
                    except:
                        pass
        except Exception as e:
            print(f"⚠️ Method 1 failed: {e}")
        
        # Method 2: Try alternative VK embed URL
        print("🔄 Method 2: Alternative VK embed URL...")
        try:
            embed_url = f"https://vk.com/video_ext.php?oid={oid}&id={video_id}"
            scraper = cloudscraper.create_scraper()
            response = scraper.get(embed_url, headers=HEADERS, timeout=30)
            
            if response.status_code == 200:
                # Parse with BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for video element
                video_elements = soup.find_all('video')
                for video in video_elements:
                    src = video.get('src')
                    if src:
                        return src, "✅ Found video src attribute"
                    
                    # Check source tags
                    sources = video.find_all('source')
                    for source in sources:
                        src = source.get('src')
                        if src:
                            return src, "✅ Found source tag"
                
                # Look for iframe
                iframe = soup.find('iframe')
                if iframe:
                    iframe_src = iframe.get('src')
                    if iframe_src:
                        print(f"🔗 Found iframe src: {iframe_src}")
                        # Follow iframe
                        try:
                            iframe_response = scraper.get(iframe_src, headers=HEADERS, timeout=15)
                            iframe_soup = BeautifulSoup(iframe_response.text, 'html.parser')
                            
                            # Look for video in iframe
                            iframe_videos = iframe_soup.find_all('video')
                            for iframe_video in iframe_videos:
                                iframe_video_src = iframe_video.get('src')
                                if iframe_video_src:
                                    return iframe_video_src, "✅ Found URL in iframe video"
                        except Exception as e:
                            print(f"⚠️ Iframe follow failed: {e}")
        except Exception as e:
            print(f"⚠️ Method 2 failed: {e}")
        
        # Method 3: Try to use external services via API
        print("🔄 Method 3: Trying external services...")
        try:
            # Try savefrom.net API
            api_url = "https://api.savefrom.net/service/convert"
            payload = {
                'url': vk_url,
                'format': 'mp4',
                'quality': '720'
            }
            
            response = requests.post(api_url, data=payload, headers=HEADERS, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if 'url' in data:
                    return data['url'], "✅ Found URL via savefrom.net"
                
                # Try to find in response text
                if 'links' in data:
                    for link in data['links']:
                        if 'url' in link:
                            return link['url'], "✅ Found URL in links"
        except Exception as e:
            print(f"⚠️ Method 3 failed: {e}")
        
        # Method 4: Try yt-dlp with alternative approaches
        print("🔄 Method 4: Trying yt-dlp with workaround...")
        try:
            # Try to use yt-dlp with cookie file if available
            ydl_opts = {
                'quiet': False,
                'no_warnings': False,
                'user_agent': USER_AGENT,
                'referer': 'https://vk.com/',
                'http_headers': HEADERS,
                'extractor_args': {
                    'vk': {
                        'skip': ['dash', 'hls'],
                    }
                },
                'force_generic_extractor': True,
            }
            
            # Try to extract info
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                print("🔍 Attempting to extract video info...")
                try:
                    info = ydl.extract_info(vk_url, download=False)
                    print(f"📊 Info extracted: {info.get('title', 'No title')}")
                    
                    # Try different ways to get URL
                    if 'url' in info:
                        return info['url'], "✅ URL extracted via yt-dlp"
                    
                    if 'formats' in info:
                        formats = info['formats']
                        print(f"📋 Found {len(formats)} formats")
                        
                        # Sort by quality
                        video_formats = [f for f in formats if f.get('vcodec') != 'none']
                        if video_formats:
                            # Try to find mp4 first
                            mp4_formats = [f for f in video_formats if f.get('ext') == 'mp4']
                            if mp4_formats:
                                best_format = max(mp4_formats, key=lambda x: x.get('height', 0))
                                return best_format['url'], f"✅ Found MP4 ({best_format.get('height', 'N/A')}p)"
                            
                            # Otherwise take best available
                            best_format = max(video_formats, key=lambda x: x.get('height', 0))
                            return best_format['url'], f"✅ Found best format ({best_format.get('height', 'N/A')}p)"
                except Exception as e:
                    print(f"⚠️ yt-dlp extraction attempt failed: {e}")
        except Exception as e:
            print(f"⚠️ Method 4 failed: {e}")
        
        return None, "❌ Could not extract VK video URL after trying all methods"
        
    except Exception as e:
        return None, f"❌ VK extraction error: {str(e)}"

def extract_video_url_from_watch_url(watch_url):
    """Extract video download URL from watch URL"""
    try:
        print(f"🔗 Analyzing URL: {watch_url}")
        
        # Check if it's a VK URL
        if 'vk.com' in watch_url or 'video_ext.php' in watch_url:
            return extract_vk_video_url(watch_url)
        
        # For non-VK URLs, use cloudscraper
        print("🔄 Using cloudscraper for non-VK URL...")
        scraper = cloudscraper.create_scraper()
        response = scraper.get(watch_url, headers=HEADERS, timeout=30)
        
        if response.status_code != 200:
            return None, f"HTTP {response.status_code}"
        
        # Try to find video URLs
        content = response.text
        video_patterns = [
            r'src="(https?://[^"]+\.mp4[^"]*)"',
            r'video-src="([^"]+)"',
            r'file:\s*["\']([^"\']+)["\']',
            r'"url"\s*:\s*"([^"]+)"',
        ]
        
        for pattern in video_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for url in matches:
                if url.startswith('http'):
                    print(f"✅ Found video URL: {url[:100]}...")
                    return url, "✅ Video URL extracted"
        
        return None, "❌ No video source found"
        
    except Exception as e:
        return None, f"❌ Error: {str(e)}"

def download_video(url, output_path):
    """Download video using yt-dlp with improved error handling"""
    try:
        ydl_opts = {
            'format': 'best[height<=720]/best',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'user_agent': USER_AGENT,
            'referer': 'https://vk.com/' if 'vk.com' in url else url,
            'http_headers': HEADERS,
            'retries': 10,
            'fragment_retries': 10,
            'skip_unavailable_fragments': True,
            'socket_timeout': 30,
            'concurrent_fragment_downloads': 3,
            'extractor_args': {
                'generic': {'player_skip': ['all']},
                'vk': {'player_skip': ['all']}
            }
        }
        
        print(f"📥 Downloading from: {url[:100]}...")
        start = time.time()
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            print(f"⚠️ yt-dlp download failed, trying alternative method: {e}")
            # Try direct download
            return download_video_direct(url, output_path)
        
        elapsed = time.time() - start
        
        # Check if file was downloaded
        if os.path.exists(output_path):
            size = os.path.getsize(output_path) / (1024*1024)
            print(f"✅ Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
            return True
        
        # Check for files with different extensions
        base, _ = os.path.splitext(output_path)
        for ext in ['.mp4', '.mkv', '.webm', '.avi', '.flv', '.mov']:
            alt_path = base + ext
            if os.path.exists(alt_path):
                shutil.move(alt_path, output_path)
                size = os.path.getsize(output_path) / (1024*1024)
                print(f"✅ Renamed {ext} to mp4 in {elapsed:.1f}s ({size:.1f}MB)")
                return True
        
        return False
        
    except Exception as e:
        print(f"❌ Download error: {e}")
        return False

def download_video_direct(url, output_path):
    """Direct video download as fallback"""
    try:
        print(f"📥 Direct downloading from: {url[:100]}...")
        
        headers = HEADERS.copy()
        headers.update({
            'Range': 'bytes=0-',
            'Accept-Ranges': 'bytes',
        })
        
        response = requests.get(url, headers=headers, stream=True, timeout=60)
        
        if response.status_code not in [200, 206]:
            print(f"❌ Direct download failed: HTTP {response.status_code}")
            return False
        
        total_size = int(response.headers.get('content-length', 0))
        chunk_size = 8192
        downloaded = 0
        start = time.time()
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        if int(percent) % 10 == 0 and int(percent) > 0:
                            print(f"📥 Download progress: {percent:.1f}%")
        
        elapsed = time.time() - start
        
        if os.path.exists(output_path):
            size = os.path.getsize(output_path) / (1024*1024)
            print(f"✅ Direct download completed in {elapsed:.1f}s ({size:.1f}MB)")
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ Direct download failed: {e}")
        return False

# باقي الدوال تبقى كما هي (compress_video, create_thumbnail, get_video_dimensions, get_video_duration, upload_video)

def compress_video(input_file, output_file):
    """Compress video to 720p"""
    if not os.path.exists(input_file):
        print(f"❌ File not found: {input_file}")
        return False
    
    original_size = os.path.getsize(input_file) / (1024 * 1024)
    print(f"🎬 Compressing video...")
    print(f"📊 Original: {original_size:.1f}MB")
    
    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-vf', 'scale=-2:720',
        '-c:v', 'libx264',
        '-crf', '23',
        '-preset', 'medium',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-y',
        output_file
    ]
    
    try:
        start = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(output_file):
            new_size = os.path.getsize(output_file) / (1024 * 1024)
            elapsed = time.time() - start
            reduction = ((original_size - new_size) / original_size) * 100
            
            print(f"✅ Compressed in {elapsed:.1f}s")
            print(f"📊 New size: {new_size:.1f}MB (-{reduction:.1f}%)")
            return True
        else:
            print(f"❌ Compression failed")
            if result.stderr:
                print(f"Error: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"❌ Compression error: {e}")
        return False

def create_thumbnail(input_file, thumbnail_path):
    """Create thumbnail from video"""
    try:
        print(f"🖼️ Creating thumbnail...")
        
        cmd = [
            'ffmpeg',
            '-i', input_file,
            '-ss', '00:01:00',
            '-vframes', '1',
            '-s', '1280x720',
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
    
    return 1280, 720

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

async def upload_video(file_path, caption, thumbnail_path=None):
    """Upload video to Telegram channel"""
    try:
        if not app or not os.path.exists(file_path):
            return False
        
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path) / (1024*1024)
        
        print(f"☁️ Uploading: {filename}")
        print(f"📊 Size: {file_size:.1f}MB")
        
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
        
        start_time = time.time()
        last_percent = 0
        
        def progress(current, total):
            nonlocal last_percent
            percent = (current / total) * 100
            if percent - last_percent >= 5 or percent == 100:
                speed = current / (time.time() - start_time) / 1024 if (time.time() - start_time) > 0 else 0
                print(f"📤 {percent:.0f}% - {speed:.0f}KB/s")
                last_percent = percent
        
        upload_params['progress'] = progress
        
        try:
            await app.send_video(**upload_params)
            elapsed = time.time() - start_time
            print(f"✅ Uploaded in {elapsed:.1f}s")
            return True
            
        except FloodWait as e:
            print(f"⏳ Flood wait: {e.value}s")
            await asyncio.sleep(e.value)
            return await upload_video(file_path, caption, thumbnail_path)
            
        except Exception as e:
            print(f"❌ Upload error: {e}")
            try:
                upload_params.pop('progress', None)
                await app.send_video(**upload_params)
                print(f"✅ Upload successful")
                return True
            except Exception as e2:
                print(f"❌ Retry failed: {e2}")
                return False
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return False

async def process_movie(watch_url, movie_name_arabic, movie_name_english, download_dir):
    """Process a single movie"""
    print(f"\n{'─'*50}")
    print(f"🎬 Movie Processing")
    print(f"{'─'*50}")
    print(f"📽️ Arabic Name: {movie_name_arabic}")
    print(f"📽️ English Name: {movie_name_english}")
    print(f"🔗 Watch URL: {watch_url}")
    
    temp_file = os.path.join(download_dir, "temp_movie.mp4")
    final_file = os.path.join(download_dir, "final_movie.mp4")
    thumbnail_file = os.path.join(download_dir, "thumb_movie.jpg")
    
    # Clean old files
    for f in [temp_file, final_file, thumbnail_file]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except:
                pass
    
    try:
        # 1. Extract URL
        print("🔍 Extracting video URL...")
        video_url, message = extract_video_url_from_watch_url(watch_url)
        
        if not video_url:
            # Try one more time with different approach
            print("🔄 Retrying with alternative method...")
            video_url, message = extract_vk_video_url(watch_url)
        
        if not video_url:
            return False, f"URL extraction failed: {message}"
        
        print(f"{message}")
        print(f"📊 Video URL: {video_url[:100]}...")
        
        # 2. Download
        print("📥 Downloading video...")
        if not download_video(video_url, temp_file):
            return False, "Download failed"
        
        # 3. Create thumbnail
        print("🖼️ Creating thumbnail...")
        create_thumbnail(temp_file, thumbnail_file)
        
        # 4. Compress
        print("🎬 Compressing video...")
        if not compress_video(temp_file, final_file):
            print("⚠️ Compression failed, using original")
            shutil.copy2(temp_file, final_file)
        
        # 5. Upload
        caption = f"{movie_name_arabic}"
        if movie_name_english:
            caption += f"\n{movie_name_english}"
        
        thumb = thumbnail_file if os.path.exists(thumbnail_file) else None
        
        if await upload_video(final_file, caption, thumb):
            # 6. Clean up
            for file_path in [temp_file, final_file, thumbnail_file]:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        print(f"🗑️ Deleted: {os.path.basename(file_path)}")
                    except:
                        pass
            return True, "✅ Movie uploaded and cleaned"
        else:
            return False, "❌ Upload failed"
        
    except Exception as e:
        print(f"❌ Processing error: {e}")
        return False, str(e)

# ===== MAIN FUNCTION =====

async def main():
    """Main function"""
    print("="*50)
    print("🎬 GitHub Movie Processor v3.0 (VK Enhanced)")
    print("="*50)
    
    # Check dependencies
    print("\n🔍 Checking dependencies...")
    
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ ffmpeg is installed")
        else:
            print("❌ ffmpeg not found, installing...")
            subprocess.run(['sudo', 'apt-get', 'update', '-y'], capture_output=True)
            subprocess.run(['sudo', 'apt-get', 'install', '-y', 'ffmpeg'], capture_output=True)
            print("✅ ffmpeg installed")
    except:
        print("❌ Cannot check ffmpeg")
    
    # Setup Telegram
    print("\n" + "="*50)
    if not await setup_telegram():
        print("❌ Cannot continue without Telegram connection")
        return
    
    # Load configuration
    config_file = "movie_config.json"
    if not os.path.exists(config_file):
        print(f"❌ Config file not found: {config_file}")
        print("💡 Creating sample config...")
        
        sample_config = {
            "watch_url": "https://vk.com/video_ext.php?oid=848084895&id=456245049",
            "movie_name_arabic": "فيلم شماريخ",
            "movie_name_english": "shamarek"
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(sample_config, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Created {config_file} with sample data")
        print("⚠️ Please edit the config file and run again")
        return
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Error reading config: {e}")
        return
    
    watch_url = config.get("watch_url", "").strip()
    movie_name_arabic = config.get("movie_name_arabic", "").strip()
    movie_name_english = config.get("movie_name_english", "").strip()
    
    if not watch_url:
        print("❌ Watch URL is required")
        return
    
    if not movie_name_arabic:
        print("❌ Arabic movie name is required")
        return
    
    # Create working directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    download_dir = f"movie_downloads_{timestamp}"
    os.makedirs(download_dir, exist_ok=True)
    
    print(f"\n{'='*50}")
    print("🚀 Starting Movie Processing")
    print('='*50)
    print(f"📽️ Arabic Name: {movie_name_arabic}")
    if movie_name_english:
        print(f"📽️ English Name: {movie_name_english}")
    print(f"🔗 Watch URL: {watch_url}")
    print(f"📁 Working dir: {download_dir}")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Process movie
    print(f"\n[Processing Movie]")
    print("─" * 50)
    
    start_time = time.time()
    success, message = await process_movie(watch_url, movie_name_arabic, movie_name_english, download_dir)
    
    elapsed = time.time() - start_time
    
    print(f"\n{'='*50}")
    print("📊 Processing Summary")
    print('='*50)
    
    if success:
        print(f"✅ Movie processed successfully!")
        print(f"⏱️ Processing time: {elapsed:.1f} seconds")
    else:
        print(f"❌ Movie processing failed: {message}")
    
    try:
        if os.path.exists(download_dir) and not os.listdir(download_dir):
            os.rmdir(download_dir)
            print(f"🗑️ Cleaned empty directory: {download_dir}")
    except:
        pass
    
    print(f"\n{'='*50}")
    print("🏁 Processing Complete")
    print(f"⏰ Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print('='*50)
    
    if app:
        await app.stop()
        print("🔌 Telegram connection closed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️ Process stopped by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {type(e).__name__}")
        print(f"📝 Details: {e}")
        sys.exit(1)
