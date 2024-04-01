from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import os
import time
import random

def get_credentials():
    email = os.getenv('LINKEDIN_EMAIL')
    password = os.getenv('LINKEDIN_PASSWORD')
    
    if not email or not password:
        raise ValueError("Please set LINKEDIN_EMAIL and LINKEDIN_PASSWORD in your .env file")
    
    return email, password

def human_typing(page, selector, text):
    box = page.locator(selector).bounding_box()
    if box:
        x = box['x'] + random.randint(10, int(box['width']-10))
        y = box['y'] + random.randint(5, int(box['height']-5))
        page.mouse.move(x, y)
        time.sleep(random.uniform(0.1, 0.3))
    
    page.click(selector)
    time.sleep(random.uniform(0.1, 0.3))
    
    for char in text:
        page.type(selector, char)
        time.sleep(random.uniform(0.1, 0.4))

def main():
    email, password = get_credentials()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            slow_mo=50
        )
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        
        page = context.new_page()
        
        try:
            print("Navigating to LinkedIn login page...")
            page.goto("https://www.linkedin.com/login", wait_until="networkidle")
            time.sleep(random.uniform(2, 3))
            
            print("Waiting for login form...")
            page.wait_for_selector('input#username', state='visible')
            time.sleep(random.uniform(1, 2))
            
            print(f"Using email: {email}")
            print("Attempting to log in...")
            
            human_typing(page, 'input#username', email)
            time.sleep(random.uniform(0.8, 1.5))
            
            human_typing(page, 'input#password', password)
            time.sleep(random.uniform(0.8, 1.5))
            
            submit_button = page.locator('button[type="submit"]')
            box = submit_button.bounding_box()
            if box:
                x = box['x'] + random.randint(10, int(box['width']-10))
                y = box['y'] + random.randint(5, int(box['height']-5))
                page.mouse.move(x, y)
                time.sleep(random.uniform(0.3, 0.7))
            
            print("Submitting login form...")
            submit_button.click()
            
            time.sleep(random.uniform(3, 4))
            
            print("Verifying login status...")
            
            try:
                success_selectors = [
                    '.feed-identity-module',
                    '.global-nav__me',
                    '.share-box-feed-entry__wrapper',
                    '.global-nav__primary-items'
                ]
                
                logged_in = False
                for selector in success_selectors:
                    try:
                        page.wait_for_selector(selector, timeout=5000)
                        print(f"Login confirmed! Found selector: {selector}")
                        logged_in = True
                        break
                    except:
                        continue
                
                if logged_in:
                    print("Successfully logged in!")
                    time.sleep(2)
                    
                    print("Attempting to navigate to profile...")
                    page.goto("https://www.linkedin.com/in/me", wait_until="networkidle")
                    time.sleep(3)
                    
                    if page.wait_for_selector('.pv-top-card', timeout=10000):
                        print("Successfully loaded profile page!")
                        page.screenshot(path="profile_page.png")
                        print("Profile screenshot saved as 'profile_page.png'")
                        
                        input("Press Enter to close the browser...")
                else:
                    print("Could not verify successful login. Please check the browser for any security challenges.")
                    input("Press Enter to close the browser...")
                
            except Exception as e:
                print("Navigation or verification error occurred.")
                print(f"Error details: {e}")
                input("Press Enter to close the browser...")
            
        except Exception as e:
            print(f"An error occurred: {e}")
            input("Press Enter to close the browser...")
        
        finally:
            browser.close()

if __name__ == "__main__":
    load_dotenv()
    main() 