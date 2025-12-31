#!/usr/bin/env python3
"""
Generate Telegram STRING_SESSION for GitHub
"""

import os
import sys
import asyncio
from pyrogram import Client

async def generate_session():
    """Generate a new string session"""
    print("="*50)
    print("Telegram String Session Generator")
    print("="*50)
    
    # إدخال البيانات
    api_id = input("Enter API_ID (from https://my.telegram.org): ").strip()
    api_hash = input("Enter API_HASH: ").strip()
    
    if not api_id.isdigit() or not api_hash:
        print("❌ Invalid API credentials")
        return
    
    try:
        api_id = int(api_id)
    except:
        print("❌ API_ID must be a number")
        return
    
    # إنشاء العميل
    client = Client(
        "my_session",
        api_id=api_id,
        api_hash=api_hash,
        in_memory=True
    )
    
    print("\n🔗 Connecting to Telegram...")
    await client.start()
    
    # التحقق من المستخدم
    me = await client.get_me()
    print(f"✅ Connected as: {me.first_name} (@{me.username})")
    
    # تصدير الجلسة
    session_string = await client.export_session_string()
    
    print("\n" + "="*50)
    print("✅ STRING_SESSION Generated Successfully!")
    print("="*50)
    
    # عرض الجلسة
    print(f"\n📋 Your STRING_SESSION:\n")
    print("-"*50)
    print(session_string)
    print("-"*50)
    
    print("\n⚠️ Important Instructions:")
    print("1. Copy the ENTIRE string above (including all characters)")
    print("2. Go to your GitHub repository → Settings → Secrets")
    print("3. Update the STRING_SESSION secret with this value")
    print("4. Make sure there are no extra spaces or line breaks")
    
    # حفظ في ملف للتأكد
    with open("session.txt", "w") as f:
        f.write(session_string)
    print(f"\n📁 Session also saved to 'session.txt'")
    
    await client.stop()

if __name__ == "__main__":
    try:
        asyncio.run(generate_session())
    except KeyboardInterrupt:
        print("\n❌ Stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
