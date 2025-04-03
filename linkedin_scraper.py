from dotenv import load_dotenv
from datetime import datetime
import random
import time
from typing import List, Dict
import json
from persistent_browser import PersistentBrowser
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

# Load environment variables
load_dotenv(override=True)

class Scrapper(PersistentBrowser):
    def __init__(self, storage_state_path: str = "browser_state.json"):
        super().__init__(storage_state_path)
        self.base_url = "https://www.linkedin.com"
        
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
        
    def _ensure_valid_url(self, url: str) -> str:
        """Ensure URL is properly formatted"""
        if not url.startswith(('http://', 'https://')):
            url = f"{self.base_url}{url if url.startswith('/') else f'/{url}'}"
        return url
        
    def _extract_connections_data(self, page: Page) -> List[Dict]:
        """Extract connection data from the page"""
        connections = []
        try:
            # Wait for the connections list to load
            page.wait_for_selector('.search-results-container ul[role="list"]', timeout=10000)

        except Exception as e:
            print(f"Error in connection extraction: {e}")
    
        # Get all connection elements
        connection_elements = page.query_selector_all('.search-results-container ul[role="list"] li')[:10]
        
        for element in connection_elements:
            try:
                name_elem = element.query_selector('.t-16 span[aria-hidden="true"]') 
                location_elem = element.query_selector('div[class*="t-14 t-normal"]:not([class*="t-black"])')
                profile_link_elem = element.query_selector('.linked-area a[href*="/in/"]')
                title_elem = element.query_selector('div[class*="t-14 t-black t-normal"]')
                
                connection = {
                        'name': name_elem.inner_text().strip(),
                        'title': title_elem.inner_text().strip(),
                        'location': location_elem.inner_text().strip(),
                        'profile_url': profile_link_elem.get_attribute('href').split('?')[0] ,
                        'scraped_at': datetime.now().isoformat()
                    }
                
                connections.append(connection)
            
            except Exception as e:
                print(f"Error extracting connection data: {e}")
                continue
        

        return connections
        
    def get_connections(self, profile_url: str) -> List[Dict]:
        """
        Get connections from a LinkedIn profile
        
        Args:
            profile_url (str): URL of the LinkedIn profile to scrape connections from
            
        Returns:
            List[Dict]: List of connections with their details
        """
        
        profile_url = self._ensure_valid_url(profile_url)
        connections = []
        
        try:
            # Navigate to the profile page
            self.page.goto(profile_url)
            self._random_delay(3.0, 5.0)

        except Exception as e:
            print(f"Error during connection scraping: {e}")
            # Save state in case of error
            self.save_state()
            
        # Find and click the connections button
        try:
            connections_button = self.page.wait_for_selector('a[href*="connectionOf"]', timeout=5000)
            if not connections_button:
                raise PlaywrightTimeoutError("Could not find connections button - profile might be private or not connected")
            
        except PlaywrightTimeoutError:
            print("Could not find connections button - profile might be private or not connected")
            return []
        

        # Move mouse naturally to the button
        connections_button.hover()
        self._random_delay(0.5, 1.0)
        connections_button.click()
        
        # Wait for connections page to load
        self._random_delay(2.0, 4.0)
        
        self.human_like_behavior()

        # Extract connections data
        
        connections = self._extract_connections_data(self.page)
        
        # Save the connections to a JSON file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"connections_{timestamp}.json"
        with open(filename, 'w') as f:
            json.dump(connections, f, indent=2)
        
        return connections

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
        

# Example usage
if __name__ == "__main__":
    scraper = Scrapper()
    try:
        page = scraper.start()
        # Replace with actual profile URL
        connections = scraper.get_connections("https://www.linkedin.com/in/bekim-alliu-183671243/")
        print(f"Found {len(connections)} connections")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        scraper.close() 