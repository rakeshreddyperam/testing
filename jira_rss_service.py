"""
Jira RSS Feed Integration
Reads Jira tickets from RSS feeds without requiring API authentication
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import re
from urllib.parse import urlparse

class JiraRSSService:
    def __init__(self, rss_urls=None):
        """
        Initialize with RSS feed URLs
        rss_urls can be a single URL string or list of URLs
        """
        self.rss_urls = rss_urls or []
        if isinstance(self.rss_urls, str):
            self.rss_urls = [self.rss_urls]
        
        # Common Jira RSS URL patterns (examples)
        self.sample_urls = [
            # Format: https://your-jira.com/sr/jira.issueviews:searchrequest-rss/FILTER_ID/SearchRequest-FILTER_ID.xml
            "https://jira.atlassian.com/sr/jira.issueviews:searchrequest-rss/15151/SearchRequest-15151.xml",
            # Format: https://your-jira.com/issues/?jql=YOUR_JQL&tempMax=100&rss=true
            "https://issues.apache.org/jira/sr/jira.issueviews:searchrequest-rss/temp/SearchRequest.xml?jqlQuery=project+%3D+KAFKA+AND+status+%3D+Open&tempMax=20"
        ]
    
    def add_rss_url(self, url):
        """Add a new RSS URL"""
        if url not in self.rss_urls:
            self.rss_urls.append(url)
    
    def test_rss_url(self, url):
        """Test if an RSS URL is accessible"""
        try:
            print(f"Testing RSS URL: {url}")
            
            # Configure session for corporate environments
            session = requests.Session()
            session.verify = False  # Disable SSL verification for corporate networks
            
            # Add headers to look like a regular browser
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/rss+xml, application/xml, text/xml, */*',
                'Accept-Language': 'en-US,en;q=0.9',
            })
            
            # Suppress SSL warnings
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            response = session.get(url, timeout=10)
            
            # Check for authentication redirects
            if response.status_code == 302 or 'login' in response.url.lower():
                return False, "Authentication required - RSS feed redirected to login page"
            
            if response.status_code == 401:
                return False, "Authentication required - 401 Unauthorized"
            
            if response.status_code == 403:
                return False, "Access forbidden - RSS feed may require permissions"
            
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if 'html' in content_type and 'xml' not in content_type:
                return False, "Returned HTML instead of XML/RSS - likely authentication required"
            
            # Try to parse as XML
            root = ET.fromstring(response.content)
            
            # Check if it's a valid RSS feed
            if root.tag == 'rss' or 'rss' in root.tag.lower():
                items = root.findall('.//item')
                print(f"✅ RSS feed is valid. Found {len(items)} items")
                return True, f"Valid RSS feed with {len(items)} items"
            elif root.tag == 'feed':  # Atom feed
                items = root.findall('.//{http://www.w3.org/2005/Atom}entry')
                print(f"✅ Atom feed is valid. Found {len(items)} items")
                return True, f"Valid Atom feed with {len(items)} items"
            else:
                print(f"❌ Not a valid RSS feed. Root tag: {root.tag}")
                return False, f"Not a valid RSS/Atom feed. Root tag: {root.tag}"
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error: {e}")
            return False, f"Network error: {str(e)}"
        except ET.ParseError as e:
            print(f"❌ XML parsing error: {e}")
            return False, f"XML parsing error: {str(e)}"
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False, f"Error: {str(e)}"
    
    def parse_rss_feed(self, url):
        """Parse a single RSS feed and extract ticket information"""
        try:
            # Configure session for corporate environments
            session = requests.Session()
            session.verify = False  # Disable SSL verification
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/rss+xml, application/xml, text/xml, */*',
            })
            
            # Suppress SSL warnings
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            response = session.get(url, timeout=10)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            tickets = []
            
            # Find all items in the RSS feed
            for item in root.findall('.//item'):
                ticket = self._parse_rss_item(item, url)
                if ticket:
                    tickets.append(ticket)
            
            return tickets
            
        except Exception as e:
            print(f"Error parsing RSS feed {url}: {e}")
            return []
    
    def _parse_rss_item(self, item, source_url):
        """Parse individual RSS item to extract ticket information"""
        try:
            # Extract basic information
            title = self._get_element_text(item, 'title', '')
            link = self._get_element_text(item, 'link', '')
            description = self._get_element_text(item, 'description', '')
            pub_date = self._get_element_text(item, 'pubDate', '')
            
            # Try to extract Jira-specific information from title
            # Common format: "[PROJECT-123] Ticket Summary"
            ticket_key = ''
            summary = title
            
            # Extract ticket key from title
            key_match = re.search(r'\[([A-Z]+-\d+)\]', title)
            if key_match:
                ticket_key = key_match.group(1)
                summary = title.replace(f'[{ticket_key}]', '').strip()
            elif re.match(r'^[A-Z]+-\d+:', title):
                # Format: "PROJECT-123: Summary"
                parts = title.split(':', 1)
                if len(parts) == 2:
                    ticket_key = parts[0].strip()
                    summary = parts[1].strip()
            
            # Extract additional info from description (if available)
            priority = self._extract_from_description(description, r'Priority:\s*(\w+)', 'Medium')
            status = self._extract_from_description(description, r'Status:\s*([^<\n]+)', 'Open')
            assignee = self._extract_from_description(description, r'Assignee:\s*([^<\n]+)', 'Unassigned')
            
            # Parse date
            created_date = self._parse_date(pub_date)
            
            # Generate Jira URL from the RSS link
            jira_url = link
            if not jira_url.startswith('http'):
                # Try to construct URL from source
                parsed_source = urlparse(source_url)
                base_url = f"{parsed_source.scheme}://{parsed_source.netloc}"
                if ticket_key:
                    jira_url = f"{base_url}/browse/{ticket_key}"
                else:
                    jira_url = link
            
            ticket = {
                'key': ticket_key or 'RSS-ITEM',
                'summary': summary or 'No summary available',
                'status': status,
                'assignee': assignee,
                'priority': priority,
                'created': created_date,
                'link': jira_url,
                'source': 'RSS Feed'
            }
            
            return ticket
            
        except Exception as e:
            print(f"Error parsing RSS item: {e}")
            return None
    
    def _get_element_text(self, parent, tag, default=''):
        """Safely get text from XML element"""
        element = parent.find(tag)
        return element.text if element is not None and element.text else default
    
    def _extract_from_description(self, description, pattern, default):
        """Extract information from description using regex"""
        match = re.search(pattern, description, re.IGNORECASE)
        return match.group(1).strip() if match else default
    
    def _parse_date(self, date_str):
        """Parse various date formats"""
        if not date_str:
            return datetime.now().isoformat()
        
        # Common RSS date formats
        formats = [
            '%a, %d %b %Y %H:%M:%S %z',  # RFC 2822
            '%a, %d %b %Y %H:%M:%S GMT',
            '%Y-%m-%dT%H:%M:%S.%fZ',     # ISO format
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d'
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.isoformat()
            except ValueError:
                continue
        
        # If all parsing fails, return current time
        return datetime.now().isoformat()
    
    def get_all_tickets(self, status_filter=None):
        """Get tickets from all configured RSS feeds"""
        all_tickets = []
        
        for url in self.rss_urls:
            print(f"Fetching tickets from: {url}")
            tickets = self.parse_rss_feed(url)
            all_tickets.extend(tickets)
        
        # Filter by status if specified
        if status_filter:
            all_tickets = [t for t in all_tickets if status_filter.lower() in t['status'].lower()]
        
        return all_tickets
    
    def get_tickets_by_status(self, status):
        """Get tickets filtered by specific status"""
        return self.get_all_tickets(status_filter=status)
    
    def discover_rss_feeds(self, jira_base_url):
        """Try to discover RSS feeds from a Jira instance"""
        suggestions = []
        
        # Common RSS feed patterns
        patterns = [
            f"{jira_base_url}/sr/jira.issueviews:searchrequest-rss/temp/SearchRequest.xml?jqlQuery=status%3DOpen",
            f"{jira_base_url}/issues/?jql=status%3D%22In%20Progress%22&tempMax=50&rss=true",
            f"{jira_base_url}/sr/jira.issueviews:searchrequest-rss/temp/SearchRequest.xml?jqlQuery=assignee%3DcurrentUser()"
        ]
        
        for pattern in patterns:
            success, message = self.test_rss_url(pattern)
            if success:
                suggestions.append(pattern)
        
        return suggestions

# Your Jira Cloud instance URLs for ZDI project
ONEZELIS_RSS_URLS = [
    # Basic project RSS feed
    "https://onezelis.atlassian.net/sr/jira.issueviews:searchrequest-rss/temp/SearchRequest.xml?jqlQuery=project%3DZDI",
    
    # QAT-Testing status filter
    "https://onezelis.atlassian.net/sr/jira.issueviews:searchrequest-rss/temp/SearchRequest.xml?jqlQuery=project%3DZDI%20AND%20status%3D%22QAT-Testing%22",
    
    # Alternative format
    "https://onezelis.atlassian.net/issues/?jql=project%3DZDI%20AND%20status%3D%22QAT-Testing%22&tempMax=50&os_authType=none",
    
    # Board-specific RSS (may need authentication)
    "https://onezelis.atlassian.net/plugins/servlet/streams?maxResults=50&streams=key+IS+ZDI",
    
    # Activity stream format
    "https://onezelis.atlassian.net/activity?maxResults=50&streams=key+IS+ZDI&os_authType=none"
]

# Example RSS URLs for testing (public Jira instances)
EXAMPLE_RSS_URLS = [
    # Apache Software Foundation JIRA
    "https://issues.apache.org/jira/sr/jira.issueviews:searchrequest-rss/temp/SearchRequest.xml?jqlQuery=project+%3D+KAFKA+AND+status+%3D+Open&tempMax=5",
    # Spring Framework
    "https://jira.spring.io/sr/jira.issueviews:searchrequest-rss/temp/SearchRequest.xml?jqlQuery=project+%3D+SPR+AND+status+%3D+Open&tempMax=5"
]

# Create global RSS service instance
jira_rss_service = JiraRSSService()