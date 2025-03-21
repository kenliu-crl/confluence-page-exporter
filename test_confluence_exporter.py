#!/usr/bin/env python3
"""
Unit tests for the Confluence Page Exporter
Run with: python3 -m unittest test_confluence_exporter.py
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import json
import re
from bs4 import BeautifulSoup
import sys
import importlib.util

# Import the main script directly (since it has a hyphen in the name)
script_path = os.path.join(os.path.dirname(__file__), "confluence-page-exporter.py")
spec = importlib.util.spec_from_file_location("confluence_exporter", script_path)
confluence_exporter = importlib.util.module_from_spec(spec)
sys.modules["confluence_exporter"] = confluence_exporter
spec.loader.exec_module(confluence_exporter)

# Import the functions from the module
extract_page_id_from_url = confluence_exporter.extract_page_id_from_url
process_macro_placeholders = confluence_exporter.process_macro_placeholders
convert_to_plain_text = confluence_exporter.convert_to_plain_text
process_user_mentions = confluence_exporter.process_user_mentions
extract_username_from_mention = confluence_exporter.extract_username_from_mention
get_user_info = confluence_exporter.get_user_info
clean_html_for_email = confluence_exporter.clean_html_for_email
create_email_html = confluence_exporter.create_email_html
HTML2TEXT_AVAILABLE = confluence_exporter.HTML2TEXT_AVAILABLE

class TestConfluenceExporter(unittest.TestCase):
    """Test cases for the Confluence Email Exporter"""

    def setUp(self):
        """Set up test fixtures"""
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {
            'CONFLUENCE_BASE_URL': 'https://example.atlassian.net',
            'CONFLUENCE_USERNAME': 'test-user',
            'CONFLUENCE_API_TOKEN': 'test-token'
        })
        self.env_patcher.start()
    
    def tearDown(self):
        """Tear down test fixtures"""
        self.env_patcher.stop()
    
    def test_extract_page_id_from_url(self):
        """Test extracting page ID from Confluence URL"""
        # Test various URL formats
        test_cases = [
            ('https://example.atlassian.net/wiki/spaces/SPACE/pages/123456/Page+Title', '123456'),
            ('https://example.atlassian.net/wiki/spaces/SPACE/pages/123456789', '123456789'),
            ('https://example.atlassian.net/wiki/spaces/~user/pages/123456', '123456'),
            ('https://example.atlassian.net/wiki/pages/viewpage.action?pageId=123456', '123456'),
        ]
        
        for url, expected_id in test_cases:
            with self.subTest(url=url):
                self.assertEqual(extract_page_id_from_url(url), expected_id)
    
    def test_extract_page_id_invalid_url(self):
        """Test extracting page ID from invalid URL format"""
        invalid_url = 'https://example.com/not-a-confluence-url'
        with self.assertRaises(ValueError):
            extract_page_id_from_url(invalid_url)
    
    @patch('confluence_exporter.get_user_info')
    def test_extract_username_from_mention(self, mock_get_user_info):
        """Test extracting username from user mention element"""
        # Create a mock user element
        soup = BeautifulSoup('<ri:user ri:account-id="123456" />', 'html.parser')
        user_element = soup.find('ri:user')
        
        # Test with API lookup returning display name
        mock_get_user_info.return_value = {'displayName': 'John Doe', 'username': 'jdoe'}
        self.assertEqual(extract_username_from_mention(user_element), 'John Doe')
        
        # Test with full name attribute
        user_element['ri:full-name'] = 'Jane Smith'
        self.assertEqual(extract_username_from_mention(user_element), 'Jane Smith')
        
        # Test with only username available
        user_element['ri:full-name'] = None
        user_element['ri:username'] = 'jsmith'
        self.assertEqual(extract_username_from_mention(user_element), '@jsmith')
    
    @patch('requests.get')
    def test_get_user_info(self, mock_get):
        """Test getting user info from Confluence API"""
        # Mock the response from the API
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'displayName': 'John Doe',
            'username': 'jdoe',
            'accountId': '123456'
        }
        mock_get.return_value = mock_response
        
        # Test successful API call
        result = get_user_info('123456')
        self.assertEqual(result['displayName'], 'John Doe')
        self.assertEqual(result['username'], 'jdoe')
        
        # Test caching (should not make a second API call)
        mock_get.reset_mock()
        result = get_user_info('123456')
        self.assertEqual(result['displayName'], 'John Doe')
        mock_get.assert_not_called()
        
        # Test user not found
        mock_response.status_code = 404
        mock_get.reset_mock()
        mock_get.return_value = mock_response
        result = get_user_info('not-found')
        self.assertIsNone(result)
    
    def test_process_user_mentions(self):
        """Test processing user mentions in HTML"""
        # Create HTML with user mentions
        html = '''
        <div>
            <p>Mentioned: <ri:user ri:account-id="123456" ri:username="jdoe" /></p>
            <p>Another mention: <ri:user ri:account-id="789012" ri:full-name="Jane Smith" /></p>
            <p>Text mention: @user-123456 in text</p>
            <pre><code>Not processed: @user-123456 in code block</code></pre>
        </div>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        
        # Mock get_user_info to return user data
        with patch('confluence_exporter.get_user_info') as mock_get_user_info:
            mock_get_user_info.side_effect = lambda account_id: (
                {'displayName': 'John Doe', 'username': 'jdoe'} if account_id == '123456'
                else {'displayName': 'Jane Smith', 'username': 'jsmith'} if account_id == '789012'
                else None
            )
            
            # Test with user resolution enabled (default)
            with patch('confluence_exporter.RESOLVE_USERS', True):
                result_soup = process_user_mentions(soup)
                result_html = str(result_soup)
                
                # Check that user mentions are replaced with span elements
                # For the account ID 123456, it would use displayName from the API
                self.assertIn('<span class="confluence-user-mention">@jdoe</span>', result_html)
                # For the account ID 789012, it would use the full-name attribute directly
                self.assertIn('<span class="confluence-user-mention">Jane Smith</span>', result_html)
                
                # Check that text mentions are replaced
                self.assertIn('Text mention: John Doe in text', result_html)
                
                # Check that code block mentions are not processed
                self.assertIn('@user-123456 in code block', result_html)
            
            # Test with user resolution disabled - need a fresh soup
            new_html = '''
            <div>
                <p>Mentioned: <ri:user ri:account-id="123456" ri:username="jdoe" /></p>
                <p>Another mention: <ri:user ri:account-id="789012" ri:full-name="Jane Smith" /></p>
                <p>Text mention: @user-123456 in text</p>
                <pre><code>Not processed: @user-123456 in code block</code></pre>
            </div>
            '''
            new_soup = BeautifulSoup(new_html, 'html.parser')
            
            with patch('confluence_exporter.RESOLVE_USERS', False):
                result_soup = process_user_mentions(new_soup)
                result_html = str(result_soup)
                
                # Check that user mentions show account IDs
                self.assertIn('<span class="confluence-user-mention">@jdoe</span>', result_html)
                
                # Check that text mentions are not replaced when resolution is disabled
                self.assertIn('Text mention: @user-123456 in text', result_html)
    
    @unittest.skipIf(not HTML2TEXT_AVAILABLE, "html2text library not available")
    def test_convert_to_plain_text(self):
        """Test converting HTML to plain text"""
        # Simple HTML to test conversion
        html = '''
        <h1>Test Heading</h1>
        <p>This is a <strong>test</strong> paragraph with a <a href="https://example.com">link</a>.</p>
        <ul>
            <li>Item 1</li>
            <li>Item 2</li>
        </ul>
        '''
        
        result = convert_to_plain_text(html)
        
        # Check that HTML elements are properly converted to plain text
        self.assertIn('# Test Heading', result)
        self.assertIn('This is a **test** paragraph with a [link](https://example.com)', result)
        self.assertIn('* Item 1', result)
        self.assertIn('* Item 2', result)
    
    def test_process_macro_placeholders(self):
        """Test processing Confluence macro placeholders"""
        # Create HTML with Confluence macros
        html = '''
        <div>
            <ac:structured-macro ac:name="info">
                <ac:rich-text-body>This is an info panel</ac:rich-text-body>
            </ac:structured-macro>
            
            <ac:structured-macro ac:name="code">
                <ac:parameter ac:name="language">python</ac:parameter>
                <ac:plain-text-body>print("Hello World")</ac:plain-text-body>
            </ac:structured-macro>
            
            <ac:emoticon ac:emoji-shortname=":smile:" ac:emoji-fallback=":)" />
            
            <ac:link><ri:page ri:content-title="Linked Page" /></ac:link>
        </div>
        '''
        
        result = process_macro_placeholders(html, '123456')
        
        # Check that macros are properly converted
        self.assertIn('<div class="info-panel">', result)
        self.assertIn('<strong>Info: </strong>', result)
        self.assertIn('<code class="language-python">print("Hello World")</code>', result)
        self.assertIn('<span class="confluence-emoticon">:)</span>', result)
        self.assertIn('<span class="confluence-page-link">Linked Page</span>', result)
    
    @patch('confluence_exporter.get_confluence_page')
    def test_create_email_html(self, mock_get_page):
        """Test creating email HTML from Confluence page data"""
        # Mock page data
        page_data = {
            'title': 'Test Page',
            'body': {
                'storage': {
                    'value': '<h1>Test Page Content</h1><p>This is test content</p>'
                }
            },
            'version': {'number': 1},
            'history': {'createdDate': '2023-01-01T12:00:00.000Z'},
            'metadata': {'properties': {}}
        }
        
        with patch('confluence_exporter.process_macro_placeholders', 
                  return_value='<h1>Test Page Content</h1><p>This is processed content</p>'):
            with patch('confluence_exporter.clean_html_for_email', 
                      return_value='<h1>Test Page Content</h1><p>This is cleaned content</p>'):
                result = create_email_html(page_data)
                
                # Check that the result contains the expected content
                self.assertIn('<title>Test Page - Confluence Export</title>', result)
                self.assertIn('<h1>Test Page Content</h1>', result)
                self.assertIn('This is cleaned content', result)


if __name__ == '__main__':
    unittest.main() 