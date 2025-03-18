#!/usr/bin/env python3
"""
Confluence to Email Exporter

This script extracts content from Confluence pages and converts it to
email-friendly HTML format with proper styling.

Requirements:
- Python 3.6+
- requests
- beautifulsoup4
- html2text (optional, for plain text version)
- python-dotenv (for environment variables)

Usage:
1. Set your Confluence credentials in .env file or as environment variables
2. Run: python confluence_email_exporter.py CONFLUENCE_PAGE_URL [--output OUTPUT_FILE]
3. For batch processing: python confluence_email_exporter.py --batch URLS_FILE
"""

import os
import argparse
import requests
import json
import re
import base64
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urlparse, parse_qs
try:
    import html2text
    HTML2TEXT_AVAILABLE = True
except ImportError:
    HTML2TEXT_AVAILABLE = False
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # .env loading is optional

# Confluence API Configuration
CONFLUENCE_BASE_URL = os.getenv('CONFLUENCE_BASE_URL')
CONFLUENCE_USERNAME = os.getenv('CONFLUENCE_USERNAME')
CONFLUENCE_API_TOKEN = os.getenv('CONFLUENCE_API_TOKEN')

# Email style settings
EMAIL_CSS = """
<style>
    body {
        font-family: Arial, sans-serif;
        line-height: 1.6;
        color: #333;
        max-width: 650px;
        margin: 0 auto;
    }
    h1 {
        color: #0052CC;
        border-bottom: 1px solid #ddd;
        padding-bottom: 10px;
        font-size: 24px;
    }
    h2 {
        color: #0052CC;
        font-size: 20px;
        margin-top: 25px;
    }
    h3 {
        color: #172B4D;
        font-size: 18px;
    }
    a {
        color: #0052CC;
        text-decoration: underline;
    }
    img {
        max-width: 100%;
        height: auto;
    }
    pre, code {
        background-color: #f4f5f7;
        border: 1px solid #dfe1e6;
        border-radius: 3px;
        padding: 10px;
        font-family: monospace;
        font-size: 14px;
        overflow-x: auto;
    }
    table {
        border-collapse: collapse;
        width: 100%;
        margin: 20px 0;
    }
    table, th, td {
        border: 1px solid #dfe1e6;
    }
    th, td {
        padding: 8px 12px;
        text-align: left;
    }
    th {
        background-color: #f4f5f7;
    }
    blockquote {
        border-left: 4px solid #dfe1e6;
        padding-left: 15px;
        margin-left: 0;
        color: #5e6c84;
    }
    .info-panel {
        background-color: #DEEBFF;
        border-left: 4px solid #0052CC;
        padding: 15px;
        margin: 15px 0;
    }
    .warning-panel {
        background-color: #FFFAE6;
        border-left: 4px solid #FFAB00;
        padding: 15px;
        margin: 15px 0;
    }
    .error-panel {
        background-color: #FFEBE6;
        border-left: 4px solid #DE350B;
        padding: 15px;
        margin: 15px 0;
    }
    .success-panel {
        background-color: #E3FCEF;
        border-left: 4px solid #00875A;
        padding: 15px;
        margin: 15px 0;
    }
    .note-panel {
        background-color: #EAE6FF;
        border-left: 4px solid #6554C0;
        padding: 15px;
        margin: 15px 0;
    }
    .email-metadata {
        color: #5e6c84;
        font-size: 12px;
        margin-bottom: 20px;
    }
    .email-footer {
        margin-top: 30px;
        padding-top: 15px;
        border-top: 1px solid #ddd;
        font-size: 12px;
        color: #5e6c84;
    }
</style>
"""


def get_auth_header():
    """Create the HTTP Basic Auth header for Confluence API"""
    if not CONFLUENCE_USERNAME or not CONFLUENCE_API_TOKEN:
        raise ValueError("Confluence credentials not found. Please set CONFLUENCE_USERNAME and CONFLUENCE_API_TOKEN")
    
    auth_str = f"{CONFLUENCE_USERNAME}:{CONFLUENCE_API_TOKEN}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    return {"Authorization": f"Basic {encoded_auth}"}


def get_confluence_page(page_id):
    """Fetch page content from Confluence using the REST API"""
    if not CONFLUENCE_BASE_URL:
        raise ValueError("CONFLUENCE_BASE_URL not set")
    
    url = f"{CONFLUENCE_BASE_URL}/rest/api/content/{page_id}?expand=body.storage,version,history,metadata"
    
    try:
        response = requests.get(url, headers=get_auth_header())
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching page content: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response: {e.response.text}")
        raise


def process_macro_placeholders(html_content, page_id):
    """Process and replace macro placeholders with appropriate HTML"""
    # Use html.parser to better preserve original HTML structure including spans
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Process info/note/warning panels
    for panel in soup.find_all('ac:structured-macro', {'ac:name': ['info', 'note', 'warning', 'error', 'success']}):
        panel_type = panel.get('ac:name', 'note')
        panel_content = panel.find('ac:rich-text-body')
        
        if panel_content:
            # Create a div with the appropriate class based on panel type
            div = soup.new_tag('div')
            div['class'] = f"{panel_type}-panel"
            
            # Instead of just extending with contents, create a proper heading
            # and then add the contents
            heading = soup.new_tag('strong')
            heading.string = panel_type.capitalize() + ": "
            div.append(heading)
            
            # Now add the actual content
            div.extend(panel_content.contents)
            panel.replace_with(div)
    
    # Process ADF panels - newer Confluence format
    for adf_panel in soup.find_all('ac:adf-node', {'type': 'panel'}):
        panel_type = 'note'  # Default
        for attr in adf_panel.find_all('ac:adf-attribute', {'key': 'panel-type'}):
            panel_type = attr.text
        
        panel_content = adf_panel.find('ac:adf-content')
        
        if panel_content:
            div = soup.new_tag('div')
            div['class'] = f"{panel_type}-panel"
            div.extend(panel_content.contents)
            adf_panel.replace_with(div)
    
    # Process code blocks
    for code_block in soup.find_all('ac:structured-macro', {'ac:name': 'code'}):
        language = code_block.find('ac:parameter', {'ac:name': 'language'})
        language = language.text if language else ""
        
        code_content = code_block.find('ac:plain-text-body')
        if code_content:
            pre = soup.new_tag('pre')
            code = soup.new_tag('code')
            if language:
                code['class'] = f"language-{language}"
            code.string = code_content.text
            pre.append(code)
            code_block.replace_with(pre)
    
    # Process emoticons
    for emoticon in soup.find_all('ac:emoticon'):
        emoji = emoticon.get('ac:emoji-shortname', '')
        fallback = emoticon.get('ac:emoji-fallback', '')
        
        # Choose the best representation
        emoji_text = fallback or emoji or ":emoji:"
        emoji_span = soup.new_tag('span')
        emoji_span['class'] = 'confluence-emoticon'
        emoji_span.string = emoji_text
        emoticon.replace_with(emoji_span)
    
    # Process user mentions
    for user in soup.find_all('ri:user'):
        account_id = user.get('ri:account-id', '')
        username = f"@user-{account_id}"
        
        user_span = soup.new_tag('span')
        user_span['class'] = 'confluence-user-mention'
        user_span.string = username
        
        # If inside a link, replace the whole link
        parent_link = user.find_parent('ac:link')
        if parent_link:
            parent_link.replace_with(user_span)
        else:
            user.replace_with(user_span)
    
    # Process page links
    for page_link in soup.find_all('ri:page'):
        title = page_link.get('ri:content-title', 'Linked Page')
        
        link_text = soup.new_tag('span')
        link_text['class'] = 'confluence-page-link'
        link_text.string = title
        
        # If inside a link with body, use that body's text
        parent_link = page_link.find_parent('ac:link')
        if parent_link and parent_link.find('ac:link-body'):
            link_body = parent_link.find('ac:link-body')
            link_text.string = ' '.join(link_body.stripped_strings) or title
        
        if parent_link:
            parent_link.replace_with(link_text)
        else:
            page_link.replace_with(link_text)
    
    # Process tables
    for table in soup.find_all('table'):
        # Set the table class (for styling)
        table['class'] = table.get('class', []) + ['confluence-table']
        
        # Process cell colors
        for cell in table.find_all(['th', 'td']):
            color = cell.get('data-highlight-colour')
            if color:
                cell['style'] = f"background-color: {color};" + (cell.get('style', '') or '')
    
    # Process images - replace with a placeholder or download and embed as base64
    for image in soup.find_all('ac:image'):
        img_src = image.get('ac:src', '')
        if img_src:
            img_tag = soup.new_tag('img')
            # You may want to handle image URLs differently
            img_tag['src'] = f"{CONFLUENCE_BASE_URL}{img_src}" if not img_src.startswith('http') else img_src
            img_tag['alt'] = "Image from Confluence"
            image.replace_with(img_tag)
    
    # Handle block quotes
    for quote in soup.find_all('blockquote'):
        quote['class'] = quote.get('class', []) + ['confluence-blockquote']
    
    return str(soup)


def clean_html_for_email(html_content, page_metadata):
    """Clean and prepare HTML content for email format"""
    # First, ensure we preserve any spans with class="cc-gniwzk" by marking them
    # with a special attribute that won't be affected by BeautifulSoup parsing
    marked_html = html_content.replace('class="cc-gniwzk"', 'class="cc-gniwzk" data-preserve="cc-gniwzk"')
    
    # Process Confluence-specific macros
    processed_html = process_macro_placeholders(marked_html, page_metadata.get('id', ''))
    
    # Use BeautifulSoup to parse and clean HTML
    soup = BeautifulSoup(processed_html, 'html.parser')
    
    # Remove any script tags and on* attributes
    for script in soup.find_all('script'):
        script.decompose()
    
    # Remove any elements with event handlers
    for tag in soup.find_all(True):
        attrs_to_remove = [attr for attr in tag.attrs if attr.startswith('on')]
        for attr in attrs_to_remove:
            del tag[attr]
    
    # Make all links absolute
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        if href.startswith('/'):
            a_tag['href'] = f"{CONFLUENCE_BASE_URL}{href}"
    
    # Check if we have any preserved spans
    preserved_spans = soup.find_all(attrs={"data-preserve": "cc-gniwzk"})
    
    # If we don't have any preserved spans in the processed HTML, try to extract them from the original HTML
    if not preserved_spans:
        # Use regex to find all spans with class="cc-gniwzk"
        cc_spans_pattern = re.compile(r'<span\s+class="cc-gniwzk"[^>]*>(.*?)</span>', re.DOTALL)
        cc_spans = cc_spans_pattern.findall(html_content)
        
        # If we found any cc-gniwzk spans, add them to our output
        if cc_spans:
            # Find a good place to insert them
            body = soup.find('body')
            if not body:
                body = soup.new_tag('body')
                soup.html.append(body) if soup.html else soup.append(soup.new_tag('html')).append(body)
            
            # Add the spans to the beginning of the body
            for span_content in cc_spans:
                span = soup.new_tag('span')
                span['class'] = 'cc-gniwzk'
                # Use BeautifulSoup to parse the content to preserve any HTML inside the span
                content_soup = BeautifulSoup(span_content, 'html.parser')
                for content in content_soup.contents:
                    span.append(content)
                body.insert(0, span)
    
    # Add metadata section at the top
    metadata_div = soup.new_tag('div')
    metadata_div['class'] = 'email-metadata'
    
    title = page_metadata.get('title', 'Confluence Page')
    last_updated = page_metadata.get('lastUpdated', datetime.now().isoformat())
    try:
        last_updated_date = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
        formatted_date = last_updated_date.strftime('%B %d, %Y at %I:%M %p')
    except (ValueError, TypeError):
        formatted_date = last_updated
    
    metadata_div.string = f"From Confluence: {title} (Last updated: {formatted_date})"
    
    # Add footer with link to original
    footer_div = soup.new_tag('div')
    footer_div['class'] = 'email-footer'
    page_id = page_metadata.get('id', '')
    view_url = f"{CONFLUENCE_BASE_URL}/pages/viewpage.action?pageId={page_id}" if page_id else '#'
    
    footer_link = soup.new_tag('a')
    footer_link['href'] = view_url
    footer_link.string = "View this page in Confluence"
    
    footer_div.append("This email was automatically generated from a Confluence page. ")
    footer_div.append(footer_link)
    
    # Assemble the final document
    body = soup.find('body')
    if not body:
        body = soup.new_tag('body')
        soup.html.append(body) if soup.html else soup.append(soup.new_tag('html')).append(body)
    
    body.insert(0, metadata_div)
    body.append(footer_div)
    
    # Return the final HTML
    return str(soup)


def convert_to_plain_text(html_content):
    """Convert HTML to plain text format"""
    if not HTML2TEXT_AVAILABLE:
        print("HTML2TEXT library not available. Install with: pip install html2text")
        return "HTML2TEXT library not available. Install with: pip install html2text"
    
    print("Converting HTML to plain text format...")
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.inline_links = True
    h.unicode_snob = True
    h.body_width = 0  # No wrapping
    
    return h.handle(html_content)


def create_email_html(page_data):
    """Create the final HTML for email with appropriate styling"""
    page_id = page_data.get('id', '')
    page_title = page_data.get('title', 'Confluence Page')
    page_version = page_data.get('version', {}).get('number', 1)
    
    # Extract the HTML content
    html_content = page_data.get('body', {}).get('storage', {}).get('value', '')
    
    # Prepare metadata for the email
    page_metadata = {
        'id': page_id,
        'title': page_title,
        'version': page_version,
        'lastUpdated': page_data.get('version', {}).get('when', '')
    }
    
    # Clean and structure the HTML for email
    email_body_html = clean_html_for_email(html_content, page_metadata)
    
    # Create the final HTML document
    email_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page_title} - Confluence Export</title>
    {EMAIL_CSS}
</head>
{email_body_html}
</html>
"""
    
    return email_html


def save_output(content, output_file, is_html=True):
    """Save the content to a file"""
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Output saved to {output_file}")
    except Exception as e:
        print(f"Error saving file: {e}")


def check_and_setup_env_variables():
    """
    Check if required environment variables are set.
    If not, prompt the user for input and save to .env file.
    """
    global CONFLUENCE_BASE_URL, CONFLUENCE_USERNAME, CONFLUENCE_API_TOKEN
    
    env_vars_missing = not all([CONFLUENCE_BASE_URL, CONFLUENCE_USERNAME, CONFLUENCE_API_TOKEN])
    
    if env_vars_missing:
        print("\n===== Confluence API Configuration =====")
        print("Required environment variables are not set.")
        print("Please provide the following information to configure the application:")
        
        if not CONFLUENCE_BASE_URL:
            CONFLUENCE_BASE_URL = input("\nConfluence Base URL (e.g., https://yourcompany.atlassian.net/wiki): ")
        
        if not CONFLUENCE_USERNAME:
            CONFLUENCE_USERNAME = input("\nConfluence Username (your Atlassian email): ")
        
        if not CONFLUENCE_API_TOKEN:
            print("\nTo generate an API token:")
            print("1. Go to: https://id.atlassian.com/manage-profile/security/api-tokens")
            print("2. Click 'Create API token'")
            print("3. Give it a name like 'Confluence Email Exporter'")
            print("4. Copy the generated token")
            CONFLUENCE_API_TOKEN = input("\nConfluence API Token: ")
        
        # Write to .env file
        with open(".env", "w") as env_file:
            env_file.write("# Confluence API Configuration\n")
            env_file.write(f"CONFLUENCE_BASE_URL={CONFLUENCE_BASE_URL}\n")
            env_file.write(f"CONFLUENCE_USERNAME={CONFLUENCE_USERNAME}\n")
            env_file.write(f"CONFLUENCE_API_TOKEN={CONFLUENCE_API_TOKEN}\n")
        
        print("\nConfiguration saved to .env file.")
        
        # Return True if we had to set up the environment
        return True
    
    return False


def extract_page_id_from_url(url):
    """
    Extract the page ID from a Confluence URL.
    Handles various Confluence URL formats.
    """
    # Try to parse the URL
    parsed_url = urlparse(url)
    
    # Check for pageId in query parameters (common in newer Confluence URLs)
    query_params = parse_qs(parsed_url.query)
    if 'pageId' in query_params:
        return query_params['pageId'][0]
    
    # Check for /pages/viewpage.action?pageId=XXXXX format
    if 'viewpage.action' in parsed_url.path and 'pageId' in query_params:
        return query_params['pageId'][0]
    
    # Check for /pages/XXXXX format
    pages_match = re.search(r'/pages/(\d+)', url)
    if pages_match:
        return pages_match.group(1)
    
    # Check for /display/SPACE/PAGE+NAME format with ID in URL fragment
    fragment = parsed_url.fragment
    if fragment and 'pageId=' in fragment:
        fragment_params = parse_qs(fragment)
        if 'pageId' in fragment_params:
            return fragment_params['pageId'][0]
    
    # Check for /wiki/spaces/SPACE/pages/XXXXX format
    spaces_match = re.search(r'/spaces/[^/]+/pages/(\d+)', url)
    if spaces_match:
        return spaces_match.group(1)
    
    raise ValueError("Could not extract page ID from the provided URL. Please check the URL format.")


def read_urls_from_file(file_path):
    """
    Read a list of Confluence URLs from a file.
    Each URL should be on its own line.
    Ignores empty lines and lines starting with #.
    """
    urls = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    urls.append(line)
        
        if not urls:
            print(f"Warning: No valid URLs found in {file_path}")
        
        return urls
    except Exception as e:
        print(f"Error reading URLs file: {e}")
        return []


def process_single_url(url, output_dir=None, generate_text=False):
    """
    Process a single Confluence URL and generate the exported HTML/text.
    Returns True if successful, False otherwise.
    """
    try:
        # Extract page ID from URL
        page_id = extract_page_id_from_url(url)
        print(f"Processing URL: {url}")
        print(f"Extracted page ID: {page_id}")
        
        # Fetch the page data from Confluence
        print(f"Fetching page content from Confluence...")
        page_data = get_confluence_page(page_id)
        
        # Create email HTML
        print(f"Converting Confluence content to email-friendly HTML...")
        email_html = create_email_html(page_data)
        
        # Create output filename
        page_title = page_data.get('title', 'confluence_page').replace(' ', '_')
        # Sanitize filename by removing invalid characters
        page_title = re.sub(r'[\\/*?:"<>|]', "", page_title)
        
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{page_title}.html")
        else:
            output_file = f"{page_title}.html"
        
        # Save the HTML output
        save_output(email_html, output_file)
        
        # Generate and save plain text version if requested
        if generate_text:
            plain_text = convert_to_plain_text(email_html)
            text_output_file = output_file.replace('.html', '.txt')
            save_output(plain_text, text_output_file, is_html=False)
            print(f"Plain text version saved to {text_output_file}")
        
        return True
    
    except Exception as e:
        print(f"Error processing URL {url}: {e}")
        return False


def main():
    """Main function to run the script"""
    print("Confluence Email Exporter")
    print("------------------------")
    
    parser = argparse.ArgumentParser(description='Export Confluence page to email-friendly format')
    
    # Create a mutually exclusive group for URL or batch file
    url_group = parser.add_mutually_exclusive_group(required=True)
    url_group.add_argument('url', nargs='?', help='Confluence page URL to export')
    url_group.add_argument('--batch', help='File containing list of Confluence URLs to process')
    
    parser.add_argument('--output', help='Output file path (default: confluence_export.html)')
    parser.add_argument('--output-dir', help='Directory to save output files (for batch processing)')
    parser.add_argument('--text', action='store_true', help='Also generate plain text version')
    parser.add_argument('--base-url', help='Confluence base URL (overrides environment variable)')
    parser.add_argument('--username', help='Confluence username (overrides environment variable)')
    parser.add_argument('--token', help='Confluence API token (overrides environment variable)')
    
    args = parser.parse_args()
    
    # Override environment variables if provided in arguments
    global CONFLUENCE_BASE_URL, CONFLUENCE_USERNAME, CONFLUENCE_API_TOKEN
    if args.base_url:
        CONFLUENCE_BASE_URL = args.base_url
    if args.username:
        CONFLUENCE_USERNAME = args.username
    if args.token:
        CONFLUENCE_API_TOKEN = args.token
    
    # Check and set up environment variables if needed
    check_and_setup_env_variables()
    
    # Handle batch processing
    if args.batch:
        urls = read_urls_from_file(args.batch)
        if not urls:
            print("No valid URLs to process.")
            return 1
        
        print(f"Processing {len(urls)} URLs...")
        success_count = 0
        
        for url in urls:
            if process_single_url(url, args.output_dir, args.text):
                success_count += 1
        
        print(f"Completed processing {success_count} out of {len(urls)} URLs successfully.")
        return 0 if success_count == len(urls) else 1
    
    # Handle single URL processing
    if args.url:
        # Set default output file if not provided
        output_file = args.output or 'confluence_export.html'
        
        try:
            # Extract page ID from URL
            page_id = extract_page_id_from_url(args.url)
            print(f"Extracted page ID: {page_id}")
            
            # Fetch the page data from Confluence
            page_data = get_confluence_page(page_id)
            
            # Create email HTML
            email_html = create_email_html(page_data)
            
            # Save the HTML output
            save_output(email_html, output_file)
            
            # Generate and save plain text version if requested
            if args.text:
                plain_text = convert_to_plain_text(email_html)
                text_output_file = output_file.replace('.html', '.txt')
                save_output(plain_text, text_output_file, is_html=False)
                print(f"Plain text version saved to {text_output_file}")
            
        except Exception as e:
            print(f"Error: {e}")
            return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
