"""
Background worker to periodically fetch and cache GitHub PR data
"""
import time
import json
import os
import logging
import threading
from datetime import datetime
from dotenv import load_dotenv
import requests
import schedule

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - WORKER - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('worker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PRCacheWorker:
    def __init__(self):
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.repositories = [
            'Zelis-Data-Intelligence-ZDI/zdi-data-admin',
            'Zelis-Data-Intelligence-ZDI/Address-Service', 
            'Zelis-Data-Intelligence-ZDI/smrf-hub',
            'Zelis-Data-Intelligence-ZDI/astro-zse'
        ]
        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'GitHub-PR-Dashboard-Worker'
        }
        if self.github_token:
            self.headers['Authorization'] = f'token {self.github_token}'
        
        self.cache_dir = 'cache'
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Track last update times to avoid too frequent updates
        self.last_updates = {}
        
    def fetch_prs_for_repo(self, repo):
        """Fetch all PRs for a repository with pagination"""
        logger.info(f"Fetching PRs for repository: {repo}")
        
        all_prs = {'open': [], 'closed': [], 'all': []}
        
        for state in ['open', 'closed']:
            url = f'https://api.github.com/repos/{repo}/pulls'
            page = 1
            max_pages = 5 if state == 'open' else 10  # More pages for closed to get better historical data
            
            while page <= max_pages:
                params = {
                    'state': state,
                    'per_page': 100,
                    'page': page,
                    'sort': 'created',
                    'direction': 'desc'
                }
                
                try:
                    response = requests.get(url, headers=self.headers, params=params, timeout=30)
                    
                    if response.status_code == 200:
                        prs = response.json()
                        if not prs:
                            break
                            
                        all_prs[state].extend(prs)
                        all_prs['all'].extend(prs)
                        
                        logger.info(f"Repo {repo} - {state} PRs page {page}: {len(prs)} PRs")
                        
                        if len(prs) < 100:
                            break
                        page += 1
                    else:
                        logger.error(f"GitHub API error for {repo} ({state}): {response.status_code}")
                        break
                        
                except Exception as e:
                    logger.error(f"Error fetching {state} PRs for {repo}: {e}")
                    break
                    
                # Rate limiting - GitHub allows 5000 requests/hour
                time.sleep(0.5)  # Small delay between requests
        
        logger.info(f"Repository {repo} - Total cached: {len(all_prs['open'])} open, {len(all_prs['closed'])} closed")
        return all_prs
    
    def get_available_months(self, prs):
        """Extract available months from PR data"""
        months = set()
        for pr in prs:
            try:
                created_date = datetime.strptime(pr['created_at'], '%Y-%m-%dT%H:%M:%SZ')
                months.add(created_date.strftime('%Y-%m'))
            except:
                continue
        return sorted(list(months), reverse=True)
    
    def get_available_labels(self, prs):
        """Extract available labels from PR data"""
        labels = set()
        for pr in prs:
            for label in pr.get('labels', []):
                labels.add(label['name'])
        return sorted(list(labels))
    
    def calculate_stats(self, prs, month=None, labels=None):
        """Calculate PR statistics with filtering"""
        open_prs = prs['open'].copy()
        closed_prs = prs['closed'].copy()
        
        # Apply month filtering
        if month:
            filtered_open = []
            filtered_closed = []
            
            for pr in open_prs:
                try:
                    created_date = datetime.strptime(pr['created_at'], '%Y-%m-%dT%H:%M:%SZ')
                    if created_date.strftime('%Y-%m') == month:
                        filtered_open.append(pr)
                except:
                    continue
                    
            for pr in closed_prs:
                try:
                    created_date = datetime.strptime(pr['created_at'], '%Y-%m-%dT%H:%M:%SZ')
                    if created_date.strftime('%Y-%m') == month:
                        filtered_closed.append(pr)
                except:
                    continue
                    
            open_prs = filtered_open
            closed_prs = filtered_closed
        
        # Calculate labeled PRs count
        labeled_count = 0
        if labels:
            for pr in open_prs:
                pr_labels = [label['name'] for label in pr.get('labels', [])]
                
                # Handle "none" label for unlabeled PRs
                if 'none' in labels and not pr_labels:
                    labeled_count += 1
                    continue
                
                # Check for specific labels
                other_labels = [l for l in labels if l != 'none']
                if other_labels and pr_labels:
                    if any(label.lower() in [pl.lower() for pl in pr_labels] for label in other_labels):
                        labeled_count += 1
        
        return {
            'available_count': len(open_prs),
            'closed_count': len(closed_prs),
            'labeled_count': labeled_count,
            'total_count': len(open_prs) + len(closed_prs),
            'testing_count': 0  # Will be updated by JIRA service
        }
    
    def update_repository_cache(self, repo):
        """Update cache for a single repository"""
        try:
            # Check if we updated this repo recently (avoid too frequent updates)
            cache_file = os.path.join(self.cache_dir, f"{repo.replace('/', '_')}_prs.json")
            
            if os.path.exists(cache_file):
                file_age = time.time() - os.path.getmtime(cache_file)
                if file_age < 300:  # Less than 5 minutes old
                    logger.info(f"Skipping {repo} - cache is fresh ({file_age:.0f}s old)")
                    return
            
            # Fetch PR data
            prs_data = self.fetch_prs_for_repo(repo)
            
            # Calculate metadata
            metadata = {
                'available_months': self.get_available_months(prs_data['all']),
                'available_labels': self.get_available_labels(prs_data['all']),
                'last_updated': datetime.now().isoformat(),
                'stats': self.calculate_stats(prs_data)
            }
            
            # Prepare cache data
            cache_data = {
                'repository': repo,
                'prs': prs_data,
                'metadata': metadata,
                'cached_at': time.time()
            }
            
            # Save to cache file
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            logger.info(f"Cache updated for {repo} - {len(prs_data['all'])} total PRs")
            self.last_updates[repo] = time.time()
            
        except Exception as e:
            logger.error(f"Error updating cache for {repo}: {e}")
    
    def update_all_repositories(self):
        """Update cache for all repositories"""
        logger.info("Starting cache update for all repositories")
        start_time = time.time()
        
        for repo in self.repositories:
            self.update_repository_cache(repo)
            # Small delay between repos to be gentle on API
            time.sleep(2)
        
        end_time = time.time()
        logger.info(f"Cache update completed in {end_time - start_time:.1f} seconds")
    
    def get_cached_data(self, repo):
        """Get cached data for a repository"""
        cache_file = os.path.join(self.cache_dir, f"{repo.replace('/', '_')}_prs.json")
        
        try:
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error reading cache for {repo}: {e}")
        
        return None
    
    def start_scheduler(self):
        """Start the background scheduler"""
        logger.info("Starting PR cache worker scheduler")
        
        # Schedule updates every 5 minutes
        schedule.every(5).minutes.do(self.update_all_repositories)
        
        # Do an initial update
        self.update_all_repositories()
        
        # Run scheduler
        while True:
            try:
                schedule.run_pending()
                time.sleep(30)  # Check every 30 seconds
            except KeyboardInterrupt:
                logger.info("Worker scheduler stopped")
                break
            except Exception as e:
                logger.error(f"Error in scheduler: {e}")
                time.sleep(60)  # Wait a minute before retrying

def run_worker():
    """Entry point for running the worker"""
    worker = PRCacheWorker()
    worker.start_scheduler()

if __name__ == '__main__':
    run_worker()