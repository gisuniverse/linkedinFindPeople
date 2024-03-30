import asyncio
from playwright.async_api import async_playwright
import os
from dotenv import load_dotenv
import json
from datetime import datetime

load_dotenv()

async def set_cookie_session(context):
    """Set cookie session from environment variable"""
    try:
        cookie_session = os.getenv('LINKEDIN_COOKIE_SESSION')
        if not cookie_session:
            raise ValueError("LINKEDIN_COOKIE_SESSION not found in .env file")
        
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

async def extract_connection_info(page):
    connections = []
    
    item_selectors = [
        '.entity-result__item',
        '.search-result__occluded-item',
        '.reusable-search__result-container',
        '.connection-item'
    ]
    
    for selector in item_selectors:
        elements = await page.query_selector_all(selector)
        if elements:
            print(f"Found connection elements using selector: {selector}")
            for element in elements:
                try:
                    name = None
                    for name_selector in ['.entity-result__title-text', '.actor-name', '.search-result__title']:
                        name_el = await element.query_selector(name_selector)
                        if name_el:
                            name = await name_el.inner_text()
                            name = name.strip()
                            break
                    
                    profile_url = None
                    for link_selector in ['a.app-aware-link', '.search-result__result-link', 'a[href*="/in/"]']:
                        link_el = await element.query_selector(link_selector)
                        if link_el:
                            profile_url = await link_el.get_attribute('href')
                            if profile_url:
                                profile_url = profile_url.split('?')[0]  # Remove query parameters
                                break
                    
                    title = ''
                    for title_selector in ['.entity-result__primary-subtitle', '.search-result__subtitle', '.occupation']:
                        title_el = await element.query_selector(title_selector)
                        if title_el:
                            title = await title_el.inner_text()
                            title = title.strip()
                            break
                    
                    if name and profile_url:
                        connection = {
                            'name': name,
                            'title': title,
                            'profile_url': profile_url
                        }
                        connections.append(connection)
                        print(f"Found connection: {name}")
                
                except Exception as e:
                    print(f"Error extracting connection info: {str(e)}")
                    continue
            
            break  
    
    return connections

async def get_profile_connections(page, profile_url):
    try:
        print(f"Navigating to profile: {profile_url}")
        await page.goto(profile_url, wait_until='domcontentloaded')
        await page.wait_for_selector('body')
        await page.wait_for_timeout(3000)  # Increased wait time

        print("\nTrying to find connection count...")
        connection_count_selectors = [
            "span.t-bold >> text=/\\d+/",  
            "a.link-without-visited-state span.t-bold >> text=/\\d+/",
            "//span[contains(@class, 't-bold')][contains(text(), 'connection')]"
        ]

        connection_count = None
        for selector in connection_count_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    import re
                    numbers = re.findall(r'\d+', text)
                    if numbers:
                        connection_count = int(numbers[0])
                        print(f"Found connection count: {connection_count}")
                        break
            except Exception as e:
                print(f"Error finding connection count with selector {selector}: {str(e)}")

        if not connection_count:
            print("Could not find connection count. The profile might be private or not accessible.")
            return []

        print("\nLooking for connections button...")
        connection_button_selectors = [
            f"a:has-text('{connection_count} connection')",  
            "a:has-text('connections')",  
            "a[href*='search/results/people/?connectionOf']",  
            "//a[contains(@href, 'connectionOf')]",  
        ]

        connection_button = None
        for selector in connection_button_selectors:
            try:
                print(f"Trying selector: {selector}")
                element = await page.wait_for_selector(selector, timeout=5000)
                if element:
                    href = await element.get_attribute('href')
                    if href and ('connectionOf' in href or 'connections' in href.lower()):
                        connection_button = element
                        print(f"Found connections button with selector: {selector}")
                        print(f"Button href: {href}")
                        break
            except Exception as e:
                print(f"Error with selector {selector}: {str(e)}")

        if not connection_button:
            print("Could not find connections button automatically.")
            return []

        print("\nClicking connections button...")
        await connection_button.click()
        await page.wait_for_load_state('networkidle')
        await page.wait_for_timeout(3000)

        await page.screenshot(path='after_click.png')
        print("Saved screenshot to after_click.png")

        print("\nLooking for connections list...")
        connections_list_selectors = [
            ".search-results-container",
            ".reusable-search__entity-result-list",
            ".scaffold-layout__list",
            "//div[contains(@class, 'search-results')]//ul",
        ]

        found_list = False
        for selector in connections_list_selectors:
            try:
                print(f"Trying selector: {selector}")
                await page.wait_for_selector(selector, timeout=5000)
                print(f"Found connections list with selector: {selector}")
                found_list = True
                
                await page.wait_for_timeout(2000)
                
                connections = await extract_connection_info(page)
                
                if connections:
                    print(f"\nFound {len(connections)} connections!")
                    return connections
                else:
                    print("No connections found in the list. Trying next selector...")
                
            except Exception as e:
                print(f"Error with selector {selector}: {str(e)}")

        if not found_list:
            print("\nCould not find connections list.")
            await page.screenshot(path='no_connections_list.png')
            print("Saved debug screenshot to no_connections_list.png")
            
        return []

    except Exception as e:
        print(f"Error getting connections: {str(e)}")
        await page.screenshot(path='error_state.png')
        print("Saved error screenshot to error_state.png")
        return []

async def main():
    profile_url = "https://www.linkedin.com/in/amir-hosein-soofi/"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--start-maximized'
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='Europe/London',
            permissions=['geolocation'],
            java_script_enabled=True,
            accept_downloads=True,
        )
        
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        if not await set_cookie_session(context):
            print("Failed to set cookie session. Please check your .env file!")
            return
        
        page = await context.new_page()
        await page.set_extra_http_headers({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1'
        })
        
        try:
            print("Accessing LinkedIn homepage...")
            await page.goto('https://www.linkedin.com', wait_until='networkidle')
            await page.wait_for_timeout(3000)
            
            connections = await get_profile_connections(page, profile_url)
            
            if connections:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"connections_{timestamp}.json"
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(connections, f, indent=2, ensure_ascii=False)
                
                print(f"\nExtracted {len(connections)} connections")
                print(f"Results saved to: {output_file}")
            else:
                print("\nNo connections were extracted. Please check the screenshots for debugging.")
            
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            await page.screenshot(path='error.png')
            print("Saved error screenshot to error.png")
        
        finally:
            await context.close()
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main()) 