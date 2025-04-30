# Brightwheel Feed Archiver

A Python tool to archive content from your child's Brightwheel feed, including images, videos, and feed entries.

## Overview

This tool allows parents to create a local archive of their child's activities posted on Brightwheel. It downloads all media content and saves feed entries as structured JSON files for easy viewing and long-term storage. It also generates a static HTML site for browsing the archive.

## Features

- Downloads all images and videos from your child's feed
- Saves feed entries as structured JSON files
- Maintains an index of all downloaded content
- Avoids re-downloading content you already have
- Respects rate limits to avoid being blocked
- Generates a static HTML site for easy browsing
- Supports multiple students
- Browser-based authentication (no manual token copying needed)

## Requirements

- Python 3.7 or higher
- `requests` library
- `tqdm` library (for progress bars)
- `beautifulsoup4` library (for HTML parsing)
- `playwright` library (for browser-based authentication)

## Installation

1. Clone or download this repository
2. Install required packages:

```bash
uv pip install -r requirements.txt
```

## Configuration

Create a `config.json` file with your API information (copy from config.example.json):

```json
{
  "output_directory": "brightwheel_archive",
  "api_base_url": "https://schools.mybrightwheel.com"
}
```

## Usage

### Authentication

The script uses browser-based authentication to handle Brightwheel's security measures:

1. When you run the script, it opens a browser window
2. You'll need to manually sign in to your Brightwheel account
3. Due to Brightwheel's antibot technology:
   - Sign-in may require multiple attempts
   - You might need to solve CAPTCHAs
   - The script will automatically retry with a fresh browser session if needed
4. Once authenticated, your session is saved for future runs

### Basic Usage

Run the scraper:

```bash
python brightwheel_scraper.py
```

This will:
1. Open a browser window for authentication (if needed)
2. Let you select which student(s) to archive
3. Download all content
4. Generate a static HTML site

### Command Line Options

- `--config CONFIG`: Path to config file (default: config.json)
- `--max-pages N`: Maximum number of pages to scrape (default: 5)
- `--all`: Download all available pages
- `--start-date YYYY-MM-DD`: Start date for feed entries
- `--end-date YYYY-MM-DD`: End date for feed entries
- `--student-id ID`: Specify a single student ID to scrape
- `--all-students`: Scrape data for all available students
- `--debug`: Enable debug logging to console

### Generating the Static Site

After downloading content, generate the static site:

```bash
python generate_site.py
```

Then open `brightwheel_archive/index.html` in your browser.

## Output Structure

The scraper creates the following directory structure:

```
brightwheel_archive/
├── index.html
├── download_history.json
├── student1_id/
│   ├── feeds/
│   │   ├── feed_index.json
│   │   └── entries/
│   │       ├── entry1.json
│   │       └── entry2.json
│   ├── images/
│   │   └── ...
│   ├── videos/
│   │   └── ...
│   └── html/
│       ├── index.html
│       ├── feed_page_1.html
│       └── ...
└── student2_id/
    └── ...
```

- `index.html`: Main index page linking to all students
- `download_history.json`: Tracks downloaded files to avoid duplicates
- Per student:
  - `feeds/`: JSON files for each feed entry
  - `images/`: Downloaded images
  - `videos/`: Downloaded videos
  - `html/`: Generated static site files

## Feed Entry Format

Each feed entry is saved as a JSON file with the following structure:

```json
{
  "id": "entry_id",
  "original_data": {
    // Original API response
  },
  "processed_timestamp": "2025-04-27T12:34:56.789",
  "downloaded_media": [
    {
      "filename": "2025-04-27-12-34-image1.jpg",
      "original_url": "https://cdn.mybrightwheel.com/...",
      "type": "image"
    },
    {
      "filename": "2025-04-27-12-34-video1.mp4",
      "original_url": "https://cdn.mybrightwheel.com/...",
      "type": "video"
    }
  ]
}
```

## Security Notes

- Authentication is handled through your browser - no need to copy tokens
- The config file only needs the API base URL
- Consider adding `config.json` to your `.gitignore` if using version control

## Troubleshooting

If you encounter errors:

1. **Authentication failures:** Try clearing your browser cookies and logging in again
2. **Video playback issues:** Make sure your browser supports MP4 playback
3. **Rate limiting:** Add delays between requests using `time.sleep()`
4. **Incomplete downloads:** Check your internet connection and try again

## Updating Your Archive

The scraper maintains a download history to avoid re-downloading files, so you can run it periodically to get new content while skipping what you've already archived.

## Legal Considerations

This tool is for personal use only to archive your own child's content. Please respect Brightwheel's terms of service and use the tool responsibly.

## License

Brightwheel Feed Archiver © 2025 by John Stillwagen is licensed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International. To view a copy of this license, visit https://creativecommons.org/licenses/by-nc-sa/4.0/
