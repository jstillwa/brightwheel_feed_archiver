import json
import os
import math
import re
from pathlib import Path
# Removed redundant: import jinja2
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
import logging

# Get logger
logger = logging.getLogger("site_generator")

# --- Configuration ---
ENTRIES_PER_PAGE = 25
ARCHIVE_BASE_DIR = Path('brightwheel_archive')
TEMPLATE_DIR = Path('templates')
# --- End Configuration ---

def format_datetime(iso_string):
    """Format ISO timestamp for display."""
    if not iso_string:
        return "Unknown time"
    try:
        dt_obj = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt_obj.strftime('%b %d, %Y, %I:%M %p %Z')
    except ValueError:
        logger.warning(f"Could not parse date: {iso_string}")
        return iso_string

def generate_child_site(child_dir, feed_template):
    """Generates the static HTML site for a single child."""
    child_index_json = child_dir / 'feeds' / 'feed_index.json'
    child_output_html_dir = child_dir / 'html'
    
    # Create static directory for assets
    static_dir = child_output_html_dir / 'static'
    static_dir.mkdir(exist_ok=True, parents=True)
    
    if not child_index_json.exists():
        logger.warning(f"Index file not found for child in {child_dir}, skipping.")
        return None # Indicate failure or skip

    logger.warning(f"--- Generating site for child in: {child_dir} ---")
    logger.debug(f"Loading data from {child_index_json}")
    try:
        with open(child_index_json, 'r') as f:
            data = json.load(f)
        all_entries = data.get('entries', [])
        student_name = data.get('student_name', child_dir.name) # Fallback to dir name
        if not all_entries:
             logger.warning(f"No entries found in the index file for {student_name}.")
             # Still create empty HTML structure
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON from {child_index_json}")
        return None
    except Exception as e:
        logger.error(f"Error loading index file for {student_name}: {e}")
        return None

    # Sort Entries
    logger.debug(f"Sorting {len(all_entries)} entries for {student_name} by date...")
    try:
        all_entries.sort(key=lambda x: x.get('original_data', {}).get('event_date', '0000'), reverse=True)
    except Exception as e:
        logger.error(f"Error sorting entries for {student_name}: {e}. Check entry structure.")
        return None

    # Pagination Logic
    total_entries_count = len(all_entries)
    total_pages = math.ceil(total_entries_count / ENTRIES_PER_PAGE) if total_entries_count > 0 else 1
    logger.debug(f"Calculated {total_pages} pages for {student_name}.")

    # Create child's HTML output directory
    logger.debug(f"Creating output directory: {child_output_html_dir}")
    child_output_html_dir.mkdir(exist_ok=True)

    # Generate Pages for this child
    logger.warning(f"Generating HTML pages for {student_name}...")
    for page_num in range(1, total_pages + 1):
        start_index = (page_num - 1) * ENTRIES_PER_PAGE
        end_index = start_index + ENTRIES_PER_PAGE
        page_entries = all_entries[start_index:end_index]

        output_filename = f'feed_page_{page_num}.html'
        output_path = child_output_html_dir / output_filename

        logger.debug(f"Rendering page {page_num} for {student_name} ({len(page_entries)} entries) to {output_path}")
        try:
            # Pass student_name to template context
            html_content = feed_template.render(
                entries=page_entries,
                current_page=page_num,
                total_pages=total_pages,
                student_name=student_name # Pass student name
            )
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
        except Exception as e:
            logger.error(f"Error rendering or writing page {page_num} for {student_name}: {e}")

    # Generate Child Index Redirect
    child_index_path = child_output_html_dir / 'index.html'
    logger.debug(f"Generating index file for {student_name}: {child_index_path}")
    index_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="0; url=feed_page_1.html">
    <title>Redirecting...</title>
</head>
<body>
    <p>If you are not redirected automatically, follow this <a href="feed_page_1.html">link to the first page for {student_name}</a>.</p>
</body>
</html>"""
    try:
        with open(child_index_path, 'w', encoding='utf-8') as f:
            f.write(index_content)
    except Exception as e:
        logger.error(f"Error writing index file for {student_name}: {e}")

    logger.warning(f"--- Finished site generation for: {student_name} ---")
    # Return info needed for the main index
    return {'name': student_name, 'path': child_output_html_dir.relative_to(ARCHIVE_BASE_DIR)}


def generate_main_index(child_sites):
    """Generates the main index.html linking to each child's report."""
    main_index_path = ARCHIVE_BASE_DIR / 'index.html'
    logger.warning(f"Generating main index file: {main_index_path}")

    links_html = ""
    if child_sites: # Use parameter name consistently
        # Sort by student name for display
        for site_info in sorted(child_sites, key=lambda x: x['name']):
             # site_info['path'] is relative path like 'student_name_123abc/html'
             # site_info['name'] is the student's display name
            links_html += f'<li><a href="{site_info["path"]}/index.html">{site_info["name"]}</a></li>\n'
    else:
        links_html = "<p>No child archives found or processed.</p>"

    main_index_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Brightwheel Archive Index</title>
    <style>
        body {{ font-family: sans-serif; padding: 2em; }}
        ul {{ list-style: none; padding: 0; }}
        li {{ margin-bottom: 0.5em; }}
        a {{ text-decoration: none; color: #0056b3; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <h1>Brightwheel Archive</h1>
    <h2>Select a Child's Report:</h2>
    <ul>
        {links_html}
    </ul>
</body>
</html>"""
    try:
        with open(main_index_path, 'w', encoding='utf-8') as f:
            f.write(main_index_content)
        logger.warning(f"Main index generated successfully.")
        logger.warning(f"Run: open {main_index_path}")
    except Exception as e:
        logger.error(f"Error writing main index file: {e}")


def main():
    """Finds child directories and generates sites for each."""
    logger.warning("Starting static site generation process...")

    # --- Setup Jinja2 ---
    if not TEMPLATE_DIR.exists() or not (TEMPLATE_DIR / 'base.html').exists() or not (TEMPLATE_DIR / 'feed_page.html').exists():
        logger.error(f"Template directory or required templates not found in {TEMPLATE_DIR}")
        return

    logger.debug(f"Setting up Jinja2 environment with templates from {TEMPLATE_DIR}")
    try:
        env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)
        env.filters['formatdatetime'] = format_datetime
        feed_template = env.get_template('feed_page.html')
    except Exception as e:
        logger.error(f"Error setting up Jinja2 environment: {e}")
        return

    # --- Find Child Directories ---
    child_sites_info = []
    if not ARCHIVE_BASE_DIR.exists():
        logger.error(f"Archive base directory not found: {ARCHIVE_BASE_DIR}")
        return
        
    logger.debug(f"Scanning for child directories in {ARCHIVE_BASE_DIR}...")
    for item in ARCHIVE_BASE_DIR.iterdir():
        if item.is_dir():
            # Basic check: does it contain a 'feeds' subdirectory?
            if (item / 'feeds').is_dir():
                logger.debug(f"Found potential child directory: {item.name}")
                site_info = generate_child_site(item, feed_template)
                if site_info:
                    child_sites_info.append(site_info)
            else:
                 logger.debug(f"Skipping directory (no 'feeds' subdir): {item.name}")

    # --- Generate Main Index ---
    generate_main_index(child_sites_info)

    logger.warning("Overall static site generation complete.")

if __name__ == "__main__":
    main()