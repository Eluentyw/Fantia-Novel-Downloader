import os
import re
import time
import requests
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import traceback
import configparser
from typing import List, Dict, Optional

# ==============================================================================
# Configuration Management
# ==============================================================================

def create_default_config(filename: str = "config.ini") -> None:
    """
    Generates the default configuration file (config.ini).
    This function is called on the first run if the config file does not exist.
    """
    config = configparser.ConfigParser()
    config['Authentication'] = {
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.121 Safari/537.36',
        'cookie': 'Please paste the Cookie string copied from your browser here',
        'x_csrf_token': 'Please paste the X-Csrf-Token copied from your browser here'
    }
    config['Settings'] = {
        'download_scope': 'all',
        'root_output_dir': 'fantia_novels',
        'request_delay': '1.5'
    }
    with open(filename, 'w', encoding='utf-8') as configfile:
        config.write(configfile)
    print(f"INFO: Configuration file '{filename}' has been created.")
    print("INFO: Please open the file, fill in your authentication details, and run the program again.")

def load_config(filename: str = "config.ini") -> Optional[configparser.ConfigParser]:
    """
    Loads the configuration file.
    If the file does not exist, it creates a default one and returns None.

    Args:
        filename (str): The name of the configuration file.

    Returns:
        Optional[configparser.ConfigParser]: The loaded config object, or None if it was just created.
    """
    if not os.path.exists(filename):
        create_default_config(filename)
        return None
    
    config = configparser.ConfigParser()
    config.read(filename, encoding='utf-8')
    return config

# ==============================================================================
# Utility Functions
# ==============================================================================

def sanitize_filename(filename: str) -> str:
    """
    Replaces characters that are invalid for file or directory names with a hyphen.

    Args:
        filename (str): The string to sanitize.

    Returns:
        str: The sanitized string.
    """
    invalid_chars = r'[\\/:*?"<>|]'
    return re.sub(invalid_chars, '-', filename)

# ==============================================================================
# Core Logic
# ==============================================================================

def get_all_post_ids(fanclub_url: str, headers: Dict[str, str], delay: float) -> List[int]:
    """
    Crawls through the post list pages of a given fan club to collect all post IDs.
    This function directly parses HTML (scraping).

    Args:
        fanclub_url (str): The URL of the fan club's post list page.
        headers (Dict[str, str]): HTTP headers to use for the request.
        delay (float): The delay in seconds between each page request.

    Returns:
        List[int]: A list of all collected post IDs.
    """
    post_ids: List[int] = []
    current_url: Optional[str] = fanclub_url
    page_num = 1
    
    path_segments = urlparse(fanclub_url).path.strip('/').split('/')
    fanclub_id = path_segments[1] if len(path_segments) > 1 else "Unknown"

    print(f"\n--- [Phase 1] Starting Post ID Collection for Fan Club ID: {fanclub_id} ---")
    
    while current_url:
        print(f"  - Scanning page {page_num}...")
        try:
            response = requests.get(current_url, headers=headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Check login status via JSON data embedded in the page
            frontend_params_tag = soup.find('script', id='frontend-params')
            if not frontend_params_tag or '"is_logged_in": false' in frontend_params_tag.string:
                 print("\nERROR: Login failed. The 'cookie' in config.ini may be invalid or expired.")
                 return []
            
            links = soup.select('div.module.post a.link-block')
            if not links:
                print("  - No post links found on this page.")
                break
                
            for link in links:
                href = link.get('href')
                if href and '/posts/' in href:
                    try:
                        post_id = int(href.split('/')[-1])
                        if post_id not in post_ids:
                            post_ids.append(post_id)
                    except (ValueError, IndexError):
                        continue
            
            next_page_tag = soup.select_one('ul.pagination li.page-item:not(.disabled) a[rel="next"]')
            if next_page_tag and next_page_tag.get('href'):
                current_url = urljoin(fanclub_url, str(next_page_tag['href']))
                page_num += 1
            else:
                current_url = None
                print("  - Reached the last page.")
            time.sleep(delay)
        except requests.exceptions.RequestException as e:
            print(f"ERROR: Failed to fetch page '{current_url}': {e}")
            return []

    print(f"  - ID collection complete. Found a total of {len(post_ids)} posts.")
    return post_ids

def scrape_and_save_post_api(post_id: int, headers: Dict[str, str], csrf_token: str, root_output_dir: str, scope: str) -> None:
    """
    Fetches data for a single post from the Fantia API and saves it as a text file
    based on the specified scope.

    Args:
        post_id (int): The ID of the post to download.
        headers (Dict[str, str]): Base HTTP headers for the request.
        csrf_token (str): The CSRF token required for API requests.
        root_output_dir (str): The root directory for saving files.
        scope (str): The download scope ('all', 'paid', or 'free').
    """
    api_url = f"https://fantia.jp/api/v1/posts/{post_id}"
    print(f"  - Fetching data for ID: {post_id} from API...")
    try:
        api_headers = headers.copy()
        api_headers.update({
            'Accept': 'application/json, text/plain, */*',
            'X-Csrf-Token': csrf_token,
            'X-Requested-With': 'XMLHttpRequest',
        })
        
        response = requests.get(api_url, headers=api_headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        post_data = data.get("post")
        if not post_data:
            print(f"  - ERROR: Post data not found in API response (ID: {post_id}).")
            return

        title = post_data.get("title", f"No Title {post_id}")
        
        # Determine if the post is for paid members
        is_paid = any(c.get("plan") and c["plan"].get("price", 0) > 0 for c in post_data.get("post_contents", []))

        # Skip processing based on the download scope
        if scope == 'paid' and not is_paid:
            print(f"  - SKIP: Free post is outside the 'paid' scope: '{title}'.")
            return
        if scope == 'free' and is_paid:
            print(f"  - SKIP: Paid post is outside the 'free' scope: '{title}'.")
            return

        # Extract the post body, checking multiple possible keys to handle different post types
        full_content = None
        if post_data.get("post_contents"):
            content_parts = [c["comment"] for c in post_data["post_contents"] if c.get("comment")]
            if content_parts:
                full_content = "\n\n".join(content_parts)
        if full_content is None and post_data.get("comment"):
            full_content = post_data["comment"]
        if full_content is None and post_data.get("blog_comment"):
            full_content = post_data["blog_comment"]
        
        if full_content is None:
            print(f"  - WARN: Text content not found for post {post_id} ('{title}').")
            return

        # Create a subdirectory for the fan club and save the file
        fanclub_name = post_data.get("fanclub", {}).get("fanclub_name_with_creator_name", f"fanclub_{post_data.get('fanclub', {}).get('id')}")
        sanitized_fanclub_name = sanitize_filename(fanclub_name)
        output_subdir = os.path.join(root_output_dir, sanitized_fanclub_name)
        os.makedirs(output_subdir, exist_ok=True)
        
        filename = sanitize_filename(title) + ".txt"
        filepath = os.path.join(output_subdir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"Title: {title}\n")
            f.write(f"URL: https://fantia.jp/posts/{post_id}\n")
            f.write("=" * 40 + "\n\n")
            f.write(full_content)
        print(f"  - OK: Saved -> {filepath}")

    except requests.exceptions.RequestException as e:
        print(f"  - ERROR: API request failed (ID: {post_id}): {e}")
    except json.JSONDecodeError:
        print(f"  - ERROR: Failed to decode API response as JSON (ID: {post_id}).")
    except Exception as e:
        print(f"  - ERROR: An unexpected error occurred (ID: {post_id}): {e}")

# ==============================================================================
# Main Execution Block
# ==============================================================================

def main():
    """
    Main entry point of the program.
    Loads configuration and processes each fan club URL from the list file.
    """
    print("Starting Fantia-Novel-Downloader_v1.1")
    try:
        config = load_config()
        if config is None:
            return

        auth_conf = config['Authentication']
        settings_conf = config['Settings']
        
        # Load and validate settings
        user_agent = auth_conf.get('user_agent')
        cookie = auth_conf.get('cookie')
        csrf_token = auth_conf.get('x_csrf_token')
        scope = settings_conf.get('download_scope', 'all').lower()
        root_dir = settings_conf.get('root_output_dir', 'fantia_novels')
        delay = settings_conf.getfloat('request_delay', 1.5)

        if "Please paste" in cookie or "Please paste" in csrf_token or not cookie or not csrf_token:
            print("\nERROR: 'cookie' or 'x_csrf_token' is not set in config.ini.")
            return
        if scope not in ['all', 'paid', 'free']:
            print(f"\nERROR: Invalid 'download_scope' in config.ini: '{scope}'. Must be one of 'all', 'paid', or 'free'.")
            return

        # Load target URLs from DL-links.txt
        links_file = "DL-links.txt"
        try:
            with open(links_file, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip() and "fantia.jp" in line]
            if not urls:
                print(f"\nERROR: No valid URLs found in '{links_file}'.")
                return
            print(f"INFO: Loaded {len(urls)} URL(s) from '{links_file}'.")
        except FileNotFoundError:
            print(f"\nERROR: '{links_file}' not found. Please create it in the same directory and add target URLs.")
            return

        base_headers = { 'Cookie': cookie, 'User-Agent': user_agent }
        os.makedirs(root_dir, exist_ok=True)
        print(f"INFO: Root save directory: '{os.path.abspath(root_dir)}'")
        print(f"INFO: Download scope: '{scope}'")

        # Process each URL sequentially
        for i, url in enumerate(urls, 1):
            print(f"\n===== Processing URL {i}/{len(urls)}: {url} =====")
            
            if '/fanclubs/' in url:
                # Fan club URL: get all post IDs and loop through them
                post_ids = get_all_post_ids(url, base_headers, delay)
                if not post_ids:
                    print(f"WARN: Failed to retrieve post IDs for the fan club. Skipping.")
                    continue
                
                print(f"\n--- Starting download of {len(post_ids)} individual posts ---")
                for j, post_id in enumerate(post_ids, 1):
                    print(f"-> Processing: {j}/{len(post_ids)}")
                    scrape_and_save_post_api(post_id, base_headers, csrf_token, root_dir, scope)
                    time.sleep(delay)

            elif '/posts/' in url:
                # Individual post URL: extract ID and process once
                try:
                    path = urlparse(url).path
                    post_id = int(path.strip('/').split('/')[-1])
                    print(f"  - Extracted Post ID: {post_id}.")
                    scrape_and_save_post_api(post_id, base_headers, csrf_token, root_dir, scope)
                    time.sleep(delay)
                except (ValueError, IndexError):
                    print(f"  - ERROR: Could not extract a valid post ID from the URL. Skipping.")
            
            else:
                print(f"WARN: Unsupported URL format. Skipping.")

        print("\nAll tasks completed successfully.")

    except Exception as e:
        print("\n" + "="*60)
        print("           An unexpected error occurred")
        print("="*60)
        traceback.print_exc()
        print("="*60)
        print(f"ERROR: {e}")
    finally:
        input("\nPress Enter to exit...")

if __name__ == '__main__':
    main()
