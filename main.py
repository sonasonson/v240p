#!/usr/bin/env python3
"""
Telegram Video Downloader - Direct Link Version for 3seq.cam
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
from urllib.parse import urlparse

# ===== CONFIGURATION =====
TELEGRAM_API_ID = os.environ.get("API_ID", "")
TELEGRAM_API_HASH = os.environ.get("API_HASH", "")
TELEGRAM_CHANNEL = os.environ.get("CHANNEL", "")
STRING_SESSION = os.environ.get("STRING_SESSION", "")

def validate_env():
    """Validate environment variables"""
    if not all([TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_CHANNEL, STRING_SESSION]):
        print("❌ Missing environment variables")
        return False
    
    if not TELEGRAM_API_ID.isdigit():
        print("❌ API_ID must be a number")
        return False
    
    print("✅ Environment variables validated")
    return True

if not validate_env():
    sys.exit(1)

TELEGRAM_API_ID = int(TELEGRAM_API_ID)

# Updated headers
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9,ar;q=0.8',
    'Referer': 'https://z.3seq.cam/',
    'DNT': '1',
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
from pyrogram.errors import FloodWait
import yt_dlp

app = None

# ===== TELEGRAM SETUP =====
async def setup_telegram():
    """Setup Telegram using string session"""
    global app
    
    print("\n" + "="*50)
    print("🔐 Telegram Setup")
    print("="*50)
    
    try:
        app = Client(
            name="uploader",
            api_id=TELEGRAM_API_ID,
            api_hash=TELEGRAM_API_HASH,
            session_string=STRING_SESSION.strip(),
            in_memory=True,
        )
        
        print("🔌 Connecting to Telegram...")
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
        print(f"❌ Connection failed: {e}")
        return False

# ===== DIRECT LINK PROCESSING =====

def load_direct_links(links_file="direct_links.json"):
    """Load direct links from JSON file"""
    if not os.path.exists(links_file):
        print(f"❌ Links file not found: {links_file}")
        
        # Create template with example links
        template = {
            "series_name_arabic": "حب للايجار",
            "season_num": 1,
            "episodes": {
                1: "https://z.3seq.cam/video/modablaj-kiralik-ask-episode-s01e01-xxxx/?do=watch",
                2: "https://z.3seq.cam/video/modablaj-kiralik-ask-episode-s01e02-avxn/?do=watch",
                # Add more episodes...
            }
        }
        
        with open(links_file, 'w', encoding='utf-8') as f:
            json.dump(template, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Created template: {links_file}")
        print("⚠️ Please edit this file with actual episode links")
        return None
    
    try:
        with open(links_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"✅ Loaded {len(data['episodes'])} direct links from {links_file}")
        return data
        
    except Exception as e:
        print(f"❌ Error loading links file: {e}")
        return None

def download_with_ytdlp(direct_url, output_path):
    """Download video directly using yt-dlp"""
    print(f"📥 Downloading: {direct_url}")
    
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
        'verbose': True,
    }
    
    try:
        start = time.time()
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info first to check
            try:
                info = ydl.extract_info(direct_url, download=False)
                print(f"ℹ️ Title: {info.get('title', 'N/A')}")
                print(f"ℹ️ Duration: {info.get('duration', 0)} seconds")
                
                # Now download
                ydl.download([direct_url])
                
                elapsed = time.time() - start
                
                # Check if file exists
                if os.path.exists(output_path):
                    size = os.path.getsize(output_path) / (1024*1024)
                    print(f"✅ Downloaded in {elapsed:.1f}s ({size:.1f}MB)")
                    return True
                
                # Check for other extensions
                base = os.path.splitext(output_path)[0]
                for ext in ['.mp4', '.mkv', '.webm', '.avi']:
                    alt_file = base + ext
                    if os.path.exists(alt_file):
                        shutil.move(alt_file, output_path)
                        size = os.path.getsize(output_path) / (1024*1024)
                        print(f"✅ Downloaded (renamed) in {elapsed:.1f}s ({size:.1f}MB)")
                        return True
                        
            except Exception as e:
                print(f"❌ yt-dlp error: {e}")
                
                # Fallback: try direct download if yt-dlp fails
                print("🔄 Trying fallback download...")
                session = requests.Session()
                session.headers.update(HEADERS)
                
                try:
                    response = session.get(direct_url, stream=True, timeout=30)
                    if response.status_code == 200:
                        with open(output_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        
                        if os.path.exists(output_path):
                            size = os.path.getsize(output_path) / (1024*1024)
                            print(f"✅ Fallback download successful ({size:.1f}MB)")
                            return True
                except Exception as fallback_error:
                    print(f"❌ Fallback also failed: {fallback_error}")
        
        return False
        
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return False

def compress_video(input_file, output_file):
    """Compress video"""
    if not os.path.exists(input_file):
        return False
    
    try:
        cmd = [
            'ffmpeg', '-i', input_file,
            '-vf', 'scale=-2:240',
            '-c:v', 'libx264', '-crf', '28', '-preset', 'veryfast',
            '-c:a', 'aac', '-b:a', '64k',
            '-y', output_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0 and os.path.exists(output_file)
    except:
        return False

def create_thumbnail(input_file, thumbnail_path):
    """Create thumbnail"""
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

async def upload_video(file_path, caption, thumbnail_path=None):
    """Upload video to Telegram"""
    try:
        if not app or not os.path.exists(file_path):
            return False
        
        file_size = os.path.getsize(file_path) / (1024*1024)
        print(f"☁️ Uploading ({file_size:.1f}MB)...")
        
        upload_params = {
            'chat_id': TELEGRAM_CHANNEL,
            'video': file_path,
            'caption': caption,
            'supports_streaming': True,
        }
        
        if thumbnail_path and os.path.exists(thumbnail_path):
            upload_params['thumb'] = thumbnail_path
        
        start_time = time.time()
        
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

async def process_episode_direct(episode_num, direct_url, series_name_arabic, season_num, download_dir):
    """Process episode using direct URL"""
    print(f"\n{'─'*50}")
    print(f"🎬 Processing Episode {episode_num:02d}")
    print(f"🔗 Direct URL: {direct_url}")
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
        # 1. Download directly using yt-dlp
        if not download_with_ytdlp(direct_url, temp_file):
            return False, "Download failed"
        
        # 2. Create thumbnail
        create_thumbnail(temp_file, thumbnail_file)
        
        # 3. Compress
        if not compress_video(temp_file, final_file):
            print("⚠️ Compression failed, using original")
            shutil.copy2(temp_file, final_file)
        
        # 4. Upload
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
    print("🎬 Direct Link Video Processor")
    print("="*50)
    
    # Check dependencies
    print("\n🔍 Checking dependencies...")
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True)
        print("✅ ffmpeg is installed")
    except:
        print("❌ ffmpeg not found")
    
    # Setup Telegram
    if not await setup_telegram():
        print("❌ Cannot continue without Telegram connection")
        return
    
    # Load direct links
    links_data = load_direct_links("direct_links.json")
    if not links_data:
        print("❌ No links to process")
        return
    
    series_name_arabic = links_data.get("series_name_arabic", "مسلسل")
    season_num = links_data.get("season_num", 1)
    episodes = links_data.get("episodes", {})
    
    if not episodes:
        print("❌ No episodes in links file")
        return
    
    # Create download directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    download_dir = f"downloads_{timestamp}"
    os.makedirs(download_dir, exist_ok=True)
    
    print(f"\n{'='*50}")
    print("🚀 Starting Processing")
    print('='*50)
    print(f"📺 Series: {series_name_arabic}")
    print(f"🎬 Season: {season_num}")
    print(f"📈 Episodes to process: {len(episodes)}")
    print(f"📁 Working dir: {download_dir}")
    
    # Process episodes
    successful = 0
    failed = []
    total = len(episodes)
    
    # Sort episodes by number
    sorted_episodes = sorted(episodes.items(), key=lambda x: int(x[0]))
    
    for idx, (episode_num_str, direct_url) in enumerate(sorted_episodes, 1):
        episode_num = int(episode_num_str)
        
        print(f"\n[Episode {idx}/{total}]")
        
        start_time = time.time()
        success, message = await process_episode_direct(
            episode_num, direct_url, series_name_arabic, season_num, download_dir
        )
        
        elapsed = time.time() - start_time
        
        if success:
            successful += 1
            print(f"✅ Episode {episode_num:02d}: {message} ({elapsed:.1f}s)")
        else:
            failed.append(episode_num)
            print(f"❌ Episode {episode_num:02d}: {message}")
        
        # Wait between episodes
        if idx < total:
            wait_time = 2
            print(f"⏳ Waiting {wait_time} seconds...")
            await asyncio.sleep(wait_time)
    
    # Summary
    print(f"\n{'='*50}")
    print("📊 Processing Summary")
    print('='*50)
    print(f"✅ Successful: {successful}/{total}")
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

# ===== HELPER TOOLS =====

def discover_episode_links(start=1, end=89, series_name="kiralik-ask", season=1):
    """
    Helper to manually discover episode links
    Returns: Dictionary of {episode_number: full_url}
    """
    print("🔍 Manual Link Discovery Tool")
    print("="*50)
    
    discovered = {}
    
    for episode in range(start, end + 1):
        print(f"\nEpisode {episode}:")
        
        # Try common suffix patterns
        common_suffixes = ['avxn', 'xyzw', 'abcd', 'wxyz', 'test', 'demo']
        
        for suffix in common_suffixes:
            if season > 1:
                url = f"https://z.3seq.cam/video/modablaj-{series_name}-episode-s{season:02d}e{episode:02d}-{suffix}/?do=watch"
            else:
                url = f"https://z.3seq.cam/video/modablaj-{series_name}-episode-{episode:02d}-{suffix}/?do=watch"
            
            print(f"  Testing: {url}")
            
            try:
                response = requests.head(url, headers=HEADERS, timeout=5)
                if response.status_code == 200:
                    discovered[episode] = url
                    print(f"  ✅ Found working link!")
                    break
                else:
                    print(f"  ❌ HTTP {response.status_code}")
            except:
                print(f"  ❌ Connection failed")
        
        time.sleep(0.5)  # Avoid rate limiting
    
    # Save discovered links
    if discovered:
        output_file = f"discovered_links_s{season:02d}.json"
        data = {
            "series_name_arabic": "حب للايجار",
            "season_num": season,
            "episodes": discovered
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ Saved {len(discovered)} discovered links to {output_file}")
    
    return discovered

def create_links_template():
    """Create a template links file"""
    template = {
        "series_name_arabic": "حب للايجار",
        "season_num": 1,
        "episodes": {
            1: "https://z.3seq.cam/video/modablaj-kiralik-ask-episode-s01e01-xxxx/?do=watch",
            2: "https://z.3seq.cam/video/modablaj-kiralik-ask-episode-s01e02-avxn/?do=watch",
            3: "https://z.3seq.cam/video/modablaj-kiralik-ask-episode-s01e03-xxxx/?do=watch",
            # Continue for all 89 episodes...
        }
    }
    
    with open("direct_links_template.json", 'w', encoding='utf-8') as f:
        json.dump(template, f, ensure_ascii=False, indent=2)
    
    print("✅ Created direct_links_template.json")
    print("⚠️ Edit this file with actual episode URLs")
    print("💡 Use format: https://z.3seq.cam/video/modablaj-kiralik-ask-episode-s01eXX-XXXX/?do=watch")

if __name__ == "__main__":
    # Check for special commands
    if len(sys.argv) > 1:
        if sys.argv[1] == "--discover":
            start = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            end = int(sys.argv[3]) if len(sys.argv) > 3 else 89
            discover_episode_links(start, end)
        elif sys.argv[1] == "--template":
            create_links_template()
        else:
            # Run main processor
            try:
                asyncio.run(main())
            except KeyboardInterrupt:
                print("\n\n⏹️ Process stopped by user")
            except Exception as e:
                print(f"\n💥 Error: {e}")
    else:
        # Run main processor
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("\n\n⏹️ Process stopped by user")
        except Exception as e:
            print(f"\n💥 Error: {e}")
