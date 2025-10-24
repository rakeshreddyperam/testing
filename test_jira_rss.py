"""
Test script to check OneZelis Jira RSS feeds
Run this to see which RSS feeds are accessible without authentication
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from jira_rss_service import JiraRSSService, ONEZELIS_RSS_URLS, EXAMPLE_RSS_URLS

def test_onezelis_feeds():
    """Test OneZelis Jira RSS feeds"""
    print("=" * 60)
    print("TESTING ONEZELIS JIRA RSS FEEDS")
    print("=" * 60)
    
    rss_service = JiraRSSService()
    
    working_urls = []
    
    for i, url in enumerate(ONEZELIS_RSS_URLS, 1):
        print(f"\n{i}. Testing: {url}")
        print("-" * 80)
        
        success, message = rss_service.test_rss_url(url)
        
        if success:
            working_urls.append(url)
            print(f"✅ SUCCESS: {message}")
            
            # Try to get actual tickets
            print("   Attempting to fetch tickets...")
            tickets = rss_service.parse_rss_feed(url)
            if tickets:
                print(f"   📋 Found {len(tickets)} tickets:")
                for ticket in tickets[:3]:  # Show first 3
                    print(f"      - {ticket['key']}: {ticket['summary'][:50]}...")
            else:
                print("   ⚠️  No tickets found or parsing failed")
        else:
            print(f"❌ FAILED: {message}")
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    if working_urls:
        print(f"✅ Found {len(working_urls)} working RSS URLs:")
        for url in working_urls:
            print(f"   - {url}")
        
        print("\n🔧 NEXT STEPS:")
        print("1. Copy one of the working URLs above")
        print("2. Update your jira_config.py with this URL")
        print("3. The dashboard will automatically use RSS feeds")
        
    else:
        print("❌ No RSS feeds are publicly accessible")
        print("\n🔧 ALTERNATIVE OPTIONS:")
        print("1. Check if your Jira admin can enable public RSS feeds")
        print("2. Create a Jira filter and share it publicly")
        print("3. Use CSV export option instead")
        print("4. Try different RSS URL formats")
    
    return working_urls

def test_public_feeds():
    """Test public Jira RSS feeds to verify the service works"""
    print("\n" + "=" * 60)
    print("TESTING PUBLIC JIRA RSS FEEDS (For verification)")
    print("=" * 60)
    
    rss_service = JiraRSSService()
    
    for i, url in enumerate(EXAMPLE_RSS_URLS, 1):
        print(f"\n{i}. Testing public feed: {url}")
        print("-" * 80)
        
        success, message = rss_service.test_rss_url(url)
        
        if success:
            print(f"✅ PUBLIC FEED WORKS: {message}")
            # Try to get tickets to verify parsing
            tickets = rss_service.parse_rss_feed(url)
            if tickets:
                print(f"   📋 Successfully parsed {len(tickets)} tickets")
                # Show one example
                if tickets:
                    example = tickets[0]
                    print(f"   Example: {example['key']} - {example['summary'][:50]}...")
        else:
            print(f"❌ PUBLIC FEED FAILED: {message}")

def suggest_jira_urls():
    """Suggest additional URLs to try based on OneZelis instance"""
    print("\n" + "=" * 60)
    print("ADDITIONAL URLs TO TRY MANUALLY")
    print("=" * 60)
    
    suggestions = [
        "https://onezelis.atlassian.net/rest/api/2/search?jql=project=ZDI&fields=key,summary,status&maxResults=10",
        "https://onezelis.atlassian.net/sr/jira.issueviews:searchrequest-xml/temp/SearchRequest.xml?jqlQuery=project=ZDI",
        "https://onezelis.atlassian.net/browse/ZDI?selectedTab=com.atlassian.jira.jira-projects-plugin:issues-panel",
        "https://onezelis.atlassian.net/projects/ZDI/issues/?filter=allissues",
        "https://onezelis.atlassian.net/issues/?jql=project=ZDI",
    ]
    
    print("Try these URLs in your browser:")
    for i, url in enumerate(suggestions, 1):
        print(f"{i}. {url}")
    
    print("\n📝 MANUAL STEPS:")
    print("1. Go to your Jira project: https://onezelis.atlassian.net/browse/ZDI")
    print("2. Click 'Issues' > 'Search for issues'")
    print("3. Use JQL: project = ZDI AND status = 'QAT-Testing'")
    print("4. Look for 'RSS' or 'XML' export options")
    print("5. Try adding '&os_authType=none' to any URLs you find")

if __name__ == "__main__":
    print("OneZelis Jira RSS Feed Tester")
    print("Testing RSS feed accessibility for ZDI project")
    
    # Test OneZelis feeds
    working_urls = test_onezelis_feeds()
    
    # Test public feeds to verify service works
    test_public_feeds()
    
    # Suggest additional URLs
    suggest_jira_urls()
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)