#!/usr/bin/env python3
"""
Quick test script to verify GitHub API connectivity and data retrieval
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_REPO = os.getenv('GITHUB_REPO')

def test_github_api():
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'GitHub-PR-Dashboard-Test'
    }
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'
    
    url = f'https://api.github.com/repos/{GITHUB_REPO}/pulls'
    params = {'state': 'all', 'per_page': 10}
    
    print(f"Testing GitHub API connection...")
    print(f"Repository: {GITHUB_REPO}")
    print(f"Token configured: {'Yes' if GITHUB_TOKEN else 'No'}")
    print(f"URL: {url}")
    print("-" * 50)
    
    try:
        response = requests.get(url, headers=headers, params=params)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            prs = response.json()
            print(f"✅ SUCCESS: Retrieved {len(prs)} PRs")
            
            open_prs = [pr for pr in prs if pr['state'] == 'open']
            closed_prs = [pr for pr in prs if pr['state'] == 'closed']
            
            print(f"Open PRs: {len(open_prs)}")
            print(f"Closed PRs: {len(closed_prs)}")
            
            if prs:
                print(f"\nSample PR:")
                print(f"  Title: {prs[0]['title']}")
                print(f"  Number: #{prs[0]['number']}")
                print(f"  State: {prs[0]['state']}")
                print(f"  Author: {prs[0]['user']['login']}")
                
        elif response.status_code == 403:
            print("❌ ERROR: Rate limit exceeded or authentication failed")
            print("Response:", response.text[:200])
        elif response.status_code == 404:
            print("❌ ERROR: Repository not found")
        else:
            print(f"❌ ERROR: HTTP {response.status_code}")
            print("Response:", response.text[:200])
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")

if __name__ == "__main__":
    test_github_api()