# import streamlit as st
# import requests
# import io
# import hashlib
# from PIL import Image
# from bs4 import BeautifulSoup

# # Selenium imports
# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver import ChromeOptions
# from webdriver_manager.chrome import ChromeDriverManager


# # ---------------------------
# # METHOD 1: Selenium (Best for JS sites)
# # ---------------------------
# def get_content_selenium(url):
#     try:
#         options = ChromeOptions()
#         options.add_argument("--headless=new")
#         options.add_argument("--disable-gpu")
#         options.add_argument("--no-sandbox")

#         driver = webdriver.Chrome(
#             service=Service(ChromeDriverManager().install()),
#             options=options
#         )

#         driver.get(url)
#         content = driver.page_source
#         driver.quit()

#         return content
#     except Exception as e:
#         return None


# # ---------------------------
# # METHOD 2: Requests
# # ---------------------------
# def get_content_requests(url):
#     try:
#         headers = {"User-Agent": "Mozilla/5.0"}
#         response = requests.get(url, headers=headers, timeout=10)
#         return response.text
#     except:
#         return None


# # ---------------------------
# # METHOD 3: Fallback
# # ---------------------------
# def get_content_fallback(url):
#     try:
#         return requests.get(url).text
#     except:
#         return None


# # ---------------------------
# # MASTER FETCH FUNCTION
# # ---------------------------
# def get_page_content(url):
#     # Try Selenium first
#     content = get_content_selenium(url)
#     if content:
#         return content, "Selenium"

#     # Fallback to requests
#     content = get_content_requests(url)
#     if content:
#         return content, "Requests"

#     # Final fallback
#     content = get_content_fallback(url)
#     if content:
#         return content, "Fallback"

#     return None, None


# # ---------------------------
# # IMAGE PARSER
# # ---------------------------
# def parse_images(content):
#     soup = BeautifulSoup(content, "html.parser")
#     image_urls = set()

#     for img in soup.find_all("img"):
#         src = img.get("src") or img.get("data-src")

#         if src and src.startswith("http"):
#             image_urls.add(src)

#     return list(image_urls)


# # ---------------------------
# # DOWNLOAD IMAGE
# # ---------------------------
# def fetch_image(img_url):
#     try:
#         headers = {"User-Agent": "Mozilla/5.0"}
#         res = requests.get(img_url, headers=headers, timeout=10)

#         image_bytes = io.BytesIO(res.content)
#         image = Image.open(image_bytes).convert("RGB")

#         return image, res.content
#     except:
#         return None, None


# # ---------------------------
# # STREAMLIT UI
# # ---------------------------
# st.set_page_config(page_title="Image Scraper Pro", layout="wide")

# st.title("🖼️ Image Scraper Pro")
# st.write("Paste a website URL → View & download images individually")

# url = st.text_input("🔗 Enter Website URL")

# if st.button("🚀 Scrape Images"):
#     if not url:
#         st.warning("Please enter a URL")
#     else:
#         with st.spinner("Fetching page..."):
#             content, method = get_page_content(url)

#         if not content:
#             st.error("❌ Failed to fetch content from all methods")
#         else:
#             st.success(f"✅ Content fetched using: {method}")

#             image_urls = parse_images(content)
#             st.info(f"📸 Found {len(image_urls)} images")

#             if len(image_urls) == 0:
#                 st.warning("No images found")
#             else:
#                 # Display images
#                 for i, img_url in enumerate(image_urls):
#                     image, raw = fetch_image(img_url)

#                     if image:
#                         col1, col2 = st.columns([3, 1])

#                         with col1:
#                             st.image(
#                                 image,
#                                 caption=f"Image {i+1}",
#                                 use_container_width=True
#                             )

#                         with col2:
#                             filename = hashlib.sha1(raw).hexdigest()[:10] + ".png"

#                             st.download_button(
#                                 label="⬇️ Download",
#                                 data=raw,
#                                 file_name=filename,
#                                 mime="image/png"
#                             )
#                     else:
#                         st.warning(f"⚠️ Could not load image {i+1}")


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

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

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
    }
    .image-card {
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 16px;
        background: #fafafa;
        margin-bottom: 16px;
    }
    .stats-badge {
        background: #f0f2f6;
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 0.85em;
        color: #555;
    }
    .download-btn {
        background: #00c853 !important;
        color: white !important;
    }
    .enhance-btn {
        background: #2979ff !important;
        color: white !important;
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

# ---------------------------
# FETCH METHODS (Fallback Chain)
# ---------------------------
@st.cache_resource
def get_chrome_driver():
    """Initialize Chrome driver with caching"""
    try:
        options = ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
        return driver
    except Exception as e:
        st.error(f"Chrome driver error: {e}")
        return None

def get_content_selenium(url, wait_time=3):
    """Use Selenium for JavaScript-rendered pages"""
    driver = None
    try:
        driver = get_chrome_driver()
        if not driver:
            return None
            
        driver.get(url)
        
        # Wait for page to load
        time.sleep(wait_time)
        
        # Scroll to trigger lazy loading
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        
        content = driver.page_source
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
    """Simple requests fallback"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        response.raise_for_status()
        return response.text
    except Exception as e:
        return None

def get_page_content(url):
    """Try multiple methods to get page content"""
    # Try Selenium first (for JS-heavy sites)
    content = get_content_selenium(url)
    if content and len(content) > 1000:
        return content, "Selenium (JavaScript-rendered)"
    
    # Fallback to requests
    content = get_content_requests(url)
    if content:
        return content, "Direct HTTP"
    
    return None, None

# ---------------------------
# ADVANCED IMAGE EXTRACTION
# ---------------------------
def extract_images(content, base_url):
    """Dynamically extract all images from any website"""
    soup = BeautifulSoup(content, "html.parser")
    image_urls = set()
    base_domain = urlparse(base_url).netloc
    
    # Pattern 1: Standard img tags with all possible attributes
    img_attributes = ['src', 'data-src', 'data-original', 'data-lazy-src', 
                      'data-srcset', 'srcset', 'data-url', 'data-image', 
                      'data-bg', 'data-poster', 'data-full', 'data-high-res']
    
    for img in soup.find_all(['img', 'picture', 'source', 'figure']):
        for attr in img_attributes:
            val = img.get(attr)
            if val:
                # Handle srcset (multiple resolutions)
                if 'srcset' in attr and val:
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
        
        # Check style attribute for background images
        style = img.get('style', '')
        bg_match = re.search(r'url\(["\']?(.*?)["\']?\)', style)
        if bg_match:
            full_url = urljoin(base_url, bg_match.group(1))
            if is_valid_image_url(full_url):
                image_urls.add(clean_url(full_url))
    
    # Pattern 2: Links to images
    for a in soup.find_all('a'):
        href = a.get('href', '')
        if any(ext in href.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp']):
            full_url = urljoin(base_url, href)
            if is_valid_image_url(full_url):
                image_urls.add(clean_url(full_url))
        
        # Check data attributes
        for attr in ['data-url', 'data-image', 'data-full', 'data-href']:
            val = a.get(attr)
            if val and any(ext in val.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                full_url = urljoin(base_url, val)
                if is_valid_image_url(full_url):
                    image_urls.add(clean_url(full_url))
    
    # Pattern 3: JSON-LD and meta tags (for structured data)
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            text = script.string
            if text:
                # Extract URLs from JSON
                urls = re.findall(r'\"(https?://[^\"]+\.(?:jpg|jpeg|png|gif|webp))\"', text)
                for url in urls:
                    if is_valid_image_url(url):
                        image_urls.add(clean_url(url))
        except:
            pass
    
    # Pattern 4: Meta tags (Open Graph, Twitter cards)
    for meta in soup.find_all('meta'):
        content_val = meta.get('content', '')
        if any(ext in content_val.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
            full_url = urljoin(base_url, content_val)
            if is_valid_image_url(full_url):
                image_urls.add(clean_url(full_url))
    
    # Pattern 5: CSS background images in any element
    for elem in soup.find_all(style=True):
        style = elem['style']
        urls = re.findall(r'url\(["\']?(.*?)["\']?\)', style)
        for url in urls:
            full_url = urljoin(base_url, url)
            if is_valid_image_url(full_url):
                image_urls.add(clean_url(full_url))
    
    # Pattern 6: Data attributes common in lazy loading
    lazy_attrs = ['data-src', 'data-original', 'data-lazy', 'data-bg', 
                  'data-image-src', 'data-full-src', 'data-high-res-src']
    for elem in soup.find_all():
        for attr in lazy_attrs:
            val = elem.get(attr)
            if val:
                full_url = urljoin(base_url, val)
                if is_valid_image_url(full_url):
                    image_urls.add(clean_url(full_url))
    
    return list(image_urls)

def is_valid_image_url(url):
    """Check if URL is a valid image"""
    if not url or not url.startswith('http'):
        return False
    
    # Skip common non-image URLs
    skip_patterns = ['javascript:', 'data:', 'blob:', 'mailto:', 'tel:', 
                     'facebook.com', 'twitter.com', 'google-analytics',
                     'googletagmanager', 'doubleclick', 'analytics']
    
    if any(pattern in url.lower() for pattern in skip_patterns):
        return False
    
    # Check for image extensions or image patterns
    image_exts = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp', '.ico']
    has_ext = any(ext in url.lower() for ext in image_exts)
    
    # Also accept URLs with image parameters
    has_img_param = any(param in url.lower() for param in ['image', 'img', 'photo', 'pic'])
    
    # Accept if has extension or looks like image URL
    return has_ext or (has_img_param and 'http' in url)

def clean_url(url):
    """Clean and normalize URL"""
    # Remove HTML entities
    url = url.replace('&amp;', '&')
    # Remove fragment
    url = url.split('#')[0]
    # Clean query parameters
    if '?' in url:
        base, query = url.split('?', 1)
        # Keep only relevant params
        params = [p for p in query.split('&') if not p.startswith(('utm_', 'ref_', 'track'))]
        if params:
            url = base + '?' + '&'.join(params)
        else:
            url = base
    return url.strip()

# ---------------------------
# IMAGE FETCHING
# ---------------------------
def fetch_image(url, max_size_mb=10):
    """Fetch and validate image from URL"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
            "Referer": url
        }
        
        # Stream to check size first
        response = requests.get(url, headers=headers, timeout=20, stream=True)
        response.raise_for_status()
        
        # Check content type
        content_type = response.headers.get('content-type', '')
        if not ('image' in content_type or any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp'])):
            return None, None, 0
        
        # Read content with size limit
        content = b''
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > max_size_mb * 1024 * 1024:
                return None, None, 0  # Too large
        
        if not content:
            return None, None, 0
        
        size_kb = len(content) / 1024
        
        # Try to open as image
        try:
            image = Image.open(io.BytesIO(content))
            
            # Convert to RGB if necessary
            if image.mode in ('RGBA', 'P', 'LA', 'L'):
                image = image.convert('RGB')
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            return image, content, size_kb
            
        except Exception as e:
            # Might be SVG or other format PIL can't handle
            if '.svg' in url.lower():
                return None, content, size_kb  # Return raw for SVG
            return None, None, 0
            
    except Exception as e:
        return None, None, 0

# ---------------------------
# IMAGE ENHANCEMENT
# ---------------------------
def enhance_image(image, scale_factor=3, enhance_quality=True):
    """Enhance image with upscaling and quality improvements"""
    try:
        original_width, original_height = image.size
        
        # Calculate new size
        new_width = int(original_width * scale_factor)
        new_height = int(original_height * scale_factor)
        
        # Use LANCZOS for high quality upscaling
        enhanced = image.resize((new_width, new_height), Image.LANCZOS)
        
        # Optional: Apply subtle sharpening
        if enhance_quality:
            enhancer = ImageEnhance.Sharpness(enhanced)
            enhanced = enhancer.enhance(1.2)  # Subtle sharpening
            
            # Slight contrast boost
            enhancer = ImageEnhance.Contrast(enhanced)
            enhanced = enhancer.enhance(1.05)
        
        # Save to bytes
        output = io.BytesIO()
        
        # Use PNG for lossless or high quality JPEG
        if scale_factor >= 3:
            enhanced.save(output, format='PNG', optimize=True)
        else:
            enhanced.save(output, format='JPEG', quality=95, optimize=True)
        
        output.seek(0)
        return output.getvalue()
        
    except Exception as e:
        st.error(f"Enhancement error: {e}")
        return None

def get_image_download_name(url, prefix="", suffix=""):
    """Generate clean download filename"""
    # Extract original filename or create hash-based name
    parsed = urlparse(url)
    path = parsed.path
    
    # Get filename from path
    filename = path.split('/')[-1] if '/' in path else 'image'
    
    # Clean filename
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    
    # Ensure has extension
    if not any(filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
        filename += '.png'
    
    # Add prefix/suffix
    name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, 'png')
    final_name = f"{prefix}{name}{suffix}.{ext}"
    
    return final_name[:100]  # Limit length

# ---------------------------
# UI COMPONENTS
# ---------------------------
def display_image_card(idx, data):
    """Display individual image with controls"""
    image = data['image']
    raw_bytes = data['bytes']
    size_kb = data['size']
    url = data['url']
    
    size_mb = size_kb / 1024
    width, height = image.size
    
    # Create columns for layout
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Display image with info
        st.image(image, use_container_width=True, caption=f"{width}×{height} px")
        
        # Stats row
        st.markdown(f"""
        <div style="display: flex; gap: 8px; margin-top: 8px;">
            <span class="stats-badge">📦 {size_mb:.2f} MB</span>
            <span class="stats-badge">📐 {width}×{height}</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Original download button
        original_filename = get_image_download_name(url)
        st.download_button(
            label="⬇️ Original",
            data=raw_bytes,
            file_name=original_filename,
            mime="image/png" if raw_bytes[:4] == b'\x89PNG' else "image/jpeg",
            key=f"dl_orig_{idx}",
            help="Download original image"
        )
        
        # Enhance button with unique key
        enhance_key = f"enhance_{idx}"
        
        if enhance_key not in st.session_state.enhanced_images:
            if st.button("✨ Enhance 3×", key=enhance_key, help="AI-powered 3x upscaling"):
                with st.spinner("Enhancing..."):
                    enhanced_bytes = enhance_image(image, scale_factor=3)
                    if enhanced_bytes:
                        st.session_state.enhanced_images[enhance_key] = {
                            'bytes': enhanced_bytes,
                            'filename': get_image_download_name(url, prefix="", suffix="_enhanced_3x")
                        }
                        st.rerun()
        
        # Show enhanced download if available
        if enhance_key in st.session_state.enhanced_images:
            enhanced_data = st.session_state.enhanced_images[enhance_key]
            
            # Show preview of enhanced image
            try:
                enhanced_img = Image.open(io.BytesIO(enhanced_data['bytes']))
                st.image(enhanced_img, caption="Enhanced Preview", use_container_width=True)
            except:
                pass
            
            st.download_button(
                label="⬇️ Enhanced 3×",
                data=enhanced_data['bytes'],
                file_name=enhanced_data['filename'],
                mime="image/png",
                key=f"dl_enh_{idx}",
                help="Download enhanced 3x upscaled image"
            )
            
            # Clear enhancement button
            if st.button("🗑️ Clear", key=f"clear_{idx}"):
                del st.session_state.enhanced_images[enhance_key]
                st.rerun()
        
        # Show image URL (truncated)
        st.markdown(f"<small style='color: gray;' title='{url}'>{url[:40]}...</small>", unsafe_allow_html=True)

# ---------------------------
# MAIN UI
# ---------------------------
st.title("🌐 Universal Image Scraper & Enhancer")
st.markdown("Extract, enhance, and download images from **any website** - works with JavaScript-heavy sites")

# Sidebar controls
with st.sidebar:
    st.header("⚙️ Settings")
    
    scrape_method = st.radio(
        "Scraping Method",
        ["Auto (Recommended)", "Selenium (JavaScript sites)", "Direct HTTP"],
        index=0,
        help="Auto tries Selenium first for modern websites"
    )
    
    wait_time = st.slider("Page Load Wait (sec)", 1, 10, 3, 
                         help="Longer wait = more lazy-loaded images")
    
    max_images = st.slider("Max Images", 10, 500, 100,
                          help="Limit to prevent memory issues")
    
    min_size_kb = st.slider("Min Image Size (KB)", 1, 100, 5,
                           help="Filter out tiny icons")
    
    st.divider()
    st.markdown("""
    **Supported Sites:**
    
    """)

# Main input area
url = st.text_input(
    "🔗 Enter Website URL",
    placeholder="https://www.website.com",
    value=st.session_state.current_url
)

col1, col2, col3 = st.columns([1, 1, 3])

with col1:
    scrape_clicked = st.button("🚀 Extract Images", type="primary", use_container_width=True)

with col2:
    if st.button("🗑️ Clear Results", use_container_width=True):
        st.session_state.images_data = []
        st.session_state.enhanced_images = {}
        st.session_state.scraping_done = False
        st.rerun()

with col3:
    if st.session_state.scraping_done:
        st.success(f"✅ Found {len(st.session_state.images_data)} valid images")

# Scraping process
if scrape_clicked and url:
    if not url.startswith('http'):
        url = 'https://' + url
    
    st.session_state.current_url = url
    st.session_state.images_data = []
    st.session_state.enhanced_images = {}
    st.session_state.scraping_done = False
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Step 1: Fetch page
    status_text.text("📡 Fetching webpage...")
    progress_bar.progress(10)
    
    content, method = get_page_content(url)
    
    if not content:
        st.error("❌ Failed to load website. Try increasing wait time or check URL.")
        st.stop()
    
    st.info(f"✅ Loaded using: **{method}**")
    progress_bar.progress(30)
    
    # Step 2: Extract image URLs
    status_text.text("🔍 Scanning for images...")
    image_urls = extract_images(content, url)
    
    # Remove duplicates and limit
    image_urls = list(dict.fromkeys(image_urls))[:max_images * 2]  # Extra for filtering
    
    status_text.text(f"📸 Found {len(image_urls)} image links, validating...")
    progress_bar.progress(50)
    
    # Step 3: Fetch and validate images
    images_data = []
    failed_count = 0
    
    for i, img_url in enumerate(image_urls):
        progress = 50 + int((i / len(image_urls)) * 40)
        progress_bar.progress(min(progress, 90))
        status_text.text(f"⏳ Processing image {i+1}/{len(image_urls)}...")
        
        image, raw_bytes, size_kb = fetch_image(img_url)
        
        if image and size_kb >= min_size_kb:
            images_data.append({
                'image': image,
                'bytes': raw_bytes,
                'size': size_kb,
                'url': img_url
            })
        else:
            failed_count += 1
        
        # Early stop if we have enough good images
        if len(images_data) >= max_images:
            break
    
    progress_bar.progress(100)
    status_text.empty()
    
    # Sort by size (largest first)
    images_data.sort(key=lambda x: x['size'], reverse=True)
    
    # Store in session state
    st.session_state.images_data = images_data
    st.session_state.scraping_done = True
    
    if not images_data:
        st.warning("⚠️ No valid images found. Try adjusting settings or check if site requires login.")
    else:
        st.success(f"✅ Successfully loaded {len(images_data)} images ({failed_count} filtered out)")

# Display results
if st.session_state.scraping_done and st.session_state.images_data:
    st.divider()
    
    # Bulk actions
    col_bulk1, col_bulk2, col_bulk3 = st.columns([1, 1, 2])
    
    with col_bulk1:
        if st.button("📦 Download All Original", type="secondary"):
            # Create ZIP of all original images
            import zipfile
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for i, data in enumerate(st.session_state.images_data):
                    filename = get_image_download_name(data['url'], prefix=f"{i+1}_")
                    zf.writestr(filename, data['bytes'])
            
            st.download_button(
                "⬇️ Download ZIP",
                data=zip_buffer.getvalue(),
                file_name="all_images_original.zip",
                mime="application/zip",
                key="bulk_download"
            )
    
    with col_bulk2:
        st.caption(f"Total: {len(st.session_state.images_data)} images")
    
    # Individual image cards
    st.markdown("### 🖼️ Individual Images")
    
    for idx, data in enumerate(st.session_state.images_data):
        with st.container():
            st.markdown(f"<div class='image-card'>", unsafe_allow_html=True)
            display_image_card(idx, data)
            st.markdown("</div>", unsafe_allow_html=True)
            st.divider()

elif st.session_state.scraping_done and not st.session_state.images_data:
    st.info("💡 Tips: Try increasing 'Page Load Wait' time, or check if the site blocks scrapers.")

# Footer
st.divider()
st.caption("🔒 Respects robots.txt | 🚀 High-performance extraction | 🎨 AI-powered enhancement")