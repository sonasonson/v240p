name: 🎬 Universal Video Uploader

on:
  workflow_dispatch:
    inputs:
      video_url:
        description: '🔗 رابط صفحة الفيلم'
        required: true
        default: 'https://vk.com/video_ext.php?oid=791768803&id=456249035'
      video_title:
        description: '🎬 اسم الفيلم'
        required: true
        default: 'اكس مراتي - الفيلم الكامل'

jobs:
  upload-video:
    runs-on: ubuntu-latest
    timeout-minutes: 120
    
    steps:
    - name: 📥 Checkout repository
      uses: actions/checkout@v4
    
    - name: 🐍 Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.10'
    
    - name: ⚙️ Install system dependencies
      run: |
        sudo apt-get update -y
        sudo apt-get install -y ffmpeg python3-pip wget curl
        
    - name: 📦 Install Python dependencies
      run: |
        echo "🔧 Installing Python packages..."
        pip install --upgrade pip
        pip install pyrogram tgcrypto yt-dlp requests beautifulsoup4 lxml cloudscraper m3u8
        
    - name: 🎬 Create video config
      run: |
        echo "🎬 Creating video_config.json..."
        cat > video_config.json << 'EOF'
        {
          "videos": [
            {
              "url": "${{ github.event.inputs.video_url }}",
              "title": "${{ github.event.inputs.video_title }}"
            }
          ]
        }
        EOF
        
        echo "✅ Config created:"
        cat video_config.json
    
    - name: 🚀 Run video uploader
      env:
        API_ID: ${{ secrets.API_ID }}
        API_HASH: ${{ secrets.API_HASH }}
        CHANNEL: ${{ secrets.CHANNEL }}
        STRING_SESSION: ${{ secrets.STRING_SESSION }}
      run: |
        echo "🚀 Starting Universal Video Uploader..."
        echo "📅 $(date)"
        echo "=========================================="
        python -u main.py 2>&1 | tee processing.log
        
        echo "=========================================="
        echo "📊 Process completed!"
        echo "📁 Check processing.log for details"
        
    - name: 📤 Upload logs
      if: always()
      uses: actions/upload-artifact@v4
      with:
        name: video-logs-${{ github.run_number }}
        path: |
          processing.log
          debug.log
          video_config.json
        retention-days: 3
