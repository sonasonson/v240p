#!/usr/bin/env python3
"""
Telegram Video Downloader & Uploader - GitHub Version
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
import math
from datetime import datetime

# ===== CONFIGURATION =====
# Get from GitHub Secrets
import os
TELEGRAM_API_ID = int(os.environ.get("API_ID", 0))
TELEGRAM_API_HASH = os.environ.get("API_HASH", "")
TELEGRAM_CHANNEL = os.environ.get("CHANNEL", "")
STRING_SESSION = os.environ.get("STRING_SESSION", "")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Referer': 'https://3seq.com/'
}

# ===== IMPORTS =====
try:
    from pyrogram import Client
    from pyrogram.errors import FloodWait
    PYROGRAM_INSTALLED = True
except ImportError:
    print("[*] Installing pyrogram...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyrogram", "tgcrypto", "-q"])
    from pyrogram import Client
    from pyrogram.errors import FloodWait
    PYROGRAM_INSTALLED = True

try:
    import yt_dlp
except ImportError:
    print("[*] Installing yt-dlp...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp", "-q"])
    import yt_dlp

app = None

# ===== TELEGRAM SETUP (STRING SESSION) =====

async def setup_telegram():
    """Setup Telegram using string session"""
    global app
    
    print("\n" + "="*50)
    print("Telegram Setup")
    print("="*50)
    
    if not STRING_SESSION:
        print("[!] STRING_SESSION not found in environment variables")
        return False
    
    try:
        print(f"[*] API_ID: {TELEGRAM_API_ID}")
        print(f"[*] Channel: {TELEGRAM_CHANNEL}")
        
        app = Client(
            "gh_session",
            api_id=TELEGRAM_API_ID,
            api_hash=TELEGRAM_API_HASH,
            session_string=STRING_SESSION,
            in_memory=True
        )
        
        print("[*] Connecting to Telegram...")
        await app.start()
        
        me = await app.get_me()
        print(f"[+] Connected as: {me.first_name} (@{me.username})")
        
        # Verify channel
        try:
            chat = await app.get_chat(TELEGRAM_CHANNEL)
            print(f"[+] Channel: {chat.title}")
        except Exception as e:
            print(f"[!] Warning: Cannot access channel - {e}")
        
        return True
        
    except Exception as e:
        print(f"[!] Connection error: {e}")
        return False

# ===== VIDEO DOWNLOAD =====

def download_video(url, output_path):
    """Download video using yt-dlp"""
    try:
        ydl_opts = {
            'format': 'best[height<=720]/best',
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'user_agent': USER_AGENT,
            'referer': 'https://v.vidsp.net/',
            'http_headers': HEADERS,
            'retries': 3,
            'fragment_retries': 3,
            'skip_unavailable_fragments': True,
        }
        
        print(f"[*] Downloading video...")
        start = time.time()
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        elapsed = time.time() - start
        
        # Check if file exists
        if os.path.exists(output_path):
            size = os.path.getsize(output_path) / (1024*1024)
            print(f"[+] Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
            return True
        else:
            # Search for other extensions
            base = os.path.splitext(output_path)[0]
            for ext in ['.mp4', '.mkv', '.webm', '.flv', '.avi']:
                if os.path.exists(base + ext):
                    shutil.move(base + ext, output_path)
                    size = os.path.getsize(output_path) / (1024*1024)
                    print(f"[+] Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
                    return True
        
        return False
        
    except Exception as e:
        print(f"[!] Download error: {e}")
        return False

# ===== VIDEO COMPRESSION =====

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

def compress_video_to_240p(input_file, output_file, crf=28):
    """Compress video to 240p"""
    if not os.path.exists(input_file):
        print(f"[!] File not found: {input_file}")
        return False
    
    original_size = os.path.getsize(input_file) / (1024 * 1024)
    print(f"[*] Compressing video to 240p...")
    print(f"[*] Original size: {original_size:.1f}MB")
    print(f"[*] CRF: {crf}")
    
    # Get video duration
    try:
        cmd = ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', input_file]
        result = subprocess.run(cmd, capture_output=True, text=True)
        duration = float(result.stdout.strip()) if result.returncode == 0 else 0
        if duration > 0:
            print(f"[*] Duration: {int(duration//60)}:{int(duration%60):02d}")
    except:
        duration = 0
    
    # Compression command
    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-vf', 'scale=-2:240',
        '-c:v', 'libx264',
        '-crf', str(crf),
        '-preset', 'veryfast',
        '-c:a', 'aac',
        '-b:a', '64k',
        '-y',
        output_file
    ]
    
    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0 and os.path.exists(output_file):
        new_size = os.path.getsize(output_file) / (1024 * 1024)
        total_time = time.time() - start_time
        reduction = ((original_size - new_size) / original_size) * 100
        
        print(f"[+] Compressed in {total_time:.1f}s")
        print(f"[+] New size: {new_size:.1f}MB")
        print(f"[+] Reduction: {reduction:.1f}%")
        return True
    
    print(f"[!] Compression failed")
    return False

# ===== THUMBNAIL CREATION =====

def create_thumbnail(input_file, thumbnail_path):
    """Create thumbnail from video"""
    try:
        print(f"[*] Creating thumbnail...")
        
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
            print(f"[+] Thumbnail created ({size:.1f}KB)")
            return True
        
        return False
        
    except Exception as e:
        print(f"[!] Thumbnail error: {e}")
        return False

# ===== VIDEO UPLOAD =====

async def upload_video_to_channel(file_path, caption, thumbnail_path=None):
    """Upload video to channel"""
    try:
        if not app or not os.path.exists(file_path):
            return False
        
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path) / (1024*1024)
        
        print(f"[*] Uploading: {filename}")
        print(f"[*] Size: {file_size:.1f}MB")
        
        # Get video info
        width, height = get_video_dimensions(file_path)
        
        # Get duration
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', file_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        duration = int(float(result.stdout.strip())) if result.returncode == 0 else 0
        
        # Upload parameters
        upload_params = {
            'chat_id': TELEGRAM_CHANNEL,
            'video': file_path,
            'caption': caption,
            'supports_streaming': True,
            'width': width,
            'height': height,
            'duration': duration,
        }
        
        # Add thumbnail if exists
        if thumbnail_path and os.path.exists(thumbnail_path):
            upload_params['thumb'] = thumbnail_path
        
        # Upload with progress
        start_time = time.time()
        
        def progress(current, total):
            percent = (current / total) * 100
            speed = current / (time.time() - start_time) / 1024 if (time.time() - start_time) > 0 else 0
            print(f'\r[*] Upload: {percent:.1f}% | Speed: {speed:.0f}KB/s', end='')
        
        upload_params['progress'] = progress
        
        # Send video
        try:
            await app.send_video(**upload_params)
            elapsed = time.time() - start_time
            print(f"\n[+] Uploaded in {elapsed:.1f}s")
            print(f"[+] Streaming enabled (pauses on exit)")
            return True
            
        except FloodWait as e:
            print(f"\n[*] Waiting {e.value} seconds...")
            await asyncio.sleep(e.value)
            return await upload_video_to_channel(file_path, caption, thumbnail_path)
            
        except Exception as e:
            print(f"\n[!] Upload error: {e}")
            # Try without progress
            try:
                upload_params.pop('progress', None)
                await app.send_video(**upload_params)
                print("[+] Upload successful")
                return True
            except:
                return False
        
    except Exception as e:
        print(f"[!] Unexpected upload error: {e}")
        return False

# ===== URL EXTRACTION =====

def extract_video_url(episode_num, series_name, season_num):
    """Extract video URL from 3seq"""
    try:
        # Build URL
        if season_num > 1:
            base_url = f"https://x.3seq.com/video/modablaj-{series_name}-episode-s{season_num:02d}e{episode_num:02d}"
        else:
            base_url = f"https://x.3seq.com/video/modablaj-{series_name}-episode-{episode_num:02d}"
        
        print(f"[*] URL: {base_url}")
        
        # Fetch page
        response = requests.get(base_url, headers=HEADERS, timeout=20)
        if response.status_code != 200:
            return None, f"Failed to fetch page: {response.status_code}"
        
        # Extract watch link
        watch_match = re.search(r'href=["\']([^"\']+episode[^"\']+\?do=watch)["\']', response.text)
        if watch_match:
            watch_url = watch_match.group(1)
            if watch_url.startswith('//'):
                watch_url = 'https:' + watch_url
            elif watch_url.startswith('/'):
                watch_url = 'https://x.3seq.com' + watch_url
        else:
            watch_url = f"{base_url}-yvra/?do=watch"
        
        # Fetch watch page
        response = requests.get(watch_url, headers=HEADERS, timeout=20)
        iframe_match = re.search(r'<iframe[^>]+src="([^"]+)"', response.text)
        
        if not iframe_match:
            return None, "Video URL not found"
        
        video_url = iframe_match.group(1)
        if video_url.startswith('//'):
            video_url = 'https:' + video_url
        elif video_url.startswith('/'):
            video_url = 'https://v.vidsp.net' + video_url
        
        return video_url, "URL extracted successfully"
        
    except Exception as e:
        return None, f"Error: {str(e)}"

# ===== EPISODE PROCESSING =====

async def process_episode(episode_num, series_name, series_name_arabic, season_num, download_dir):
    """Process a single episode"""
    print(f"\n{'-'*50}")
    print(f"Episode {episode_num:02d}")
    print('-'*50)
    
    temp_file = os.path.join(download_dir, f"temp_{episode_num:02d}.mp4")
    final_file = os.path.join(download_dir, f"final_{episode_num:02d}.mp4")
    thumbnail_file = os.path.join(download_dir, f"thumb_{episode_num:02d}.jpg")
    
    # Clean old files
    for f in [temp_file, final_file, thumbnail_file]:
        if os.path.exists(f):
            os.remove(f)
    
    try:
        # 1. Extract video URL
        print("[*] Extracting video URL...")
        video_url, message = extract_video_url(episode_num, series_name, season_num)
        
        if not video_url:
            return False, message
        
        print(f"[+] {message}")
        
        # 2. Download video
        print("[*] Downloading video...")
        if not download_video(video_url, temp_file):
            return False, "Download failed"
        
        # 3. Create thumbnail
        print("[*] Creating thumbnail...")
        create_thumbnail(temp_file, thumbnail_file)
        
        # 4. Compress video
        print("[*] Compressing video...")
        if not compress_video_to_240p(temp_file, final_file, crf=28):
            # If compression fails, use original
            print("[!] Compression failed, using original file")
            shutil.copy2(temp_file, final_file)
        
        # 5. Upload to Telegram
        caption = f"{series_name_arabic} الموسم {season_num} الحلقة {episode_num}"
        thumb_to_use = thumbnail_file if os.path.exists(thumbnail_file) else None
        
        if await upload_video_to_channel(final_file, caption, thumb_to_use):
            # 6. Delete files after successful upload
            files_to_delete = [temp_file, final_file, thumbnail_file]
            for file_path in files_to_delete:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        print(f"[+] Deleted: {os.path.basename(file_path)}")
                    except:
                        pass
            
            return True, "Uploaded and files deleted"
        else:
            return False, "Upload failed"
        
    except Exception as e:
        print(f"[!] Unexpected error: {e}")
        return False, str(e)

# ===== MAIN FUNCTION =====

async def main():
    """Main function"""
    print("="*50)
    print("GitHub Video Processor")
    print("="*50)
    
    # Check dependencies
    print("\n[*] Checking dependencies...")
    
    # Check ffmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        print("[+] ffmpeg installed")
    except:
        print("[!] ffmpeg not found")
        # Try to install on Ubuntu
        try:
            subprocess.run(['apt-get', 'update', '-y'], capture_output=True)
            subprocess.run(['apt-get', 'install', '-y', 'ffmpeg'], capture_output=True)
            print("[+] ffmpeg installed")
        except:
            print("[!] Cannot install ffmpeg automatically")
            return
    
    # Setup Telegram
    if not await setup_telegram():
        print("[!] Telegram setup failed")
        return
    
    # Load series configuration
    config_file = "series_config.json"
    if not os.path.exists(config_file):
        print(f"[!] Configuration file '{config_file}' not found")
        return
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    series_name = config.get("series_name", "")
    series_name_arabic = config.get("series_name_arabic", "")
    season_num = config.get("season_num", 1)
    start_ep = config.get("start_episode", 1)
    end_ep = config.get("end_episode", 1)
    
    if not series_name or not series_name_arabic:
        print("[!] Series configuration incomplete")
        return
    
    # Create download directory
    download_dir = f"downloads_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(download_dir, exist_ok=True)
    
    print(f"\n{'='*50}")
    print("Starting Processing")
    print('='*50)
    print(f"Series: {series_name_arabic}")
    print(f"Season: {season_num}")
    print(f"Episodes: {start_ep} to {end_ep}")
    print(f"Download dir: {download_dir}")
    
    # Process episodes
    successful = 0
    failed = []
    total = end_ep - start_ep + 1
    
    for episode_num in range(start_ep, end_ep + 1):
        current = episode_num - start_ep + 1
        
        print(f"\n[{current}/{total}] Episode {episode_num:02d}")
        print("-" * 40)
        
        start_time = time.time()
        success, message = await process_episode(
            episode_num, series_name, series_name_arabic, season_num, download_dir
        )
        
        elapsed = time.time() - start_time
        
        if success:
            successful += 1
            print(f"[+] {episode_num:02d}: {message} ({elapsed/60:.1f} minutes)")
        else:
            failed.append(episode_num)
            print(f"[!] {episode_num:02d}: {message}")
        
        # Wait between episodes
        if episode_num < end_ep:
            wait = 2
            print(f"[*] Waiting {wait} seconds...")
            await asyncio.sleep(wait)
    
    # Results
    print(f"\n{'='*50}")
    print("Final Results")
    print('='*50)
    print(f"[+] Successful: {successful}/{total}")
    print(f"[+] All videos support streaming (pause on exit)")
    
    if failed:
        print(f"[!] Failed episodes: {failed}")
    
    # Clean up download directory if empty
    try:
        if not os.listdir(download_dir):
            os.rmdir(download_dir)
            print(f"[+] Cleaned empty directory: {download_dir}")
    except:
        pass
    
    print(f"\n{'='*50}")
    print("Processing Complete")
    
    # Close Telegram session
    if app:
        await app.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[*] Stopped by user")
    except Exception as e:
        print(f"\n[!] Error: {e}")
