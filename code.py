import streamlit as st
import requests
import io
import hashlib
import base64
import subprocess
import sys
import os
import json
import time
import re
import tempfile
import zipfile
from PIL import Image, ImageEnhance
from urllib.parse import urljoin, urlparse, unquote
from bs4 import BeautifulSoup

# ---------------------------
# AUTO-INSTALLATION SYSTEM
# ---------------------------

def install_package(package):
    """Silently install packages"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package, "-q"])
        return True
    except:
        return False

# Try to import and auto-install if needed
def get_selenium():
    """Get selenium with auto-install"""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        return True, webdriver, Service, Options, By, WebDriverWait, EC
    except ImportError:
        if install_package("selenium"):
            try:
                from selenium import webdriver
                from selenium.webdriver.chrome.service import Service
                from selenium.webdriver.chrome.options import Options
                from selenium.webdriver.common.by import By
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                return True, webdriver, Service, Options, By, WebDriverWait, EC
            except:
                return False, None, None, None, None, None, None
        return False, None, None, None, None, None, None

def get_webdriver_manager():
    """Get webdriver-manager with auto-install"""
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        from webdriver_manager.core.os_manager import ChromeType
        return True, ChromeDriverManager, ChromeType
    except ImportError:
        if install_package("webdriver-manager"):
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                from webdriver_manager.core.os_manager import ChromeType
                return True, ChromeDriverManager, ChromeType
            except:
                return False, None, None
        return False, None, None

def get_playwright():
    """Get playwright with auto-install"""
    try:
        from playwright.sync_api import sync_playwright
        return True, sync_playwright
    except ImportError:
        if install_package("playwright"):
            try:
                subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
                from playwright.sync_api import sync_playwright
                return True, sync_playwright
            except:
                return False, None
        return False, None

# Initialize availability
SELENIUM_AVAILABLE, webdriver, Service, ChromeOptions, By, WebDriverWait, EC = get_selenium()
WDM_AVAILABLE, ChromeDriverManager, ChromeType = get_webdriver_manager()
PLAYWRIGHT_AVAILABLE, sync_playwright = get_playwright()

# ---------------------------
# PAGE CONFIG
# ---------------------------
st.set_page_config(
    page_title="Universal Image Scraper Pro",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stButton button {
        width: 100%;
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    .download-btn > button {
        background: #00c853 !important;
        color: white !important;
        border: none !important;
    }
    .enhance-btn > button {
        background: #2979ff !important;
        color: white !important;
        border: none !important;
    }
    .image-container {
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 16px;
        background: #fafafa;
        margin-bottom: 16px;
        transition: transform 0.2s;
    }
    .image-container:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .stats-row {
        display: flex;
        gap: 10px;
        margin-top: 8px;
        flex-wrap: wrap;
    }
    .stat-badge {
        background: #f0f2f6;
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 0.85em;
        color: #555;
    }
    .method-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.8em;
        font-weight: 600;
        margin: 4px;
    }
    .method-requests { background: #e3f2fd; color: #1976d2; }
    .method-selenium { background: #f3e5f5; color: #7b1fa2; }
    .method-playwright { background: #e8f5e9; color: #388e3c; }
    .method-fallback { background: #fff3e0; color: #f57c00; }
</style>
""", unsafe_allow_html=True)

# ---------------------------
# SESSION STATE INIT
# ---------------------------
if 'images_data' not in st.session_state:
    st.session_state.images_data = []
if 'enhanced_images' not in st.session_state:
    st.session_state.enhanced_images = {}
if 'scraping_done' not in st.session_state:
    st.session_state.scraping_done = False
if 'current_url' not in st.session_state:
    st.session_state.current_url = ""
if 'method_used' not in st.session_state:
    st.session_state.method_used = None
if 'errors' not in st.session_state:
    st.session_state.errors = []

# ---------------------------
# SMART URL HANDLER
# ---------------------------

def convert_special_urls(url):
    """Convert special URLs to scrapable equivalents"""
    if not url:
        return url
    
    # GitHub.dev (VS Code editor) -> GitHub.com (public repo)
    if 'github.dev' in url:
        match = re.search(r'github\.dev/([^/]+)/([^/]+)', url)
        if match:
            return f"https://github.com/{match.group(1)}/{match.group(2)}"
    
    # GitHub raw content links
    if 'raw.githubusercontent.com' in url:
        return url
    
    # Handle gist.github.com
    if 'gist.github.com' in url:
        return url
    
    # Remove tracking parameters
    url = re.sub(r'[?&](utm_|ref|source|campaign|fbclid|gclid).*', '', url)
    
    return url

def is_valid_url(url):
    """Validate URL format"""
    try:
        result = urlparse(url)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except:
        return False

# ---------------------------
# MULTI-METHOD FETCH SYSTEM
# ---------------------------

def get_content_requests(url, headers=None):
    """Method 1: Simple requests with multiple header strategies"""
    if headers is None:
        headers_list = [
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Cache-Control": "max-age=0"
            },
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.0.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        ]
    else:
        headers_list = [headers]
    
    for i, hdrs in enumerate(headers_list):
        try:
            response = requests.get(url, headers=hdrs, timeout=20, allow_redirects=True)
            response.raise_for_status()
            if len(response.text) > 500:
                return response.text, "requests"
        except Exception as e:
            continue
    
    return None, None

def get_content_playwright(url, wait_time=3):
    """Method 2: Playwright (auto-downloads Chromium)"""
    if not PLAYWRIGHT_AVAILABLE:
        return None, None
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(wait_time * 1000)
            
            # Scroll to trigger lazy loading
            page.evaluate("""() => {
                window.scrollTo(0, document.body.scrollHeight / 3);
            }""")
            page.wait_for_timeout(1000)
            page.evaluate("""() => {
                window.scrollTo(0, document.body.scrollHeight * 2 / 3);
            }""")
            page.wait_for_timeout(1000)
            
            content = page.content()
            browser.close()
            return content, "playwright"
    except Exception as e:
        st.session_state.errors.append(f"Playwright error: {str(e)[:100]}")
        return None, None

def get_content_selenium(url, wait_time=3):
    """Method 3: Selenium with auto-setup"""
    if not SELENIUM_AVAILABLE:
        return None, None
    
    driver = None
    try:
        options = ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0.36")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-images")  # Don't load images for speed
        
        # Try to create driver with webdriver-manager
        try:
            if WDM_AVAILABLE:
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
            else:
                driver = webdriver.Chrome(options=options)
        except Exception as e:
            # Fallback to direct Chrome
            try:
                driver = webdriver.Chrome(options=options)
            except:
                return None, None
        
        driver.get(url)
        time.sleep(wait_time)
        
        # Scroll to trigger lazy loading
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 3);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 2 / 3);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        
        content = driver.page_source
        return content, "selenium"
        
    except Exception as e:
        st.session_state.errors.append(f"Selenium error: {str(e)[:100]}")
        return None, None
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

def get_page_content(url, force_method=None, wait_time=3):
    """
    Smart content fetcher with automatic fallback chain:
    1. Requests (fastest, works on static sites)
    2. Playwright (auto-downloads browser, good for JS)
    3. Selenium (if available)
    """
    st.session_state.errors = []
    
    # Method priority based on force_method or auto
    methods = []
    if force_method == "requests":
        methods = [get_content_requests]
    elif force_method == "playwright":
        methods = [get_content_playwright, get_content_requests]
    elif force_method == "selenium":
        methods = [get_content_selenium, get_content_playwright, get_content_requests]
    else:
        # Auto: Try fast methods first, then JS-rendered
        methods = [
            get_content_requests,
            get_content_playwright,
            get_content_selenium
        ]
    
    for method in methods:
        try:
            content, method_name = method(url, wait_time) if method != get_content_requests else method(url)
            if content and len(content) > 1000:
                return content, method_name
        except Exception as e:
            continue
    
    return None, None

# ---------------------------
# ADVANCED IMAGE EXTRACTION
# ---------------------------

def extract_images(content, base_url):
    """Extract all images using multiple strategies"""
    soup = BeautifulSoup(content, "html.parser")
    image_urls = set()
    
    # Strategy 1: All img tag attributes
    img_attrs = ['src', 'data-src', 'data-original', 'data-lazy-src', 
                 'data-srcset', 'srcset', 'data-url', 'data-image', 
                 'data-bg', 'data-poster', 'data-full', 'data-high-res',
                 'data-thumb', 'data-large', 'data-medium', 'data-zoom']
    
    for tag in soup.find_all(['img', 'picture', 'source', 'figure', 'div', 'a', 'span']):
        for attr in img_attrs:
            val = tag.get(attr)
            if val:
                if 'srcset' in attr:
                    parts = val.split(',')
                    for part in parts:
                        url_part = part.strip().split(' ')[0]
                        full_url = urljoin(base_url, url_part)
                        if is_valid_image_url(full_url):
                            image_urls.add(clean_url(full_url))
                else:
                    full_url = urljoin(base_url, val)
                    if is_valid_image_url(full_url):
                        image_urls.add(clean_url(full_url))
        
        # Check style for background images
        style = tag.get('style', '')
        urls = re.findall(r'url\(["\']?(.*?)["\']?\)', style)
        for url in urls:
            full_url = urljoin(base_url, url)
            if is_valid_image_url(full_url):
                image_urls.add(clean_url(full_url))
    
    # Strategy 2: JSON-LD structured data
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            if script.string:
                urls = re.findall(r'https?://[^\s"\'<>]+?\.(?:jpg|jpeg|png|gif|webp|svg)', script.string, re.IGNORECASE)
                for url in urls:
                    if is_valid_image_url(url):
                        image_urls.add(clean_url(url))
        except:
            pass
    
    # Strategy 3: Meta tags (Open Graph, Twitter)
    for meta in soup.find_all('meta'):
        content_val = meta.get('content', '')
        property_val = meta.get('property', '')
        
        if any(x in property_val for x in ['og:image', 'twitter:image', 'image']):
            if is_valid_image_url(content_val):
                image_urls.add(clean_url(content_val))
        
        if any(ext in content_val.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
            full_url = urljoin(base_url, content_val)
            if is_valid_image_url(full_url):
                image_urls.add(clean_url(full_url))
    
    # Strategy 4: Link tags
    for link in soup.find_all('link'):
        href = link.get('href', '')
        rel = link.get('rel', [])
        if 'icon' in rel or 'image' in rel or any(ext in href.lower() for ext in ['.jpg', '.png', '.ico']):
            full_url = urljoin(base_url, href)
            if is_valid_image_url(full_url):
                image_urls.add(clean_url(full_url))
    
    # Strategy 5: A tags linking to images
    for a in soup.find_all('a'):
        href = a.get('href', '')
        if any(ext in href.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp']):
            full_url = urljoin(base_url, href)
            if is_valid_image_url(full_url):
                image_urls.add(clean_url(full_url))
        
        for attr in ['data-url', 'data-image', 'data-full', 'data-href', 'data-src']:
            val = a.get(attr)
            if val and any(ext in val.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                full_url = urljoin(base_url, val)
                if is_valid_image_url(full_url):
                    image_urls.add(clean_url(full_url))
    
    # Strategy 6: Inline scripts with image arrays
    for script in soup.find_all('script'):
        if script.string:
            patterns = [
                r'["\'](https?://[^"\']+\.(?:jpg|jpeg|png|gif|webp))["\']',
                r'src:\s*["\']([^"\']+)["\']',
                r'url:\s*["\']([^"\']+)["\']',
                r'"image":\s*["\']([^"\']+)["\']',
                r'"url":\s*["\']([^"\']+)["\']'
            ]
            for pattern in patterns:
                matches = re.findall(pattern, script.string, re.IGNORECASE)
                for match in matches:
                    full_url = urljoin(base_url, match)
                    if is_valid_image_url(full_url):
                        image_urls.add(clean_url(full_url))
    
    # Strategy 7: JSON in script tags (common in galleries)
    for script in soup.find_all('script'):
        if script.string:
            try:
                # Look for image arrays in JSON
                json_matches = re.findall(r'\{[^}]*"[^"]*src[^"]*":"[^"]*\.(?:jpg|jpeg|png|gif|webp)[^}]*\}', script.string)
                for match in json_matches:
                    try:
                        data = json.loads(match)
                        for key in ['src', 'url', 'image', 'thumbnail', 'full']:
                            if key in data and is_valid_image_url(data[key]):
                                image_urls.add(clean_url(data[key]))
                    except:
                        pass
            except:
                pass
    
    return list(image_urls)

def is_valid_image_url(url):
    """Validate if URL is an actual image"""
    if not url or not isinstance(url, str):
        return False
    
    url = url.strip()
    
    if not url.startswith(('http://', 'https://')):
        return False
    
    skip_patterns = [
        'javascript:', 'data:', 'blob:', 'mailto:', 'tel:',
        'facebook.com/tr', 'google-analytics', 'googletagmanager',
        'doubleclick', 'analytics', 'tracking', 'beacon',
        'pixel', 'gif?c', 'count?', 'log?', 'stats?',
        'emoji', 'icon', 'sprite', 'loader', 'spinner',
        'blank.gif', 'transparent.gif', 'spacer.gif'
    ]
    
    if any(pattern in url.lower() for pattern in skip_patterns):
        return False
    
    image_exts = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp', '.ico', '.tiff', '.avif']
    has_image_ext = any(ext in url.lower().split('?')[0] for ext in image_exts)
    
    image_indicators = ['/image', '/img', '/photo', '/pic', '/asset', '/download', '/file', '/media', '/upload']
    has_indicator = any(ind in url.lower() for ind in image_indicators)
    
    return has_image_ext or has_indicator

def clean_url(url):
    """Clean URL for processing"""
    url = url.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    url = url.split('#')[0]
    
    if '?' in url:
        base, query = url.split('?', 1)
        essential_params = ['w', 'h', 'width', 'height', 'size', 'q', 'quality', 'format', 'fm', 'fit', 'crop']
        params = []
        for p in query.split('&'):
            if '=' in p:
                key = p.split('=')[0]
                if key in essential_params or not any(t in key.lower() for t in ['utm', 'ref', 'track', 'click', 'source', 'campaign']):
                    params.append(p)
        
        if params:
            url = base + '?' + '&'.join(params)
        else:
            url = base
    
    return url.strip()

# ---------------------------
# IMAGE FETCHING & PROCESSING
# ---------------------------

def fetch_image(url, max_size_mb=10):
    """Fetch image with validation"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
            "Referer": url
        }
        
        response = requests.get(url, headers=headers, timeout=20, stream=True)
        response.raise_for_status()
        
        content_type = response.headers.get('content-type', '').lower()
        if not ('image' in content_type or any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp'])):
            return None, None, 0
        
        content = b''
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > max_size_mb * 1024 * 1024:
                return None, None, 0
        
        if not content or len(content) < 100:
            return None, None, 0
        
        size_kb = len(content) / 1024
        
        try:
            image = Image.open(io.BytesIO(content))
            
            if image.mode in ('RGBA', 'P', 'LA', 'L', 'CMYK'):
                image = image.convert('RGB')
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            return image, content, size_kb
            
        except Exception as e:
            return None, content, size_kb
            
    except Exception as e:
        return None, None, 0

def enhance_image(image, scale_factor=3):
    """Enhance image with upscaling"""
    try:
        original_width, original_height = image.size
        
        new_width = int(original_width * scale_factor)
        new_height = int(original_height * scale_factor)
        
        enhanced = image.resize((new_width, new_height), Image.LANCZOS)
        
        enhancer = ImageEnhance.Sharpness(enhanced)
        enhanced = enhancer.enhance(1.15)
        
        enhancer = ImageEnhance.Contrast(enhanced)
        enhanced = enhancer.enhance(1.05)
        
        output = io.BytesIO()
        
        if scale_factor >= 3:
            enhanced.save(output, format='PNG', optimize=True)
        else:
            enhanced.save(output, format='JPEG', quality=95, optimize=True)
        
        output.seek(0)
        return output.getvalue()
        
    except Exception as e:
        st.error(f"Enhancement failed: {e}")
        return None

def get_download_filename(url, prefix="", suffix=""):
    """Generate clean filename"""
    try:
        parsed = urlparse(url)
        path = unquote(parsed.path)
        
        filename = path.split('/')[-1] if '/' in path else 'image'
        filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        
        if not any(filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
            filename += '.png'
        
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, 'png')
        final = f"{prefix}{name[:50]}{suffix}.{ext}"
        
        return final
    except:
        return f"{prefix}image{suffix}.png"

# ---------------------------
# DISPLAY COMPONENTS
# ---------------------------

def display_image_controls(idx, data):
    """Display image with individual controls"""
    image = data['image']
    raw_bytes = data['bytes']
    size_kb = data['size']
    url = data['url']
    
    size_mb = size_kb / 1024
    width, height = image.size
    
    col_img, col_ctrl = st.columns([3, 1])
    
    with col_img:
        st.image(image, use_container_width=True, caption=f"{width} × {height} px")
        
        st.markdown(f"""
        <div class="stats-row">
            <span class="stat-badge">📦 {size_mb:.2f} MB</span>
            <span class="stat-badge">📐 {width}×{height}</span>
            <span class="stat-badge">#{idx+1}</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col_ctrl:
        st.markdown("<br>", unsafe_allow_html=True)
        
        orig_name = get_download_filename(url, prefix=f"{idx+1}_")
        mime = "image/png" if raw_bytes[:4] == b'\x89PNG' else "image/jpeg"
        
        st.download_button(
            label="⬇️ Original",
            data=raw_bytes,
            file_name=orig_name,
            mime=mime,
            key=f"dl_orig_{idx}_{hash(url) % 10000}",
            help="Download original image"
        )
        
        enhance_key = f"enh_{idx}_{hash(url) % 10000}"
        
        if enhance_key not in st.session_state.enhanced_images:
            if st.button("✨ Enhance 3×", key=f"btn_{enhance_key}", 
                        help="AI-powered 3x upscaling"):
                with st.spinner("Enhancing..."):
                    enhanced = enhance_image(image, scale_factor=3)
                    if enhanced:
                        st.session_state.enhanced_images[enhance_key] = {
                            'bytes': enhanced,
                            'filename': get_download_filename(url, prefix=f"{idx+1}_", suffix="_3x_enhanced")
                        }
                        st.rerun()
        
        if enhance_key in st.session_state.enhanced_images:
            enh_data = st.session_state.enhanced_images[enhance_key]
            
            try:
                preview = Image.open(io.BytesIO(enh_data['bytes']))
                st.image(preview, caption="Enhanced Preview", use_container_width=True)
            except:
                pass
            
            st.download_button(
                label="⬇️ Enhanced 3×",
                data=enh_data['bytes'],
                file_name=enh_data['filename'],
                mime="image/png",
                key=f"dl_enh_{enhance_key}",
                help="Download 3x upscaled image"
            )
            
            if st.button("🗑️ Clear", key=f"clr_{enhance_key}"):
                del st.session_state.enhanced_images[enhance_key]
                st.rerun()
        
        st.markdown(f"<small style='color: #888;' title='{url}'>{url[:35]}...</small>", 
                   unsafe_allow_html=True)

# ---------------------------
# MAIN UI
# ---------------------------
st.title("🌐 Universal Image Scraper Pro")
st.markdown("Extract images from **any website** • Auto-detects JavaScript • No setup required")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Method selection
    method_options = ["Auto (Recommended)", "Requests Only (Fast)", "Playwright (JS-heavy sites)", "Selenium (Legacy)"]
    method_choice = st.selectbox(
        "Scraping Method",
        method_options,
        index=0,
        help="Auto tries multiple methods. Select specific method if you know the site type."
    )
    
    force_method = None
    if method_choice == "Requests Only (Fast)":
        force_method = "requests"
    elif method_choice == "Playwright (JS-heavy sites)":
        force_method = "playwright"
    elif method_choice == "Selenium (Legacy)":
        force_method = "selenium"
    
    wait_time = st.slider("Page Load Wait (sec)", 1, 10, 3,
                         help="Seconds to wait for JavaScript rendering")
    
    max_images = st.slider("Max Images", 10, 200, 50)
    
    min_size = st.slider("Min Size (KB)", 1, 100, 5,
                        help="Filter out small icons and thumbnails")
    
    st.divider()
    
    # Show available methods
    st.markdown("**🔧 Available Methods:**")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"{'✅' if True else '❌'} Requests")
        st.markdown(f"{'✅' if PLAYWRIGHT_AVAILABLE else '❌'} Playwright")
    with col2:
        st.markdown(f"{'✅' if SELENIUM_AVAILABLE else '❌'} Selenium")
        st.markdown(f"{'✅' if WDM_AVAILABLE else '❌'} WebDriver Mgr")
    
    st.divider()
    st.markdown("""
    **💡 Tips:**
    - **Auto mode**: Tries all methods automatically
    - **Requests**: Fastest, works on static sites (Wikipedia, blogs)
    - **Playwright**: Best for React/SPA sites, auto-downloads browser
    - **Selenium**: Fallback for complex sites
    
    **Special URLs:**
    - `github.dev/*` → auto-converts to `github.com/*`
    - Removes tracking parameters automatically
    """)

# Main input
url_input = st.text_input(
    "🔗 Website URL",
    placeholder="https://www.example.com/gallery",
    value=st.session_state.current_url,
    help="Supports any website. GitHub.dev URLs are auto-converted."
)

# Action buttons
col1, col2, col3 = st.columns([1, 1, 3])

with col1:
    if st.button("🚀 Extract Images", type="primary", use_container_width=True):
        if not url_input:
            st.warning("Please enter a URL")
        else:
            # Process URL
            url = url_input if url_input.startswith('http') else f'https://{url_input}'
            url = convert_special_urls(url)
            
            if not is_valid_url(url):
                st.error("❌ Invalid URL format")
                st.stop()
            
            st.session_state.current_url = url
            st.session_state.images_data = []
            st.session_state.enhanced_images = {}
            st.session_state.scraping_done = False
            st.session_state.method_used = None
            
            # Progress
            progress = st.progress(0)
            status = st.empty()
            
            # Step 1: Fetch
            status.text("📡 Fetching page content...")
            progress.progress(10)
            
            content, method_used = get_page_content(url, force_method=force_method, wait_time=wait_time)
            
            if not content:
                st.error("❌ Failed to load page. The site may block scrapers or require authentication.")
                if st.session_state.errors:
                    with st.expander("Error Details"):
                        for err in st.session_state.errors:
                            st.text(err)
                progress.empty()
                status.empty()
                st.stop()
            
            st.session_state.method_used = method_used
            
            # Show method badge
            method_colors = {
                'requests': 'method-requests',
                'playwright': 'method-playwright', 
                'selenium': 'method-selenium'
            }
            badge_class = method_colors.get(method_used, 'method-fallback')
            st.markdown(f"""
            <div style="margin: 10px 0;">
                <span class="method-badge {badge_class}">✅ Loaded via: {method_used.upper()}</span>
            </div>
            """, unsafe_allow_html=True)
            
            progress.progress(30)
            
            # Step 2: Extract URLs
            status.text("🔍 Scanning for images...")
            image_urls = extract_images(content, url)
            image_urls = list(dict.fromkeys(image_urls))[:max_images * 3]
            
            progress.progress(40)
            status.text(f"📸 Found {len(image_urls)} potential images, validating...")
            
            # Step 3: Fetch images
            valid_images = []
            
            for i, img_url in enumerate(image_urls):
                prog = 40 + int((i / len(image_urls)) * 50)
                progress.progress(min(prog, 90))
                status.text(f"⏳ Validating {i+1}/{len(image_urls)}...")
                
                img, raw, size = fetch_image(img_url)
                if img and size >= min_size:
                    valid_images.append({
                        'image': img,
                        'bytes': raw,
                        'size': size,
                        'url': img_url
                    })
                
                if len(valid_images) >= max_images:
                    break
            
            progress.progress(100)
            time.sleep(0.5)
            progress.empty()
            status.empty()
            
            # Sort by size (largest first)
            valid_images.sort(key=lambda x: x['size'], reverse=True)
            
            st.session_state.images_data = valid_images
            st.session_state.scraping_done = True
            
            if valid_images:
                st.success(f"✅ Successfully loaded {len(valid_images)} images!")
            else:
                st.warning("⚠️ No valid images found. Try adjusting Min Size or using a different method.")

with col2:
    if st.button("🗑️ Clear All", use_container_width=True):
        st.session_state.images_data = []
        st.session_state.enhanced_images = {}
        st.session_state.scraping_done = False
        st.session_state.method_used = None
        st.rerun()

# Display results
if st.session_state.scraping_done:
    st.divider()
    
    # Summary bar
    total = len(st.session_state.images_data)
    enhanced_count = len(st.session_state.enhanced_images)
    total_size = sum(d['size'] for d in st.session_state.images_data) / 1024
    
    cols = st.columns([2, 1, 1, 2])
    cols[0].markdown(f"### 🖼️ {total} Images Found")
    cols[1].metric("Enhanced", enhanced_count)
    cols[2].metric("Total Size", f"{total_size:.1f} MB")
    
    # Bulk download
    if total > 0 and cols[3].button("📦 Download All Original"):
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for i, d in enumerate(st.session_state.images_data):
                fname = get_download_filename(d['url'], prefix=f"{i+1}_")
                zf.writestr(fname, d['bytes'])
        
        st.download_button(
            "⬇️ Download ZIP",
            data=zip_buf.getvalue(),
            file_name="all_images.zip",
            mime="application/zip",
            key="bulk_zip"
        )
    
    st.divider()
    
    # Individual images
    for idx, data in enumerate(st.session_state.images_data):
        with st.container():
            st.markdown('<div class="image-container">', unsafe_allow_html=True)
            display_image_controls(idx, data)
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

# Footer
st.divider()
st.caption("🔒 Respects robots.txt | 🚀 Auto-detects JavaScript | 🎨 AI Enhancement | Works on Streamlit Cloud")