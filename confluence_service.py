import os
import re
from typing import Dict, Any, Optional
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
from atlassian import Confluence
from config import settings


class ConfluenceService:
    def __init__(self):
        self._confluence = None

    def _client(self) -> Confluence:
        if self._confluence is None:
            self._confluence = Confluence(
                url=settings.CONFLUENCE_URL,
                username=settings.CONFLUENCE_USER,
                password=settings.CONFLUENCE_TOKEN
            )
    
        return self._confluence

    def extract_page_id_from_url(self, url: str) -> Optional[str]:
        """Extract page ID from Confluence URL"""
        try:
            # Handle different URL formats
            # Format 1: https://domain.atlassian.net/wiki/spaces/SPACE/pages/123456789/Page+Title
            # Format 2: https://domain.atlassian.net/wiki/pages/viewpage.action?pageId=123456789
            # Format 3: https://domain.atlassian.net/wiki/spaces/SPACE/pages/123456789
            
            parsed_url = urlparse(url)
            
            # Check for pageId parameter
            if parsed_url.query:
                query_params = parse_qs(parsed_url.query)
                if 'pageId' in query_params:
                    return query_params['pageId'][0]
            
            # Check for pages/ID pattern in path
            path_match = re.search(r'/pages/(\d+)', parsed_url.path)
            if path_match:
                return path_match.group(1)
            
            return None
        except Exception as e:
            print(f"Error extracting page ID from URL: {e}")
            return None

    def html_to_text(self, html: str) -> str:
        """Convert HTML content to plain text"""
        soup = BeautifulSoup(html, "html.parser")
        
        # Remove script and style elements
        for s in soup(["script", "style"]):
            s.decompose()
        
        # Get text content
        text = soup.get_text(separator="\n")
        
        # Clean up whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)

    def fetch_page_by_url(self, url: str) -> Dict[str, Any]:
        """Fetch Confluence page content by URL"""
        page_id = self.extract_page_id_from_url(url)
        if not page_id:
            raise ValueError(f"Could not extract page ID from URL: {url}")
        
        return self.fetch_page_by_id(page_id)

    def fetch_page_by_id(self, page_id: str) -> Dict[str, Any]:
        """Fetch Confluence page content by ID"""
        try:
            c = self._client()
            page = c.get_page_by_id(
                page_id, 
                expand="body.storage,version,space"
            )
            
            if not page:
                raise ValueError(f"Page with ID {page_id} not found or accessible")
            
            return page
        except Exception as e:
            raise Exception(f"Error fetching page {page_id}: {str(e)}")

    def extract_page_content(self, page_data: Dict[str, Any], url: str = None) -> Dict[str, str]:
        """Extract and process page content"""
        title = page_data.get("title", "Untitled")
        page_id = page_data.get("id", "")
        
        # Get HTML content
        body_html = page_data.get("body", {}).get("storage", {}).get("value", "")
        
        # Convert to plain text
        text_content = self.html_to_text(body_html)
        
        # Get space information
        space_info = page_data.get("space", {})
        space_name = space_info.get("name", "Unknown Space")
        
        # Create filename
        safe_title = re.sub(r'[^\w\s-]', '', title).strip()
        safe_title = re.sub(r'[-\s]+', '-', safe_title)
        filename = f"confluence-{page_id}-{safe_title}.txt"
        
        return {
            "title": title,
            "content": text_content,
            "filename": filename,
            "page_id": page_id,
            "space_name": space_name,
            "html_content": body_html,
            "json_content": {
                "page_id": page_id,
                "title": title,
                "content": text_content,
                "url": url,
                "source": "confluence"
            }
        }
