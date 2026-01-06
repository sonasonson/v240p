#!/usr/bin/env python3
"""
VK Video Downloader - MPD Edition
Extracts and downloads DASH MPD streams from VK
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
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urlparse, parse_qs, unquote
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

# Generate browser-like headers
def generate_headers():
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]
    
    return {
        'User-Agent': random.choice(user_agents),
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Referer': 'https://vk.com/',
        'Origin': 'https://vk.com/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
    }

async def setup_telegram():
    """Setup Telegram client"""
    global app
    print("\n🔐 Setting up Telegram...")
    
    try:
        app = Client(
            "vk_mpd_downloader",
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

def extract_mpd_url_from_page(url):
    """Extract MPD URL from VK page with network simulation"""
    print("🎯 Extracting MPD URL from VK page...")
    
    try:
        session = requests.Session()
        headers = generate_headers()
        
        # First, get the page
        print("🔄 Loading VK video page...")
        response = session.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Failed to load page: {response.status_code}")
            return None
        
        html = response.text
        
        # Look for MPD URL patterns (from your network log)
        print("🔍 Searching for MPD URLs...")
        
        # Pattern 1: Direct MPD URLs
        mpd_patterns = [
            r'https?://vkvd[0-9]+\.okcdn\.ru/[^"\']+\.mpd[^"\']*',
            r'https?://[^"\']+okcdn\.ru/[^"\']+\.mpd[^"\']*',
            r'ondemand/[^"\']+\.mpd',
        ]
        
        for pattern in mpd_patterns:
            matches = re.findall(pattern, html)
            for match in matches:
                if not match.startswith('http'):
                    # Make it a full URL
                    if 'okcdn.ru' in match:
                        match = f"https://vkvd1.okcdn.ru/{match}" if match.startswith('/') else f"https://{match}"
                    else:
                        # Try to construct from context
                        base_match = re.search(r'(https?://[^/]+)/', html)
                        if base_match:
                            base = base_match.group(1)
                            match = f"{base}/{match}" if match.startswith('/') else f"{base}/ondemand/{match}"
                
                print(f"✅ Found MPD URL: {match[:100]}...")
                return match
        
        # Pattern 2: Look for initialization segments that might lead to MPD
        print("🔄 Searching for video segments...")
        segment_patterns = [
            r'https?://[^"\']+\.m4s[^"\']*',
            r'https?://[^"\']+track\.(?:v|a)\.m4s[^"\']*',
            r'ondemand/[^"\']+\.m4s',
        ]
        
        for pattern in segment_patterns:
            matches = re.findall(pattern, html)
            for match in matches:
                if not match.startswith('http'):
                    match = f"https://vkvd1.okcdn.ru/{match}" if match.startswith('/') else f"https://{match}"
                
                # Try to derive MPD URL from segment URL
                if '.m4s' in match:
                    # Extract base path
                    parsed = urlparse(match)
                    path_parts = parsed.path.split('/')
                    
                    # Look for pattern like dash4_xxxxx.mpd
                    for i, part in enumerate(path_parts):
                        if part.startswith('dash4_') and '.mpd' in part:
                            # Construct MPD URL
                            mpd_path = '/'.join(path_parts[:i+1])
                            mpd_url = f"{parsed.scheme}://{parsed.netloc}{mpd_path}"
                            print(f"✅ Derived MPD URL from segment: {mpd_url[:100]}...")
                            return mpd_url
        
        # Pattern 3: Look for JSON data containing MPD info
        print("🔄 Searching for JSON data...")
        json_patterns = [
            r'<script[^>]*>([^<]+video[^<]+)</script>',
            r'videoData\s*=\s*({[^;]+});',
            r'playerConfig\s*=\s*({[^}]+})',
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches:
                if 'mpd' in match.lower() or 'dash' in match.lower():
                    # Try to extract URL
                    url_match = re.search(r'https?://[^"\'\s]+\.mpd[^"\'\s]*', match)
                    if url_match:
                        print(f"✅ Found MPD in JSON: {url_match.group(0)[:100]}...")
                        return url_match.group(0)
        
        print("❌ No MPD URL found")
        return None
        
    except Exception as e:
        print(f"❌ Extraction error: {e}")
        return None

def parse_mpd_for_lowest_quality(mpd_url):
    """Parse MPD file to find lowest quality video (around 240p)"""
    print("📊 Parsing MPD for lowest quality...")
    
    try:
        session = requests.Session()
        headers = generate_headers()
        
        # Download MPD file
        print(f"📥 Downloading MPD file...")
        response = session.get(mpd_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Failed to download MPD: {response.status_code}")
            return None, None
        
        mpd_content = response.text
        
        # Parse XML
        try:
            root = ET.fromstring(mpd_content)
        except:
            # Try to clean the XML
            mpd_content_clean = mpd_content.split('<?xml', 1)[-1] if '<?xml' in mpd_content else mpd_content
            try:
                root = ET.fromstring(f'<?xml version="1.0"?>{mpd_content_clean}')
            except:
                print("❌ Failed to parse MPD XML")
                return None, None
        
        # Namespace handling
        ns = {'mpd': 'urn:mpeg:dash:schema:mpd:2011'}
        
        # Find AdaptationSets for video and audio
        video_urls = []
        audio_urls = []
        
        for adaptation_set in root.findall('.//mpd:AdaptationSet', ns):
            mime_type_elem = adaptation_set.find('mpd:Representation/mpd:BaseURL', ns)
            if mime_type_elem is None:
                mime_type_elem = adaptation_set.find('mpd:BaseURL', ns)
            
            if mime_type_elem is not None:
                content_type = adaptation_set.get('contentType', '')
                mime_type = adaptation_set.get('mimeType', '')
                
                # Get bandwidth/quality info
                representation = adaptation_set.find('mpd:Representation', ns)
                bandwidth = representation.get('bandwidth', '0') if representation is not None else '0'
                width = representation.get('width', '0') if representation is not None else '0'
                height = representation.get('height', '0') if representation is not None else '0'
                
                base_url = mime_type_elem.text.strip()
                if not base_url.startswith('http'):
                    # Construct full URL
                    parsed_mpd = urlparse(mpd_url)
                    base_url = f"{parsed_mpd.scheme}://{parsed_mpd.netloc}{base_url}"
                
                # Categorize by type
                if 'video' in content_type.lower() or 'video' in mime_type.lower():
                    video_urls.append({
                        'url': base_url,
                        'bandwidth': int(bandwidth),
                        'width': int(width) if width.isdigit() else 0,
                        'height': int(height) if height.isdigit() else 0
                    })
                elif 'audio' in content_type.lower() or 'audio' in mime_type.lower():
                    audio_urls.append({
                        'url': base_url,
                        'bandwidth': int(bandwidth)
                    })
        
        # If we couldn't parse properly, try regex approach
        if not video_urls:
            print("🔄 Using regex fallback for MPD parsing...")
            
            # Look for video segments
            video_segments = re.findall(r'https?://[^\s"\']+\.(?:v\.m4s|video\d+\.m4s)[^\s"\']*', mpd_content)
            audio_segments = re.findall(r'https?://[^\s"\']+\.(?:a\.m4s|audio\d+\.m4s)[^\s"\']*', mpd_content)
            
            if video_segments:
                # Use first video segment and try to find pattern
                first_video = video_segments[0]
                # Extract base pattern
                if 'track.v.m4s' in first_video:
                    base_url = first_video.replace('track.v.m4s', '')
                    video_urls.append({'url': base_url + 'track.v.m4s', 'bandwidth': 100000, 'height': 240})
                else:
                    video_urls.append({'url': first_video, 'bandwidth': 100000, 'height': 240})
            
            if audio_segments:
                first_audio = audio_segments[0]
                if 'track.a.m4s' in first_audio:
                    base_url = first_audio.replace('track.a.m4s', '')
                    audio_urls.append({'url': base_url + 'track.a.m4s', 'bandwidth': 64000})
                else:
                    audio_urls.append({'url': first_audio, 'bandwidth': 64000})
        
        # Sort video URLs by height (lowest first)
        video_urls.sort(key=lambda x: x['height'])
        
        print(f"📊 Found {len(video_urls)} video quality options")
        for v in video_urls:
            print(f"  • {v['height']}p ({v['bandwidth']//1000}Kbps)")
        
        print(f"📊 Found {len(audio_urls)} audio options")
        
        if video_urls and audio_urls:
            # Select lowest video quality (closest to 240p)
            selected_video = None
            target_height = 240
            
            # First try to find exact 240p
            for v in video_urls:
                if v['height'] == target_height:
                    selected_video = v
                    break
            
            # If not found, find closest
            if not selected_video:
                # Find lowest quality above 144p
                for v in video_urls:
                    if v['height'] >= 144:
                        selected_video = v
                        break
            
            if not selected_video:
                selected_video = video_urls[0]  # Fallback
            
            selected_audio = audio_urls[0]  # Usually only one audio track
            
            print(f"✅ Selected video: {selected_video['height']}p")
            print(f"✅ Selected audio")
            
            return selected_video['url'], selected_audio['url']
        
        print("❌ No video/audio tracks found in MPD")
        return None, None
        
    except Exception as e:
        print(f"❌ MPD parsing error: {e}")
        return None, None

def download_dash_segments(base_video_url, base_audio_url, output_path):
    """Download DASH video and audio segments and combine them"""
    print("🎬 Downloading DASH segments...")
    
    try:
        session = requests.Session()
        headers = generate_headers()
        
        # Create temp directory
        temp_dir = "dash_temp"
        os.makedirs(temp_dir, exist_ok=True)
        
        # Download video segments (s0 to sN)
        video_segments = []
        audio_segments = []
        
        print("📥 Downloading video segments...")
        for i in range(0, 100):  # Try up to 100 segments
            segment_url = base_video_url.replace('track.v.m4s', f's{i}.v.m4s')
            
            try:
                response = session.head(segment_url, headers=headers, timeout=5)
                if response.status_code != 200:
                    # Try alternative pattern
                    segment_url = base_video_url.replace('track.v.m4s', f'video{i}.m4s')
                    response = session.head(segment_url, headers=headers, timeout=5)
                    if response.status_code != 200:
                        break  # No more segments
                
                # Download segment
                segment_file = os.path.join(temp_dir, f'video_{i:04d}.m4s')
                print(f"  📥 Segment {i}...")
                
                seg_response = session.get(segment_url, headers=headers, timeout=30, stream=True)
                with open(segment_file, 'wb') as f:
                    for chunk in seg_response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                video_segments.append(segment_file)
                
            except Exception as e:
                print(f"⚠️ Failed segment {i}: {e}")
                break
        
        if not video_segments:
            print("❌ No video segments downloaded")
            # Try to download the init segment
            init_url = base_video_url
            init_file = os.path.join(temp_dir, 'video_init.m4s')
            try:
                response = session.get(init_url, headers=headers, timeout=30)
                with open(init_file, 'wb') as f:
                    f.write(response.content)
                video_segments.append(init_file)
            except:
                pass
        
        # Download audio segments
        print("📥 Downloading audio segments...")
        for i in range(0, 100):
            segment_url = base_audio_url.replace('track.a.m4s', f's{i}.a.m4s')
            
            try:
                response = session.head(segment_url, headers=headers, timeout=5)
                if response.status_code != 200:
                    # Try alternative pattern
                    segment_url = base_audio_url.replace('track.a.m4s', f'audio{i}.m4s')
                    response = session.head(segment_url, headers=headers, timeout=5)
                    if response.status_code != 200:
                        break
                
                segment_file = os.path.join(temp_dir, f'audio_{i:04d}.m4s')
                print(f"  📥 Audio segment {i}...")
                
                seg_response = session.get(segment_url, headers=headers, timeout=30, stream=True)
                with open(segment_file, 'wb') as f:
                    for chunk in seg_response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                audio_segments.append(segment_file)
                
            except Exception as e:
                print(f"⚠️ Failed audio segment {i}: {e}")
                break
        
        if not audio_segments:
            print("❌ No audio segments downloaded")
            # Try to download the init segment
            init_url = base_audio_url
            init_file = os.path.join(temp_dir, 'audio_init.m4s')
            try:
                response = session.get(init_url, headers=headers, timeout=30)
                with open(init_file, 'wb') as f:
                    f.write(response.content)
                audio_segments.append(init_file)
            except:
                pass
        
        if not video_segments:
            print("❌ No content downloaded")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return False
        
        # Combine video segments
        print("🔗 Combining video segments...")
        video_list_file = os.path.join(temp_dir, 'video_list.txt')
        with open(video_list_file, 'w') as f:
            for seg in video_segments:
                f.write(f"file '{os.path.basename(seg)}'\n")
        
        video_combined = os.path.join(temp_dir, 'video_combined.mp4')
        cmd_video = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', video_list_file,
            '-c', 'copy',
            '-y',
            video_combined
        ]
        
        result = subprocess.run(cmd_video, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"❌ Failed to combine video: {result.stderr[:200]}")
        
        # Combine audio segments if available
        audio_combined = None
        if audio_segments:
            print("🔗 Combining audio segments...")
            audio_list_file = os.path.join(temp_dir, 'audio_list.txt')
            with open(audio_list_file, 'w') as f:
                for seg in audio_segments:
                    f.write(f"file '{os.path.basename(seg)}'\n")
            
            audio_combined = os.path.join(temp_dir, 'audio_combined.mp4')
            cmd_audio = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', audio_list_file,
                '-c', 'copy',
                '-y',
                audio_combined
            ]
            
            result = subprocess.run(cmd_audio, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                print(f"⚠️ Failed to combine audio: {result.stderr[:200]}")
                audio_combined = None
        
        # Merge video and audio
        print("🎵 Merging video and audio...")
        if audio_combined and os.path.exists(audio_combined):
            cmd_merge = [
                'ffmpeg',
                '-i', video_combined,
                '-i', audio_combined,
                '-c', 'copy',
                '-y',
                output_path
            ]
        else:
            # Just copy video if no audio
            cmd_merge = [
                'ffmpeg',
                '-i', video_combined,
                '-c', 'copy',
                '-y',
                output_path
            ]
        
        result = subprocess.run(cmd_merge, capture_output=True, text=True, timeout=300)
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        if result.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path) / (1024 * 1024)
            print(f"✅ DASH download complete: {file_size:.1f} MB")
            return True
        else:
            print(f"❌ Failed to merge: {result.stderr[:200]}")
            return False
        
    except Exception as e:
        print(f"❌ DASH download error: {e}")
        # Cleanup on error
        if 'temp_dir' in locals():
            shutil.rmtree(temp_dir, ignore_errors=True)
        return False

def compress_to_240p(input_path, output_path):
    """Compress video to 240p"""
    print("🎬 Compressing to 240p...")
    
    if not os.path.exists(input_path):
        return False
    
    input_size = os.path.getsize(input_path) / (1024 * 1024)
    print(f"📊 Input size: {input_size:.1f} MB")
    
    # Check current quality
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
    """Process VK video using DASH MPD"""
    print(f"\n{'='*60}")
    print(f"🎬 Processing: {title}")
    print(f"🔗 URL: {url}")
    print(f"{'='*60}")
    
    timestamp = datetime.now().strftime('%H%M%S')
    temp_dir = f"vk_dash_{timestamp}"
    os.makedirs(temp_dir, exist_ok=True)
    
    temp_file = os.path.join(temp_dir, "video.mp4")
    final_file = os.path.join(temp_dir, "video_240p.mp4")
    
    try:
        # Step 1: Extract MPD URL
        print("1️⃣ Extracting MPD URL...")
        mpd_url = extract_mpd_url_from_page(url)
        
        if not mpd_url:
            print("❌ Failed to extract MPD URL")
            return False, "MPD extraction failed"
        
        print(f"✅ MPD URL: {mpd_url[:150]}...")
        
        # Step 2: Parse MPD for video/audio URLs
        print("2️⃣ Parsing MPD for segments...")
        video_base_url, audio_base_url = parse_mpd_for_lowest_quality(mpd_url)
        
        if not video_base_url:
            print("❌ Failed to parse MPD")
            return False, "MPD parsing failed"
        
        print(f"✅ Video base URL: {video_base_url[:100]}...")
        if audio_base_url:
            print(f"✅ Audio base URL: {audio_base_url[:100]}...")
        
        # Step 3: Download DASH segments
        print("3️⃣ Downloading DASH segments...")
        if not download_dash_segments(video_base_url, audio_base_url, temp_file):
            return False, "DASH download failed"
        
        # Check file
        if not os.path.exists(temp_file) or os.path.getsize(temp_file) < 1024:
            return False, "Downloaded file is invalid"
        
        print(f"📊 File size: {os.path.getsize(temp_file) / (1024*1024):.1f} MB")
        
        # Step 4: Compress
        print("4️⃣ Compressing to 240p...")
        if not compress_to_240p(temp_file, final_file):
            final_file = temp_file
        
        # Step 5: Upload
        print("5️⃣ Uploading to Telegram...")
        if not await upload_to_telegram(final_file, title):
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
    print("🎬 VK DASH Downloader v5.0")
    print("📊 Uses MPD (DASH) streaming protocol")
    print("🎯 Extracts and combines video/audio segments")
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
