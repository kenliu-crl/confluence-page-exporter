# Confluence Page Exporter

A Python tool that extracts content from Confluence pages and converts it to email-friendly HTML format with proper styling.

## Features

- Extract content from Confluence pages using the Atlassian REST API
- Convert Confluence content to clean, email-friendly HTML
- Maintain formatting, tables, and images
- Process special Confluence elements like panels, emoticons, user mentions, and page links
- Handle ADF (Atlassian Document Format) content
- Generate plain text versions of the content (optional)
- Automatically handle authentication and configuration
- Batch processing for exporting multiple pages at once

## Requirements

- Python 3.6+
- Required Python packages (installed via `pip`):
  - requests
  - beautifulsoup4
  - python-dotenv
  - html2text (optional, for plain text version)

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/confluence-page-exporter.git
   cd confluence-page-exporter
   ```

2. Set up a virtual environment (recommended):
   ```
   ./setup-venv.sh
   ```
   Or manually:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

## Configuration

On first run, the script will prompt you for the required Confluence API credentials:

1. **Confluence Base URL**: Your Atlassian Confluence URL (e.g., `https://yourcompany.atlassian.net/wiki`)
2. **Confluence Username**: Your Atlassian account email
3. **Confluence API Token**: An API token for authentication

To generate an API token:
1. Go to: https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Give it a name like "Confluence Email Exporter"
4. Set the expiration date far in the future
5. Copy the generated token

These credentials will be saved to a `.env` file in the project directory for future use.

## Usage

### Single Page Export

Basic usage:
```
python3 confluence-page-exporter.py CONFLUENCE_PAGE_URL
```

Where `CONFLUENCE_PAGE_URL` is the full URL of the Confluence page you want to export. The script will automatically extract the page ID from the URL.

### Batch Processing

To process multiple Confluence pages at once:
```
python3 confluence-page-exporter.py --batch-file urls_file.txt --output-dir exports
```

The `urls_file.txt` should contain one Confluence URL per line. Empty lines and lines starting with `#` are ignored.

Example `urls_file.txt`:
```
# Meeting notes
https://yourcompany.atlassian.net/wiki/spaces/TEAM/pages/123456/Meeting+Notes
https://yourcompany.atlassian.net/wiki/spaces/TEAM/pages/789012/Project+Planning

# Documentation
https://yourcompany.atlassian.net/wiki/spaces/DOCS/pages/345678/User+Guide
```

### Options

- `--output FILE`: Output file path for single page export (default: confluence_export.html)
- `--output-dir DIR`: Directory to save output files (for batch processing)
- `--text`: Also generate plain text version
- `--base-url URL`: Confluence base URL (overrides environment variable)
- `--username USERNAME`: Confluence username (overrides environment variable)
- `--token TOKEN`: Confluence API token (overrides environment variable)
- `--batch-file FILE`: File containing list of Confluence URLs to process in batch

### Examples

Export a page using its URL:
```
python3 confluence-page-exporter.py "https://yourcompany.atlassian.net/wiki/spaces/SPACE/pages/123456/Page+Title"
```

Export a page to a specific file and generate a text version:
```
python3 confluence-page-exporter.py "https://yourcompany.atlassian.net/wiki/spaces/SPACE/pages/123456/Page+Title" --output my_page.html --text
```

Export multiple pages to an 'exports' directory with text versions:
```
python3 confluence-page-exporter.py --batch-file sample_urls.txt --output-dir exports --text
```


## Supported Confluence Elements

The exporter handles various Confluence-specific elements:

- **Panels**: Info, note, warning, error, and success panels
- **Code Blocks**: With syntax highlighting
- **Tables**: Including cell background colors
- **Images**: Both embedded and linked
- **Emoticons**: Preserves emoji characters
- **User Mentions**: Automatically resolves @user-ID to real names (can be disabled with `--no-resolve-users`)
- **Page Links**: Preserves linked page titles
- **Block Quotes**: Properly formatted with styling
- **ADF Content**: Support for newer Atlassian Document Format

## Development

### Running Tests

The exporter comes with unit tests to ensure everything works correctly. To run the tests:

```
python3 -m unittest test_confluence_exporter.py
```

The tests cover:
- URL parsing and page ID extraction
- User mention resolution
- Confluence macro handling
- HTML to plain text conversion
- API integration

### Test Coverage

The unit tests cover the most important aspects of the functionality:

1. **URL Parsing**: Tests various Confluence URL formats to ensure page IDs are correctly extracted.
2. **User Resolution**: Tests the core feature of resolving user mentions from alphanumeric IDs to real names.
3. **Macro Processing**: Tests the conversion of Confluence macros like panels, code blocks, and emoticons to HTML.
4. **HTML to Text Conversion**: Tests the conversion of HTML content to plain text format.
5. **API Mocking**: Uses mock objects to simulate API responses and test handling of various scenarios.

### Writing New Tests

To add new tests for additional functionality:

1. Create a new test method in the `TestConfluenceExporter` class in `test_confluence_exporter.py`.
2. Use Python's `unittest.mock` to mock any external dependencies like API calls.
3. Create simple HTML samples that represent Confluence content.
4. Test both the normal flow and edge cases.

Example of adding a new test:

```python
def test_my_new_feature(self):
    # Create sample input
    sample_html = """
    <div>
        <!-- Your test HTML -->
    </div>
    """
    
    # Call the function being tested
    result = my_function(sample_html)
    
    # Assert expected outcomes
    self.assertIn("expected output", result)
    self.assertNotIn("unwanted output", result)
```

## License

This project is licensed under the terms of the included LICENSE file. 