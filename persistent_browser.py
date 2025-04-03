from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from typing import Optional
import os

class PersistentBrowser:
    def __init__(self, storage_state_path: str = "browser_state.json"):
        """
        Initialize the persistent browser manager.
        
        Args:
            storage_state_path (str): Path where browser state will be saved
        """
        self.storage_state_path = storage_state_path
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
    def start(self) -> Page:
        """
        Start or restore a browser session.
        
        Returns:
            Page: The browser page object
        """
        playwright = sync_playwright().start()
        
        # Create browser
        self.browser = playwright.chromium.launch(headless=False)
        
        # Create or restore context with stored state
        context_params = {}
        if os.path.exists(self.storage_state_path):
            context_params["storage_state"] = self.storage_state_path
            
        self.context = self.browser.new_context(**context_params)
        self.page = self.context.new_page()
        
        return self.page
    
    def save_state(self):
        """Save the current browser state"""
        if self.context:
            self.context.storage_state(path=self.storage_state_path)
    
    def close(self):
        """Close the browser and save state"""
        try:
            self.save_state()
        finally:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()

# Example usage
if __name__ == "__main__":
    # Initialize the persistent browser
    browser_manager = PersistentBrowser()
    
    try:
        # Start or restore the browser session
        page = browser_manager.start()
        
        # Navigate to a website
        page.goto("https://www.linkedin.com")
        
        # Do your work here...
        # Save state periodically
        browser_manager.save_state()
        
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # This will save state and close everything properly
        browser_manager.close() 