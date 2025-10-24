"""
Manual Jira Ticket Management
Simple interface to manually add/edit Jira tickets for the dashboard
"""

import json
import os
from datetime import datetime

class ManualJiraService:
    def __init__(self, data_file='jira_tickets.json'):
        self.data_file = data_file
        self.tickets = self._load_tickets()
    
    def _load_tickets(self):
        """Load tickets from JSON file"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def _save_tickets(self):
        """Save tickets to JSON file"""
        with open(self.data_file, 'w') as f:
            json.dump(self.tickets, f, indent=2)
    
    def add_ticket(self, key, summary, status='QAT-Testing', assignee='Unassigned', priority='Medium'):
        """Add a new ticket"""
        ticket = {
            'key': key,
            'summary': summary,
            'status': status,
            'assignee': assignee,
            'priority': priority,
            'created': datetime.now().isoformat(),
            'link': f'https://onezelis.atlassian.net/browse/{key}',
            'source': 'Manual Entry'
        }
        
        # Check if ticket already exists
        for i, existing in enumerate(self.tickets):
            if existing['key'] == key:
                self.tickets[i] = ticket
                self._save_tickets()
                return f"Updated ticket {key}"
        
        # Add new ticket
        self.tickets.append(ticket)
        self._save_tickets()
        return f"Added ticket {key}"
    
    def update_ticket_status(self, key, new_status):
        """Update ticket status"""
        for ticket in self.tickets:
            if ticket['key'] == key:
                ticket['status'] = new_status
                self._save_tickets()
                return f"Updated {key} status to {new_status}"
        return f"Ticket {key} not found"
    
    def remove_ticket(self, key):
        """Remove a ticket"""
        self.tickets = [t for t in self.tickets if t['key'] != key]
        self._save_tickets()
        return f"Removed ticket {key}"
    
    def get_tickets_by_status(self, status):
        """Get tickets by status"""
        return [t for t in self.tickets if t['status'].lower() == status.lower()]
    
    def get_qat_testing_tickets(self):
        """Get tickets in QAT-Testing status"""
        return self.get_tickets_by_status('QAT-Testing')
    
    def get_all_tickets(self):
        """Get all tickets"""
        return self.tickets
    
    def clear_all_tickets(self):
        """Clear all tickets"""
        self.tickets = []
        self._save_tickets()
        return "All tickets cleared"
    
    def add_sample_tickets(self):
        """Add some sample ZDI tickets for demonstration"""
        sample_tickets = [
            {
                'key': 'ZDI-001',
                'summary': 'Fix user authentication bug in login module',
                'status': 'QAT-Testing',
                'assignee': 'John Smith',
                'priority': 'High'
            },
            {
                'key': 'ZDI-002', 
                'summary': 'Update dashboard performance metrics',
                'status': 'QAT-Testing',
                'assignee': 'Sarah Johnson',
                'priority': 'Medium'
            },
            {
                'key': 'ZDI-003',
                'summary': 'Implement new search functionality',
                'status': 'QAT-Testing', 
                'assignee': 'Mike Davis',
                'priority': 'Low'
            },
            {
                'key': 'ZDI-004',
                'summary': 'Database connection timeout issue',
                'status': 'QAT-Testing',
                'assignee': 'Lisa Wilson',
                'priority': 'Critical'
            },
            {
                'key': 'ZDI-005',
                'summary': 'Email notification system enhancement',
                'status': 'In Progress',
                'assignee': 'Tom Brown',
                'priority': 'Medium'
            }
        ]
        
        for ticket_data in sample_tickets:
            self.add_ticket(**ticket_data)
        
        return f"Added {len(sample_tickets)} sample ZDI tickets"

# Create global instance
manual_jira_service = ManualJiraService()