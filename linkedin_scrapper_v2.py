import asyncio
from playwright.async_api import async_playwright
import os
from dotenv import load_dotenv
from datetime import datetime
from sqlalchemy import select, func
from models import init_db, Connection, ScrapingHistory
from playwright.sync_api import sync_playwright
import json
from typing import Dict, List
import random
from persistent_browser import PersistentBrowser
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
import time
# Load environment variables
load_dotenv(override=True)

# Initialize database session
Session = init_db()

async def set_cookie_session(context):
    """Set cookie session from environment variable"""
    try:
        cookie_session = os.getenv('LINKEDIN_COOKIE_SESSION')
        if not cookie_session:
            raise ValueError("LINKEDIN_COOKIE_SESSION not found in .env file")
        
        # Set the li_at cookie for LinkedIn
        await context.add_cookies([{
            'name': 'li_at',
            'value': cookie_session,
            'domain': '.linkedin.com',
            'path': '/'
        }])
        return True
    except Exception as e:
        print(f"Error setting cookie session: {str(e)}")
        return False

def save_single_connection(connection_data, source_profile):
    """Save or update a single connection in the database"""
    session = Session()
    try:
        # Try to find existing connection
        existing = session.query(Connection).filter_by(
            profile_url=connection_data['profile_url']
        ).first()
        
        if existing:
            # Update existing connection
            existing.name = connection_data['name']
            existing.occupation = connection_data['occupation']
            existing.source_profile = source_profile
            print(f"Updated existing connection: {connection_data['name']}")
        else:
            # Create new connection
            new_connection = Connection(
                name=connection_data['name'],
                occupation=connection_data['occupation'],
                profile_url=connection_data['profile_url'],
                source_profile=source_profile
            )
            session.add(new_connection)
            print(f"Saved new connection: {connection_data['name']}")
        
        # Commit the change
        session.commit()
        return True
    
    except Exception as e:
        print(f"Error saving connection {connection_data['name']}: {str(e)}")
        session.rollback()
        return False
    
    finally:
        session.close()

async def get_profile_connections(page, profile_url):
    """Scrape connections from a specific LinkedIn profile"""
    print(f"Navigating to profile: {profile_url}")
    try:
        # First navigate to the profile
        await page.goto(profile_url, wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_selector('body', timeout=10000)
        await page.wait_for_timeout(3000)
        
        # Look for connections count using multiple possible selectors
        connection_selectors = [
            'a[href*="connectionOf"] span.t-bold',  # New format
            '.link-without-visited-state span.t-bold',  # Alternative format
            'a[href*="/search/results/people/?connectionOf"]',  # Generic connection link
        ]
        
        connections_element = None
        connections_count = 0
        connection_id = None
        
        for selector in connection_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    connections_element = element
                    count_text = await element.inner_text()
                    # Extract number from text (e.g., "425" from "425 connections")
                    connections_count = int(''.join(filter(str.isdigit, count_text)))
                    
                    # Get the connection ID from the parent anchor href
                    parent_anchor = await element.evaluate('node => node.closest("a")')
                    if parent_anchor:
                        href = await parent_anchor.get_attribute('href')
                        if 'connectionOf' in href:
                            # Extract the connection ID from the URL
                            import re
                            match = re.search(r'connectionOf=%5B%22(.*?)%22%5D', href)
                            if match:
                                connection_id = match.group(1)
                    
                    print(f"Found {connections_count} connections")
                    break
            except Exception as e:
                print(f"Error with selector {selector}: {str(e)}")
                continue
        
        if not connections_element or not connection_id:
            print("Could not find connections count or ID. The profile might be private.")
            return []
        
        # Construct the search URL with the connection ID
        search_url = f"https://www.linkedin.com/search/results/people/?connectionOf=%5B%22{connection_id}%22%5D&network=%5B%22F%22%2C%22S%22%5D&origin=MEMBER_PROFILE_CANNED_SEARCH"
        print(f"Navigating to search results: {search_url}")
        
        await page.goto(search_url, wait_until='domcontentloaded', timeout=60000)
        await page.wait_for_selector('.search-results-container', timeout=10000)
        
    except Exception as e:
        print(f"Navigation error: {str(e)}")
        return []
    
    connections = []
    total_saved = 0
    failed_saves = 0
    current_page = 1
    
    print("\nStarting to extract connections...")
    print(f"Expected total connections: {connections_count}")
    
    while total_saved < connections_count:
        try:
            print(f"\nProcessing page {current_page}")
            
            # Wait for the search results to load
            await page.wait_for_selector('.search-results-container', timeout=10000)
            await page.wait_for_timeout(2000)
            
            # Get all connection elements on the current page
            connection_elements = await page.query_selector_all('.reusable-search__result-container')
            
            if not connection_elements:
                print("No connection elements found on this page")
                break
            
            print(f"Found {len(connection_elements)} connections on page {current_page}")
            
            for element in connection_elements:
                try:
                    # Extract connection details
                    name = await element.query_selector('.entity-result__title-text')
                    name_text = await name.inner_text() if name else "N/A"
                    name_text = name_text.replace('View profile for ', '').strip()  # Clean up the name
                    
                    occupation = await element.query_selector('.entity-result__primary-subtitle')
                    occupation_text = await occupation.inner_text() if occupation else "N/A"
                    
                    profile_link = await element.query_selector('.app-aware-link')
                    profile_url = await profile_link.get_attribute('href') if profile_link else "N/A"
                    
                    if profile_url != "N/A":
                        profile_url = profile_url.split('?')[0]
                    
                    connection = {
                        'name': name_text.strip(),
                        'occupation': occupation_text.strip(),
                        'profile_url': profile_url
                    }
                    
                    if connection not in connections and connection['name'] != "N/A":
                        connections.append(connection)
                        if save_single_connection(connection, profile_url):
                            total_saved += 1
                            print(f"Progress: {total_saved}/{connections_count} connections saved")
                        else:
                            failed_saves += 1
                
                except Exception as e:
                    print(f"Error processing connection: {str(e)}")
                    continue
            
            # Check for next page button
            next_button = await page.query_selector('button[aria-label="Next"]')
            if not next_button:
                print("No more pages available")
                break
            
            # Check if next button is disabled
            is_disabled = await next_button.get_attribute('disabled')
            if is_disabled:
                print("Reached last page")
                break
            
            # Click next page and wait for navigation
            await next_button.click()
            await page.wait_for_timeout(2000)  # Wait for page transition
            current_page += 1
            
        except Exception as e:
            print(f"Error processing page {current_page}: {str(e)}")
            break
    
    print(f"\nFinished extracting. Total connections saved: {total_saved}/{connections_count}")
    if failed_saves > 0:
        print(f"Failed to save {failed_saves} connections")
    
    return connections

def print_extraction_stats(profile_url):
    """Print statistics about the extracted connections"""
    session = Session()
    try:
        # Get total connections from this profile
        total_connections = session.query(Connection).filter_by(
            source_profile=profile_url
        ).count()
        
        # Get new connections added in this session
        new_connections = session.query(Connection).filter(
            Connection.source_profile == profile_url,
            Connection.first_seen >= datetime.now().replace(second=0, microsecond=0)
        ).count()
        
        print("\n=== Extraction Statistics ===")
        print(f"Profile: {profile_url}")
        print(f"Total connections extracted: {total_connections}")
        print(f"New connections added: {new_connections}")
        print("==========================\n")
    
    finally:
        session.close()

async def main():
    # Get profile URL from user
    profile_url = input("Enter the LinkedIn profile URL to extract connections from: ").strip()
    
    if not profile_url:
        print("Please provide a valid profile URL")
        return
    
    # Ensure the URL is in the correct format
    if not profile_url.startswith('https://www.linkedin.com/'):
        profile_url = f'https://www.linkedin.com/in/{profile_url}'
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        
        if not await set_cookie_session(context):
            print("Failed to set cookie session. Please check your .env file!")
            return
        
        page = await context.new_page()
        
        try:
            connections = await get_profile_connections(page, profile_url)
            print_extraction_stats(profile_url)
            
        except Exception as e:
            print(f"An error occurred: {str(e)}")
        
        finally:
            await context.close()
            await browser.close()

def extract_connection_info(page) -> List[Dict]:
    connections = []
    
    # Wait for the connections list to load
    page.wait_for_selector('ul.HhVStUlnpyqWXCvMFtgOOSXoXttneABVU')
    
    # Get all connection items
    connection_items = page.query_selector_all('li.AdHMbgDGIMDafLgUlAYlroYNrSpshgCHY')
    
    for item in connection_items:
        try:
            # Extract name
            name_element = item.query_selector('span.mkMastUmWkELhAcaaNYzKMdrjlCmJXnYgZE')
            name = name_element.inner_text().strip() if name_element else "N/A"
            
            # Extract title
            title_element = item.query_selector('div.mTjnOwtMxHPffEIRcJLDWXTPzwQcTgTqrfveo')
            title = title_element.inner_text().strip() if title_element else "N/A"
            
            # Extract location
            location_element = item.query_selector('div.bPSmFcwecOKZVgXSLAwwTDITpxNrJUrPIOE')
            location = location_element.inner_text().strip() if location_element else "N/A"
            
            # Extract profile URL
            profile_link = item.query_selector('a.dgePcUVTyZcmWIuOySyndWdGoBMukAZsio')
            profile_url = profile_link.get_attribute('href') if profile_link else "N/A"
            
            connection = {
                'name': name,
                'title': title,
                'location': location,
                'profile_url': profile_url
            }
            connections.append(connection)
            
        except Exception as e:
            print(f"Error extracting connection info: {str(e)}")
            continue
    
    return connections

def get_total_pages(page) -> int:
    try:
        # Look for pagination text that shows "Page 1 of X"
        pagination_text = page.query_selector('div.artdeco-pagination__page-state')
        if pagination_text:
            text = pagination_text.inner_text()
            return int(text.split('of')[-1].strip())
    except Exception:
        pass
    return 1

def extract_connections(page):
    
    
    
    page.goto('https://www.linkedin.com/mynetwork/invite-connect/connections/')
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        
        # Load cookies if file exists
        if os.path.exists(cookies_file):
            with open(cookies_file, 'r') as f:
                cookies = json.load(f)
            context.add_cookies(cookies)
        
        page = context.new_page()
        
        # Navigate to connections page
        page.wait_for_load_state('networkidle')
        
        all_connections = []
        total_pages = get_total_pages(page)
        
        for page_num in range(1, total_pages + 1):
            print(f"Processing page {page_num} of {total_pages}")
            
            # Extract connections from current page
            connections = extract_connection_info(page)
            all_connections.extend(connections)
            
            # Click next page button if not on last page
            if page_num < total_pages:
                next_button = page.query_selector('button.artdeco-pagination__button--next')
                if next_button:
                    next_button.click()
                    page.wait_for_load_state('networkidle')
        
        # Save the results
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_connections, f, indent=2, ensure_ascii=False)
        
        print(f"Extracted {len(all_connections)} connections and saved to {output_file}")
        
        browser.close()



class Scrapper(PersistentBrowser):

    def __init__(self):

        super().__init__()
        
        self.main_url = "https://www.linkedin.com/"

    def _random_delay(self, min_seconds: float = 2.0, max_seconds: float = 5.0):
        """Add random delay to mimic human behavior"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
        
    def _human_scroll(self, page: Page, scroll_distance: int = 300):
        """Scroll like a human with variable speed and pauses"""
        current_position = 0
        target_position = scroll_distance
        
        while current_position < target_position:
            
            # Random scroll chunk (20-60 pixels)
            scroll_chunk = random.randint(20, 60)
            current_position = min(current_position + scroll_chunk, target_position)
            
            # Scroll with smooth behavior
            page.evaluate(f"window.scrollTo({{top: {current_position}, behavior: 'smooth'}})")
            
            # Random micro-pause between scrolls (0.1-0.3 seconds)
            time.sleep(random.uniform(0.1, 0.3))
            
        # Pause at the end of scroll
        self._random_delay(1.0, 2.0)


    def human_like_behavior(self):
        
        # Initialize variables for infinite scroll
        last_height = self.page.evaluate('document.body.scrollHeight')
        all_loaded = False
        scroll_attempts = 0
        max_scroll_attempts = 20  # Limit scrolling to prevent infinite loops
        

        while not all_loaded and scroll_attempts < max_scroll_attempts:
            # Scroll like a human
            self._human_scroll(self.page, scroll_distance=random.randint(300, 500))
            
            # Wait for possible new content to load
            self._random_delay(1.0, 2.0)
            
            # Check if we've reached the bottom
            new_height = self.page.evaluate('document.body.scrollHeight')
            if new_height == last_height:
                scroll_attempts += 1
                if scroll_attempts >= 3:  # If height hasn't changed for 3 attempts, assume all loaded
                    all_loaded = True
            else:
                scroll_attempts = 0  # Reset counter if height changed
                last_height = new_height
                
            # Save state periodically
            if scroll_attempts % 5 == 0:
                self.save_state()
        

    def load_connection_page_from_main(self):
                
        # Navigate to the profile page
        self.page.goto(self.main_url)
        self._random_delay(3.0, 5.0)

        connections_button = self.page.wait_for_selector('a[href*="connectionOf"]', timeout=5000)
        # if not connections_button:
        #     raise PlaywrightTimeoutError("Could not find connections button - profile might be private or not connected")
        

        # Move mouse naturally to the button
        connections_button.hover()
        self._random_delay(0.5, 1.0)
        connections_button.click()
        
        # Wait for connections page to load
        self._random_delay(2.0, 4.0)
        
        self.human_like_behavior()

        # try:
            # Wait for the connections list to load
        self.page.wait_for_selector('.search-results-container ul[role="list"]', timeout=10000)

        # except Exception as e:
        #     print(f"Error in connection extraction: {e}")


    def load_connection_page_from_anywhere(self):
            
        # Navigate to the profile page

        self.page.goto('https://www.linkedin.com/mynetwork/invite-connect/connections/')
        
        self.human_like_behavior()

        # try:
            # Wait for the connections list to load
        self.page.wait_for_selector('.search-results-container ul[role="list"]', timeout=10000)

        # except Exception as e:
        #     print(f"Error in connection extraction: {e}")


    def check_if_connection_page(self):
            
        # Navigate to the profile page
        
        self.human_like_behavior()

        try:
            # Wait for the connections list to load
            self.page.wait_for_selector('.search-results-container ul[role="list"]', timeout=10000)

        except Exception as e:
            print(f"Error in connection extraction: {e}")
            self.page.reload()

            self.page.wait_for_selector('.search-results-container ul[role="list"]', timeout=10000)


    def extract_connection_count(self, text: str) -> int:
        # Remove "Connections" text and clean the number
        try:
            # Example input: "1,704 Connections"
            clean_number = text.split(" ")[0].replace(",", "")
            return int(clean_number)
        except (ValueError, IndexError):
            return 0


    def get_connections(self):
        
        
        if self.page.url !=  "https://www.linkedin.com/mynetwork/invite-connect/connections/":
            if random.randint(1,100) % 3 == 0:
                self.load_connection_page_from_anywhere()
            else:
                self.load_connection_page_from_main()
        
        self.check_if_connection_page()

        header_element = self.page.query_selector('div[componentkey="ConnectionsPage_ConnectionsListHeader"] p')
        connections_count_text = header_element.inner_text() if header_element else "0 Connections"
        
        connections_elements = self.page.query_selector_all('div[data-view-name="connections-list"]')

        for element in connections_elements:
            
            profile_elem = element.query_selector('a[href*="/in/"]:not([data-view-name="connections-profile"])')
            title_elem = element.query_selector('p:not(:has(a))')

            profile_url = profile_elem.get_attribute('href') 
            name = profile_elem.inner_text().strip() 
            title = title_elem.inner_text().strip() 

            print(name)

        connections_count = self.extract_connection_count(connections_count_text)

        return connections_count




if __name__ == "__main__":
    scraper = Scrapper()
    try:
        scraper.start()
        # Replace with actual profile URL
        connections = scraper.get_connections()

        print(f"Found {len(connections)} connections")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        scraper.close() 

# if __name__ == "__main__":
#     cookies_file = "linkedin_cookies.json"
#     output_file = "connections.json"
    
#     if not os.path.exists(cookies_file):
#         print(f"Error: Cookie file {cookies_file} not found!")
#         exit(1)
    
#     extract_connections(cookies_file, output_file) 