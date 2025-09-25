"""
URL Detection Service for identifying Confluence and JIRA links
"""

import re
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from enum import Enum


class SourceType(str, Enum):
    CONFLUENCE = "confluence"
    JIRA = "jira"
    UNKNOWN = "unknown"


class URLDetector:
    """Service for detecting and parsing Confluence and JIRA URLs"""
    
    # Confluence URL patterns
    CONFLUENCE_PATTERNS = [
        r'https?://[^/]+/wiki/spaces/[^/]+/pages/\d+',
        r'https?://[^/]+/wiki/[^/]+/[^/]+',
        r'https?://[^/]+/display/[^/]+/[^/]+',
        r'https?://[^/]+/pages/viewpage\.action\?pageId=\d+',
    ]
    
    # JIRA URL patterns
    JIRA_PATTERNS = [
        r'https?://[^/]+/browse/[A-Z]+-\d+',
        r'https?://[^/]+/jira/browse/[A-Z]+-\d+',
        r'https?://[^/]+/projects/[^/]+/issues/[A-Z]+-\d+',
        r'https?://[^/]+/secure/RapidBoard\.jspa\?rapidView=\d+',
        r'https?://[^/]+/jira/software/projects/[^/]+/boards/\d+',
    ]
    
    @classmethod
    def detect_source_type(cls, url: str) -> SourceType:
        """Detect if URL is Confluence, JIRA, or unknown"""
        if not url or not isinstance(url, str):
            return SourceType.UNKNOWN
        
        # Check Confluence patterns
        for pattern in cls.CONFLUENCE_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                return SourceType.CONFLUENCE
        
        # Check JIRA patterns
        for pattern in cls.JIRA_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                return SourceType.JIRA
        
        return SourceType.UNKNOWN
    
    @classmethod
    def extract_confluence_page_id(cls, url: str) -> Optional[str]:
        """Extract Confluence page ID from URL"""
        if cls.detect_source_type(url) != SourceType.CONFLUENCE:
            return None
        
        # Pattern 1: /pages/viewpage.action?pageId=123456
        page_id_match = re.search(r'pageId=(\d+)', url)
        if page_id_match:
            return page_id_match.group(1)
        
        # Pattern 2: /pages/123456/Page+Title
        pages_match = re.search(r'/pages/(\d+)/', url)
        if pages_match:
            return pages_match.group(1)
        
        return None
    
    @classmethod
    def extract_jira_issue_key(cls, url: str) -> Optional[str]:
        """Extract JIRA issue key from URL"""
        if cls.detect_source_type(url) != SourceType.JIRA:
            return None
        
        # Pattern 1: /browse/PROJECT-123
        browse_match = re.search(r'/browse/([A-Z]+-\d+)', url)
        if browse_match:
            return browse_match.group(1)
        
        # Pattern 2: /issues/PROJECT-123
        issues_match = re.search(r'/issues/([A-Z]+-\d+)', url)
        if issues_match:
            return issues_match.group(1)
        
        return None
    
    @classmethod
    def extract_jira_board_info(cls, url: str) -> Optional[Dict[str, str]]:
        """Extract JIRA board information from URL"""
        if cls.detect_source_type(url) != SourceType.JIRA:
            return None
        
        # Pattern: /jira/software/projects/PROJECT/boards/123
        board_match = re.search(r'/jira/software/projects/([^/]+)/boards/(\d+)', url)
        if board_match:
            return {
                "project_key": board_match.group(1),
                "board_id": board_match.group(2)
            }
        
        # Pattern: /secure/RapidBoard.jspa?rapidView=123
        rapid_view_match = re.search(r'rapidView=(\d+)', url)
        if rapid_view_match:
            return {
                "rapid_view_id": rapid_view_match.group(1)
            }
        
        return None
    
    @classmethod
    def parse_url(cls, url: str) -> Dict[str, Any]:
        """Parse URL and extract relevant information"""
        source_type = cls.detect_source_type(url)
        
        result = {
            "source_type": source_type,
            "url": url,
            "domain": None,
            "identifier": None,
            "is_valid": source_type != SourceType.UNKNOWN
        }
        
        if source_type == SourceType.UNKNOWN:
            return result
        
        try:
            parsed = urlparse(url)
            result["domain"] = parsed.netloc
        except Exception:
            pass
        
        if source_type == SourceType.CONFLUENCE:
            result["identifier"] = cls.extract_confluence_page_id(url)
        elif source_type == SourceType.JIRA:
            # Check if it's a board URL first
            board_info = cls.extract_jira_board_info(url)
            if board_info:
                result["identifier"] = board_info
                result["url_type"] = "board"
            else:
                result["identifier"] = cls.extract_jira_issue_key(url)
                result["url_type"] = "issue"
        
        return result
    
    @classmethod
    def validate_url(cls, url: str) -> bool:
        """Validate if URL is a supported Confluence or JIRA URL"""
        return cls.detect_source_type(url) != SourceType.UNKNOWN
