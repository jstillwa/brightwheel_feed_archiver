# Brightwheel Feed Archiver

A Python tool for downloading and archiving content from Brightwheel, including images, videos, and feed entries.

## Features

- Downloads images and videos from Brightwheel feeds
- Supports multiple students
- Browser-based authentication
- Generates static HTML site for browsing
- Maintains an organized archive structure
- Handles rate limiting
- Provides detailed logging

## Requirements

- Python 3.7+
- Required packages:
  - requests
  - tqdm
  - beautifulsoup4
  - playwright
  - jinja2

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/brightwheel-scraper.git
cd brightwheel-scraper
```

2. Install dependencies:
```bash
uv pip install -r requirements.txt
```

3. Create a config.json file (see config.example.json)

## Usage

### Scraping Content

Run the scraper with:
```bash
python brightwheel_scraper.py
```

The script will:
1. Open a browser window for authentication
2. Let you sign in to your Brightwheel account
3. Download content after successful authentication

**Note about Authentication:**
- You will need to sign in to your Brightwheel account manually in the browser window
- Brightwheel uses antibot technology that may require multiple sign-in attempts
- If sign-in fails, the script will retry with a fresh browser session
- Once authenticated, your session is saved for future runs

Optional arguments:
- `--config`: Path to config file (default: config.json)
- `--max-pages`: Maximum number of pages to scrape (default: 5)
- `--all`: Download all available pages
- `--start-date`: Start date for feed entries (YYYY-MM-DD)
- `--end-date`: End date for feed entries (YYYY-MM-DD)
- `--student-id`: Specify a single student ID to scrape
- `--all-students`: Scrape data for all available students
- `--debug`: Enable debug logging to console

### Generating Static Site

After downloading content, generate the browsable site:
```bash
python generate_site.py
```

Then open `brightwheel_archive/index.html` in your browser.

## Configuration

1. Copy `config.example.json` to `config.json`
2. Update the configuration:
```json
{
  "output_directory": "brightwheel_archive",
  "api_base_url": "https://schools.mybrightwheel.com"
}
```

Authentication is now handled through your browser - no need to manually copy tokens.

## Student Selection

The scraper will:
1. Fetch the list of students associated with your guardian account
2. Let you choose to:
   - Download all students' feeds
   - Select a specific student
   - Specify a student ID via command line

## Output Structure

The scraper creates the following directory structure:
```
brightwheel_archive/
├── index.html
├── download_history.json
├── student1_id/
│   ├── feeds/
│   ├── images/
│   ├── videos/
│   └── html/
└── student2_id/
    └── ...
```

Each student's directory contains:
- `feeds/`: JSON files for each feed entry
- `images/`: Downloaded images
- `videos/`: Downloaded videos
- `html/`: Generated static site files

## Security

See [SECURITY.md](SECURITY.md) for security policy and vulnerability reporting guidelines.

For more detailed documentation, see [brightwheel_readme.md](brightwheel_readme.md).

## License

Brightwheel Feed Archiver © 2025 by John Stillwagen is licensed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International. To view a copy of this license, visit https://creativecommons.org/licenses/by-nc-sa/4.0/