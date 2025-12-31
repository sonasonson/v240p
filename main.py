#!/usr/bin/env python3
"""
Telegram Video Downloader & Uploader - Fixed Session Issue
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

# Install packages
install_requirements()

from pyrogram import Client
from pyrogram.errors import FloodWait, AuthKeyUnregistered, SessionPasswordNeeded
import yt_dlp

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
        # تنظيف STRING_SESSION من أي مسافات أو أسطر إضافية
        cleaned_session = STRING_SESSION.strip()
        
        print(f"🔧 Creating client with cleaned session ({len(cleaned_session)} chars)...")
        
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
        
        # بدء العميل
        await app.start()
        
        # التحقق من الاتصال
        me = await app.get_me()
        print(f"✅ Connected as: {me.first_name} (@{me.username})")
        print(f"📞 Phone: {me.phone_number}")
        
        # التحقق من القناة
        try:
            chat = await app.get_chat(TELEGRAM_CHANNEL)
            print(f"📢 Channel found: {chat.title}")
            
            # التحقق من الصلاحيات
            try:
                member = await app.get_chat_member(TELEGRAM_CHANNEL, me.id)
                print(f"👤 Role: {member.status}")
                
                if member.status not in ["creator", "administrator", "member"]:
                    print("⚠️ Warning: You may not have upload permissions")
                    
            except:
                print("⚠️ Warning: Cannot check channel permissions")
                
            return True
            
        except Exception as e:
            print(f"❌ Cannot access channel: {e}")
            print("⚠️ Make sure:")
            print("  1. The channel exists")
            print("  2. Your account is a member")
            print("  3. You have permission to send messages")
            return False
            
    except AuthKeyUnregistered:
        print("❌ STRING_SESSION is invalid or expired")
        print("💡 Generate a new one with:")
        print("   python generate_session.py")
        return False
        
    except SessionPasswordNeeded:
        print("❌ Account has 2FA enabled")
        print("💡 Disable 2FA or use a different account")
        return False
        
    except Exception as e:
        print(f"❌ Connection failed: {type(e).__name__}")
        print(f"📝 Error details: {str(e)[:100]}")
        
        # نصائح استكشاف الأخطاء
        print("\n🔧 Troubleshooting tips:")
        print("1. Check STRING_SESSION length (should be ~350 chars)")
        print("2. Regenerate session with generate_session.py")
        print("3. Verify API_ID and API_HASH")
        print("4. Check if account is banned")
        return False

# ===== VIDEO PROCESSING FUNCTIONS =====
# (ابقاء نفس دوال معالجة الفيديو كما هي في الكود السابق)
# download_video, compress_video, create_thumbnail, upload_video, process_episode
# ... [نفس دوال معالجة الفيديو من الإصدار السابق] ...

# ===== MAIN FUNCTION =====

async def main():
    """Main function"""
    print("="*50)
    print("🎬 GitHub Video Processor v2.0")
    print("="*50)
    
    # Check dependencies
    print("\n🔍 Checking dependencies...")
    
    # Check ffmpeg
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ ffmpeg is installed")
            
            # Get ffmpeg version
            version_match = re.search(r'ffmpeg version (\S+)', result.stdout)
            if version_match:
                print(f"  Version: {version_match.group(1)}")
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
    config_file = "series_config.json"
    if not os.path.exists(config_file):
        print(f"❌ Config file not found: {config_file}")
        print("💡 Creating sample config...")
        
        sample_config = {
            "series_name": "the-protector",
            "series_name_arabic": "المحافظ",
            "season_num": 2,
            "start_episode": 1,
            "end_episode": 8
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
    
    series_name = config.get("series_name", "").strip()
    series_name_arabic = config.get("series_name_arabic", "").strip()
    season_num = int(config.get("season_num", 1))
    start_ep = int(config.get("start_episode", 1))
    end_ep = int(config.get("end_episode", 1))
    
    if not series_name or not series_name_arabic:
        print("❌ Invalid series configuration")
        return
    
    if start_ep > end_ep:
        print("❌ Start episode must be less than end episode")
        return
    
    # Create working directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    download_dir = f"downloads_{timestamp}"
    os.makedirs(download_dir, exist_ok=True)
    
    print(f"\n{'='*50}")
    print("🚀 Starting Video Processing")
    print('='*50)
    print(f"📺 Series: {series_name_arabic}")
    print(f"🌐 English name: {series_name}")
    print(f"🎬 Season: {season_num}")
    print(f"📈 Episodes: {start_ep} to {end_ep} (total: {end_ep - start_ep + 1})")
    print(f"📁 Working dir: {download_dir}")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Process episodes
    successful = 0
    failed = []
    total = end_ep - start_ep + 1
    
    for episode_num in range(start_ep, end_ep + 1):
        current = episode_num - start_ep + 1
        
        print(f"\n[Episode {current}/{total}] Processing episode {episode_num:02d}")
        print("─" * 50)
        
        start_time = time.time()
        success, message = await process_episode(
            episode_num, series_name, series_name_arabic, season_num, download_dir
        )
        
        elapsed = time.time() - start_time
        
        if success:
            successful += 1
            print(f"✅ Episode {episode_num:02d}: {message}")
            print(f"   ⏱️ Processing time: {elapsed:.1f} seconds")
        else:
            failed.append(episode_num)
            print(f"❌ Episode {episode_num:02d}: {message}")
        
        # Wait between episodes (to avoid rate limits)
        if episode_num < end_ep:
            wait_time = 3
            print(f"⏳ Waiting {wait_time} seconds before next episode...")
            await asyncio.sleep(wait_time)
    
    # Results summary
    print(f"\n{'='*50}")
    print("📊 Processing Summary")
    print('='*50)
    print(f"✅ Successful: {successful}/{total}")
    print(f"❌ Failed: {len(failed)}")
    
    if successful == total:
        print("🎉 All episodes processed successfully!")
    elif successful > 0:
        print(f"⚠️ Partially successful ({successful}/{total})")
    else:
        print("💥 All episodes failed!")
    
    if failed:
        print(f"📝 Failed episodes: {failed}")
        print("💡 You can rerun the workflow for failed episodes only")
    
    # Cleanup empty directory
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
    
    # Close Telegram connection
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
