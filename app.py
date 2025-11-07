from flask import Flask, render_template, request, jsonify, session
import requests
import os
import json
import csv
from datetime import datetime
from dotenv import load_dotenv
import logging
import time
from functools import wraps
from werkzeug.utils import secure_filename

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pr_dashboard.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'

# Simple memory cache for PR data
pr_cache = {
    'data': None,
    'timestamp': None,
    'ttl': 900  # 15 minutes cache for much better performance
}

# Create uploads directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Security headers middleware
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; img-src 'self' data: https:;"
    return response

# Cache helper functions
def is_cache_valid():
    """Check if cache is still valid"""
    if pr_cache['data'] is None or pr_cache['timestamp'] is None:
        return False
    return time.time() - pr_cache['timestamp'] < pr_cache['ttl']

def get_cached_data():
    """Get cached data if valid"""
    if is_cache_valid():
        return pr_cache['data']
    return None

def set_cache_data(data):
    """Set cache data with current timestamp"""
    pr_cache['data'] = data
    pr_cache['timestamp'] = time.time()

# Rate limiting decorator
def rate_limit(max_requests=60, window=60):
    """Simple rate limiting decorator"""
    request_counts = {}
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
            current_time = time.time()
            
            # Clean old entries
            request_counts[client_ip] = [
                req_time for req_time in request_counts.get(client_ip, [])
                if current_time - req_time < window
            ]
            
            # Check rate limit
            if len(request_counts.get(client_ip, [])) >= max_requests:
                logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                return jsonify({'error': 'Rate limit exceeded'}), 429
            
            # Add current request
            if client_ip not in request_counts:
                request_counts[client_ip] = []
            request_counts[client_ip].append(current_time)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# GitHub API configuration
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_REPO = os.getenv('GITHUB_REPO', 'microsoft/vscode')  # Default to a public repo
BASE_URL = 'https://api.github.com'

# JIRA API configuration
JIRA_URL = os.getenv('JIRA_URL')  # e.g., 'https://yourcompany.atlassian.net'
JIRA_USERNAME = os.getenv('JIRA_USERNAME')
JIRA_API_TOKEN = os.getenv('JIRA_API_TOKEN')  # JIRA API token for authentication

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
        
        # Handle state parameter correctly
        if state == 'all':
            api_state = 'all'
        elif state in ['open', 'closed']:
            api_state = state
        else:
            logger.warning(f"Invalid state '{state}', defaulting to 'all'")
            api_state = 'all'
        
        params = {
            'state': api_state,
            'per_page': 100,
            'sort': 'created',
            'direction': 'desc'
        }
        
        try:
            logger.debug(f"Fetching PRs from {url} with params {params}")
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            
            logger.debug(f"Response status: {response.status_code}")
            
            # Enhanced error handling for different HTTP status codes
            if response.status_code == 403:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                if 'rate limit' in error_data.get('message', '').lower():
                    logger.error("Rate limit exceeded. Consider using a personal access token for higher limits.")
                else:
                    logger.error("Authentication required or insufficient permissions. Check your GitHub token.")
                return self._get_mock_data(state, labels, month)
            elif response.status_code == 404:
                logger.error(f"Repository '{self.repo}' not found or you don't have access. Check repository name and permissions.")
                return self._get_mock_data(state, labels, month)
            elif response.status_code == 401:
                logger.error("Invalid GitHub token. Please check your GITHUB_TOKEN environment variable.")
                return self._get_mock_data(state, labels, month)
            elif response.status_code != 200:
                logger.error(f"API error {response.status_code}: {response.text}")
                return self._get_mock_data(state, labels, month)
            
            prs = response.json()
            logger.debug(f"Retrieved {len(prs)} PRs from API")
            
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
    
    def get_pr_last_comment_date(self, pr_number):
        """Get the last comment date for a specific PR (optimized)"""
        try:
            import concurrent.futures
            import threading
            
            # Cache key for this PR's comment data
            cache_key = f"comments_{self.repo}_{pr_number}"
            
            # Simple thread-local cache for comment dates
            if not hasattr(self, '_comment_cache'):
                self._comment_cache = {}
            
            # Check cache first
            if cache_key in self._comment_cache:
                cached_time, cached_result = self._comment_cache[cache_key]
                # Cache for 5 minutes
                if time.time() - cached_time < 300:
                    return cached_result
            
            last_comment_date = None
            
            # Use ThreadPoolExecutor for parallel API calls
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                # Submit all three API calls in parallel
                comments_future = executor.submit(self._fetch_issue_comments, pr_number)
                review_comments_future = executor.submit(self._fetch_review_comments, pr_number)
                reviews_future = executor.submit(self._fetch_reviews, pr_number)
                
                # Collect results
                all_dates = []
                
                # Get issue comments
                comments = comments_future.result()
                if comments:
                    all_dates.extend([comment['created_at'] for comment in comments])
                
                # Get review comments
                review_comments = review_comments_future.result()
                if review_comments:
                    all_dates.extend([comment['created_at'] for comment in review_comments])
                
                # Get reviews
                reviews = reviews_future.result()
                if reviews:
                    all_dates.extend([review['submitted_at'] for review in reviews if review.get('submitted_at')])
            
            # Find the most recent date
            if all_dates:
                last_comment_date = max(all_dates)
                logger.debug(f"PR #{pr_number}: Found {len(all_dates)} total comments/reviews, latest: {last_comment_date}")
            
            # Cache the result
            self._comment_cache[cache_key] = (time.time(), last_comment_date)
            
            return last_comment_date
        
        except Exception as e:
            logger.error(f"Error fetching last comment date for PR #{pr_number}: {e}")
            return None
    
    def _fetch_issue_comments(self, pr_number):
        """Fetch issue comments for a PR"""
        try:
            comments_url = f'{BASE_URL}/repos/{self.repo}/issues/{pr_number}/comments'
            response = requests.get(comments_url, headers=self.headers, timeout=10)
            return response.json() if response.status_code == 200 else []
        except Exception as e:
            logger.error(f"Error fetching issue comments for PR #{pr_number}: {e}")
            return []
    
    def _fetch_review_comments(self, pr_number):
        """Fetch review comments for a PR"""
        try:
            review_comments_url = f'{BASE_URL}/repos/{self.repo}/pulls/{pr_number}/comments'
            response = requests.get(review_comments_url, headers=self.headers, timeout=10)
            return response.json() if response.status_code == 200 else []
        except Exception as e:
            logger.error(f"Error fetching review comments for PR #{pr_number}: {e}")
            return []
    
    def _fetch_reviews(self, pr_number):
        """Fetch reviews for a PR"""
        try:
            reviews_url = f'{BASE_URL}/repos/{self.repo}/pulls/{pr_number}/reviews'
            response = requests.get(reviews_url, headers=self.headers, timeout=10)
            return response.json() if response.status_code == 200 else []
        except Exception as e:
            logger.error(f"Error fetching reviews for PR #{pr_number}: {e}")
            return []

    def get_pr_review_status(self, pr_number):
        """Get the review status and merge readiness for a specific PR"""
        try:
            # Get PR details
            pr_url = f'{BASE_URL}/repos/{self.repo}/pulls/{pr_number}'
            pr_response = requests.get(pr_url, headers=self.headers)
            
            # Get PR reviews
            reviews_url = f'{BASE_URL}/repos/{self.repo}/pulls/{pr_number}/reviews'
            reviews_response = requests.get(reviews_url, headers=self.headers)
            
            # Get PR status checks
            status_url = f'{BASE_URL}/repos/{self.repo}/commits/{pr_response.json().get("head", {}).get("sha", "")}/status'
            status_response = requests.get(status_url, headers=self.headers)
            
            review_status = {
                'approved': False,
                'changes_requested': False,
                'pending_review': True,
                'mergeable': False,
                'status_checks': 'unknown',
                'review_count': 0,
                'approval_count': 0
            }
            
            if pr_response.status_code == 200:
                pr_data = pr_response.json()
                review_status['mergeable'] = pr_data.get('mergeable', False)
                review_status['draft'] = pr_data.get('draft', False)
            
            if reviews_response.status_code == 200:
                reviews = reviews_response.json()
                review_status['review_count'] = len(reviews)
                
                # Analyze reviews (latest review per reviewer wins)
                reviewer_states = {}
                for review in reviews:
                    reviewer = review['user']['login']
                    state = review['state']
                    reviewer_states[reviewer] = state
                
                # Count final states
                approved_count = sum(1 for state in reviewer_states.values() if state == 'APPROVED')
                changes_requested = any(state == 'CHANGES_REQUESTED' for state in reviewer_states.values())
                
                review_status['approval_count'] = approved_count
                review_status['approved'] = approved_count > 0 and not changes_requested
                review_status['changes_requested'] = changes_requested
                review_status['pending_review'] = len(reviewer_states) == 0
            
            if status_response.status_code == 200:
                status_data = status_response.json()
                review_status['status_checks'] = status_data.get('state', 'unknown')
            
            return review_status
        except Exception as e:
            print(f"Error fetching review status for PR #{pr_number}: {e}")
            return {
                'approved': False,
                'changes_requested': False,
                'pending_review': True,
                'mergeable': False,
                'status_checks': 'unknown',
                'review_count': 0,
                'approval_count': 0
            }
    
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

class JiraService:
    def __init__(self):
        self.jira_data = {}  # Will store uploaded JIRA data
        self.upload_metadata = None  # Will store upload timestamp and metadata
        self.load_jira_data()
    
    def load_jira_data(self):
        """Load JIRA data from uploaded file only (no dummy data)"""
        try:
            # Only load from uploaded file
            jira_file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'jira_data.json')
            if os.path.exists(jira_file_path):
                with open(jira_file_path, 'r') as f:
                    data = json.load(f)
                    
                    # Handle new metadata format
                    if isinstance(data, dict) and 'tickets' in data:
                        self.jira_data = data['tickets']
                        self.upload_metadata = {
                            'uploaded_at': data.get('uploaded_at'),
                            'ticket_count': data.get('ticket_count', len(self.jira_data))
                        }
                    elif isinstance(data, list):
                        self.jira_data = {ticket['key']: ticket for ticket in data}
                        self.upload_metadata = None
                    else:
                        self.jira_data = data
                        self.upload_metadata = None
                        
                logger.info(f"Loaded uploaded JIRA data for {len(self.jira_data)} tickets")
            else:
                # No uploaded data found
                self.jira_data = {}
                self.upload_metadata = None
                logger.info("No uploaded JIRA data found. Upload a file to see tickets.")
        except Exception as e:
            logger.error(f"Error loading JIRA data: {e}")
            self.jira_data = {}
            self.upload_metadata = None
    
    def save_jira_data(self, data):
        """Save JIRA data to file with metadata"""
        try:
            import datetime
            jira_file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'jira_data.json')
            
            # Create metadata
            metadata = {
                'uploaded_at': datetime.datetime.now().isoformat(),
                'ticket_count': len(data),
                'tickets': data
            }
            
            with open(jira_file_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            self.jira_data = data
            logger.info(f"Saved JIRA data for {len(data)} tickets")
            return True
        except Exception as e:
            logger.error(f"Error saving JIRA data: {e}")
            return False
    
    def extract_jira_keys(self, text):
        """Extract JIRA ticket keys from text (e.g., PROJ-123, ABC-456)"""
        import re
        if not text:
            return []
        # Common JIRA key pattern: 2+ uppercase letters, dash, 1+ digits
        pattern = r'\b[A-Z]{2,}-\d+\b'
        return list(set(re.findall(pattern, text)))
    
    def get_jira_ticket_status(self, ticket_key):
        """Get JIRA ticket status from loaded data"""
        if ticket_key in self.jira_data:
            ticket = self.jira_data[ticket_key]
            return {
                'key': ticket_key,
                'status': ticket.get('status', 'Unknown'),
                'status_category': self.get_status_category(ticket.get('status', 'Unknown')),
                'summary': ticket.get('summary', 'No summary'),
                'assignee': ticket.get('assignee', 'Unassigned'),
                'priority': ticket.get('priority', 'Unknown'),
                'link': ticket.get('link', f"https://onezelis.atlassian.net/browse/{ticket_key}"),
                'found': True
            }
        else:
            return {
                'key': ticket_key,
                'status': 'Not Found',
                'status_category': 'Unknown',
                'summary': 'Ticket not found in data',
                'assignee': 'Unknown',
                'priority': 'Unknown',
                'link': f"https://onezelis.atlassian.net/browse/{ticket_key}",
                'found': False
            }
    
    def get_status_category(self, status):
        """Map status to category for color coding"""
        status_lower = status.lower()
        if any(word in status_lower for word in ['done', 'completed', 'resolved', 'closed']):
            return 'Done'
        elif any(word in status_lower for word in ['progress', 'development', 'testing', 'qat']):
            return 'In Progress'
        elif any(word in status_lower for word in ['todo', 'to do', 'open', 'new', 'backlog']):
            return 'To Do'
        else:
            return 'In Progress'  # Default
    
    def get_multiple_tickets_status(self, ticket_keys):
        """Get status for multiple JIRA tickets"""
        if not ticket_keys:
            return []
        
        tickets = []
        for key in ticket_keys:
            tickets.append(self.get_jira_ticket_status(key))
        return tickets
    
    def process_uploaded_file(self, file_path, file_type):
        """Process uploaded JIRA file (CSV only)"""
        try:
            if file_type == 'csv':
                jira_dict = {}
                processed_count = 0
                with open(file_path, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    logger.info(f"CSV headers detected: {reader.fieldnames}")
                    
                    for row_num, row in enumerate(reader, 1):
                        try:
                            # Handle different CSV column formats for JIRA export
                            key = (row.get('Issue key') or row.get('Key') or 
                                   row.get('key') or row.get('issue_key') or 
                                   row.get('Issue Key'))
                            
                            if key and key.strip():
                                # Get status with multiple possible column names
                                status = (row.get('Status') or row.get('status') or 
                                        row.get('status_name') or 'Unknown')
                                
                                # Get summary with multiple possible column names  
                                summary = (row.get('Summary') or row.get('summary') or 
                                         row.get('Description') or row.get('description') or 
                                         'No summary')
                                
                                # Get assignee with multiple possible column names
                                assignee = (row.get('Assignee') or row.get('assignee') or 
                                          row.get('assigned_to') or row.get('Assigned To') or 
                                          'Unassigned')
                                
                                # Get priority with multiple possible column names
                                priority = (row.get('Priority') or row.get('priority') or 
                                          row.get('priority_name') or 'Unknown')
                                
                                # Create JIRA link if not provided
                                link = row.get('link', f"https://onezelis.atlassian.net/browse/{key}")
                                
                                jira_dict[key] = {
                                    'key': key,
                                    'status': status,
                                    'summary': summary,
                                    'assignee': assignee,
                                    'priority': priority,
                                    'link': link,
                                    'source': 'Uploaded CSV'
                                }
                                processed_count += 1
                            else:
                                logger.warning(f"Row {row_num}: Missing or empty issue key")
                        except Exception as e:
                            logger.error(f"Error processing row {row_num}: {e}")
                            continue
                
                logger.info(f"Processed {processed_count} tickets from CSV")
                return self.save_jira_data(jira_dict)
            else:
                logger.error(f"Unsupported file type: {file_type}. Only CSV is supported.")
                return False
            
        except Exception as e:
            logger.error(f"Error processing JIRA file: {e}")
            return False
        except Exception as e:
            logger.error(f"Error processing JIRA file: {e}")
            return False

github_service = GitHubService(GITHUB_TOKEN, GITHUB_REPO)
jira_service = JiraService()

@app.route('/')
def dashboard():
    """Main dashboard page"""
    logger.info("Dashboard accessed")
    return render_template('dashboard.html')

@app.route('/api/pr-stats')
@rate_limit(max_requests=30, window=60)
def pr_stats():
    """API endpoint to get PR statistics (optimized for speed)"""
    try:
        logger.info("PR stats requested")
        start_time = time.time()
        
        month = request.args.get('month')
        labels = request.args.getlist('labels')
        repo = request.args.get('repo', GITHUB_REPO)  # Use repo from request or default
        
        logger.debug(f"Getting PR stats for repo={repo}, month={month}, labels={labels}")
        
        # Create cache key for stats
        stats_cache_key = f"stats_{repo}_{month}_{','.join(sorted(labels))}"
        
        # Check cache first - aggressive caching for stats
        cached_data = get_cached_data()
        if cached_data and cached_data.get('cache_key') == stats_cache_key:
            logger.info(f"Returning CACHED stats (saved {time.time() - start_time:.2f}s)")
            return jsonify(cached_data['data'])
        
        # Create GitHub service for the requested repository
        current_service = GitHubService(GITHUB_TOKEN, repo) if repo != GITHUB_REPO else github_service
        
        # Get all PRs (no comments for speed)
        all_prs = current_service.get_pull_requests(month=month)
        logger.debug(f"Got {len(all_prs)} total PRs")
        
        # Get open PRs
        open_prs = [pr for pr in all_prs if pr['state'] == 'open']
        logger.debug(f"Found {len(open_prs)} open PRs")
        
        # Get closed PRs
        closed_prs = [pr for pr in all_prs if pr['state'] == 'closed']
        logger.debug(f"Found {len(closed_prs)} closed PRs")
    
        # Get PRs with specific labels (only open ones)
        if labels:
            # Filter open PRs by labels instead of getting all labeled PRs
            labeled_prs = []
            for pr in open_prs:
                pr_labels = [label['name'] for label in pr['labels']]
                if any(label.lower() in [pl.lower() for pl in pr_labels] for label in labels):
                    labeled_prs.append(pr)
            logger.debug(f"Found {len(labeled_prs)} labeled open PRs")
            # Debug: print the states of labeled PRs
            for pr in labeled_prs:
                logger.debug(f"Labeled PR #{pr['number']}: {pr['title']} - State: {pr['state']}")
        else:
            labeled_prs = []
        
        # Get testing tickets count from JIRA
        testing_count = 0
        try:
            for key, ticket in jira_service.jira_data.items():
                status = ticket.get('status', '').strip()
                # Only count tickets with exact "Testing" status
                if status.lower() == 'testing':
                    testing_count += 1
                    logger.debug(f"Testing ticket found: {key} - Status: {ticket.get('status', '')}")
        except Exception as e:
            logger.warning(f"Error counting testing tickets: {e}")
        
        stats = {
            'available_count': len(open_prs),
            'closed_count': len(closed_prs),
            'labeled_count': len(labeled_prs),
            'testing_count': testing_count,
            'total_count': len(all_prs)
        }
        
        response_time = time.time() - start_time
        logger.info(f"PR stats response time: {response_time:.2f}s")
        logger.debug(f"Returning stats: {stats}")
        
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting PR stats: {e}")
        return jsonify({'error': 'Failed to fetch PR statistics'}), 500

@app.route('/api/prs')
@rate_limit(max_requests=30, window=60)
def get_prs():
    """API endpoint to get detailed PR list"""
    try:
        logger.info("PR details requested")
        start_time = time.time()
        
        pr_type = request.args.get('type', 'open')
        month = request.args.get('month')
        labels = request.args.getlist('labels')
        repo = request.args.get('repo', GITHUB_REPO)  # Use repo from request or default
        sort_by = request.args.get('sort', 'newest')  # newest, oldest, most_recent, updated
        include_comments = request.args.get('include_comments', 'false').lower() == 'true'
        
        logger.debug(f"Getting PRs: type={pr_type}, month={month}, labels={labels}, repo={repo}, sort={sort_by}, include_comments={include_comments}")
        
        # Create cache key based on request parameters
        cache_key_base = f"{pr_type}_{month}_{','.join(sorted(labels))}_{repo}_{sort_by}"
        cache_key = f"{cache_key_base}_comments_{include_comments}"
        logger.debug(f"Cache key: {cache_key}")
        
        # Check cache to improve performance
        cached_data = get_cached_data()
        if cached_data and cached_data.get('cache_key') == cache_key:
            logger.info(f"Returning cached data for key: {cache_key} (saved {time.time() - start_time:.2f}s)")
            return jsonify(cached_data['data'])
        else:
            logger.debug(f"Cache miss for key: {cache_key} (cached_key: {cached_data.get('cache_key') if cached_data else 'None'})")
        
        # Create GitHub service for the requested repository
        current_service = GitHubService(GITHUB_TOKEN, repo) if repo != GITHUB_REPO else github_service
        
        if pr_type == 'labeled':
            # Get only open PRs and filter by labels
            all_prs = current_service.get_pull_requests(state='open', month=month)
            logger.debug(f"Got {len(all_prs)} open PRs for label filtering")
            prs = []
            if labels:
                for pr in all_prs:
                    pr_labels = [label['name'] for label in pr['labels']]
                    if any(label.lower() in [pl.lower() for pl in pr_labels] for label in labels):
                        prs.append(pr)
                        logger.debug(f"Including labeled PR #{pr['number']}: {pr['title']} - State: {pr['state']}")
            else:
                prs = all_prs
            logger.debug(f"Final labeled PRs count: {len(prs)}")
        elif pr_type == 'all':
            # Get both open and closed PRs
            open_prs = current_service.get_pull_requests(state='open', month=month)
            closed_prs = current_service.get_pull_requests(state='closed', month=month)
            prs = open_prs + closed_prs
            logger.debug(f"Got {len(open_prs)} open + {len(closed_prs)} closed = {len(prs)} total PRs")
        else:
            # Get PRs for specific state (open or closed)
            prs = current_service.get_pull_requests(state=pr_type, month=month)
    
        # Format PR data for frontend and optionally get last comment dates and review status
        formatted_prs = []
        
        # If comments are requested, fetch them only for open PRs (available/labeled)
        comment_dates = {}
        if include_comments and prs:
            # Only fetch comments for open PRs - closed PRs don't need comment info
            open_prs_for_comments = [pr for pr in prs if pr['state'] == 'open']
            
            if open_prs_for_comments:
                logger.info(f"Fetching comments for {len(open_prs_for_comments)} open PRs in parallel...")
                import concurrent.futures
                
                def fetch_comment_for_pr(pr):
                    try:
                        return pr['number'], current_service.get_pr_last_comment_date(pr['number'])
                    except Exception as e:
                        logger.error(f"Failed to fetch comment for PR #{pr['number']}: {e}")
                        return pr['number'], None
                
                # Limit concurrent requests to avoid overwhelming the API
                max_workers = min(3, len(open_prs_for_comments))
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    comment_futures = [executor.submit(fetch_comment_for_pr, pr) for pr in open_prs_for_comments]
                    for future in concurrent.futures.as_completed(comment_futures, timeout=60):
                        try:
                            pr_number, comment_date = future.result(timeout=10)
                            comment_dates[pr_number] = comment_date
                        except Exception as e:
                            logger.error(f"Error fetching comment for PR: {e}")
                            # Continue processing other PRs even if one fails
            else:
                logger.info("No open PRs found - skipping comment fetching")
        
        for pr in prs:
            # Get last comment date from parallel fetch results
            last_comment_date = comment_dates.get(pr['number']) if include_comments else None
            
            # Get review status for open PRs
            review_status = None
            if pr['state'] == 'open':
                review_status = current_service.get_pr_review_status(pr['number'])
            
            # Extract and get JIRA ticket information
            # Handle None values properly for title and body
            pr_title = pr.get('title') or ''
            pr_body = pr.get('body') or ''
            jira_keys = jira_service.extract_jira_keys(pr_title + ' ' + pr_body)
            jira_tickets = jira_service.get_multiple_tickets_status(jira_keys) if jira_keys else []
            
            formatted_prs.append({
                'title': pr_title,
                'number': pr['number'],
                'state': pr['state'],
                'created_at': pr['created_at'],
                'updated_at': pr['updated_at'],
                'last_comment_at': last_comment_date,
                'review_status': review_status,
                'jira_tickets': jira_tickets,
                'html_url': pr['html_url'],
                'user': pr.get('user', {}).get('login', 'Unknown'),
                'labels': [label['name'] for label in pr.get('labels', [])]
            })
        
        # Sort PRs based on sort parameter
        if sort_by == 'newest':
            # Most recently created first
            formatted_prs.sort(key=lambda x: x['created_at'], reverse=True)
        elif sort_by == 'oldest':
            # Oldest created first
            formatted_prs.sort(key=lambda x: x['created_at'], reverse=False)
        elif sort_by == 'most_recent':
            # Most recently updated first
            formatted_prs.sort(key=lambda x: x['updated_at'], reverse=True)
        
        response_time = time.time() - start_time
        logger.info(f"PR details response time: {response_time:.2f}s, returned {len(formatted_prs)} PRs")
        
        # Cache the result for faster future requests
        cache_data = {
            'cache_key': cache_key,
            'data': formatted_prs
        }
        set_cache_data(cache_data)
        logger.info(f"Cached data for key: {cache_key}")
        
        return jsonify(formatted_prs)
    except Exception as e:
        logger.error(f"Error getting PR details: {e}", exc_info=True)
        # Return more specific error information for debugging
        error_details = {
            'error': f'Failed to fetch PR details: {str(e)}',
            'type': pr_type,
            'repo': repo,
            'details': str(e)
        }
        return jsonify(error_details), 500

@app.route('/api/debug/closed-prs')
def debug_closed_prs():
    """Debug endpoint for testing closed PRs specifically"""
    try:
        logger.info("Testing closed PRs fetch...")
        current_service = GitHubService(GITHUB_TOKEN, GITHUB_REPO)
        closed_prs = current_service.get_pull_requests(state='closed')
        logger.info(f"Successfully fetched {len(closed_prs)} closed PRs")
        return jsonify({
            'success': True,
            'count': len(closed_prs),
            'sample': closed_prs[:3] if closed_prs else []
        })
    except Exception as e:
        logger.error(f"Error fetching closed PRs: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

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

@app.route('/api/available-labels')
def available_labels():
    """Get available labels from PRs"""
    try:
        repo = request.args.get('repo', GITHUB_REPO)  # Use repo from request or default
        
        # Create GitHub service for the requested repository
        current_service = GitHubService(GITHUB_TOKEN, repo) if repo != GITHUB_REPO else github_service
        
        prs = current_service.get_pull_requests()
        labels = set()
        
        for pr in prs:
            for label in pr.get('labels', []):
                labels.add(label['name'])
        
        return jsonify(sorted(list(labels)))
    except Exception as e:
        print(f"Error getting available labels: {e}")
        # Return some default labels if there's an error
        return jsonify(['bug', 'feature', 'enhancement', 'documentation', 'performance'])

@app.route('/api/test-mock')
def test_mock():
    """Test endpoint to force mock data"""
    mock_data = github_service._get_mock_data()
    return jsonify({
        'count': len(mock_data),
        'sample': mock_data[0] if mock_data else None
    })

@app.route('/api/reviewer-stats')
def get_reviewer_stats():
    """Get reviewer statistics for open PRs"""
    try:
        repo = request.args.get('repo', GITHUB_REPO)
        month = request.args.get('month')
        
        # Create GitHub service for the requested repository
        current_service = GitHubService(GITHUB_TOKEN, repo) if repo != GITHUB_REPO else github_service
        
        # Get open PRs
        prs = current_service.get_pull_requests(state='open', month=month)
        
        # Count PRs per reviewer
        reviewer_stats = {}
        
        for pr in prs:
            # Get requested reviewers
            requested_reviewers = pr.get('requested_reviewers', [])
            
            # Also check for review requests from teams (if any)
            requested_teams = pr.get('requested_teams', [])
            
            # Count individual reviewers
            for reviewer in requested_reviewers:
                reviewer_login = reviewer['login']
                if reviewer_login not in reviewer_stats:
                    reviewer_stats[reviewer_login] = {
                        'name': reviewer_login,
                        'avatar_url': reviewer.get('avatar_url', ''),
                        'count': 0,
                        'prs': []
                    }
                reviewer_stats[reviewer_login]['count'] += 1
                reviewer_stats[reviewer_login]['prs'].append({
                    'number': pr['number'],
                    'title': pr['title'],
                    'html_url': pr['html_url'],
                    'created_at': pr['created_at']
                })
            
            # Count team reviewers
            for team in requested_teams:
                team_name = f"@{team['name']}"
                if team_name not in reviewer_stats:
                    reviewer_stats[team_name] = {
                        'name': team_name,
                        'avatar_url': '',
                        'count': 0,
                        'prs': []
                    }
                reviewer_stats[team_name]['count'] += 1
                reviewer_stats[team_name]['prs'].append({
                    'number': pr['number'],
                    'title': pr['title'],
                    'html_url': pr['html_url'],
                    'created_at': pr['created_at']
                })
        
        # Convert to list and sort by count
        reviewer_list = list(reviewer_stats.values())
        reviewer_list.sort(key=lambda x: x['count'], reverse=True)
        
        return jsonify({
            'reviewers': reviewer_list,
            'total_reviewers': len(reviewer_list),
            'total_pending_reviews': sum(r['count'] for r in reviewer_list)
        })
        
    except Exception as e:
        print(f"Error getting reviewer stats: {e}")
        return jsonify({'reviewers': [], 'total_reviewers': 0, 'total_pending_reviews': 0}), 500

@app.route('/api/reviewer-prs')
def get_reviewer_prs():
    """Get PRs assigned to a specific reviewer"""
    try:
        reviewer = request.args.get('reviewer')
        repo = request.args.get('repo', GITHUB_REPO)
        month = request.args.get('month')
        
        if not reviewer:
            return jsonify({'error': 'Reviewer parameter required'}), 400
        
        # Create GitHub service for the requested repository
        current_service = GitHubService(GITHUB_TOKEN, repo) if repo != GITHUB_REPO else github_service
        
        # Get open PRs
        prs = current_service.get_pull_requests(state='open', month=month)
        
        # Filter PRs for the specific reviewer
        reviewer_prs = []
        for pr in prs:
            requested_reviewers = pr.get('requested_reviewers', [])
            requested_teams = pr.get('requested_teams', [])
            
            # Check if reviewer is in requested reviewers
            is_reviewer = any(r['login'] == reviewer for r in requested_reviewers)
            
            # Check if reviewer is a team (starts with @)
            if reviewer.startswith('@'):
                team_name = reviewer[1:]  # Remove @ prefix
                is_reviewer = any(t['name'] == team_name for t in requested_teams)
            
            if is_reviewer:
                reviewer_prs.append({
                    'number': pr['number'],
                    'title': pr['title'],
                    'html_url': pr['html_url'],
                    'created_at': pr['created_at'],
                    'updated_at': pr['updated_at'],
                    'user': pr['user']['login'],
                    'labels': [label['name'] for label in pr['labels']]
                })
        
        return jsonify(reviewer_prs)
        
    except Exception as e:
        print(f"Error getting reviewer PRs: {e}")
        return jsonify([]), 500

@app.route('/api/jira/upload', methods=['POST'])
def upload_jira_file():
    """Upload JIRA data file (CSV or JSON)"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Check file extension
        filename = secure_filename(file.filename)
        file_ext = filename.lower().split('.')[-1]
        
        if file_ext not in ['csv', 'json']:
            return jsonify({'error': 'Only CSV and JSON files are supported'}), 400
        
        # Save uploaded file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f'uploaded_jira.{file_ext}')
        file.save(file_path)
        
        # Process the file
        success = jira_service.process_uploaded_file(file_path, file_ext)
        
        # Clean up uploaded file
        os.remove(file_path)
        
        if success:
            return jsonify({
                'message': 'JIRA data uploaded successfully',
                'tickets_count': len(jira_service.jira_data)
            })
        else:
            return jsonify({'error': 'Failed to process JIRA file'}), 400
            
    except Exception as e:
        logger.error(f"Error uploading JIRA file: {e}")
        return jsonify({'error': 'Failed to upload JIRA file'}), 500

@app.route('/api/jira/status')
def get_jira_status():
    """Get current JIRA data status"""
    try:
        return jsonify({
            'loaded': len(jira_service.jira_data) > 0,
            'tickets_count': len(jira_service.jira_data),
            'sample_tickets': list(jira_service.jira_data.keys())[:5] if jira_service.jira_data else [],
            'uploaded_at': jira_service.upload_metadata.get('uploaded_at') if jira_service.upload_metadata else None,
            'upload_metadata': jira_service.upload_metadata
        })
    except Exception as e:
        logger.error(f"Error getting JIRA status: {e}")
        return jsonify({'error': 'Failed to get JIRA status'}), 500

@app.route('/api/jira/tickets')
def get_jira_tickets():
    """Get all uploaded JIRA tickets"""
    try:
        tickets = []
        for key, ticket in jira_service.jira_data.items():
            tickets.append({
                'key': key,
                'summary': ticket.get('summary', 'No summary'),
                'status': ticket.get('status', 'Unknown'),
                'status_category': ticket.get('status_category', 'Unknown'),
                'assignee': ticket.get('assignee', 'Unassigned'),
                'priority': ticket.get('priority', 'Unknown'),
                'issue_type': ticket.get('issue_type', 'Unknown'),
                'created': ticket.get('created', ''),
                'updated': ticket.get('updated', ''),
                'description': ticket.get('description', '')[:200] + '...' if ticket.get('description', '') else ''
            })
        
        # Sort tickets by key
        tickets.sort(key=lambda x: x['key'])
        
        return jsonify({
            'tickets': tickets,
            'total_count': len(tickets)
        })
    except Exception as e:
        logger.error(f"Error getting JIRA tickets: {e}")
        return jsonify({'error': 'Failed to get JIRA tickets'}), 500

@app.route('/api/jira/testing-tickets')
def get_testing_tickets():
    """Get JIRA tickets that are under testing"""
    try:
        testing_tickets = []
        for key, ticket in jira_service.jira_data.items():
            status = ticket.get('status', '').strip()
            # Only count tickets with exact "Testing" status
            if status.lower() == 'testing':
                testing_tickets.append({
                    'key': key,
                    'summary': ticket.get('summary', 'No summary'),
                    'status': ticket.get('status', 'Unknown'),
                    'status_category': jira_service.get_status_category(ticket.get('status', 'Unknown')),
                    'assignee': ticket.get('assignee', 'Unassigned'),
                    'priority': ticket.get('priority', 'Unknown'),
                    'link': ticket.get('link', f"https://onezelis.atlassian.net/browse/{key}"),
                    'created': ticket.get('created', ''),
                    'updated': ticket.get('updated', '')
                })
        
        # Sort tickets by key
        testing_tickets.sort(key=lambda x: x['key'])
        
        return jsonify({
            'tickets': testing_tickets,
            'total_count': len(testing_tickets)
        })
    except Exception as e:
        logger.error(f"Error getting testing tickets: {e}")
        return jsonify({'error': 'Failed to get testing tickets'}), 500

@app.route('/api/jira/clear', methods=['POST'])
def clear_jira_data():
    """Clear JIRA data"""
    try:
        jira_service.jira_data = {}
        jira_file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'jira_data.json')
        if os.path.exists(jira_file_path):
            os.remove(jira_file_path)
        return jsonify({'message': 'JIRA data cleared successfully'})
    except Exception as e:
        logger.error(f"Error clearing JIRA data: {e}")
        return jsonify({'error': 'Failed to clear JIRA data'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)