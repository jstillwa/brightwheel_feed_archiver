#!/usr/bin/env python3
"""
Brightwheel Feed Archiver

This script downloads and archives content from a Brightwheel account,
including images, videos, and feed entries.

Usage:
    python brightwheel_scraper.py --config config.json

Requirements:
    - Python 3.7+
    - requests
    - tqdm
    - beautifulsoup4 (for HTML parsing)
"""

import argparse
import json
import logging
import os
import re
import requests
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from tqdm import tqdm
from urllib.parse import urlparse, urljoin, unquote
from bs4 import BeautifulSoup
from browser_auth import authenticate

# Configure logging
logger = logging.getLogger("brightwheel_scraper")
logger.setLevel(logging.DEBUG)

def setup_logging(debug_mode=False):
    """Configure logging with different levels for file and console output"""
    # Format for both handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # File handler - always logs everything
    file_handler = logging.FileHandler("brightwheel_scraper.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Console handler - level depends on debug mode
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO if debug_mode else logging.WARNING)
    console_handler.setFormatter(formatter)
    
    # Remove any existing handlers
    logger.handlers.clear()
    
    # Add both handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

class BrightwheelScraper:
    """Main scraper class for Brightwheel content"""
    
    # Modify constructor to accept args
    def __init__(self, config_path, args):
        """Initialize the scraper with configuration and command line args."""
        self.config = self._load_config(config_path)
        self.session = requests.Session()
        
        # Authenticate using browser
        self._login()
        
        # Set up session with auth data
        self._setup_session_headers()
        
        # Get available students
        self.students = self.get_students()
        if not self.students:
            logger.error("No students found for guardian")
            sys.exit(1)
            
        # Base output directory
        self.base_dir = Path(self.config.get('output_directory', 'brightwheel_archive'))
        self.base_dir.mkdir(exist_ok=True, parents=True)
            
        self.downloaded_files = set()
        # Load history from a single file in the base directory
        self._load_download_history()
        
        # Handle student selection based on args or prompting
        self._filter_students_based_on_selection(args)
    
    def _load_config(self, config_path):
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                
            # Only api_base_url is required now
            if 'api_base_url' not in config:
                raise ValueError("Missing required configuration field: api_base_url")
                    
            return config
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            sys.exit(1)
    
    def _setup_session_headers(self):
        """Configure the requests session with non-authentication headers"""
        # Add base headers that don't relate to auth state
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:137.0) Gecko/20100101 Firefox/137.0',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'X-Client-Name': 'web',
            'X-Client-Version': '1747',
            'Referer': 'https://schools.mybrightwheel.com/',
            'Origin': 'https://schools.mybrightwheel.com',
            'DNT': '1',
            'Connection': 'keep-alive'
        }
        
        # Add the dynamically obtained CSRF token
        if self.csrf_token:
             self.session.headers['X-CSRF-Token'] = self.csrf_token
        else:
             logger.warning("CSRF token not set in session headers.")

        # Ensure Accept header prioritizes JSON
        self.session.headers['Accept'] = 'application/json, text/plain, */*'
    
    def _load_download_history(self):
        """Load history of downloaded files to avoid duplicates"""
        history_path = self.base_dir / 'download_history.json'
        if history_path.exists():
            try:
                with open(history_path, 'r') as f:
                    self.downloaded_files = set(json.load(f))
            except Exception as e:
                logger.warning(f"Could not load download history: {e}")
    
    def _save_download_history(self):
        """Save history of downloaded files"""
        history_path = self.base_dir / 'download_history.json'
        try:
            with open(history_path, 'w') as f:
                json.dump(list(self.downloaded_files), f)
        except Exception as e:
            logger.warning(f"Could not save download history: {e}")

    def _login(self):
        """Handle login using browser-based authentication."""
        try:
            # Use browser-based authentication
            logger.warning("Starting browser-based authentication...")
            cookies, csrf_token, guardian_id = authenticate(self.config['api_base_url'])

            # Update session with cookies
            for name, value in cookies.items():
                self.session.cookies.set(name, value)

            # Store authentication data
            self.guardian_id = guardian_id
            self.csrf_token = csrf_token

            logger.warning(f"Successfully authenticated as guardian: {self.guardian_id}")
            logger.debug(f"CSRF Token obtained: {self.csrf_token[:10]}...")  # Token details only in debug

        except Exception as e:
            logger.error(f"Browser authentication failed: {e}")
            sys.exit(1)

    def get_students(self):
        """Fetch list of students for the guardian"""
        url = f"{self.config['api_base_url']}/api/v1/guardians/{self.guardian_id}/students"
        params = {
            'include[]': 'schools'
        }
        
        try:
            logger.debug(f"Fetching students list from {url}")
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            logger.debug(f"API Response: {json.dumps(data, indent=2)}")
            
            if 'students' in data:
                students = []
                for entry in data['students']:
                    if 'student' in entry:
                        student_data = entry['student']
                        students.append({
                            'id': student_data.get('object_id'),
                            'first_name': student_data.get('first_name', ''),
                            'last_name': student_data.get('last_name', ''),
                            'status': student_data.get('enrollment_status', '')
                        })
                
                logger.warning(f"Found {len(students)} total students")
                # Log student statuses for debugging
                status_counts = {}
                for student in students:
                    status = student.get('status', 'Unknown')
                    status_counts[status] = status_counts.get(status, 0) + 1
                logger.debug("Student status breakdown:")
                for status, count in status_counts.items():
                    logger.debug(f"- {status}: {count}")
                return students
            else:
                logger.error("No students found in API response")
                return None
        except Exception as e:
            logger.error(f"Failed to fetch students: {e}")
            return None
            
    def _select_student(self):
        """Prompt user to select one or all students."""
        if not self.students:
            logger.error("No students data available for selection.")
            return None # Indicate no selection possible

        num_students = len(self.students)
        print("\nAvailable active students:")
        for i, student in enumerate(self.students, 1):
            name = f"{student.get('first_name', '')} {student.get('last_name', '')}".strip()
            print(f"{i}. {name} (ID: {student.get('id', 'unknown')})")
        print(f"{num_students + 1}. All Students") # Add 'All' option

        while True:
            try:
                prompt = f"\nSelect student number (1-{num_students}) or {num_students + 1} for All: "
                choice_str = input(prompt)
                choice = int(choice_str)

                if 1 <= choice <= num_students:
                    selected = self.students[choice - 1]
                    name = f"{selected.get('first_name', '')} {selected.get('last_name', '')}".strip()
                    logger.info(f"Selected student: {name}")
                    return [selected] # Return list containing the single selected student
                elif choice == num_students + 1:
                    logger.info("Selected: All Students")
                    return self.students # Return the original full list
                else:
                     print(f"Invalid choice. Please enter a number between 1 and {num_students + 1}.")

            except ValueError:
                 print(f"Invalid input. Please enter a number.") # Handle non-integer input
            except KeyboardInterrupt:
                 logger.info("\nSelection cancelled by user.")
                 sys.exit(0)


    def _filter_students_based_on_selection(self, args):
        """Filters self.students based on command line args or user prompt."""
        logger.debug(f"Starting student selection with {len(self.students)} available students")
        target_student_id = getattr(args, 'student_id', None)
        all_students = getattr(args, 'all_students', False)
        logger.debug(f"Command line arguments - student_id: {target_student_id}, all_students: {all_students}")

        if target_student_id and all_students:
            logger.error("Cannot specify both --student-id and --all-students")
            sys.exit(1)
        elif target_student_id:
            # User specified an ID via command line
            logger.info(f"Attempting to select student by provided ID: {target_student_id}")
            original_students = self.students # Keep original list for error message
            self.students = [s for s in self.students if s.get('id') == target_student_id]
            
            if self.students:
                name = f"{self.students[0].get('first_name', '')} {self.students[0].get('last_name', '')}".strip()
                logger.info(f"Successfully selected student by ID: {name}")
            else:
                logger.error(f"Student ID '{target_student_id}' not found among available active students.")
                print("\nAvailable student IDs:")
                for s in original_students:
                     print(f"- {s.get('id')} ({s.get('first_name', '')} {s.get('last_name', '')})")
                sys.exit(1)
        elif len(self.students) > 1:
            if all_students:
                logger.info("--all-students flag set, processing all available students")
                # Keep self.students as is to process all
            else:
                # Multiple students and no --all-students flag, prompt user
                logger.info(f"Multiple active students found ({len(self.students)} students). Prompting for selection...")
                selected_students = self._select_student() # This now returns a list or None
                if selected_students is not None:
                     logger.info(f"User selected {len(selected_students)} student(s)")
                     self.students = selected_students # Update self.students with the selection (could be one or all)
                else:
                     # Handle case where selection was cancelled or failed
                     logger.error("No student selection made.")
                     sys.exit(1)
        elif len(self.students) == 1:
            # Only one student, proceed automatically
            name = f"{self.students[0].get('first_name', '')} {self.students[0].get('last_name', '')}".strip()
            status = self.students[0].get('status', 'Unknown')
            logger.info(f"Only one student found: {name} (Status: {status}). Proceeding automatically.")
            # No filtering needed
        else:
             # No students found initially
             logger.error("No students found after initial fetch.")
             sys.exit(1)
        
        logger.info(f"Final student selection: {len(self.students)} student(s)")
        for student in self.students:
            name = f"{student.get('first_name', '')} {student.get('last_name', '')}".strip()
            logger.info(f"- {name} (ID: {student.get('id')})")

    def get_feed(self, student_id, page=1, page_size=10, start_date_str=None, end_date_str=None, include_parent_actions=True):
        """Fetch feed entries from the Brightwheel API for a specific student and date range."""
        # Construct the URL dynamically using the provided student_id
        api_url = f"{self.config['api_base_url']}/api/v1/students/{student_id}/activities"

        # Format dates for API (YYYY-MM-DDTHH:MM:SS.sssZ)
        # Default to fetching all if dates aren't provided
        start_date_iso = None
        if start_date_str:
            try:
                start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
                start_date_iso = start_dt.strftime('%Y-%m-%dT00:00:00.000Z')
            except ValueError:
                logger.warning(f"Invalid start date format: {start_date_str}. Use YYYY-MM-DD.")

        end_date_iso = None
        if end_date_str:
             try:
                 end_dt = datetime.strptime(end_date_str, '%Y-%m-%d')
                 # Set time to end of the day
                 end_date_iso = end_dt.strftime('%Y-%m-%dT23:59:59.999Z')
             except ValueError:
                 logger.warning(f"Invalid end date format: {end_date_str}. Use YYYY-MM-DD.")

        params = {
            'page': page,
            'page_size': page_size,
            'include_parent_actions': include_parent_actions
        }
        if start_date_iso:
            params['start_date'] = start_date_iso
        if end_date_iso:
            params['end_date'] = end_date_iso
        
        try:
            # Log detailed request setup
            full_url = f"{api_url}?{'&'.join(f'{k}={v}' for k,v in params.items())}"
            logger.debug("=== REQUEST DETAILS ===")
            logger.debug(f"Full URL: {full_url}")
            
            # Log headers with special attention to CSRF and client headers
            headers_log = dict(self.session.headers)
            logger.debug("\nHeaders:")
            logger.debug(f"X-CSRF-Token: {headers_log.get('X-CSRF-Token', 'MISSING')}")
            logger.debug(f"X-Client-Name: {headers_log.get('X-Client-Name', 'MISSING')}")
            logger.debug(f"X-Client-Version: {headers_log.get('X-Client-Version', 'MISSING')}")
            logger.debug(f"Origin: {headers_log.get('Origin', 'MISSING')}")
            logger.debug(f"Referer: {headers_log.get('Referer', 'MISSING')}")
            logger.debug(f"All Headers: {json.dumps(headers_log, indent=2)}")
            
            # Clean up any duplicate cookies before request
            cookie_names = set()
            cookies_to_remove = []
            for cookie in self.session.cookies:
                if cookie.name in cookie_names:
                    cookies_to_remove.append(cookie)
                else:
                    cookie_names.add(cookie.name)
            
            for cookie in cookies_to_remove:
                logger.debug(f"Removing duplicate cookie: {cookie.name}")
                self.session.cookies.clear(cookie.domain, cookie.path, cookie.name)
            
            # Log final cookie state
            cookies_log = dict(self.session.cookies)
            logger.debug("\nCookies:")
            logger.debug(f"brightwheel_v2: {cookies_log.get('brightwheel_v2', 'MISSING')}")
            logger.debug(f"_brightwheel_v2: {cookies_log.get('_brightwheel_v2', 'MISSING')}")
            logger.debug(f"csrf_token: {cookies_log.get('csrf_token', 'MISSING')}")
            logger.debug(f"All Cookies: {json.dumps(cookies_log, indent=2)}")
            
            # Debug URL construction
            logger.debug(f"API Base URL: {self.config['api_base_url']}")
            logger.debug(f"Final API URL: {api_url}")
            logger.debug(f"All parameters: {json.dumps(params, indent=2)}")
            
            response = self.session.get(api_url, params=params)
            
            # Log detailed response information
            logger.info("\n=== RESPONSE DETAILS ===")
            logger.info(f"Status Code: {response.status_code}")
            
            resp_headers = dict(response.headers)
            logger.info("\nResponse Headers:")
            logger.info(f"Content-Type: {resp_headers.get('Content-Type', 'MISSING')}")
            logger.info(f"Set-Cookie: {resp_headers.get('Set-Cookie', 'MISSING')}")
            logger.info(f"All Response Headers: {json.dumps(resp_headers, indent=2)}")
            
            # Log response content with better formatting
            logger.info("\nResponse Content Preview:")
            content_preview = response.text[:500]
            try:
                # Try to parse and format JSON response
                json_content = response.json()
                logger.info(f"JSON Response: {json.dumps(json_content, indent=2)[:500]}...")
            except:
                logger.info(f"Raw Response: {content_preview}...")
            
            response.raise_for_status()
            
            # Check if response is JSON or HTML
            content_type = response.headers.get('Content-Type', '')
            
            if 'application/json' in content_type:
                # Parse JSON and transform to expected format
                data = response.json()
                activities = data.get('activities', [])
                
                # Process video_info if present
                for activity in activities:
                    try:
                        if 'video_info' in activity:
                            logger.info(f"Found video_info in activity {activity.get('object_id')}")
                            video_info = activity.get('video_info')
                            logger.info(f"Video info structure: {json.dumps(video_info, indent=2)}")
                            
                            if video_info and isinstance(video_info, dict):
                                # Extract video URLs
                                streamable_url = video_info.get('streamable_url')
                                downloadable_url = video_info.get('downloadable_url')
                                thumbnail_url = video_info.get('thumbnail_url')
                                logger.info(f"Extracted URLs - streamable: {streamable_url}, downloadable: {downloadable_url}, thumbnail: {thumbnail_url}")
                                
                                if streamable_url or downloadable_url or thumbnail_url:
                                    # Initialize media dict if needed
                                    if activity.get('media') is None:
                                        activity['media'] = {}
                                    
                                    # Prefer downloadable MP4 URL over HLS stream
                                    if downloadable_url:
                                        activity['media']['video_url'] = downloadable_url
                                        logger.info(f"Using downloadable MP4 URL")
                                    elif streamable_url:
                                        # Extract direct MP4 URL from streamable URL if possible
                                        if 'playlist.m3u8' in streamable_url:
                                            mp4_url = streamable_url.replace('playlist.m3u8', 'video.mp4')
                                            activity['media']['video_url'] = mp4_url
                                            logger.info(f"Converted HLS URL to direct MP4: {mp4_url}")
                                        else:
                                            activity['media']['video_url'] = streamable_url
                                            logger.info(f"Using streamable URL as fallback")
                                    
                                    if thumbnail_url:
                                        activity['media']['video_thumbnail_url'] = thumbnail_url
                                    logger.info(f"Successfully added video URLs to media")
                    except Exception as e:
                        logger.error(f"Error processing video_info: {str(e)}")
                        logger.error(f"Activity structure: {json.dumps(activity, indent=2)}")
                
                return {
                    'entries': activities,
                    'has_more': data.get('count', 0) > (data.get('page', 1) * data.get('page_size', 10))
                }
            else:
                # If HTML, we need to parse it
                soup = BeautifulSoup(response.text, 'html.parser')
                video_posters = soup.find_all('div', class_='video-react-poster')
                
                entries = []
                for poster in video_posters:
                    style = poster.get('style', '')
                    if 'background-image' in style:
                        # Extract thumbnail URL from style
                        thumbnail_url = style.split('url("')[1].split('")')[0]
                        logger.info(f"Found video thumbnail URL in HTML: {thumbnail_url}")
                        
                        # Create entry with video info
                        entry = {
                            'id': str(uuid.uuid4()),
                            'media': {
                                'thumbnail_url': thumbnail_url,
                                'type': 'video'
                            }
                        }
                        entries.append(entry)
                
                return {
                    'entries': entries,
                    'has_more': False
                }
                
        except Exception as e:
            logger.error(f"Failed to fetch feed: {e}")
            return None
            
    def _parse_feed_html(self, html_content):
        """Parse feed entries from HTML content"""
        soup = BeautifulSoup(html_content, 'html.parser')
        logger.info("Parsing HTML feed content")

        # --- DEBUG LOG REMOVED ---
        # try:
        #     debug_html_path = Path('debug_feed_page.html')
        #     with open(debug_html_path, 'w', encoding='utf-8') as f_html:
        #         f_html.write(html_content)
        #     logger.info(f"Saved received HTML for debugging to: {debug_html_path}")
        # except Exception as e_dbg:
        #     logger.warning(f"Could not save debug HTML: {e_dbg}")
        # --- DEBUG LOG REMOVED ---

        result = {
            'entries': [],
            'has_more': False
        }
        
        # Look for feed entries in the HTML
        # This is a placeholder and will need to be adjusted based on actual HTML structure
        feed_entries = soup.select('.feed-entry, .post, .activity')
        
        for entry in feed_entries:
            # Extract entry data based on HTML structure
            entry_data = {
                'id': entry.get('id') or entry.get('data-id'),
                'timestamp': None,
                'media': []
            }
            
            # Look for timestamps
            timestamp_elem = entry.select_one('.timestamp, .date, time')
            if timestamp_elem:
                entry_data['timestamp'] = timestamp_elem.text.strip()
                
            # Look for text content
            content_elem = entry.select_one('.content, .text, .description')
            if content_elem:
                entry_data['content'] = content_elem.text.strip()
                
            # Look for media (images and videos)
            media_elements = entry.select('img, video, a.media-link, .attachment')
            
            for media in media_elements:
                media_item = {}
                
                # Check for images
                if media.name == 'img':
                    media_item['type'] = 'image'
                    media_item['url'] = media.get('src')
                    if media.get('alt'):
                        media_item['description'] = media.get('alt')
                
                # Check for videos
                elif media.name == 'video':
                    media_item['type'] = 'video'
                    source = media.select_one('source')
                    if source:
                        media_item['url'] = source.get('src')
                
                # Check for media links
                elif media.name == 'a' and ('media' in media.get('class', []) or media.get('href', '').endswith(('.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mov'))):
                    href = media.get('href')
                    if any(ext in href.lower() for ext in ['.mp4', '.mov', '.avi']):
                        media_item['type'] = 'video'
                    else:
                        media_item['type'] = 'image'
                    media_item['url'] = href
                
                if media_item and 'url' in media_item:
                    entry_data['media'].append(media_item)
            
            result['entries'].append(entry_data)
        
        # Check if there's a "next page" or "load more" button
        next_page = soup.select_one('.next-page, .load-more, .pagination a.next')
        if next_page:
            result['has_more'] = True
            
        logger.info(f"Found {len(result['entries'])} entries in HTML")
        return result
    
    def download_media(self, url, media_type, event_date, output_dir):
        """Download a media file, prefix with timestamp, and save to the child's directory."""
        # Generate a base filename from the URL
        parsed_url = urlparse(url)
        file_path = unquote(parsed_url.path)
        base_file_name = os.path.basename(file_path)

        # Ensure a usable base filename
        if not base_file_name or '.' not in base_file_name:
            url_hash = hash(url) % 10000
            timestamp = int(time.time())
            base_file_name = f"media_{timestamp}_{url_hash}.{media_type}" # Use media_type for extension guess

        # Create timestamp prefix (handle potential None event_date)
        ts_prefix = event_date.strftime('%Y-%m-%d-%H-%M') if event_date else datetime.now().strftime('%Y-%m-%d-%H-%M')
        
        # Combine timestamp and base filename
        timestamped_file_name = f"{ts_prefix}-{base_file_name}"
        
        # For all files, construct the full output path in the child's dir
        output_path = output_dir / timestamped_file_name
        
        # Check if file already exists or URL was downloaded
        if output_path.exists():
            logger.debug(f"File already exists: {timestamped_file_name}")
            self.downloaded_files.add(url)  # Mark URL as downloaded
            return timestamped_file_name
        elif url in self.downloaded_files:
            logger.debug(f"URL already downloaded: {url}")
            return timestamped_file_name
            
        # Download the file
        try:
            # Set headers for video files
            headers = {}
            if media_type == 'video':
                headers['Accept'] = 'video/mp4,video/*;q=0.9,*/*;q=0.8'
            
            response = self.session.get(url, stream=True, headers=headers)
            response.raise_for_status()
            
            # Get file size for progress bar
            total_size = int(response.headers.get('content-length', 0))
            
            # Show progress bar for larger files
            with open(output_path, 'wb') as f:
                if total_size > 1024*1024:  # Show progress for files > 1MB
                    with tqdm(total=total_size, unit='B', unit_scale=True, desc=timestamped_file_name) as pbar:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                pbar.update(len(chunk))
                else:
                    f.write(response.content)
                    
            # Set file permissions to be readable
            os.chmod(output_path, 0o644)
            
            # Mark as downloaded
            self.downloaded_files.add(url)
            self._save_download_history()
            
            logger.warning(f"Downloaded: {timestamped_file_name}")  # Show successful downloads by default
            return timestamped_file_name
        except Exception as e:
             # Use timestamped_file_name in the error log
            logger.error(f"Failed to download {url} (intended filename: {timestamped_file_name}): {e}")
            return None

    # Remove the unused HLS video download function since we're using direct MP4 downloads now
    
    def process_feed_entry(self, entry, child_feeds_dir, child_images_dir, child_videos_dir):
        """Process a single activity entry, download media, and save JSON."""
        entry_id = entry.get('object_id', str(hash(json.dumps(entry)) % 10000))
        
        # Get event date for timestamping media
        event_date_str = entry.get('event_date')
        event_date = None
        if event_date_str:
            try:
                event_date = datetime.fromisoformat(event_date_str.replace('Z', '+00:00'))
            except ValueError:
                logger.warning(f"Could not parse event_date '{event_date_str}' for entry {entry_id}")
                event_date = datetime.now() # Fallback to current time if date is invalid

        processed_entry = {
            'id': entry_id,
            'original_data': entry,
            'processed_timestamp': datetime.now().isoformat(),
            'downloaded_media': []
        }
        
        # Extract media if present
        media = entry.get('media')
        if media:
            logger.debug(f"Processing media for entry {entry_id}")
            logger.debug(f"Media object: {json.dumps(media, indent=2)}")
            
            # Handle image URLs
            for url_type in ['image_url', 'thumbnail_url']:
                media_url = media.get(url_type)
                if media_url:
                    logger.debug(f"Found {url_type}: {media_url}")
                    # Pass event_date and child_images_dir
                    downloaded_file = self.download_media(media_url, 'image', event_date, child_images_dir)
                    if downloaded_file:
                        processed_entry['downloaded_media'].append({
                            'filename': downloaded_file,
                            'original_url': media_url,
                            'type': 'image',
                            'url_type': url_type
                        })
            
            # Handle video URLs (including video thumbnails)
            video_thumbnail_url = media.get('video_thumbnail_url')
            video_url = media.get('video_url')

            if video_thumbnail_url:
                 logger.debug(f"Found video_thumbnail_url: {video_thumbnail_url}")
                 # Download thumbnail to images dir
                 downloaded_thumb = self.download_media(video_thumbnail_url, 'image', event_date, child_images_dir)
                 if downloaded_thumb:
                     processed_entry['downloaded_media'].append({
                         'filename': downloaded_thumb,
                         'original_url': video_thumbnail_url,
                         'type': 'image', # It's an image thumbnail
                         'url_type': 'video_thumbnail_url'
                     })

            if video_url:
                logger.debug(f"Found video_url: {video_url}")
                # Pass event_date and child_videos_dir
                downloaded_video = self.download_media(video_url, 'video', event_date, child_videos_dir)
                if downloaded_video:
                    processed_entry['downloaded_media'].append({
                        'filename': downloaded_video,
                        'original_url': video_url,
                        'type': 'video',
                        'url_type': 'video_url'
                    })
        
        # Format the entry filename using datetime and actor info
        actor = entry.get('actor', {})
        first_name = actor.get('first_name', 'unknown')
        last_name = actor.get('last_name', 'unknown')
        
        # Use event_date for filename timestamp if available
        ts_format = event_date.strftime('%Y-%m-%d-%H-%M-%S') if event_date else datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
        filename = f"{ts_format}-{first_name.lower()}-{last_name.lower()}-{entry_id}.json"
        entry_path = child_feeds_dir / filename # Save to child's feed dir
        
        with open(entry_path, 'w') as f:
            json.dump(processed_entry, f, indent=2)
        
        return processed_entry
    
    def _scrape_feed_for_student(self, student_id, student_name, child_base_dir, child_feeds_dir, child_images_dir, child_videos_dir, max_pages=None, start_date=None, end_date=None):
        """Scrape feed pages for a specific student."""
        logger.warning(f"--- Starting scrape for student: {student_name} ({student_id}) ---")
        page = 1
        all_entries_for_student = []
        has_more = True
        total_entries = None
        
        try:
            # Get first page to determine total entries, using date range
            feed_data = self.get_feed(student_id=student_id, page=1, start_date_str=start_date, end_date_str=end_date)
            if feed_data:
                # Assuming 'count' is still in the response for total entries for this student
                # If not, we might need another way to estimate total
                total_entries = feed_data.get('count', 0)
                logger.warning(f"Found {total_entries} total entries for {student_name}")
            
            while has_more and (max_pages is None or page <= max_pages):
                logger.debug(f"Fetching feed page {page} for {student_name} (Dates: {start_date or 'any'} to {end_date or 'any'})")
                feed_data = self.get_feed(student_id=student_id, page=page, start_date_str=start_date, end_date_str=end_date)
                
                if not feed_data or 'entries' not in feed_data:
                    logger.warning(f"No valid feed data found on page {page} for {student_name}")
                    break
                    
                entries = feed_data.get('entries', [])
                if not entries:
                    logger.info(f"No more entries found for {student_name} after page {page-1}")
                    break
                    
                # Process each entry, passing child-specific directories
                for i, entry in enumerate(entries, 1):
                    logger.debug(f"Processing entry {i} of {len(entries)} on page {page} for {student_name}")
                    try:
                        processed = self.process_feed_entry(entry, child_feeds_dir, child_images_dir, child_videos_dir)
                        all_entries_for_student.append(processed)
                    except Exception as e:
                        logger.error(f"Error processing entry for {student_name}: {e}")
                        continue
                
                # Check if there are more pages
                has_more = feed_data.get('has_more', False)
                page += 1
                
                # Be nice to the server
                time.sleep(2)
                
        except KeyboardInterrupt:
            logger.info(f"\nDownload interrupted by user for student {student_name}. Saving progress...")
        
        finally:
            # Save student-specific index
            index_path = child_feeds_dir / 'feed_index.json'
            with open(index_path, 'w') as f:
                json.dump({
                    'student_id': student_id,
                    'student_name': student_name,
                    'total_entries_scraped': len(all_entries_for_student),
                    'total_entries_available': total_entries, # May be None if first page failed
                    'pages_scraped': page - 1,
                    'scraped_date': datetime.now().isoformat(),
                    'entries': all_entries_for_student # Contains processed entries with downloaded media info
                }, f, indent=2)
                
            logger.warning(f"Completed scraping {len(all_entries_for_student)} entries across {page-1} pages for {student_name}")
            if total_entries:
                 logger.warning(f"Progress for {student_name}: {len(all_entries_for_student)}/{total_entries} entries ({(len(all_entries_for_student)/total_entries)*100:.1f}%)")
            logger.warning(f"--- Finished scrape for student: {student_name} ---")
            # Save global download history after each student finishes
            self._save_download_history()
            return all_entries_for_student

    def scrape_for_all_students(self, max_pages=None, start_date=None, end_date=None):
        """Iterate through all students and scrape their feeds."""
        if not self.students:
            logger.error("No students available to scrape.")
            return

        logger.warning(f"Starting scraping process for {len(self.students)} student(s).")
        
        for student in self.students:
            student_id = student.get('id')
            first_name = student.get('first_name', 'Unknown')
            last_name = student.get('last_name', 'Student')
            student_name = f"{first_name} {last_name}".strip()
            
            # Sanitize name and append ID for unique directory name
            safe_base_name = re.sub(r'[^\w\-]+', '_', f"{first_name}_{last_name}".lower())
            safe_dir_name = f"{safe_base_name}_{student_id}"
            child_base_dir = self.base_dir / safe_dir_name
            
            logger.warning(f"Processing student: {student_name}")
            
            # Create child-specific directories
            child_feeds_dir = child_base_dir / 'feeds'
            child_images_dir = child_base_dir / 'images'
            child_videos_dir = child_base_dir / 'videos'
            child_html_dir = child_base_dir / 'html'  # Add html directory for site generation
            
            for directory in [child_base_dir, child_feeds_dir, child_images_dir, child_videos_dir, child_html_dir]:
                directory.mkdir(exist_ok=True, parents=True)
                
            # Scrape feed for this student
            self._scrape_feed_for_student(
                student_id=student_id,
                student_name=student_name,
                child_base_dir=child_base_dir,
                child_feeds_dir=child_feeds_dir,
                child_images_dir=child_images_dir,
                child_videos_dir=child_videos_dir,
                max_pages=max_pages,
                start_date=start_date,
                end_date=end_date
            )
            
        logger.warning("Finished scraping for all students.")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Brightwheel Feed Archiver')
    parser.add_argument('--config', default='config.json', help='Path to config file')
    parser.add_argument('--max-pages', type=int, default=5, help='Maximum number of pages to scrape (default: 5)')
    parser.add_argument('--all', action='store_true', help='Download all available pages (overrides --max-pages)')
    parser.add_argument('--start-date', help='Start date for feed entries (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='End date for feed entries (YYYY-MM-DD)')
    parser.add_argument('--student-id', help='Specify a single student ID to scrape')
    parser.add_argument('--all-students', action='store_true', help='Scrape data for all available students')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging to console')

    args = parser.parse_args()

    # Determine max_pages based on --all flag
    max_pages = None if args.all else args.max_pages

    # Validate date formats if provided
    # (Basic validation, get_feed handles conversion and more robust checks)
    if args.start_date:
        try:
            datetime.strptime(args.start_date, '%Y-%m-%d')
        except ValueError:
            logger.error("Invalid start date format. Please use YYYY-MM-DD.")
            sys.exit(1)
    if args.end_date:
         try:
             datetime.strptime(args.end_date, '%Y-%m-%d')
         except ValueError:
             logger.error("Invalid end date format. Please use YYYY-MM-DD.")
             sys.exit(1)

    # Configure logging based on debug flag
    setup_logging(args.debug)
    
    # Pass args to constructor to handle student selection
    scraper = BrightwheelScraper(args.config, args)
    # Call the method to scrape for the filtered list of students
    scraper.scrape_for_all_students(max_pages=max_pages, start_date=args.start_date, end_date=args.end_date)

if __name__ == "__main__":
    main()
