"""Browser-based authentication for Brightwheel using Playwright."""

import asyncio
import json
import logging
import random
# Removed redundant: import playwright.async_api
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

class BrowserAuth:
    """Handles browser-based authentication with Playwright."""

    def __init__(self, base_url):
        """Initialize the browser auth handler."""
        self.base_url = base_url

    async def authenticate(self):
        """Open sign-in page and wait for user to complete authentication."""
        async with async_playwright() as p:
            # Launch browser with enhanced capabilities
            browser = await p.firefox.launch(
                headless=False,
                firefox_user_prefs={
                    # Disable automation hints
                    "dom.webdriver.enabled": False,
                    "dom.automation": False,
                    
                    # Enable common features
                    "javascript.enabled": True,
                    "dom.ipc.plugins.enabled": True,
                    "media.navigator.enabled": True,
                    "webgl.disabled": False,
                    "canvas.capturestream.enabled": True,
                    
                    # Privacy settings that most users have
                    "privacy.trackingprotection.enabled": True,
                    "network.cookie.cookieBehavior": 0,
                    "privacy.resistFingerprinting": False,
                    
                    # Hardware acceleration and graphics
                    "layers.acceleration.enabled": True,
                    "gfx.canvas.azure.accelerated": True,
                    "webgl.force-enabled": True,
                    
                    # Font settings
                    "font.default.x-western": "sans-serif",
                    "font.name.sans-serif.x-western": "Arial",
                    "font.name.serif.x-western": "Times New Roman"
                }
            )
            
            # Set up context with realistic browser features
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/113.0',
                locale='en-US',
                timezone_id='America/Los_Angeles',
                color_scheme='light',
                has_touch=True,
                is_mobile=False,
                permissions=['geolocation', 'notifications'],
                accept_downloads=True,
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1'
                }
            )
            
            page = await context.new_page()
            
            # Override navigator properties
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        {
                            0: {type: "application/x-google-chrome-pdf"},
                            description: "Portable Document Format",
                            filename: "internal-pdf-viewer",
                            length: 1,
                            name: "Chrome PDF Plugin"
                        }
                    ]
                });
            """)
            
            # Simulate natural browsing behavior
            async def random_mouse_movement():
                x = random.randint(0, 1280)
                y = random.randint(0, 800)
                await page.mouse.move(x, y, steps=random.randint(5, 10))
                await page.wait_for_timeout(random.randint(100, 300))
            
            # Initial page interaction
            await page.wait_for_timeout(random.randint(1000, 2000))
            for _ in range(3):
                await random_mouse_movement()
            await page.mouse.wheel(delta_x=0, delta_y=random.randint(-200, 200))
            await page.wait_for_timeout(random.randint(500, 1000))

            try:
                # Navigate to sign-in page
                sign_in_url = f"{self.base_url}/sign-in"
                logger.debug(f"Opening sign-in page: {sign_in_url}")
                await page.goto(sign_in_url)
                
                logger.warning("Please sign in manually. Waiting for successful login...")
                
                # Wait for navigation away from sign-in page
                while True:
                    await page.wait_for_timeout(1000)  # Check every second
                    current_url = page.url
                    
                    if not current_url.endswith('/sign-in'):
                        logger.debug(f"Navigation detected away from sign-in to: {current_url}")
                        # Wait a moment for everything to settle
                        await page.wait_for_timeout(2000)
                        break
                    
                logger.warning("Login successful!")
                
                # Get cookies and tokens (with retries)
                cookies = await page.context.cookies()
                logger.debug(f"Got {len(cookies)} cookies")
                
                # Wait and retry a few times for tokens
                max_retries = 5
                for attempt in range(max_retries):
                    # Log localStorage contents
                    storage = await page.evaluate("""() => {
                        const data = {};
                        for (let i = 0; i < localStorage.length; i++) {
                            const key = localStorage.key(i);
                            data[key] = localStorage.getItem(key);
                        }
                        return data;
                    }""")
                    logger.debug(f"localStorage contents (attempt {attempt + 1}):")
                    for key, value in storage.items():
                        logger.debug(f"  {key}: {value[:50]}...")
                    
                    # Extract CSRF token
                    csrf_token = await page.evaluate("""() => {
                        return window.localStorage.getItem('csrf_token') ||
                               document.querySelector('meta[name="csrf-token"]')?.content;
                    }""")
                    logger.debug(f"CSRF Token: {csrf_token[:20] if csrf_token else 'None'}")
                    
                    # Get user data from API
                    logger.debug("Fetching user data from API...")
                    response = await page.evaluate("""async () => {
                        const response = await fetch('/api/v1/users/me', {
                            headers: {
                                'Accept': 'application/json',
                                'X-CSRF-Token': localStorage.getItem('csrf_token')
                            }
                        });
                        if (!response.ok) {
                            throw new Error(`API request failed: ${response.status}`);
                        }
                        const data = await response.json();
                        return {
                            object_id: data.object_id,
                            user_type: data.user_type
                        };
                    }""")
                    
                    logger.debug(f"API Response: {json.dumps(response, indent=2)}")
                    
                    if response.get('user_type') != 'guardian':
                        raise Exception(f"User is not a guardian (type: {response.get('user_type')})")
                        
                    guardian_id = response.get('object_id')
                    logger.debug(f"Guardian ID: {guardian_id if guardian_id else 'None'}")
                    
                    if csrf_token and guardian_id:
                        break
                        
                    logger.warning(f"Tokens not found, retrying in 2 seconds... ({attempt + 1}/{max_retries})")
                    await page.wait_for_timeout(2000)
                
                if not csrf_token or not guardian_id:
                    raise Exception("Failed to extract required tokens after retries")
                
                logger.warning("Successfully captured authentication data!")
                return ({c["name"]: c["value"] for c in cookies}, csrf_token, guardian_id)

            except Exception as e:
                logger.error(f"Authentication failed: {str(e)}")
                raise

            finally:
                await browser.close()

def authenticate(base_url):
    """Synchronous wrapper for browser authentication."""
    auth = BrowserAuth(base_url)
    return asyncio.run(auth.authenticate())