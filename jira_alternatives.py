# Alternative Jira Integration Solutions
# When API access is not available

## Option 1: CSV Export/Import
"""
Steps to use CSV export/import:
1. In Jira, go to Issues > Search for issues
2. Use JQL: project = YOUR_PROJECT AND status = "QAT-Testing"
3. Click "Export" > "Export Excel CSV (all fields)"
4. Save the file as 'jira_export.csv' in the project directory
5. The dashboard will automatically read from this file
"""

## Option 2: Jira RSS Feeds
"""
Many Jira instances provide RSS feeds:
1. In Jira, create a filter for your desired tickets
2. Share the filter and get the RSS URL
3. RSS URLs typically look like: https://your-jira.com/sr/jira.issueviews:searchrequest-rss/12345/SearchRequest-12345.xml
4. This doesn't require authentication in many cases
"""

## Option 3: Manual Entry
"""
Use the built-in manual entry interface to add tickets
"""

# CSV Headers that should be included in Jira export:
CSV_HEADERS = [
    'Issue key',
    'Summary',
    'Status',
    'Assignee',
    'Priority',
    'Created',
    'Issue Type',
    'Project key'
]

# Sample CSV data format:
SAMPLE_CSV_DATA = """Issue key,Summary,Status,Assignee,Priority,Created,Issue Type,Project key
PROJ-123,Fix login page validation error,QAT-Testing,John Doe,High,2024-10-20 10:30,Bug,PROJ
PROJ-124,Update user dashboard performance,QAT-Testing,Jane Smith,Medium,2024-10-19 14:15,Task,PROJ
PROJ-125,Implement new search functionality,QAT-Testing,Mike Johnson,Low,2024-10-18 09:45,Story,PROJ"""