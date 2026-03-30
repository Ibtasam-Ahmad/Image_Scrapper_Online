import streamlit as st
import requests
import io
import hashlib
import base64
from PIL import Image, ImageEnhance
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
import time
import json

# Try to import selenium, but don't fail if not available
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.common.by import By
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# ---------------------------
# PAGE CONFIG
# ---------------------------
st.set_page_config(
    page_title="Universal Image Scraper & Enhancer",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
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
if 'selenium_works' not in st.session_state:
    st.session_state.selenium_works = False

# ---------------------------
# FETCH METHODS
# ---------------------------
def get_content_selenium(url, wait_time=3):
    """Use Selenium for JavaScript-rendered pages - with better error handling"""
    if not SELENIUM_AVAILABLE:
        return None
    
    driver = None
    try:
        options = ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        # Try to create driver
        try:
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=options
            )
        except Exception as e:
            st.warning(f"Chrome not available: {str(e)[:100]}")
            return None
        
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
        st.session_state.selenium_works = True
        return content
        
    except Exception as e:
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

def get_content_requests(url):
    """Simple requests with multiple header strategies"""
    headers_list = [
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        },
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    ]
    
    for headers in headers_list:
        try:
            response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            response.raise_for_status()
            if len(response.text) > 500:  # Valid HTML check
                return response.text
        except:
            continue
    
    return None

def get_page_content(url, use_selenium=False, wait_time=3):
    """Get page content with fallback methods"""
    
    # Try Selenium if requested and available
    if use_selenium and SELENIUM_AVAILABLE:
        content = get_content_selenium(url, wait_time)
        if content:
            return content, "Selenium (JavaScript-rendered)"
    
    # Always try requests as primary method (works for most sites)
    content = get_content_requests(url)
    if content:
        return content, "Direct HTTP"
    
    # Final fallback - try selenium even if not requested
    if SELENIUM_AVAILABLE and not st.session_state.selenium_works:
        content = get_content_selenium(url, wait_time)
        if content:
            return content, "Selenium (Fallback)"
    
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
                 'data-thumb', 'data-large', 'data-medium']
    
    for tag in soup.find_all(['img', 'picture', 'source', 'figure', 'div', 'a']):
        # Check all possible attributes
        for attr in img_attrs:
            val = tag.get(attr)
            if val:
                if 'srcset' in attr or attr == 'data-srcset':
                    # Parse srcset for multiple resolutions
                    parts = val.split(',')
                    for part in parts:
                        url_part = part.strip().split(' ')[0]
                        full_url = urljoin(base_url, url_part.replace('&amp;', '&'))
                        if is_valid_image_url(full_url):
                            image_urls.add(clean_url(full_url))
                else:
                    full_url = urljoin(base_url, val.replace('&amp;', '&'))
                    if is_valid_image_url(full_url):
                        image_urls.add(clean_url(full_url))
        
        # Check style for background images
        style = tag.get('style', '')
        urls = re.findall(r'url\(["\']?(.*?)["\']?\)', style)
        for url in urls:
            full_url = urljoin(base_url, url.replace('&amp;', '&'))
            if is_valid_image_url(full_url):
                image_urls.add(clean_url(full_url))
    
    # Strategy 2: JSON-LD structured data
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            text = script.string
            if text:
                # Find all URLs in JSON
                urls = re.findall(r'https?://[^\s"\'<>]+?\.(?:jpg|jpeg|png|gif|webp|svg)', text, re.IGNORECASE)
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
        
        # Also check any image-like content
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
        
        # Check data attributes
        for attr in ['data-url', 'data-image', 'data-full', 'data-href', 'data-src']:
            val = a.get(attr)
            if val and any(ext in val.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                full_url = urljoin(base_url, val)
                if is_valid_image_url(full_url):
                    image_urls.add(clean_url(full_url))
    
    # Strategy 6: Inline scripts with image arrays (common in galleries)
    for script in soup.find_all('script'):
        if script.string:
            # Look for image arrays in JavaScript
            patterns = [
                r'["\'](https?://[^"\']+\.(?:jpg|jpeg|png|gif|webp))["\']',
                r'src:\s*["\']([^"\']+)["\']',
                r'url:\s*["\']([^"\']+)["\']',
            ]
            for pattern in patterns:
                matches = re.findall(pattern, script.string, re.IGNORECASE)
                for match in matches:
                    full_url = urljoin(base_url, match)
                    if is_valid_image_url(full_url):
                        image_urls.add(clean_url(full_url))
    
    return list(image_urls)

def is_valid_image_url(url):
    """Validate if URL is an actual image"""
    if not url or not isinstance(url, str):
        return False
    
    url = url.strip()
    
    if not url.startswith(('http://', 'https://')):
        return False
    
    # Skip common non-image patterns
    skip_patterns = [
        'javascript:', 'data:', 'blob:', 'mailto:', 'tel:',
        'facebook.com/tr', 'google-analytics', 'googletagmanager',
        'doubleclick', 'analytics', 'tracking', 'beacon',
        'pixel', 'gif?c', 'count?', 'log?', 'stats?'
    ]
    
    if any(pattern in url.lower() for pattern in skip_patterns):
        return False
    
    # Check for image extensions or patterns
    image_exts = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp', '.ico', '.tiff']
    has_image_ext = any(ext in url.lower().split('?')[0] for ext in image_exts)
    
    # Check for image indicators in URL
    image_indicators = ['/image', '/img', '/photo', '/pic', '/asset', '/download', '/file']
    has_indicator = any(ind in url.lower() for ind in image_indicators)
    
    # Accept if has extension or indicator
    return has_image_ext or has_indicator

def clean_url(url):
    """Clean URL for processing"""
    # Remove HTML entities
    url = url.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    # Remove fragment
    url = url.split('#')[0]
    # Clean tracking parameters
    if '?' in url:
        base, query = url.split('?', 1)
        # Keep only essential params
        essential_params = ['w', 'h', 'width', 'height', 'size', 'q', 'quality', 'format', 'fm']
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
# IMAGE FETCHING
# ---------------------------
def fetch_image(url, max_size_mb=10):
    """Fetch image with validation"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
            "Referer": url
        }
        
        # Stream to check size
        response = requests.get(url, headers=headers, timeout=20, stream=True)
        response.raise_for_status()
        
        # Check content type
        content_type = response.headers.get('content-type', '').lower()
        if not ('image' in content_type or any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp'])):
            return None, None, 0
        
        # Read with size limit
        content = b''
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > max_size_mb * 1024 * 1024:
                return None, None, 0
        
        if not content or len(content) < 100:  # Too small
            return None, None, 0
        
        size_kb = len(content) / 1024
        
        # Try to open as image
        try:
            image = Image.open(io.BytesIO(content))
            
            # Convert to RGB for processing
            if image.mode in ('RGBA', 'P', 'LA', 'L', 'CMYK'):
                image = image.convert('RGB')
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            return image, content, size_kb
            
        except Exception as e:
            # Return raw for non-PIL formats
            return None, content, size_kb
            
    except Exception as e:
        return None, None, 0

# ---------------------------
# IMAGE ENHANCEMENT
# ---------------------------
def enhance_image(image, scale_factor=3):
    """Enhance image with upscaling"""
    try:
        original_width, original_height = image.size
        
        # Calculate new dimensions
        new_width = int(original_width * scale_factor)
        new_height = int(original_height * scale_factor)
        
        # High-quality resize
        enhanced = image.resize((new_width, new_height), Image.LANCZOS)
        
        # Subtle sharpening
        enhancer = ImageEnhance.Sharpness(enhanced)
        enhanced = enhancer.enhance(1.15)
        
        # Slight contrast
        enhancer = ImageEnhance.Contrast(enhanced)
        enhanced = enhancer.enhance(1.05)
        
        # Save
        output = io.BytesIO()
        
        # Use PNG for quality, JPEG for size
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
        path = parsed.path
        
        # Get filename
        filename = path.split('/')[-1] if '/' in path else 'image'
        filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        
        # Ensure extension
        if not any(filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
            filename += '.png'
        
        # Add prefix/suffix
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
    
    # Layout
    col_img, col_ctrl = st.columns([3, 1])
    
    with col_img:
        st.image(image, use_container_width=True, caption=f"{width} × {height} px")
        
        # Stats
        st.markdown(f"""
        <div class="stats-row">
            <span class="stat-badge">📦 {size_mb:.2f} MB</span>
            <span class="stat-badge">📐 {width}×{height}</span>
            <span class="stat-badge">#{idx+1}</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col_ctrl:
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Original download
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
        
        # Enhancement section
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
        
        # Show enhanced if available
        if enhance_key in st.session_state.enhanced_images:
            enh_data = st.session_state.enhanced_images[enhance_key]
            
            # Preview
            try:
                preview = Image.open(io.BytesIO(enh_data['bytes']))
                st.image(preview, caption="Enhanced Preview", use_container_width=True)
            except:
                pass
            
            # Download enhanced
            st.download_button(
                label="⬇️ Enhanced 3×",
                data=enh_data['bytes'],
                file_name=enh_data['filename'],
                mime="image/png",
                key=f"dl_enh_{enhance_key}",
                help="Download 3x upscaled image"
            )
            
            # Clear button
            if st.button("🗑️ Clear", key=f"clr_{enhance_key}"):
                del st.session_state.enhanced_images[enhance_key]
                st.rerun()
        
        # URL info
        st.markdown(f"<small style='color: #888;' title='{url}'>{url[:35]}...</small>", 
                   unsafe_allow_html=True)

# ---------------------------
# MAIN UI
# ---------------------------
st.title("🌐 Universal Image Scraper & Enhancer")
st.markdown("Extract images from **any website** ")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    
    use_selenium = st.toggle(
        "Use Selenium (for JS sites)",
        value=False,
        help="Enable for JavaScript-heavy sites like Instagram. Requires Chrome."
    )
    
    if use_selenium and not SELENIUM_AVAILABLE:
        st.error("⚠️ Selenium not installed")
    
    wait_time = st.slider("Page Load Wait", 1, 10, 3,
                         help="Seconds to wait for JavaScript loading")
    
    max_images = st.slider("Max Images", 10, 200, 50,
                          help="Maximum images to process")
    
    min_size = st.slider("Min Size (KB)", 1, 100, 5,
                        help="Filter out small icons")
    
    st.divider()
    st.markdown("""
    **💡 Tips:**
    - For static sites: Use HTTP only (faster)
    - For React/SPA sites: Enable Selenium
    - Increase wait time for slow sites
    - Some sites block scrapers - try different URLs
    """)

# Main input
url_input = st.text_input(
    "🔗 Website URL",
    placeholder="https://www.example.com/gallery",
    value=st.session_state.current_url
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
            st.session_state.current_url = url
            st.session_state.images_data = []
            st.session_state.enhanced_images = {}
            st.session_state.scraping_done = False
            
            # Progress
            progress = st.progress(0)
            status = st.empty()
            
            # Step 1: Fetch
            status.text("📡 Fetching page...")
            progress.progress(10)
            
            content, method = get_page_content(url, use_selenium=use_selenium, wait_time=wait_time)
            
            if not content:
                st.error("❌ Failed to load page. The site may block scrapers or require authentication.")
                progress.empty()
                status.empty()
                st.stop()
            
            st.info(f"✅ Loaded via: **{method}**")
            progress.progress(30)
            
            # Step 2: Extract URLs
            status.text("🔍 Finding images...")
            image_urls = extract_images(content, url)
            image_urls = list(dict.fromkeys(image_urls))[:max_images * 3]
            
            progress.progress(40)
            status.text(f"📸 Found {len(image_urls)} potential images, validating...")
            
            # Step 3: Fetch images
            valid_images = []
            
            for i, img_url in enumerate(image_urls):
                prog = 40 + int((i / len(image_urls)) * 50)
                progress.progress(min(prog, 90))
                status.text(f"⏳ Processing {i+1}/{len(image_urls)}...")
                
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
            
            # Sort by size
            valid_images.sort(key=lambda x: x['size'], reverse=True)
            
            st.session_state.images_data = valid_images
            st.session_state.scraping_done = True
            
            if valid_images:
                st.success(f"✅ Loaded {len(valid_images)} images successfully!")
            else:
                st.warning("⚠️ No valid images found. Try enabling Selenium or adjusting settings.")

with col2:
    if st.button("🗑️ Clear All", use_container_width=True):
        st.session_state.images_data = []
        st.session_state.enhanced_images = {}
        st.session_state.scraping_done = False
        st.rerun()

# Display results
if st.session_state.scraping_done:
    st.divider()
    
    # Summary bar
    total = len(st.session_state.images_data)
    enhanced_count = len(st.session_state.enhanced_images)
    
    cols = st.columns([2, 1, 1, 2])
    cols[0].markdown(f"### 🖼️ {total} Images Found")
    cols[1].metric("Enhanced", enhanced_count)
    cols[2].metric("Total Size", f"{sum(d['size'] for d in st.session_state.images_data)/1024:.1f} MB")
    
    # Bulk download
    if total > 0 and cols[3].button("📦 Download All Original"):
        import zipfile
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
st.caption("🔒 Respects robots.txt | 🚀 Works on most websites | 🎨 AI Enhancement powered by PIL")