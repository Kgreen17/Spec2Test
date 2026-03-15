"""Link extractor: fetches and extracts content from Confluence pages and Jira tickets.

Supports:
- Confluence pages (cloud and server)
- Jira tickets/issues

Uses REST APIs to fetch content from these platforms.
"""

import re
import json
from typing import Dict, Optional, Tuple
import requests
from urllib.parse import urlparse, parse_qs
import logging

logger = logging.getLogger(__name__)


def extract_confluence_url_parts(url: str) -> Optional[Tuple[str, str, str]]:
    """Extract base URL, space key, and page ID from Confluence URL.
    
    Supports formats like:
    - https://domain.atlassian.net/wiki/spaces/SPACEKEY/pages/123456/PageTitle
    - https://domain.atlassian.net/wiki/spaces/SPACEKEY/pages/123456
    - https://confluence.domain.com/display/SPACEKEY/PageTitle
    - https://confluence.domain.com/pages/viewpage.action?pageId=123456&spaceKey=SPACEKEY
    """
    try:
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        
        # Cloud format: /wiki/spaces/{spaceKey}/pages/{pageId}
        match = re.search(r'/wiki/spaces/([^/]+)/pages/(\d+)', url)
        if match:
            space_key = match.group(1)
            page_id = match.group(2)
            return domain, space_key, page_id
        
        # Server format: /display/{spaceKey}/
        match = re.search(r'/display/([^/]+)', url)
        if match:
            space_key = match.group(1)
            # Extract page ID from query param if available
            query_params = parse_qs(parsed.query)
            page_id = query_params.get('pageId', [None])[0]
            return domain, space_key, page_id
        
        return None
    except Exception as e:
        logger.error(f"Error parsing Confluence URL: {e}")
        return None


def extract_jira_url_parts(url: str) -> Optional[Tuple[str, str]]:
    """Extract base URL and issue key from Jira URL.
    
    Supports formats like:
    - https://domain.atlassian.net/browse/PROJECT-123
    - https://jira.domain.com/browse/PROJECT-123
    - https://domain.atlassian.net/jira/software/projects/PROJECT/issues/PROJECT-123
    """
    try:
        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        
        # Format: /browse/{issueKey}
        match = re.search(r'/browse/([A-Z]+-\d+)', url)
        if match:
            issue_key = match.group(1)
            return domain, issue_key
        
        # Format: /issues/{issueKey}
        match = re.search(r'/issues/([A-Z]+-\d+)', url)
        if match:
            issue_key = match.group(1)
            return domain, issue_key
        
        return None
    except Exception as e:
        logger.error(f"Error parsing Jira URL: {e}")
        return None


def fetch_confluence_content(url: str, auth: Optional[Tuple[str, str]] = None) -> Optional[Dict]:
    """Fetch Confluence page content using REST API.
    
    Args:
        url: Confluence page URL
        auth: Optional tuple of (username, api_token) for authentication
    
    Returns:
        Dict with 'title' and 'content' keys, or None if fetch fails
    """
    url_parts = extract_confluence_url_parts(url)
    if not url_parts:
        logger.error(f"Could not parse Confluence URL: {url}")
        return None
    
    domain, space_key, page_id = url_parts
    
    try:
        if page_id:
            # Use page ID for API call (more reliable)
            api_url = f"{domain}/wiki/api/v2/pages/{page_id}"
        else:
            logger.warning(f"No page ID found in URL: {url}")
            # Try fetching from the web page itself
            return fetch_confluence_from_html(url, auth)
        
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'Spec2Test/1.0'
        }
        
        response = requests.get(api_url, headers=headers, auth=auth, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Extract title and body
        title = data.get('title', 'Untitled')
        
        # Get body content
        body_content = ''
        if 'body' in data:
            body = data['body']
            if isinstance(body, dict):
                # Try different storage formats
                body_content = body.get('storage', {}).get('value', '')
                if not body_content:
                    body_content = body.get('view', {}).get('value', '')
        
        if not body_content:
            logger.warning(f"Could not extract body content from Confluence page")
            body_content = data.get('description', '')
        
        # Clean HTML if present
        body_content = clean_html_content(body_content)
        
        return {
            'title': title,
            'content': body_content,
            'source': url,
            'type': 'confluence'
        }
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Confluence content: {e}")
        return None


def fetch_confluence_from_html(url: str, auth: Optional[Tuple[str, str]] = None) -> Optional[Dict]:
    """Fallback: fetch Confluence page content by parsing HTML.
    
    This is used when page ID is not available in the URL.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("BeautifulSoup4 required for HTML parsing")
        return None
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Spec2Test/1.0)'
        }
        
        response = requests.get(url, headers=headers, auth=auth, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract title
        title_elem = soup.find('h1', class_='page-title')
        if title_elem:
            title = title_elem.get_text(strip=True)
        else:
            title = soup.find('title')
            title = title.get_text(strip=True) if title else 'Untitled'
        
        # Extract main content
        content_elem = soup.find('div', class_='wiki-content')
        if not content_elem:
            content_elem = soup.find('div', class_='page-content')
        if not content_elem:
            content_elem = soup.find('article')
        
        if content_elem:
            content = content_elem.get_text(separator='\n')
        else:
            content = soup.get_text(separator='\n')
        
        return {
            'title': title,
            'content': content,
            'source': url,
            'type': 'confluence'
        }
    
    except Exception as e:
        logger.error(f"Error parsing Confluence HTML: {e}")
        return None


def fetch_jira_content(url: str, auth: Optional[Tuple[str, str]] = None) -> Optional[Dict]:
    """Fetch Jira issue content using REST API.
    
    Args:
        url: Jira issue URL
        auth: Optional tuple of (username, api_token) for authentication
    
    Returns:
        Dict with 'title' and 'content' keys, or None if fetch fails
    """
    url_parts = extract_jira_url_parts(url)
    if not url_parts:
        logger.error(f"Could not parse Jira URL: {url}")
        return None
    
    domain, issue_key = url_parts
    
    try:
        # Use Jira REST API v2 for compatibility
        api_url = f"{domain}/rest/api/2/issue/{issue_key}"
        
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'Spec2Test/1.0'
        }
        
        response = requests.get(api_url, headers=headers, auth=auth, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        fields = data.get('fields', {})
        
        # Extract title and description
        title = fields.get('summary', issue_key)
        description = fields.get('description', '')
        
        # Build content from multiple fields
        content_parts = []
        
        if description:
            content_parts.append(description)
        
        # Add custom fields and other relevant info
        issue_type = fields.get('issuetype', {}).get('name', '')
        priority = fields.get('priority', {}).get('name', '')
        
        if issue_type:
            content_parts.append(f"\nIssue Type: {issue_type}")
        if priority:
            content_parts.append(f"Priority: {priority}")
        
        # Add acceptance criteria if present
        if 'customfield' in fields:
            for field_name, field_value in fields.items():
                if 'criteria' in field_name.lower() or 'requirement' in field_name.lower():
                    if field_value:
                        content_parts.append(f"\n{field_name}: {field_value}")
        
        content = '\n'.join(content_parts)
        
        return {
            'title': title,
            'content': content,
            'source': url,
            'type': 'jira'
        }
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Jira content: {e}")
        return None


def fetch_link_content(url: str, auth: Optional[Tuple[str, str]] = None) -> Optional[Dict]:
    """Fetch content from a Confluence or Jira link.
    
    Args:
        url: URL to a Confluence page or Jira issue
        auth: Optional tuple of (username, api_token) for authentication
    
    Returns:
        Dict with 'title', 'content', 'source', and 'type' keys
    """
    url = url.strip()
    
    # Determine if it's Confluence or Jira
    if 'atlassian.net' in url or 'confluence' in url.lower():
        if '/browse/' in url or 'jira' in url.lower():
            logger.info(f"Detected Jira URL: {url}")
            return fetch_jira_content(url, auth)
        else:
            logger.info(f"Detected Confluence URL: {url}")
            return fetch_confluence_content(url, auth)
    elif 'jira' in url.lower():
        logger.info(f"Detected Jira URL: {url}")
        return fetch_jira_content(url, auth)
    else:
        logger.error(f"Unsupported URL: {url}")
        return None


def clean_html_content(content: str) -> str:
    """Remove HTML tags and clean up content."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(content, 'html.parser')
        # Remove script and style elements
        for script in soup(['script', 'style']):
            script.decompose()
        text = soup.get_text(separator='\n', strip=False)
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        text = '\n'.join(line for line in lines if line)
        return text
    except Exception:
        # Fallback: basic regex removal
        content = re.sub(r'<[^>]+>', '', content)
        return content


if __name__ == '__main__':
    # Test the extractor
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python link_extractor.py <confluence_or_jira_url> [username] [api_token]")
        sys.exit(1)
    
    url = sys.argv[1]
    auth = None
    
    if len(sys.argv) >= 4:
        username = sys.argv[2]
        api_token = sys.argv[3]
        auth = (username, api_token)
    
    result = fetch_link_content(url, auth)
    
    if result:
        print(json.dumps(result, indent=2))
    else:
        print("Failed to fetch content")
        sys.exit(1)

