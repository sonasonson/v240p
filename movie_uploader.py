name: 🎬 Movie Uploader (Selenium)

on:
  workflow_dispatch:
    inputs:
      watch_url:
        description: '🔗 رابط مشاهدة الفيلم'
        required: true
        default: 'https://vk.com/video_ext.php?oid=848084895&id=456245049'
      movie_name_arabic:
        description: '📽️ اسم الفيلم (عربي)'
        required: true
        default: 'فيلم شماريخ'
      movie_name_english:
        description: '📽️ اسم الفيلم (إنجليزي)'
        required: false
        default: 'shamarek'

jobs:
  upload-movie-selenium:
    runs-on: ubuntu-latest
    timeout-minutes: 180
    
    steps:
    - name: 📥 Checkout repository
      uses: actions/checkout@v4
    
    - name: 🐍 Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.10'
    
    - name: ⚙️ Install system dependencies
      run: |
        sudo apt-get update
        sudo apt-get install -y ffmpeg python3-pip wget
        sudo apt-get install -y chromium-browser chromium-chromedriver
    
    - name: 📦 Install Python dependencies
      run: |
        pip install --upgrade pip
        pip install -r requirements_selenium.txt
    
    - name: 📽️ إعداد الفيلم
      run: |
        echo "🎬 إعداد ملف الفيلم..."
        
        cat > movie_config.json << 'EOF'
        {
          "watch_url": "${{ github.event.inputs.watch_url }}",
          "movie_name_arabic": "${{ github.event.inputs.movie_name_arabic }}",
          "movie_name_english": "${{ github.event.inputs.movie_name_english }}"
        }
        EOF
        
        echo "✅ تم إنشاء movie_config.json"
        cat movie_config.json
    
    - name: 🚀 تشغيل سكريبت الأفلام مع Selenium
      env:
        API_ID: ${{ secrets.API_ID }}
        API_HASH: ${{ secrets.API_HASH }}
        CHANNEL: ${{ secrets.CHANNEL }}
        STRING_SESSION: ${{ secrets.STRING_SESSION }}
      run: |
        echo "🎬 بدء رفع الفيلم مع Selenium..."
        python movie_uploader_selenium.py 2>&1 | tee movie_processing_selenium.log
