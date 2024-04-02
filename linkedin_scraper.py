import asyncio
from playwright.async_api import async_playwright
import os
from dotenv import load_dotenv
from datetime import datetime
from sqlalchemy import select, func
from models import init_db, Connection, ScrapingHistory

load_dotenv(override=True)

Session = init_db()

def save_connections_to_db(connections_data):
    session = Session()
    try:
        for conn_data in connections_data:
            existing = session.query(Connection).filter_by(
                profile_url=conn_data['profile_url']
            ).first()
            
            if existing:
                existing.name = conn_data['name']
                existing.occupation = conn_data['occupation']
            else:
                new_connection = Connection(
                    name=conn_data['name'],
                    occupation=conn_data['occupation'],
                    profile_url=conn_data['profile_url']
                )
                session.add(new_connection)
        
        scraping_record = ScrapingHistory(
            connections_count=len(connections_data)
        )
        session.add(scraping_record)
        
        session.commit()
        return True
    
    except Exception as e:
        print(f"Error saving to database: {str(e)}")
        session.rollback()
        return False
    
    finally:
        session.close()

async def set_cookie_session(context):
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

def save_single_connection(connection_data):
    session = Session()
    try:
        existing = session.query(Connection).filter_by(
            profile_url=connection_data['profile_url']
        ).first()
        
        if existing:
            existing.name = connection_data['name']
            existing.occupation = connection_data['occupation']
            print(f"Updated existing connection: {connection_data['name']}")
        else:
            new_connection = Connection(
                name=connection_data['name'],
                occupation=connection_data['occupation'],
                profile_url=connection_data['profile_url']
            )
            session.add(new_connection)
            print(f"Saved new connection: {connection_data['name']}")
        
        session.commit()
        return True
    
    except Exception as e:
        print(f"Error saving connection {connection_data['name']}: {str(e)}")
        session.rollback()
        return False
    
    finally:
        session.close()

def record_scraping_session(total_connections):
    session = Session()
    try:
        scraping_record = ScrapingHistory(
            connections_count=total_connections
        )
        session.add(scraping_record)
        session.commit()
        return True
    except Exception as e:
        print(f"Error recording scraping session: {str(e)}")
        session.rollback()
        return False
    finally:
        session.close()

async def get_connections(page):
    print("Navigating to connections page...")
    try:
        await page.goto(
            'https://www.linkedin.com/mynetwork/invite-connect/connections/',
            wait_until='domcontentloaded',
            timeout=60000
        )
    except Exception as e:
        print(f"Navigation error: {str(e)}")
        print("Trying to proceed anyway...")
    
    if 'login' in page.url:
        raise Exception("Not logged in. Please check your cookie session value.")
    
    print("Waiting for page to load...")
    try:
        await page.wait_for_selector('body', timeout=10000)
        await page.wait_for_timeout(5000)
        
        current_url = page.url
        if 'connections' not in current_url:
            print(f"Warning: Unexpected URL: {current_url}")
    except Exception as e:
        print(f"Initial loading error: {str(e)}")
        print("Trying to proceed anyway...")
    
    connections = []
    last_height = 0
    scroll_attempts = 0
    max_scroll_attempts = 100
    total_saved = 0
    failed_saves = 0
    
    while scroll_attempts < max_scroll_attempts:
        print(f"\nScroll attempt {scroll_attempts + 1}/{max_scroll_attempts}")
        
        try:
            for _ in range(3):
                current_position = await page.evaluate('window.pageYOffset')
                await page.evaluate('window.scrollBy(0, window.innerHeight)')
                await page.wait_for_timeout(1000)
                new_position = await page.evaluate('window.pageYOffset')
                if new_position == current_position:
                    print("Reached bottom of page (no scroll possible)")
                    break
            
            await page.wait_for_timeout(2000)
            
            selectors = [
                'div.scaffold-finite-scroll__content > div > div',
                '.mn-connections-list__card',
                '.mn-connection-card',
                '[data-control-name="connection_card"]',
                '.artdeco-list__item',
                'li.mn-connection-card'
            ]
            
            connection_elements = []
            for selector in selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        print(f"Found {len(elements)} elements using selector: {selector}")
                        connection_elements = elements
                        break
                except Exception as e:
                    continue
            
            if not connection_elements:
                print("No connection elements found with any selector")
                await page.screenshot(path=f'debug_scroll_{scroll_attempts}.png')
                continue
            
            new_connections_found = False
            for element in connection_elements:
                try:
                    name = await element.query_selector('.mn-connection-card__name, .artdeco-entity-lockup__title, span[aria-hidden="true"]')
                    name_text = await name.inner_text() if name else "N/A"
                    
                    occupation = await element.query_selector('.mn-connection-card__occupation, .artdeco-entity-lockup__subtitle, .entity-result__primary-subtitle')
                    occupation_text = await occupation.inner_text() if occupation else "N/A"
                    
                    profile_link = await element.query_selector('a[href*="/in/"], a.app-aware-link, .entity-result__title-text > a')
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
                        if save_single_connection(connection):
                            total_saved += 1
                            new_connections_found = True
                        else:
                            failed_saves += 1
                
                except Exception as e:
                    print(f"Error processing connection element: {str(e)}")
                    continue
            
            if not new_connections_found:
                print("No new connections found in this scroll")
                no_new_connections_count += 1
                if no_new_connections_count >= 5:
                    print("\nNo new connections found in last 5 scrolls, assuming we reached the end")
                    break
            else:
                no_new_connections_count = 0
                print(f"\nProgress: {total_saved} connections saved successfully")
                if failed_saves > 0:
                    print(f"Failed saves: {failed_saves}")
            
            scroll_attempts += 1
            await page.wait_for_timeout(1000)
            
        except Exception as e:
            print(f"Error during scroll attempt {scroll_attempts}: {str(e)}")
            await page.wait_for_timeout(2000)
            continue
    
    print(f"\nFinished scrolling. Total connections saved: {total_saved}")
    if failed_saves > 0:
        print(f"Failed to save {failed_saves} connections")
    
    if total_saved > 0:
        record_scraping_session(total_saved)
    
    return connections

def print_stats():
    session = Session()
    try:
        total_connections = session.query(Connection).count()
        
        new_connections = session.query(Connection).filter(
            Connection.first_seen >= datetime.now().replace(second=0, microsecond=0)
        ).count()
        
        last_scrapes = session.query(ScrapingHistory).order_by(
            ScrapingHistory.scrape_date.desc()
        ).limit(2).all()
        
        print("\n=== Scraping Statistics ===")
        print(f"Total connections in database: {total_connections}")
        print(f"New connections added: {new_connections}")
        
        if len(last_scrapes) > 1:
            prev_count = last_scrapes[1].connections_count
            current_count = last_scrapes[0].connections_count
            diff = current_count - prev_count
            print(f"Change since last scrape: {diff:+d}")
        
        print("=========================\n")
    
    finally:
        session.close()

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        
        if not await set_cookie_session(context):
            print("Failed to set cookie session. Please check your .env file!")
            return
        
        page = await context.new_page()
        
        try:
            connections = await get_connections(page)
            print_stats()
            
        except Exception as e:
            print(f"An error occurred: {str(e)}")
        
        finally:
            await context.close()
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main()) 