#!/usr/bin/env python3
"""
Telegram Video Downloader & Uploader - Fixed for 3seq.cam direct links
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
import argparse
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# ===== CONFIGURATION =====
TELEGRAM_API_ID = os.environ.get("API_ID", "")
TELEGRAM_API_HASH = os.environ.get("API_HASH", "")
TELEGRAM_CHANNEL = os.environ.get("CHANNEL", "")
STRING_SESSION = os.environ.get("STRING_SESSION", "")

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
    
    if errors:
        print("\n".join(errors))
        return False
    
    print("✅ Environment variables validated")
    return True

if not validate_env():
    sys.exit(1)

TELEGRAM_API_ID = int(TELEGRAM_API_ID)

# Updated headers to mimic real browser
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
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
from pyrogram.errors import FloodWait, AuthKeyUnregistered, SessionPasswordNeeded
import yt_dlp
import cloudscraper

app = None

# ===== TELEGRAM SETUP =====
async def setup_telegram():
    """Setup Telegram using string session"""
    global app
    
    print("\n" + "="*50)
    print("🔐 Telegram Setup")
    print("="*50)
    
    try:
        cleaned_session = STRING_SESSION.strip()
        
        app = Client(
            name="github_uploader",
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
        
        # التحقق من القناة
        try:
            chat = await app.get_chat(TELEGRAM_CHANNEL)
            print(f"📢 Channel found: {chat.title}")
            return True
        except Exception as e:
            print(f"❌ Cannot access channel: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

# ===== URL GENERATION FUNCTIONS =====

def generate_watch_url(episode_num, series_name="kiralik-ask", season_num=1, suffix_map=None):
    """
    Generate the CORRECT watch URL format based on actual link structure:
    https://z.3seq.cam/video/modablaj-kiralik-ask-episode-s01e02-avxn/?do=watch
    """
    
    # First try: Use the exact URL format you provided
    if season_num > 1:
        base_url = f"https://z.3seq.cam/video/modablaj-{series_name}-episode-s{season_num:02d}e{episode_num:02d}"
    else:
        base_url = f"https://z.3seq.cam/video/modablaj-{series_name}-episode-{episode_num:02d}"
    
    # If we have a suffix map (episode_number -> suffix), use it
    if suffix_map and episode_num in suffix_map:
        suffix = suffix_map[episode_num]
        if season_num > 1:
            final_url = f"https://z.3seq.cam/video/modablaj-{series_name}-episode-s{season_num:02d}e{episode_num:02d}-{suffix}/?do=watch"
        else:
            final_url = f"https://z.3seq.cam/video/modablaj-{series_name}-episode-{episode_num:02d}-{suffix}/?do=watch"
        print(f"🔗 Using mapped URL with suffix '{suffix}': {final_url}")
        return final_url
    
    # If no suffix map, we need to discover the suffix
    print(f"🔍 Attempting to discover suffix for episode {episode_num}...")
    
    # Create a cloudscraper session to bypass Cloudflare
    scraper = cloudscraper.create_scraper(
        browser={
            'custom': USER_AGENT,
        }
    )
    
    try:
        # Try to access the base URL and follow redirects
        response = scraper.get(base_url, headers=HEADERS, timeout=30, allow_redirects=True)
        
        if response.status_code == 200:
            final_url = response.url
            print(f"✅ Discovered final URL: {final_url}")
            
            # Check if we already have ?do=watch in URL
            if '?do=watch' in final_url:
                return final_url
            else:
                # Add ?do=watch parameter
                if '?' in final_url:
                    watch_url = final_url + '&do=watch'
                else:
                    watch_url = final_url.rstrip('/') + '/?do=watch'
                return watch_url
        else:
            print(f"⚠️ Could not discover suffix, using base URL with direct watch parameter")
            return f"{base_url}/?do=watch"
            
    except Exception as e:
        print(f"⚠️ Discovery failed: {e}, using fallback method")
        return f"{base_url}/?do=watch"

def get_arabic_series_name(english_name):
    """Map English series names to Arabic names"""
    series_mapping = {
        "kiralik-ask": "حب للايجار",
        "the-protector": "المحافظ",
        "dirilis-ertugrul": "قيامة ارطغرل",
        "kurulus-osman": "تأسيس عثمان",
        "yargi": "قضاء",
        "ramo": "رامو",
        "son-yaz": "آخر كتابة",
        "sadakatsiz": "الخائن",
        "sen-calka": "أنت رقصت",
        "icerde": "في الداخل"
    }
    
    if english_name in series_mapping:
        return series_mapping[english_name]
    
    for key, arabic_name in series_mapping.items():
        if key in english_name:
            return arabic_name
    
    return english_name.replace('-', ' ').title()

# ===== VIDEO EXTRACTION FUNCTIONS =====

def extract_video_from_watch_url(watch_url):
    """
    Extract video URL from the watch page
    Example watch_url: https://z.3seq.cam/video/modablaj-kiralik-ask-episode-s01e02-avxn/?do=watch
    """
    print(f"🎬 Extracting video from watch URL: {watch_url}")
    
    # Use cloudscraper to bypass Cloudflare protection
    scraper = cloudscraper.create_scraper(
        browser={
            'custom': USER_AGENT,
        }
    )
    
    try:
        # Fetch the watch page
        response = scraper.get(watch_url, headers=HEADERS, timeout=30)
        
        if response.status_code != 200:
            return None, f"HTTP {response.status_code}"
        
        content = response.text
        
        # Debug: Save page for analysis
        debug_file = f"watch_page_{int(time.time())}.html"
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(content[:5000])
        print(f"📄 Saved watch page snippet to {debug_file}")
        
        # Method 1: Look for vidsp.net embed (most common)
        vidsp_patterns = [
            r'src=["\'](https?://[^"\']*vidsp\.net[^"\']*)["\']',
            r'iframe.*?src=["\'](https?://[^"\']*vidsp\.net[^"\']*)["\']',
            r'<iframe[^>]+src=["\']([^"]*vidsp\.net[^"]*)["\']',
        ]
        
        for pattern in vidsp_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if match:
                    video_url = match
                    if video_url.startswith('//'):
                        video_url = 'https:' + video_url
                    print(f"✅ Found vidsp.net URL: {video_url}")
                    return video_url, "✅ Video URL extracted"
        
        # Method 2: Look for mp4/m3u8 direct links
        video_patterns = [
            r'(https?://[^"\'\s<>]+\.mp4[^"\'\s<>]*)',
            r'(https?://[^"\'\s<>]+\.m3u8[^"\'\s<>]*)',
            r'file["\']?\s*:\s*["\'](https?://[^"\']+)["\']',
            r'source["\']?\s*:\s*["\'](https?://[^"\']+)["\']',
        ]
        
        for pattern in video_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if match and any(ext in match.lower() for ext in ['.mp4', '.m3u8', 'mpeg']):
                    video_url = match
                    print(f"✅ Found direct video URL: {video_url}")
                    return video_url, "✅ Video URL extracted"
        
        # Method 3: Look for common video hosting domains
        hosting_patterns = [
            r'(https?://[^"\'\s<>]*cloudvideo\.tv[^"\'\s<>]*)',
            r'(https?://[^"\'\s<>]*streamtape\.com[^"\'\s<>]*)',
            r'(https?://[^"\'\s<>]*dood\.watch[^"\'\s<>]*)',
            r'(https?://[^"\'\s<>]*embedo\.to[^"\'\s<>]*)',
        ]
        
        for pattern in hosting_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if match:
                    video_url = match
                    print(f"✅ Found video hosting URL: {video_url}")
                    return video_url, "✅ Video URL extracted"
        
        # Method 4: Search for any iframe
        iframe_pattern = r'<iframe[^>]+src=["\']([^"\']+)["\']'
        iframe_matches = re.findall(iframe_pattern, content, re.IGNORECASE)
        
        for iframe_url in iframe_matches:
            if iframe_url and iframe_url.startswith('http'):
                print(f"🔍 Testing iframe URL: {iframe_url}")
                # Test if this iframe might contain video
                try:
                    iframe_response = scraper.head(iframe_url, timeout=10)
                    content_type = iframe_response.headers.get('content-type', '')
                    if 'video' in content_type or 'html' in content_type:
                        print(f"✅ Iframe URL looks promising: {iframe_url}")
                        return iframe_url, "✅ Iframe URL found"
                except:
                    continue
        
        return None, "❌ No video URL found in watch page"
        
    except Exception as e:
        return None, f"❌ Error extracting video: {str(e)[:100]}"

# ===== VIDEO PROCESSING FUNCTIONS =====

def download_video(video_url, output_path):
    """Download video using yt-dlp with enhanced settings"""
    try:
        print(f"📥 Downloading from: {video_url[:100]}...")
        
        ydl_opts = {
            'format': 'best[height<=720]/best',
            'outtmpl': output_path,
            'quiet': False,
            'no_warnings': False,
            'user_agent': USER_AGENT,
            'referer': 'https://z.3seq.cam/',
            'http_headers': HEADERS,
            'retries': 10,
            'fragment_retries': 10,
            'skip_unavailable_fragments': True,
            'socket_timeout': 30,
            'extractor_args': {
                'generic': ['--no-check-certificate']
            },
            'verbose': True,
        }
        
        start = time.time()
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(video_url, download=True)
                filename = ydl.prepare_filename(info)
                print(f"✅ Downloaded: {filename}")
            except Exception as e:
                print(f"❌ yt-dlp failed: {e}")
                return False
        
        elapsed = time.time() - start
        
        # Check if file exists
        if os.path.exists(output_path):
            size = os.path.getsize(output_path) / (1024*1024)
            print(f"✅ Download completed in {elapsed:.1f}s ({size:.1f}MB)")
            return True
        
        # Check for alternate extensions
        base = os.path.splitext(output_path)[0]
        for ext in ['.mp4', '.mkv', '.webm', '.avi']:
            alt_file = base + ext
            if os.path.exists(alt_file):
                shutil.move(alt_file, output_path)
                size = os.path.getsize(output_path) / (1024*1024)
                print(f"✅ Download completed (renamed) in {elapsed:.1f}s ({size:.1f}MB)")
                return True
        
        return False
        
    except Exception as e:
        print(f"❌ Download error: {e}")
        return False

def compress_video(input_file, output_file):
    """Compress video to 240p"""
    if not os.path.exists(input_file):
        return False
    
    original_size = os.path.getsize(input_file) / (1024 * 1024)
    print(f"🎬 Compressing video ({original_size:.1f}MB)...")
    
    cmd = [
        'ffmpeg', '-i', input_file,
        '-vf', 'scale=-2:240',
        '-c:v', 'libx264', '-crf', '28', '-preset', 'veryfast',
        '-c:a', 'aac', '-b:a', '64k',
        '-y', output_file
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and os.path.exists(output_file):
            new_size = os.path.getsize(output_file) / (1024 * 1024)
            print(f"✅ Compressed to {new_size:.1f}MB")
            return True
        return False
    except:
        return False

def create_thumbnail(input_file, thumbnail_path):
    """Create thumbnail from video"""
    try:
        cmd = [
            'ffmpeg', '-i', input_file,
            '-ss', '00:00:05', '-vframes', '1',
            '-s', '320x180', '-f', 'image2',
            '-y', thumbnail_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode == 0 and os.path.exists(thumbnail_path)
    except:
        return False

def get_video_dimensions(input_file):
    """Get video dimensions"""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'csv=p=0', input_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            dims = result.stdout.strip().split(',')
            if len(dims) == 2:
                return int(dims[0]), int(dims[1])
    except:
        pass
    return 426, 240

def get_video_duration(input_file):
    """Get video duration in seconds"""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
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
        
        file_size = os.path.getsize(file_path) / (1024*1024)
        print(f"☁️ Uploading ({file_size:.1f}MB)...")
        
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
            if percent - last_percent >= 5:
                speed = current / (time.time() - start_time) / 1024 if (time.time() - start_time) > 0 else 0
                print(f"📤 {percent:.0f}% ({speed:.0f}KB/s)")
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
            return False
            
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return False

# ===== MAIN PROCESSING =====

async def process_episode(episode_num, series_name, series_name_arabic, season_num, download_dir, suffix_map=None):
    """Process a single episode with correct URL format"""
    print(f"\n{'─'*50}")
    print(f"🎬 Processing Episode {episode_num:02d}")
    print(f"{'─'*50}")
    
    temp_file = os.path.join(download_dir, f"temp_e{episode_num:03d}.mp4")
    final_file = os.path.join(download_dir, f"final_e{episode_num:03d}.mp4")
    thumbnail_file = os.path.join(download_dir, f"thumb_e{episode_num:03d}.jpg")
    
    # Clean old files
    for f in [temp_file, final_file, thumbnail_file]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except:
                pass
    
    try:
        # 1. Generate CORRECT watch URL
        print("🔗 Generating watch URL...")
        watch_url = generate_watch_url(episode_num, series_name, season_num, suffix_map)
        print(f"📺 Watch URL: {watch_url}")
        
        # 2. Extract video URL from watch page
        print("🔍 Extracting video URL...")
        video_url, message = extract_video_from_watch_url(watch_url)
        
        if not video_url:
            return False, f"Video extraction failed: {message}"
        
        print(f"✅ {message}")
        print(f"🎬 Video URL: {video_url[:100]}...")
        
        # 3. Download video
        print("📥 Downloading...")
        if not download_video(video_url, temp_file):
            return False, "Download failed"
        
        # 4. Create thumbnail
        create_thumbnail(temp_file, thumbnail_file)
        
        # 5. Compress
        if not compress_video(temp_file, final_file):
            print("⚠️ Compression failed, using original")
            shutil.copy2(temp_file, final_file)
        
        # 6. Upload
        caption = f"{series_name_arabic} الموسم {season_num} الحلقة {episode_num}"
        thumb = thumbnail_file if os.path.exists(thumbnail_file) else None
        
        if await upload_video(final_file, caption, thumb):
            # Clean up
            for file_path in [temp_file, final_file, thumbnail_file]:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except:
                        pass
            return True, "✅ Uploaded successfully"
        else:
            return False, "❌ Upload failed"
            
    except Exception as e:
        print(f"❌ Processing error: {e}")
        return False, str(e)

async def main():
    """Main function"""
    print("="*50)
    print("🎬 3seq.cam Video Processor v4.0")
    print("   Fixed URL Format")
    print("="*50)
    
    # Setup argument parser
    parser = argparse.ArgumentParser(description='Download videos from 3seq.cam')
    parser.add_argument('--episode', type=int, help='Single episode to process')
    parser.add_argument('--start', type=int, default=1, help='Start episode')
    parser.add_argument('--end', type=int, default=89, help='End episode')
    parser.add_argument('--series', type=str, default='kiralik-ask', help='Series name')
    parser.add_argument('--season', type=int, default=1, help='Season number')
    parser.add_argument('--suffix-map', type=str, help='JSON file mapping episode numbers to suffixes')
    
    args = parser.parse_args()
    
    # Check dependencies
    print("\n🔍 Checking dependencies...")
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True)
        print("✅ ffmpeg is installed")
    except:
        print("❌ ffmpeg not found, installing...")
        subprocess.run(['sudo', 'apt-get', 'install', '-y', 'ffmpeg'], capture_output=True)
    
    # Setup Telegram
    print("\n" + "="*50)
    if not await setup_telegram():
        print("❌ Cannot continue without Telegram connection")
        return
    
    # Load suffix map if provided
    suffix_map = None
    if args.suffix_map and os.path.exists(args.suffix_map):
        try:
            with open(args.suffix_map, 'r') as f:
                suffix_map = json.load(f)
            print(f"📋 Loaded suffix map for {len(suffix_map)} episodes")
        except:
            print("⚠️ Could not load suffix map")
    
    # Get Arabic series name
    series_name_arabic = get_arabic_series_name(args.series)
    
    # Create download directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    download_dir = f"downloads_{timestamp}"
    os.makedirs(download_dir, exist_ok=True)
    
    # Determine episodes to process
    if args.episode:
        episodes = [args.episode]
        start_ep = args.episode
        end_ep = args.episode
    else:
        start_ep = args.start
        end_ep = args.end
        episodes = list(range(start_ep, end_ep + 1))
    
    print(f"\n{'='*50}")
    print("🚀 Starting Processing")
    print('='*50)
    print(f"📺 Series: {series_name_arabic}")
    print(f"🌐 English name: {args.series}")
    print(f"🎬 Season: {args.season}")
    print(f"📈 Episodes: {start_ep} to {end_ep} (total: {len(episodes)})")
    print(f"📁 Working dir: {download_dir}")
    
    # Process episodes
    successful = 0
    failed = []
    
    for episode_num in episodes:
        print(f"\n[Episode {episode_num}/{end_ep}]")
        
        start_time = time.time()
        success, message = await process_episode(
            episode_num, args.series, series_name_arabic, 
            args.season, download_dir, suffix_map
        )
        
        elapsed = time.time() - start_time
        
        if success:
            successful += 1
            print(f"✅ Episode {episode_num:02d}: {message} ({elapsed:.1f}s)")
        else:
            failed.append(episode_num)
            print(f"❌ Episode {episode_num:02d}: {message}")
        
        # Wait between episodes
        if episode_num < end_ep:
            wait_time = 2
            print(f"⏳ Waiting {wait_time} seconds...")
            await asyncio.sleep(wait_time)
    
    # Summary
    print(f"\n{'='*50}")
    print("📊 Processing Summary")
    print('='*50)
    print(f"✅ Successful: {successful}/{len(episodes)}")
    print(f"❌ Failed: {len(failed)}")
    
    if failed:
        print(f"📝 Failed episodes: {failed}")
    
    # Cleanup
    try:
        if os.path.exists(download_dir) and not os.listdir(download_dir):
            os.rmdir(download_dir)
    except:
        pass
    
    print(f"\n{'='*50}")
    print("🏁 Processing Complete")
    print('='*50)
    
    if app:
        await app.stop()

# ===== SUFFIX MAP GENERATOR =====
def generate_suffix_map(start_ep=1, end_ep=89, series_name="kiralik-ask", season_num=1):
    """
    Helper function to generate a suffix map by discovering suffixes for each episode
    """
    print("🔍 Generating suffix map...")
    
    import cloudscraper
    scraper = cloudscraper.create_scraper()
    
    suffix_map = {}
    
    for episode_num in range(start_ep, end_ep + 1):
        try:
            if season_num > 1:
                url = f"https://z.3seq.cam/video/modablaj-{series_name}-episode-s{season_num:02d}e{episode_num:02d}"
            else:
                url = f"https://z.3seq.cam/video/modablaj-{series_name}-episode-{episode_num:02d}"
            
            print(f"🔗 Testing episode {episode_num}...")
            response = scraper.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
            
            if response.status_code == 200:
                final_url = response.url
                # Extract suffix from URL
                match = re.search(r'-(\w{4})/?$', final_url)
                if match:
                    suffix = match.group(1)
                    suffix_map[episode_num] = suffix
                    print(f"  ✅ Episode {episode_num}: suffix '{suffix}'")
                else:
                    print(f"  ⚠️ Episode {episode_num}: no suffix found")
            else:
                print(f"  ❌ Episode {episode_num}: HTTP {response.status_code}")
            
            time.sleep(1)  # Avoid rate limiting
            
        except Exception as e:
            print(f"  ❌ Episode {episode_num}: Error - {e}")
    
    # Save suffix map
    if suffix_map:
        filename = f"suffix_map_{series_name}_s{season_num:02d}.json"
        with open(filename, 'w') as f:
            json.dump(suffix_map, f, indent=2)
        print(f"\n✅ Saved suffix map to {filename}")
        print(f"📋 Use with: --suffix-map {filename}")
    
    return suffix_map

if __name__ == "__main__":
    # Check if we want to generate suffix map
    if len(sys.argv) > 1 and sys.argv[1] == "--generate-suffix-map":
        start_ep = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        end_ep = int(sys.argv[3]) if len(sys.argv) > 3 else 89
        generate_suffix_map(start_ep, end_ep)
    else:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("\n\n⏹️ Process stopped by user")
        except Exception as e:
            print(f"\n💥 Error: {e}")
