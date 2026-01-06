def extract_vidspeed_video_url(url):
    """Extract video URL from vidspeed.org - Direct approach"""
    print("🔍 Using direct vidspeed extractor...")
    
    try:
        # Try cloudscraper first to bypass any protections
        scraper = cloudscraper.create_scraper()
        
        headers = HEADERS.copy()
        headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://vidspeed.org/',
            'Sec-Fetch-Dest': 'iframe',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'cross-site',
            'Upgrade-Insecure-Requests': '1'
        })
        
        print("🌐 Fetching vidspeed page...")
        response = scraper.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"⚠️ HTTP {response.status_code}")
            return None
        
        content = response.text
        
        # Save full page for debugging
        debug_filename = f"vidspeed_full_{datetime.now().strftime('%H%M%S')}.html"
        with open(debug_filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"📝 Saved full page to {debug_filename}")
        
        # Method 1: Try to find the exact HLS URL from your network logs
        print("🔍 Method 1: Looking for exact HLS URL pattern...")
        
        # Extract the video ID from the URL
        video_id = url.split('/')[-1].replace('.html', '').replace('embed-', '')
        print(f"🎯 Video ID: {video_id}")
        
        # Based on your network logs, construct potential HLS URLs
        potential_urls = [
            f"https://vsped-fs11-u3z.cdnz.quest/hls2/04/00177/{video_id}_/master.m3u8",
            f"https://vsped-fs11-u3z.cdnz.quest/hls2/04/00177/{video_id}/master.m3u8",
            f"https://vsped-fs11-u3z.cdnz.quest/hls2/04/00177/{video_id}_n/index-v1-a1.m3u8",
            f"https://vsped-fs11-u3z.cdnz.quest/hls2/04/00177/{video_id}_l/index-v1-a1.m3u8",
        ]
        
        # Try each potential URL
        for test_url in potential_urls:
            print(f"🔗 Testing: {test_url}")
            try:
                test_headers = headers.copy()
                test_headers['Referer'] = url
                test_response = requests.head(test_url, headers=test_headers, timeout=10)
                if test_response.status_code == 200:
                    print(f"✅ Found working HLS URL: {test_url}")
                    return test_url
            except:
                continue
        
        # Method 2: Search for HLS patterns in the page
        print("🔍 Method 2: Searching for HLS patterns in page...")
        
        # Look for JW Player specific patterns
        jw_patterns = [
            r'"file"\s*:\s*"([^"]+\.m3u8[^"]*)"',
            r'"sources"\s*:\s*\[[^\]]*"([^"]+\.m3u8[^"]*)"[^\]]*\]',
            r'playlist\s*:\s*\[[^\]]*"([^"]+\.m3u8[^"]*)"[^\]]*\]',
            r'jwplayer\([^)]+\)\.setup\(({[^}]+})\)',
            r'playerInstance\.setup\(({[^}]+})\)',
        ]
        
        for pattern in jw_patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            for match in matches:
                if isinstance(match, str) and '.m3u8' in match:
                    print(f"✅ Found HLS URL in JW Player config: {match[:100]}...")
                    return match
                elif isinstance(match, str) and '{' in match:
                    # Try to parse as JSON
                    try:
                        # Clean the JSON
                        json_str = match.replace('\\"', '"').replace('\\/', '/')
                        # Remove trailing commas
                        json_str = re.sub(r',\s*}', '}', json_str)
                        json_str = re.sub(r',\s*]', ']', json_str)
                        
                        config = json.loads(json_str)
                        
                        # Look for file or sources
                        if 'file' in config:
                            file_url = config['file']
                            if '.m3u8' in file_url:
                                print(f"✅ Found HLS URL in JSON: {file_url[:100]}...")
                                return file_url
                        
                        if 'sources' in config and isinstance(config['sources'], list):
                            for source in config['sources']:
                                if isinstance(source, dict) and 'file' in source:
                                    file_url = source['file']
                                    if '.m3u8' in file_url:
                                        print(f"✅ Found HLS URL in sources: {file_url[:100]}...")
                                        return file_url
                    except:
                        pass
        
        # Method 3: Search for all m3u8 URLs in the page
        print("🔍 Method 3: Searching for all m3u8 URLs...")
        m3u8_patterns = [
            r'https?://[^"\'\s<>]+\.m3u8(?:\?[^"\'\s<>]*)?',
            r'//[^"\'\s<>]+\.m3u8(?:\?[^"\'\s<>]*)?',
            r'"[^"]+\.m3u8[^"]*"',
            r"'[^']+\.m3u8[^']*'",
        ]
        
        all_m3u8_urls = []
        for pattern in m3u8_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                # Clean the URL
                url_clean = match.strip('"\'').replace('\\/', '/')
                if url_clean.startswith('//'):
                    url_clean = 'https:' + url_clean
                
                if url_clean not in all_m3u8_urls:
                    all_m3u8_urls.append(url_clean)
        
        # Filter and sort URLs
        filtered_urls = []
        for m3u8_url in all_m3u8_urls:
            if 'cdnz.quest' in m3u8_url or 'vsped-' in m3u8_url:
                filtered_urls.append(m3u8_url)
        
        if filtered_urls:
            print(f"📊 Found {len(filtered_urls)} potential HLS URLs:")
            for i, m3u8_url in enumerate(filtered_urls[:5]):  # Show first 5
                print(f"  {i+1}. {m3u8_url[:100]}...")
            
            # Try the first one
            first_url = filtered_urls[0]
            print(f"🔗 Testing first URL: {first_url}")
            try:
                test_headers = headers.copy()
                test_headers['Referer'] = url
                test_response = requests.head(first_url, headers=test_headers, timeout=10)
                if test_response.status_code == 200:
                    print(f"✅ First HLS URL works: {first_url}")
                    return first_url
            except:
                pass
        
        # Method 4: Try to find by scanning the page line by line
        print("🔍 Method 4: Scanning page line by line...")
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'm3u8' in line.lower() or 'hls' in line.lower():
                # Look for URLs in this line
                url_pattern = r'https?://[^"\'\s<>]+\.m3u8[^"\'\s<>]*'
                matches = re.findall(url_pattern, line)
                for match in matches:
                    print(f"✅ Found HLS URL on line {i}: {match[:100]}...")
                    return match
        
        # Method 5: Try to extract from script tags
        print("🔍 Method 5: Extracting from script tags...")
        soup = BeautifulSoup(content, 'html.parser')
        script_tags = soup.find_all('script')
        
        for script in script_tags:
            if script.string:
                script_content = script.string
                # Look for video configuration
                if 'jwplayer' in script_content or 'setup' in script_content:
                    # Extract JSON-like configuration
                    json_patterns = [
                        r'sources\s*:\s*\[([^\]]+)\]',
                        r'file\s*:\s*["\']([^"\']+)["\']',
                        r'playlist\s*:\s*\[([^\]]+)\]',
                    ]
                    
                    for pattern in json_patterns:
                        matches = re.findall(pattern, script_content, re.DOTALL)
                        for match in matches:
                            if '.m3u8' in match:
                                # Clean the URL
                                url_match = re.search(r'https?://[^\s,]+\.m3u8[^\s,]*', match)
                                if url_match:
                                    video_url = url_match.group(0)
                                    print(f"✅ Found HLS URL in script: {video_url[:100]}...")
                                    return video_url
        
        print("❌ Could not extract video URL from vidspeed")
        return None
        
    except Exception as e:
        print(f"⚠️ Vidspeed extraction error: {e}")
        import traceback
        traceback.print_exc()
        return None
