# LinkedIn Profile Finder

A Python-based tool for automating LinkedIn profile discovery and connection data extraction. This project uses Playwright for web automation and provides various utilities for LinkedIn interaction.

## Features

- Automated LinkedIn login and session management
- Profile connection extraction
- Connection data scraping
- Persistent browser session handling
- Data storage and management using SQLAlchemy

## Project Structure

- `linkedin_scrapper_v2.py` - Enhanced version of the LinkedIn scraping functionality
- `linkedin_scrapper.py` - Base LinkedIn scraping implementation
- `persistent_browser.py` - Browser session management utilities
- `linkedin_login.py` - LinkedIn authentication handling
- `get_profile_connections.py` - Profile connection extraction logic
- `extract_connections.py` - Connection data extraction utilities
- `models.py` - SQLAlchemy database models
- `main.py` - Main application entry point

## Prerequisites

- Python 3.x
- Virtual environment (recommended)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/gisuniverse/linkedinFindPeople.git
cd linkedinFindPeople
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install Playwright browsers:
```bash
playwright install
```

## Dependencies

- `playwright` (v1.42.0) - Web automation
- `python-dotenv` (v1.0.1) - Environment variable management
- `pandas` (v2.2.1) - Data manipulation and analysis
- `sqlalchemy` (v2.0.28) - Database ORM

## Configuration

1. Create a `.env` file in the project root with your LinkedIn credentials:
```
LINKEDIN_USERNAME=your_email@example.com
LINKEDIN_PASSWORD=your_password
```

## Usage

1. Ensure your virtual environment is activated:
```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Run the main script:
```bash
python main.py
```

## Security Notes

- Never commit your `.env` file or expose your LinkedIn credentials
- Use the virtual environment to manage dependencies
- Be mindful of LinkedIn's usage terms and rate limits