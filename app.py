from flask import Flask, render_template, request, jsonify
import requests
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# GitHub API configuration
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_REPO = os.getenv('GITHUB_REPO', 'microsoft/vscode')  # Default to a public repo
BASE_URL = 'https://api.github.com'

class GitHubService:
    def __init__(self, token, repo):
        self.token = token
        self.repo = repo
        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'GitHub-PR-Dashboard'
        }
        if token:
            self.headers['Authorization'] = f'token {token}'
    
    def get_pull_requests(self, state='all', labels=None, month=None):
        """Fetch pull requests from GitHub API"""
        url = f'{BASE_URL}/repos/{self.repo}/pulls'
        params = {
            'state': 'all' if state == 'all' else state,
            'per_page': 100,
            'sort': 'created',
            'direction': 'desc'
        }
        
        try:
            print(f"DEBUG: Fetching PRs from {url} with params {params}")
            response = requests.get(url, headers=self.headers, params=params)
            
            print(f"DEBUG: Response status: {response.status_code}")
            
            # Enhanced error handling for different HTTP status codes
            if response.status_code == 403:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                if 'rate limit' in error_data.get('message', '').lower():
                    print("Rate limit exceeded. Consider using a personal access token for higher limits.")
                else:
                    print("Authentication required or insufficient permissions. Check your GitHub token.")
                return self._get_mock_data(state, labels, month)
            elif response.status_code == 404:
                print(f"Repository '{self.repo}' not found or you don't have access. Check repository name and permissions.")
                return self._get_mock_data(state, labels, month)
            elif response.status_code == 401:
                print("Invalid GitHub token. Please check your GITHUB_TOKEN environment variable.")
                return self._get_mock_data(state, labels, month)
            elif response.status_code != 200:
                print(f"API error {response.status_code}: {response.text}")
                return self._get_mock_data(state, labels, month)
            
            prs = response.json()
            print(f"DEBUG: Retrieved {len(prs)} PRs from API")
            
            # Filter by month if specified
            if month:
                filtered_prs = []
                for pr in prs:
                    created_date = datetime.strptime(pr['created_at'], '%Y-%m-%dT%H:%M:%SZ')
                    if created_date.strftime('%Y-%m') == month:
                        filtered_prs.append(pr)
                prs = filtered_prs
                print(f"DEBUG: After month filter ({month}): {len(prs)} PRs")
            
            # Filter by labels if specified
            if labels:
                filtered_prs = []
                for pr in prs:
                    pr_labels = [label['name'] for label in pr['labels']]
                    if any(label.lower() in [pl.lower() for pl in pr_labels] for label in labels):
                        filtered_prs.append(pr)
                prs = filtered_prs
                print(f"DEBUG: After label filter ({labels}): {len(prs)} PRs")
            
            return prs
        except requests.exceptions.RequestException as e:
            print(f"Error fetching PRs: {e}. Using mock data.")
            return self._get_mock_data(state, labels, month)
    
    def _get_mock_data(self, state='all', labels=None, month=None):
        """Return mock PR data for testing"""
        mock_prs = [
            {
                'title': 'Fix authentication bug in login system',
                'number': 123,
                'state': 'open',
                'created_at': '2024-10-15T10:30:00Z',
                'updated_at': '2024-10-20T14:22:00Z',
                'html_url': 'https://github.com/example/repo/pull/123',
                'user': {'login': 'developer1'},
                'labels': [{'name': 'bug'}, {'name': 'authentication'}]
            },
            {
                'title': 'Add new dashboard features',
                'number': 124,
                'state': 'open',
                'created_at': '2024-10-18T09:15:00Z',
                'updated_at': '2024-10-22T16:45:00Z',
                'html_url': 'https://github.com/example/repo/pull/124',
                'user': {'login': 'developer2'},
                'labels': [{'name': 'feature'}, {'name': 'enhancement'}]
            },
            {
                'title': 'Update documentation for API endpoints',
                'number': 125,
                'state': 'closed',
                'created_at': '2024-10-10T08:00:00Z',
                'updated_at': '2024-10-17T12:30:00Z',
                'html_url': 'https://github.com/example/repo/pull/125',
                'user': {'login': 'developer3'},
                'labels': [{'name': 'documentation'}]
            },
            {
                'title': 'Improve performance of data processing',
                'number': 126,
                'state': 'open',
                'created_at': '2024-09-28T14:20:00Z',
                'updated_at': '2024-10-01T11:10:00Z',
                'html_url': 'https://github.com/example/repo/pull/126',
                'user': {'login': 'developer1'},
                'labels': [{'name': 'performance'}, {'name': 'enhancement'}]
            },
            {
                'title': 'Security patch for user input validation',
                'number': 127,
                'state': 'closed',
                'created_at': '2024-10-12T16:45:00Z',
                'updated_at': '2024-10-19T10:20:00Z',
                'html_url': 'https://github.com/example/repo/pull/127',
                'user': {'login': 'security-team'},
                'labels': [{'name': 'security'}, {'name': 'bug'}]
            }
        ]
        
        # Filter by state
        if state != 'all':
            mock_prs = [pr for pr in mock_prs if pr['state'] == state]
        
        # Filter by month if specified
        if month:
            filtered_prs = []
            for pr in mock_prs:
                created_date = datetime.strptime(pr['created_at'], '%Y-%m-%dT%H:%M:%SZ')
                if created_date.strftime('%Y-%m') == month:
                    filtered_prs.append(pr)
            mock_prs = filtered_prs
        
        # Filter by labels if specified
        if labels:
            filtered_prs = []
            for pr in mock_prs:
                pr_labels = [label['name'] for label in pr['labels']]
                if any(label in pr_labels for label in labels):
                    filtered_prs.append(pr)
            mock_prs = filtered_prs
        
        return mock_prs

github_service = GitHubService(GITHUB_TOKEN, GITHUB_REPO)

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/pr-stats')
def pr_stats():
    """API endpoint to get PR statistics"""
    month = request.args.get('month')
    labels = request.args.getlist('labels')
    repo = request.args.get('repo', GITHUB_REPO)  # Use repo from request or default
    
    print(f"DEBUG: Getting PR stats for repo={repo}, month={month}, labels={labels}")
    
    # Create GitHub service for the requested repository
    current_service = GitHubService(GITHUB_TOKEN, repo) if repo != GITHUB_REPO else github_service
    
    # Get all PRs
    all_prs = current_service.get_pull_requests(month=month)
    print(f"DEBUG: Got {len(all_prs)} total PRs")
    
    # Get open PRs
    open_prs = [pr for pr in all_prs if pr['state'] == 'open']
    print(f"DEBUG: Found {len(open_prs)} open PRs")
    
    # Get closed PRs
    closed_prs = [pr for pr in all_prs if pr['state'] == 'closed']
    print(f"DEBUG: Found {len(closed_prs)} closed PRs")
    
    # Get PRs with specific labels
    labeled_prs = current_service.get_pull_requests(labels=labels, month=month) if labels else []
    print(f"DEBUG: Found {len(labeled_prs)} labeled PRs")
    
    stats = {
        'available_count': len(open_prs),
        'closed_count': len(closed_prs),
        'labeled_count': len(labeled_prs),
        'total_count': len(all_prs)
    }
    
    print(f"DEBUG: Returning stats: {stats}")
    return jsonify(stats)

@app.route('/api/prs')
def get_prs():
    """API endpoint to get detailed PR list"""
    pr_type = request.args.get('type', 'open')
    month = request.args.get('month')
    labels = request.args.getlist('labels')
    repo = request.args.get('repo', GITHUB_REPO)  # Use repo from request or default
    
    # Create GitHub service for the requested repository
    current_service = GitHubService(GITHUB_TOKEN, repo) if repo != GITHUB_REPO else github_service
    
    if pr_type == 'labeled':
        prs = current_service.get_pull_requests(labels=labels, month=month)
    else:
        prs = current_service.get_pull_requests(state=pr_type, month=month)
    
    # Format PR data for frontend
    formatted_prs = []
    for pr in prs:
        formatted_prs.append({
            'title': pr['title'],
            'number': pr['number'],
            'state': pr['state'],
            'created_at': pr['created_at'],
            'updated_at': pr['updated_at'],
            'html_url': pr['html_url'],
            'user': pr['user']['login'],
            'labels': [label['name'] for label in pr['labels']]
        })
    
    return jsonify(formatted_prs)

@app.route('/api/available-months')
def available_months():
    """Get available months from PRs"""
    try:
        repo = request.args.get('repo', GITHUB_REPO)  # Use repo from request or default
        
        # Create GitHub service for the requested repository
        current_service = GitHubService(GITHUB_TOKEN, repo) if repo != GITHUB_REPO else github_service
        
        prs = current_service.get_pull_requests()
        months = set()
        
        for pr in prs:
            created_date = datetime.strptime(pr['created_at'], '%Y-%m-%dT%H:%M:%SZ')
            months.add(created_date.strftime('%Y-%m'))
        
        return jsonify(sorted(list(months), reverse=True))
    except Exception as e:
        print(f"Error getting available months: {e}")
        # Return some default months if there's an error
        return jsonify(['2024-10', '2024-09', '2024-08'])

@app.route('/api/test-mock')
def test_mock():
    """Test endpoint to force mock data"""
    mock_data = github_service._get_mock_data()
    return jsonify({
        'count': len(mock_data),
        'sample': mock_data[0] if mock_data else None
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)