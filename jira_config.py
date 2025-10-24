# Jira Integration Configuration
# This file contains configuration options for connecting to Jira

# Option 1: Mock Data (Current Implementation)
# No authentication required - uses sample data for demonstration
USE_MOCK_DATA = True

# Option 2: Jira Cloud with API Token
# Requires:
# - Jira Cloud instance URL
# - Email address
# - API token (created from: https://id.atlassian.com/manage-profile/security/api-tokens)
JIRA_CLOUD_CONFIG = {
    'url': 'https://your-company.atlassian.net',
    'email': 'your-email@company.com',
    'api_token': '',  # Create at: https://id.atlassian.com/manage-profile/security/api-tokens
    'project_key': 'PROJ',  # Your project key
    'status_filter': 'QAT-Testing'  # Status to filter tickets
}

# Option 3: Jira Server with Basic Auth
# Requires:
# - Jira Server URL
# - Username and Password
JIRA_SERVER_CONFIG = {
    'url': 'https://jira.your-company.com',
    'username': 'your-username',
    'password': '',  # Your password
    'project_key': 'PROJ',
    'status_filter': 'QAT-Testing'
}

# Option 4: Jira Server with Personal Access Token (Jira 8.14+)
# Requires:
# - Jira Server URL
# - Personal Access Token
JIRA_PAT_CONFIG = {
    'url': 'https://jira.your-company.com',
    'token': '',  # Personal Access Token
    'project_key': 'PROJ',
    'status_filter': 'QAT-Testing'
}

# Option 5: Public Jira (if available)
# Some Jira instances allow anonymous access to public projects
JIRA_PUBLIC_CONFIG = {
    'url': 'https://issues.apache.org/jira',  # Example: Apache JIRA
    'project_key': 'HADOOP',  # Example project
    'status_filter': 'Open'
}

# Instructions for setup:
"""
To connect to your Jira instance:

1. For Jira Cloud (Recommended):
   - Set USE_MOCK_DATA = False
   - Fill in JIRA_CLOUD_CONFIG with your details
   - Create API token at: https://id.atlassian.com/manage-profile/security/api-tokens
   - Update app.py to use jira_service.py

2. For Jira Server:
   - Check if your Jira server supports API access
   - Use either basic auth or PAT (if available)
   - Update the appropriate config section

3. Alternative solutions if no API access:
   - Export Jira data to CSV and import to dashboard
   - Use Jira webhooks to push data to your dashboard
   - Create a proxy service that has Jira access
   - Use Jira's RSS feeds (if available)

4. Testing without authentication:
   - Keep USE_MOCK_DATA = True
   - Mock data will continue to work for demonstration
"""