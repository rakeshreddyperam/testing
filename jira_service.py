"""
Jira Service Module
Handles connection to Jira API with support for multiple authentication methods
"""

import requests
from datetime import datetime
import base64
from jira_config import *

class JiraService:
    def __init__(self, use_mock=True):
        self.use_mock = use_mock
        self.session = requests.Session()
        self.base_url = None
        self.project_key = None
        self.status_filter = None
        
        if not use_mock:
            self._setup_authentication()
    
    def _setup_authentication(self):
        """Setup authentication based on configuration"""
        # Try different authentication methods
        if JIRA_CLOUD_CONFIG.get('api_token'):
            self._setup_cloud_auth()
        elif JIRA_SERVER_CONFIG.get('password'):
            self._setup_server_auth()
        elif JIRA_PAT_CONFIG.get('token'):
            self._setup_pat_auth()
        else:
            print("No valid Jira authentication found, falling back to mock data")
            self.use_mock = True
    
    def _setup_cloud_auth(self):
        """Setup Jira Cloud authentication with API token"""
        config = JIRA_CLOUD_CONFIG
        self.base_url = config['url'].rstrip('/')
        self.project_key = config['project_key']
        self.status_filter = config['status_filter']
        
        # Create basic auth string for Jira Cloud
        auth_string = f"{config['email']}:{config['api_token']}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        
        self.session.headers.update({
            'Authorization': f'Basic {encoded_auth}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def _setup_server_auth(self):
        """Setup Jira Server authentication with username/password"""
        config = JIRA_SERVER_CONFIG
        self.base_url = config['url'].rstrip('/')
        self.project_key = config['project_key']
        self.status_filter = config['status_filter']
        
        auth_string = f"{config['username']}:{config['password']}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        
        self.session.headers.update({
            'Authorization': f'Basic {encoded_auth}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def _setup_pat_auth(self):
        """Setup Jira Server authentication with Personal Access Token"""
        config = JIRA_PAT_CONFIG
        self.base_url = config['url'].rstrip('/')
        self.project_key = config['project_key']
        self.status_filter = config['status_filter']
        
        self.session.headers.update({
            'Authorization': f'Bearer {config["token"]}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def get_tickets_in_status(self, status=None):
        """Get tickets in specific status"""
        if self.use_mock:
            return self._get_mock_tickets()
        
        try:
            status = status or self.status_filter
            
            # JQL query to get tickets in specific status
            jql = f'project = "{self.project_key}" AND status = "{status}"'
            
            url = f'{self.base_url}/rest/api/2/search'
            params = {
                'jql': jql,
                'fields': 'key,summary,status,assignee,priority,created',
                'maxResults': 100
            }
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Format tickets for dashboard
            tickets = []
            for issue in data.get('issues', []):
                ticket = {
                    'key': issue['key'],
                    'summary': issue['fields']['summary'],
                    'status': issue['fields']['status']['name'],
                    'assignee': issue['fields']['assignee']['displayName'] if issue['fields']['assignee'] else 'Unassigned',
                    'priority': issue['fields']['priority']['name'] if issue['fields']['priority'] else 'None',
                    'created': issue['fields']['created'],
                    'link': f"{self.base_url}/browse/{issue['key']}"
                }
                tickets.append(ticket)
            
            return tickets
            
        except Exception as e:
            print(f"Error fetching Jira tickets: {e}")
            # Fallback to mock data on error
            return self._get_mock_tickets()
    
    def get_ticket_count_by_status(self, status=None):
        """Get count of tickets in specific status"""
        tickets = self.get_tickets_in_status(status)
        return len(tickets)
    
    def _get_mock_tickets(self):
        """Return mock ticket data for demonstration"""
        return [
            {
                'key': 'PROJ-123',
                'summary': 'Fix login page validation error',
                'status': 'QAT-Testing',
                'assignee': 'John Doe',
                'priority': 'High',
                'created': '2024-10-20T10:30:00Z',
                'link': 'https://your-jira-instance.atlassian.net/browse/PROJ-123'
            },
            {
                'key': 'PROJ-124',
                'summary': 'Update user dashboard performance',
                'status': 'QAT-Testing',
                'assignee': 'Jane Smith',
                'priority': 'Medium',
                'created': '2024-10-19T14:15:00Z',
                'link': 'https://your-jira-instance.atlassian.net/browse/PROJ-124'
            },
            {
                'key': 'PROJ-125',
                'summary': 'Implement new search functionality',
                'status': 'QAT-Testing',
                'assignee': 'Mike Johnson',
                'priority': 'Low',
                'created': '2024-10-18T09:45:00Z',
                'link': 'https://your-jira-instance.atlassian.net/browse/PROJ-125'
            },
            {
                'key': 'PROJ-126',
                'summary': 'Database connection timeout issue',
                'status': 'QAT-Testing',
                'assignee': 'Sarah Wilson',
                'priority': 'Critical',
                'created': '2024-10-17T16:20:00Z',
                'link': 'https://your-jira-instance.atlassian.net/browse/PROJ-126'
            },
            {
                'key': 'PROJ-127',
                'summary': 'Email notification system bug',
                'status': 'QAT-Testing',
                'assignee': 'Alex Brown',
                'priority': 'Medium',
                'created': '2024-10-16T11:30:00Z',
                'link': 'https://your-jira-instance.atlassian.net/browse/PROJ-127'
            }
        ]
    
    def test_connection(self):
        """Test connection to Jira API"""
        if self.use_mock:
            return True, "Using mock data"
        
        try:
            url = f'{self.base_url}/rest/api/2/myself'
            response = self.session.get(url)
            response.raise_for_status()
            
            user_info = response.json()
            return True, f"Connected as: {user_info.get('displayName', 'Unknown')}"
            
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

# Create global jira service instance
jira_service = JiraService(use_mock=USE_MOCK_DATA)