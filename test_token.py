import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

token = os.getenv('GITHUB_TOKEN')
repo = os.getenv('GITHUB_REPO')

print(f"Testing token for repository: {repo}")
print(f"Token starts with: {token[:10]}..." if token else "No token found")

# Test repository access
headers = {'Authorization': f'token {token}'} if token else {}
response = requests.get(f'https://api.github.com/repos/{repo}', headers=headers)

print(f"Status Code: {response.status_code}")

if response.status_code == 200:
    print("✅ Repository is accessible!")
    repo_data = response.json()
    print(f"Repository: {repo_data['full_name']}")
    print(f"Description: {repo_data.get('description', 'No description')}")
elif response.status_code == 401:
    print("❌ Authentication failed - Bad credentials")
    print("Your GitHub token might be:")
    print("  - Expired")
    print("  - Invalid")
    print("  - Doesn't have the right permissions")
elif response.status_code == 404:
    print("❌ Repository not found")
    print("Check if the repository name is correct or if you have access to it")
else:
    print(f"❌ Error: {response.status_code}")
    print(response.json())

# Test pull requests access
print("\nTesting pull requests access...")
pr_response = requests.get(f'https://api.github.com/repos/{repo}/pulls', headers=headers)
print(f"PR Status Code: {pr_response.status_code}")

if pr_response.status_code == 200:
    prs = pr_response.json()
    print(f"✅ Found {len(prs)} pull requests")
else:
    print(f"❌ Cannot access pull requests: {pr_response.status_code}")
    if pr_response.status_code != 404:
        print(pr_response.json())