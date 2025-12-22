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
from cache_db import cache_db
from collections import defaultdict

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

# Cache is now handled by cache_db module

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

# Cache is now handled by cache_db module - old functions removed

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
GITHUB_TOKEN_ZDI = os.getenv('GITHUB_TOKEN_ZDI')
GITHUB_TOKEN_IE = os.getenv('GITHUB_TOKEN_IE')
GITHUB_REPO = os.getenv('GITHUB_REPO', 'microsoft/vscode')  # Default to a public repo
BASE_URL = 'https://api.github.com'

# Helper function to get enterprise token
def get_enterprise_token(enterprise):
    if enterprise == 'zdi':
        return GITHUB_TOKEN_ZDI
    elif enterprise == 'ie':
        return GITHUB_TOKEN_IE
    else:
        return GITHUB_TOKEN

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
        """Fetch pull requests from GitHub API with proper pagination"""
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
            'per_page': 100,  # Maximum per page
            'sort': 'created',
            'direction': 'desc'
        }
        
        all_prs = []
        page = 1
        # Higher limit for open PRs to get all reviewers, lower for closed to avoid performance issues
        max_pages = 10 if state == 'open' else 5
        
        try:
            while page <= max_pages:
                current_params = params.copy()
                current_params['page'] = page
                
                logger.debug(f"Fetching PRs page {page} from {url} with params {current_params}")
                response = requests.get(url, headers=self.headers, params=current_params, timeout=30)
                
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
                logger.debug(f"Retrieved {len(prs)} PRs from API page {page}")
                
                if not prs:  # No more PRs, break the loop
                    break
                    
                all_prs.extend(prs)
                
                # If we got less than per_page PRs, we're on the last page
                if len(prs) < params['per_page']:
                    break
                    
                page += 1
            
            logger.info(f"PAGINATION DEBUG - Total PRs fetched across all pages: {len(all_prs)} for state='{state}'")
            
            # Filter by month if specified
            if month:
                filtered_prs = []
                for pr in all_prs:
                    created_date = datetime.strptime(pr['created_at'], '%Y-%m-%dT%H:%M:%SZ')
                    if created_date.strftime('%Y-%m') == month:
                        filtered_prs.append(pr)
                all_prs = filtered_prs
                logger.debug(f"After month filter ({month}): {len(all_prs)} PRs")
            
            # Filter by labels if specified
            if labels:
                filtered_prs = []
                for pr in all_prs:
                    pr_labels = [label['name'] for label in pr['labels']]
                    if any(label.lower() in [pl.lower() for pl in pr_labels] for label in labels):
                        filtered_prs.append(pr)
                all_prs = filtered_prs
                logger.debug(f"After label filter ({labels}): {len(all_prs)} PRs")
            
            return all_prs
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

# Initialize cache and clean up expired entries
try:
    expired_count = cache_db.clear_expired()
    cache_info = cache_db.get_cache_info()
    logger.info(f"Cache initialized - {cache_info['valid_entries']} valid entries, cleared {expired_count} expired entries")
except Exception as e:
    logger.error(f"Error initializing cache: {e}")

@app.route('/')
def dashboard():
    """Main dashboard page"""
    logger.info("Dashboard accessed")
    return render_template('dashboard.html')


@app.route('/metrics')
def metrics():
    """Executive metrics dashboard"""
    logger.info("Metrics dashboard accessed")
    return render_template('metrics.html')

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
        enterprise = request.args.get('enterprise', 'zdi')  # Default to zdi
        
        logger.info(f"DEBUG - PR STATS REQUEST - enterprise={enterprise}, repo={repo}, month={month}, labels={labels}")
        logger.debug(f"Getting PR stats for enterprise={enterprise}, repo={repo}, month={month}, labels={labels}")
        
        # Get the appropriate token for the enterprise
        token = get_enterprise_token(enterprise)
        
        # Create cache key for stats
        stats_cache_key = f"pr_stats_{enterprise}_{repo}_{month or 'all'}_{','.join(sorted(labels))}"
        
        # Check database cache first (5 minute TTL for fast responses)
        # Skip cache if refresh is requested
        skip_cache = request.args.get('refresh', '').lower() == 'true'
        cached_stats = None if skip_cache else cache_db.get_cache(stats_cache_key)
        if cached_stats:
            logger.info(f"Returning CACHED stats from DB (saved {time.time() - start_time:.2f}s)")
            return jsonify(cached_stats)
        
        # Create GitHub service for the requested repository
        current_service = GitHubService(token, repo)
        
        # Use same logic as PR details endpoint - force fresh API call
        logger.info(f"PR STATS DEBUG - Making DIRECT GitHub API call for open PRs")
        
        # Make direct API call with pagination
        import requests
        api_url = f'https://api.github.com/repos/{repo}/pulls'
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'Authorization': f'token {token}',
            'User-Agent': 'GitHub-PR-Dashboard'
        }
        
        all_open_prs = []
        page = 1
        
        while page <= 2:  # Max 2 pages to get recent PRs (200 open PRs max)
            params = {
                'state': 'open',
                'per_page': 100,
                'page': page,
                'sort': 'created',
                'direction': 'desc'
            }
            
            response = requests.get(api_url, headers=headers, params=params, timeout=30)
            if response.status_code == 200:
                prs = response.json()
                if not prs:
                    break
                all_open_prs.extend(prs)
                logger.info(f"PR STATS DEBUG - Page {page}: Got {len(prs)} PRs")
                if len(prs) < 100:
                    break
                page += 1
            else:
                logger.error(f"GitHub API error: {response.status_code}")
                break
        
        # Apply month filtering if specified
        if month:
            filtered_open_prs = []
            for pr in all_open_prs:
                created_date = datetime.strptime(pr['created_at'], '%Y-%m-%dT%H:%M:%SZ')
                if created_date.strftime('%Y-%m') == month:
                    filtered_open_prs.append(pr)
            open_prs = filtered_open_prs
            logger.info(f"DEBUG - After month filter ({month}): {len(open_prs)} open PRs")
        else:
            open_prs = all_open_prs
        
        logger.info(f"PR STATS DEBUG - FINAL OPEN PR COUNT: {len(open_prs)}")
        
        # Get closed PRs with same logic - increase pagination for accurate count
        all_closed_prs = []
        page = 1
        
        while page <= 20:  # Max 20 pages for closed PRs (2000 closed PRs max)
            params = {
                'state': 'closed',
                'per_page': 100,
                'page': page,
                'sort': 'created',
                'direction': 'desc'
            }
            
            response = requests.get(api_url, headers=headers, params=params, timeout=30)
            if response.status_code == 200:
                prs = response.json()
                if not prs:
                    break
                all_closed_prs.extend(prs)
                logger.info(f"PR STATS DEBUG - Closed PRs Page {page}: Got {len(prs)} PRs")
                if len(prs) < 100:
                    break
                page += 1
            else:
                logger.error(f"GitHub API error for closed PRs: {response.status_code}")
                break
                
        # Apply month filtering to closed PRs if specified
        if month:
            filtered_closed_prs = []
            for pr in all_closed_prs:
                created_date = datetime.strptime(pr['created_at'], '%Y-%m-%dT%H:%M:%SZ')
                if created_date.strftime('%Y-%m') == month:
                    filtered_closed_prs.append(pr)
            closed_prs = filtered_closed_prs
            logger.info(f"DEBUG - After month filter ({month}): {len(closed_prs)} closed PRs")
        else:
            closed_prs = all_closed_prs
        
        logger.info(f"PR STATS DEBUG - FINAL CLOSED PR COUNT: {len(closed_prs)}")
        all_prs = open_prs + closed_prs
    
        # Get PRs with specific labels (only open ones) - using filtered open_prs
        if labels:
            # Filter open PRs by labels instead of getting all labeled PRs
            labeled_prs = []
            added_pr_numbers = set()  # Track added PRs to avoid duplicates
            
            for pr in open_prs:  # Use already filtered open_prs which includes month filter
                pr_labels = [label['name'] for label in pr['labels']]
                pr_number = pr['number']
                
                # Skip if already added
                if pr_number in added_pr_numbers:
                    continue
                
                # Check if "none" is in the filter (for PRs with no labels)
                if 'none' in labels and not pr_labels:
                    labeled_prs.append(pr)
                    added_pr_numbers.add(pr_number)
                    logger.debug(f"Including unlabeled PR #{pr['number']}: {pr['title']} - State: {pr['state']}")
                    continue
                
                # Check for specific labels (excluding "none")
                other_labels = [l for l in labels if l != 'none']
                if other_labels and pr_labels:
                    if any(label.lower() in [pl.lower() for pl in pr_labels] for label in other_labels):
                        labeled_prs.append(pr)
                        added_pr_numbers.add(pr_number)
                        logger.debug(f"Including labeled PR #{pr['number']}: {pr['title']} - State: {pr['state']}")
            
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
        
        # FINAL DEBUG - Show exactly what we're returning
        logger.info(f"DEBUG - FINAL STATS BEING RETURNED:")
        logger.info(f"DEBUG - Available Count (open PRs): {len(open_prs)}")
        logger.info(f"DEBUG - Closed Count: {len(closed_prs)}")
        logger.info(f"DEBUG - Total Count: {len(all_prs)}")
        
        # Log sample PR numbers for verification
        if open_prs:
            open_pr_numbers = [pr['number'] for pr in open_prs[:10]]  # First 10
            logger.info(f"DEBUG - FIRST 10 OPEN PR NUMBERS: {open_pr_numbers}")
        
        if closed_prs:
            closed_pr_numbers = [pr['number'] for pr in closed_prs[:10]]  # First 10
            logger.info(f"DEBUG - FIRST 10 CLOSED PR NUMBERS: {closed_pr_numbers}")
        
        response_time = time.time() - start_time
        logger.info(f"PR stats response time: {response_time:.2f}s")
        logger.debug(f"Returning stats: {stats}")
        
        # Cache the stats in database for faster subsequent requests (5 minute TTL)
        cache_db.set_cache(stats_cache_key, stats, ttl_seconds=300)  # 5 minutes cache
        logger.info(f"Cached stats for key: {stats_cache_key}")
        
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
        enterprise = request.args.get('enterprise', 'zdi')  # Default to zdi
        sort_by = request.args.get('sort', 'newest')  # newest, oldest, most_recent, updated
        include_comments = request.args.get('include_comments', 'false').lower() == 'true'
        # Server-side pagination params
        try:
            page = int(request.args.get('page', '1'))
            per_page = int(request.args.get('per_page', '6'))
            if page < 1:
                page = 1
            if per_page < 1:
                per_page = 6
        except Exception:
            page = 1
            per_page = 6
        
        logger.debug(f"Getting PRs: type={pr_type}, month={month}, labels={labels}, repo={repo}, sort={sort_by}, include_comments={include_comments}")
        
        # Get the appropriate token for the enterprise
        token = get_enterprise_token(enterprise)
        
        # Create cache key based on request parameters
        cache_key_base = f"{enterprise}_{pr_type}_{month or 'all'}_{','.join(sorted(labels))}_{repo}_{sort_by}_p{page}_pp{per_page}"
        # Versioned cache key to ensure new fields (display_state/is_draft) propagate
        cache_key = f"prs_{cache_key_base}_v2_comments_{include_comments}"
        logger.debug(f"Cache key: {cache_key}")
        
        # Check database cache first (3 minute TTL for PR details)
        cached_prs = cache_db.get_cache(cache_key)
        if cached_prs:
            logger.info(f"Returning cached PR data from DB (saved {time.time() - start_time:.2f}s)")
            return jsonify(cached_prs)
        
        # Create GitHub service for the requested repository with enterprise token
        current_service = GitHubService(token, repo)
        
        if pr_type == 'labeled':
            # Get only open PRs and filter by labels
            all_prs = current_service.get_pull_requests(state='open', month=month)
            logger.debug(f"Got {len(all_prs)} open PRs for label filtering")
            prs = []
            if labels:
                added_pr_numbers = set()  # Track added PRs to avoid duplicates
                
                for pr in all_prs:
                    pr_labels = [label['name'] for label in pr['labels']]
                    pr_number = pr['number']
                    
                    # Skip if already added
                    if pr_number in added_pr_numbers:
                        continue
                    
                    # Check if "none" is in the filter (for PRs with no labels)
                    if 'none' in labels and not pr_labels:
                        prs.append(pr)
                        added_pr_numbers.add(pr_number)
                        logger.debug(f"Including unlabeled PR #{pr['number']}: {pr['title']} - State: {pr['state']}")
                        continue
                    
                    # Check for specific labels (excluding "none")
                    other_labels = [l for l in labels if l != 'none']
                    if other_labels and pr_labels:
                        if any(label.lower() in [pl.lower() for pl in pr_labels] for label in other_labels):
                            prs.append(pr)
                            added_pr_numbers.add(pr_number)
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
    
        # Sort raw PRs before pagination to keep consistent ordering
        if sort_by == 'newest':
            prs.sort(key=lambda x: x['created_at'], reverse=True)
        elif sort_by == 'oldest':
            prs.sort(key=lambda x: x['created_at'], reverse=False)
        elif sort_by == 'most_recent':
            prs.sort(key=lambda x: x['updated_at'], reverse=True)

        total_items = len(prs)
        total_pages = max(1, (total_items + per_page - 1) // per_page)
        # Compute slice indices for server-side pagination
        start_index = (page - 1) * per_page
        end_index = min(start_index + per_page, total_items)
        page_prs = prs[start_index:end_index]

        # Format PR data for frontend and optionally get last comment dates and review status
        formatted_prs = []
        
        # If comments are requested, fetch them only for open PRs (available/labeled)
        comment_dates = {}
        if include_comments and page_prs:
            # Only fetch comments for open PRs - closed PRs don't need comment info
            open_prs_for_comments = [pr for pr in page_prs if pr['state'] == 'open']
            
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
        
        for pr in page_prs:
            # Get last comment date from parallel fetch results
            last_comment_date = comment_dates.get(pr['number']) if include_comments else None
            
            # Get review status for open PRs (skip for faster loading unless specifically requested)
            review_status = None
            if pr['state'] == 'open' and include_comments:  # Only fetch when comments are requested
                review_status = current_service.get_pr_review_status(pr['number'])
            
            # Extract and get JIRA ticket information (always include field for compatibility)
            pr_title = pr.get('title') or ''
            pr_body = pr.get('body') or ''
            jira_keys = jira_service.extract_jira_keys(pr_title + ' ' + pr_body)
            jira_tickets = jira_service.get_multiple_tickets_status(jira_keys) if jira_keys else []

            # Preserve GitHub state but surface draft explicitly for UI consumers
            is_draft = pr.get('draft', False)
            display_state = 'draft' if is_draft else pr['state']
            
            formatted_prs.append({
                'title': pr_title,
                'number': pr['number'],
                'state': pr['state'],
                'display_state': display_state,
                'is_draft': is_draft,
                'draft': is_draft,
                'created_at': pr['created_at'],
                'updated_at': pr['updated_at'],
                'last_comment_at': last_comment_date,
                'review_status': review_status,
                'jira_tickets': jira_tickets,
                'html_url': pr['html_url'],
                'user': pr.get('user', {}).get('login', 'Unknown'),
                'labels': [label['name'] for label in pr.get('labels', [])]
            })
        
        response_time = time.time() - start_time
        logger.info(f"PR details response time: {response_time:.2f}s, returned {len(formatted_prs)} PRs (page {page}/{total_pages}, total {total_items})")

        result = {
            'items': formatted_prs,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'total_items': total_items
        }

        # Cache the result in database for faster future requests (10 minute TTL for better performance)
        cache_db.set_cache(cache_key, result, ttl_seconds=600)  # 10 minutes cache for PR details
        logger.info(f"Cached PR data for key: {cache_key}")

        return jsonify(result)
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
        repo = request.args.get('repo', GITHUB_REPO)
        enterprise = request.args.get('enterprise', 'zdi')
        cache_key = f"months_{enterprise}_{repo}"
        
        # Check cache first (10 minute TTL)
        cached_months = cache_db.get_cache(cache_key)
        if cached_months:
            return jsonify(cached_months)
        
        # Get the appropriate token for the enterprise
        token = get_enterprise_token(enterprise)
        
        # Create GitHub service for the requested repository
        current_service = GitHubService(token, repo)
        
        prs = current_service.get_pull_requests()
        months = set()
        
        for pr in prs:
            created_date = datetime.strptime(pr['created_at'], '%Y-%m-%dT%H:%M:%SZ')
            months.add(created_date.strftime('%Y-%m'))
        
        result = sorted(list(months), reverse=True)
        
        # Cache result for 10 minutes
        cache_db.set_cache(cache_key, result, ttl_seconds=600)
        
        return jsonify(result)
    except Exception as e:
        print(f"Error getting available months: {e}")
        # Return some default months if there's an error
        return jsonify(['2024-10', '2024-09', '2024-08'])

@app.route('/api/available-labels')
def available_labels():
    """Get available labels from PRs"""
    try:
        repo = request.args.get('repo', GITHUB_REPO)
        enterprise = request.args.get('enterprise', 'zdi')
        cache_key = f"labels_{enterprise}_{repo}"
        
        # Check cache first (10 minute TTL)
        cached_labels = cache_db.get_cache(cache_key)
        if cached_labels:
            return jsonify(cached_labels)
        
        # Get the appropriate token for the enterprise
        token = get_enterprise_token(enterprise)
        
        # Create GitHub service for the requested repository
        current_service = GitHubService(token, repo)
        
        prs = current_service.get_pull_requests()
        labels = set()
        
        for pr in prs:
            for label in pr.get('labels', []):
                labels.add(label['name'])
        
        result = sorted(list(labels))
        
        # Cache result for 10 minutes
        cache_db.set_cache(cache_key, result, ttl_seconds=600)
        
        return jsonify(result)
    except Exception as e:
        print(f"Error getting available labels: {e}")
        # Return some default labels if there's an error
        return jsonify(['bug', 'feature', 'enhancement', 'documentation', 'performance'])


@app.route('/api/metrics')
@rate_limit(max_requests=20, window=60)
def get_metrics_dashboard():
    """Aggregated PR metrics for the metrics dashboard"""
    repo = request.args.get('repo', GITHUB_REPO)
    enterprise = request.args.get('enterprise', 'zdi')
    label = request.args.get('label')
    start = request.args.get('start')  # YYYY-MM-DD
    end = request.args.get('end')      # YYYY-MM-DD

    token = get_enterprise_token(enterprise)
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'GitHub-PR-Dashboard'
    }
    if token:
        headers['Authorization'] = f'token {token}'

    def parse_date(dt_str):
        return datetime.strptime(dt_str, '%Y-%m-%dT%H:%M:%SZ') if dt_str else None

    prs = []
    page = 1
    try:
        while page <= 10:
            resp = requests.get(
                f'{BASE_URL}/repos/{repo}/pulls',
                headers=headers,
                params={'state': 'all', 'per_page': 100, 'page': page, 'sort': 'created', 'direction': 'desc'},
                timeout=30
            )
            if resp.status_code != 200:
                logger.error(f"Metrics fetch failed: {resp.status_code} {resp.text}")
                return jsonify({'error': f'GitHub API error {resp.status_code}', 'details': resp.text}), 500
            batch = resp.json()
            if not batch:
                break
            prs.extend(batch)
            if len(batch) < 100:
                break
            page += 1
    except Exception as exc:
        logger.error(f"Metrics fetch exception: {exc}", exc_info=True)
        return jsonify({'error': 'Failed to fetch metrics data', 'details': str(exc)}), 500

    start_dt = datetime.strptime(start, '%Y-%m-%d') if start else None
    end_dt = datetime.strptime(end, '%Y-%m-%d') if end else None

    def in_range(dt_obj):
        if not dt_obj:
            return False
        d = dt_obj.date()
        if start_dt and d < start_dt.date():
            return False
        if end_dt and d > end_dt.date():
            return False
        return True

    created_bucket = defaultdict(list)
    merged_bucket = defaultdict(list)
    closed_bucket = defaultdict(list)
    created_trace = []
    merged_trace = []

    for pr in prs:
        pr_labels_raw = [lbl.get('name') for lbl in pr.get('labels', [])]
        if label and label.lower() != 'all':
            target = label.lower()
            pr_label_lc = [l.lower() for l in pr_labels_raw if l]
            if target not in pr_label_lc:
                continue

        created_dt = parse_date(pr.get('created_at'))
        merged_dt = parse_date(pr.get('merged_at'))
        closed_dt = parse_date(pr.get('closed_at'))

        if created_dt and in_range(created_dt):
            created_bucket[created_dt.date().isoformat()].append(pr)
            created_trace.append((created_dt.date().isoformat(), pr.get('number')))

        if merged_dt and in_range(merged_dt):
            merged_bucket[merged_dt.date().isoformat()].append(pr)
            merged_trace.append((merged_dt.date().isoformat(), pr.get('number')))

        if closed_dt and not merged_dt and in_range(closed_dt):
            closed_bucket[closed_dt.date().isoformat()].append(pr)

    all_dates = sorted(set(list(created_bucket.keys()) + list(merged_bucket.keys()) + list(closed_bucket.keys())))

    day_items = []
    for day in all_dates:
        created_items = created_bucket.get(day, [])
        merged_items = merged_bucket.get(day, [])
        closed_items = closed_bucket.get(day, [])

        created_count = len(created_items)
        merged_count = len(merged_items)
        closed_without_merge = len(closed_items)

        cycles = []
        reviews = []
        for pr in merged_items:
            c_dt = parse_date(pr.get('created_at'))
            m_dt = parse_date(pr.get('merged_at'))
            if c_dt and m_dt:
                delta_sec = max((m_dt - c_dt).total_seconds(), 0)
                cycles.append(delta_sec / 86400)
                reviews.append(delta_sec / 3600)

        avg_cycle = round(sum(cycles) / len(cycles), 1) if cycles else 0
        avg_review = round(sum(reviews) / len(reviews), 1) if reviews else 0

        day_items.append({
            'date': day,
            'repo': repo,
            'label': label or 'all',
            'created': created_count,
            'merged': merged_count,
            'closed': closed_without_merge,
            'cycle': avg_cycle,
            'reviewHrs': avg_review,
            'openCount': 0,
            'mergedCount': merged_count
        })

    day_items.sort(key=lambda x: x['date'])

    total_created = sum(d['created'] for d in day_items)
    total_merged = sum(d['merged'] for d in day_items)
    total_closed_no_merge = sum(d['closed'] for d in day_items)
    all_cycles = [d['cycle'] for d in day_items if d['cycle']]
    avg_cycle = round(sum(all_cycles) / len(all_cycles), 1) if all_cycles else 0

    peak_day = max(day_items, key=lambda x: x['created'], default=None)
    merge_rate = int((total_merged / total_created) * 100) if total_created else 0
    review_series = [d['reviewHrs'] for d in day_items if d['reviewHrs']]
    review_delta = None
    if len(review_series) >= 2:
        review_delta = round(review_series[-1] - review_series[0], 1)

    # Debug logging to trace per-day counts and included PRs
    try:
        logger.info("/api/metrics filters repo=%s enterprise=%s start=%s end=%s label=%s", repo, enterprise, start, end, label)
        logger.info("Metrics fetched %s PRs from GitHub", len(prs))
        day_summary = {d['date']: {'created': d['created'], 'merged': d['merged'], 'closed': d['closed']} for d in day_items}
        logger.info("Per-day summary: %s", day_summary)
        logger.info("Created trace (date, #): %s", created_trace[:200])
        logger.info("Merged trace (date, #): %s", merged_trace[:200])
    except Exception:
        pass

    return jsonify({
        'items': day_items,
        'kpis': {
            'created': total_created,
            'merged': total_merged,
            'closed_without_merge': total_closed_no_merge,
            'cycle_avg': avg_cycle
        },
        'insights': {
            'peak_date': peak_day['date'] if peak_day else None,
            'peak_created': peak_day['created'] if peak_day else 0,
            'merge_rate': merge_rate,
            'cycle_avg': avg_cycle,
            'review_delta': review_delta
        },
        'range': {'start': start, 'end': end}
    })


@app.route('/api/metrics/pr-list')
@rate_limit(max_requests=20, window=60)
def get_metrics_pr_list():
    """Return PR list for metrics cards based on date range and label filters."""
    repo = request.args.get('repo', GITHUB_REPO)
    enterprise = request.args.get('enterprise', 'zdi')
    label = request.args.get('label')
    start = request.args.get('start')
    end = request.args.get('end')
    list_type = request.args.get('type', 'created')  # created, merged, or closed

    token = get_enterprise_token(enterprise)
    current_service = GitHubService(token, repo)

    start_dt = datetime.strptime(start, '%Y-%m-%d').date() if start else None
    end_dt = datetime.strptime(end, '%Y-%m-%d').date() if end else None
    if start_dt and end_dt and start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt

    def parse(dt_str):
        return datetime.strptime(dt_str, '%Y-%m-%dT%H:%M:%SZ') if dt_str else None

    try:
        prs = current_service.get_pull_requests(state='all')
        items = []
        for pr in prs:
            created_dt = parse(pr.get('created_at'))
            merged_dt = parse(pr.get('merged_at'))
            if not created_dt:
                continue
            pr_labels = [l.get('name') for l in pr.get('labels', [])]
            if label and label.lower() != 'all':
                target = label.lower()
                if target not in [pl.lower() for pl in pr_labels if pl]:
                    continue

            if list_type == 'merged':
                if not merged_dt:
                    continue
                d = merged_dt.date()
            elif list_type == 'closed':
                closed_dt = parse(pr.get('closed_at'))
                if not closed_dt or merged_dt:
                    continue
                d = closed_dt.date()
            else:
                d = created_dt.date()

            if start_dt and d < start_dt:
                continue
            if end_dt and d > end_dt:
                continue

            items.append({
                'number': pr.get('number'),
                'title': pr.get('title'),
                'state': pr.get('state'),
                'user': pr.get('user', {}).get('login'),
                'created_at': pr.get('created_at'),
                'merged_at': pr.get('merged_at'),
                'closed_at': pr.get('closed_at'),
                'html_url': pr.get('html_url'),
                'labels': pr_labels
            })

        if list_type == 'merged':
            items.sort(key=lambda x: x.get('merged_at') or x.get('created_at'), reverse=True)
        elif list_type == 'closed':
            items.sort(key=lambda x: x.get('closed_at') or x.get('created_at'), reverse=True)
        else:
            items.sort(key=lambda x: x['created_at'], reverse=True)
        try:
            logger.info("/api/metrics/pr-list filters repo=%s enterprise=%s type=%s start=%s end=%s label=%s", repo, enterprise, list_type, start_dt, end_dt, label)
            logger.info("PR list total fetched=%s, returned=%s", len(prs), len(items))
            sample_dates = [ (itm.get('number'), itm.get('created_at'), itm.get('merged_at'), itm.get('closed_at')) for itm in items[:50] ]
            logger.info("PR list sample (num, created_at, merged_at, closed_at): %s", sample_dates)
        except Exception:
            pass
        return jsonify({'items': items, 'count': len(items)})
    except Exception as exc:
        logger.error(f"Metrics PR list error: {exc}", exc_info=True)
        return jsonify({'items': [], 'count': 0, 'error': str(exc)}), 500

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
        enterprise = request.args.get('enterprise', 'zdi')
        
        # Get the appropriate token for the enterprise
        token = get_enterprise_token(enterprise)
        
        # Make direct API calls to get ALL open PRs for accurate reviewer stats
        import requests
        api_url = f'https://api.github.com/repos/{repo}/pulls'
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'Authorization': f'token {token}',
            'User-Agent': 'GitHub-PR-Dashboard'
        }
        
        all_open_prs = []
        page = 1
        
        while page <= 10:  # Max 10 pages for open PRs (1000 open PRs)
            params = {
                'state': 'open',
                'per_page': 100,
                'page': page,
                'sort': 'created',
                'direction': 'desc'
            }
            
            response = requests.get(api_url, headers=headers, params=params, timeout=30)
            if response.status_code == 200:
                prs_page = response.json()
                if not prs_page:
                    break
                all_open_prs.extend(prs_page)
                if len(prs_page) < 100:
                    break
                page += 1
            else:
                logger.error(f"GitHub API error for reviewer stats: {response.status_code}")
                break
        
        # Apply month filtering if specified
        if month:
            filtered_prs = []
            for pr in all_open_prs:
                created_date = datetime.strptime(pr['created_at'], '%Y-%m-%dT%H:%M:%SZ')
                if created_date.strftime('%Y-%m') == month:
                    filtered_prs.append(pr)
            prs = filtered_prs
        else:
            prs = all_open_prs
        
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
        enterprise = request.args.get('enterprise', 'zdi')
        
        if not reviewer:
            return jsonify({'error': 'Reviewer parameter required'}), 400
        
        # Get the appropriate token for the enterprise
        token = get_enterprise_token(enterprise)
        
        # Create GitHub service for the requested repository
        current_service = GitHubService(token, repo)
        
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
        logger.info("JIRA file upload request received")
        
        if 'file' not in request.files:
            logger.warning("No file in request")
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            logger.warning("Empty filename")
            return jsonify({'error': 'No file selected'}), 400
        
        logger.info(f"Processing file: {file.filename}")
        
        # Check file extension
        filename = secure_filename(file.filename)
        file_ext = filename.lower().split('.')[-1]
        
        logger.info(f"File extension: {file_ext}")
        
        if file_ext not in ['csv', 'json']:
            logger.warning(f"Unsupported file type: {file_ext}")
            return jsonify({'error': 'Only CSV and JSON files are supported'}), 400
        
        # Save uploaded file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f'uploaded_jira.{file_ext}')
        logger.info(f"Saving file to: {file_path}")
        file.save(file_path)
        
        # Process the file
        logger.info("Processing uploaded file")
        success = jira_service.process_uploaded_file(file_path, file_ext)
        
        # Clean up uploaded file
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info("Cleaned up temporary file")
        
        if success:
            tickets_count = len(jira_service.jira_data)
            logger.info(f"Successfully processed {tickets_count} JIRA tickets")
            return jsonify({
                'message': 'JIRA data uploaded successfully',
                'tickets_count': tickets_count
            })
        else:
            logger.error("Failed to process JIRA file")
            return jsonify({'error': 'Failed to process JIRA file'}), 400
            
    except Exception as e:
        logger.error(f"Error uploading JIRA file: {e}", exc_info=True)
        return jsonify({'error': f'Failed to upload JIRA file: {str(e)}'}), 500

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

@app.route('/api/cache/clear', methods=['POST'])
def clear_cache():
    """Clear all API cache"""
    try:
        cache_db.clear_cache()
        return jsonify({'message': 'Cache cleared successfully'})
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return jsonify({'error': 'Failed to clear cache'}), 500

@app.route('/api/cache/info')
def cache_info():
    """Get cache information"""
    try:
        info = cache_db.get_cache_info()
        return jsonify(info)
    except Exception as e:
        logger.error(f"Error getting cache info: {e}")
        return jsonify({'error': 'Failed to get cache info'}), 500

# Periodic cache cleanup function
def cleanup_cache():
    """Clean up expired cache entries"""
    try:
        expired_count = cache_db.clear_expired()
        if expired_count > 0:
            logger.info(f"Cleaned up {expired_count} expired cache entries")
    except Exception as e:
        logger.error(f"Error during cache cleanup: {e}")

# Schedule cache cleanup every 30 minutes
import threading
def schedule_cache_cleanup():
    cleanup_cache()
    # Schedule next cleanup in 30 minutes
    threading.Timer(1800, schedule_cache_cleanup).start()

if __name__ == '__main__':
    # Start cache cleanup scheduler
    schedule_cache_cleanup()
    app.run(debug=True, host='0.0.0.0', port=5000)