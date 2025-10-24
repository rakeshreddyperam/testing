"""
Quick setup script to add sample ZDI tickets
Run this to populate your dashboard with sample data
"""

from manual_jira_service import manual_jira_service

def setup_sample_tickets():
    """Add sample ZDI tickets to the dashboard"""
    print("Setting up sample ZDI tickets...")
    
    # Clear existing tickets first
    manual_jira_service.clear_all_tickets()
    print("✅ Cleared existing tickets")
    
    # Add sample tickets
    result = manual_jira_service.add_sample_tickets()
    print(f"✅ {result}")
    
    # Show current status
    qat_tickets = manual_jira_service.get_qat_testing_tickets()
    all_tickets = manual_jira_service.get_all_tickets()
    
    print(f"\n📊 Dashboard Status:")
    print(f"   - Total tickets: {len(all_tickets)}")
    print(f"   - QAT-Testing tickets: {len(qat_tickets)}")
    
    print(f"\n🎯 QAT-Testing Tickets:")
    for ticket in qat_tickets:
        print(f"   - {ticket['key']}: {ticket['summary']} ({ticket['priority']})")
    
    print(f"\n🌐 Access your dashboard at: http://localhost:5000")
    print(f"🔧 Manage tickets at: http://localhost:5000/jira-admin")

if __name__ == "__main__":
    setup_sample_tickets()