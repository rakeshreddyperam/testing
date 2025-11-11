# GitHub PR Dashboard with JIRA Integration

A comprehensive Python Flask web application for monitoring GitHub Pull Requests and JIRA tickets with an interactive dashboard, advanced filtering, and real-time analytics.

## Features

### GitHub Integration
- **Available PRs Card**: Display count and list of open pull requests with pagination
- **Labeled PRs Card**: Filter PRs by specific labels including "None" for unlabeled PRs  
- **Closed PRs Card**: Show count and detailed list of closed pull requests
- **PR Reviewers Card**: Track reviewer workload with pagination (6 reviewers per page)
- **Multi-Repository Support**: Switch between different GitHub repositories
- **Advanced Filtering**: Filter by month, labels, and search within PR lists

### JIRA Integration
- **JIRA Status Cards**: Six interactive cards showing ticket counts by status:
  - New
  - Work in progress
  - Reviewing
  - On Hold
  - Work Complete
  - Testing
- **Clickable Status Cards**: Click any JIRA status card to view filtered tickets
- **JIRA Ticket Pagination**: Browse tickets with 10 items per page
- **CSV/Excel Upload**: Upload JIRA export files for data processing
- **Selective JIRA Refresh**: Refresh only JIRA data without affecting PR stats

### Performance & User Experience
- **Parallel Processing**: ThreadPoolExecutor for concurrent API calls
- **Intelligent Caching**: 15-minute caching system for optimal performance
- **Responsive Design**: Bootstrap-based mobile-friendly interface
- **Real-time Updates**: Live data fetching with loading indicators
- **Compact UI**: Space-efficient card designs for better visibility
- **Search Functionality**: Quick search within PR and ticket lists

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- GitHub Personal Access Token
- Git repository access

### Installation

1. **Clone or navigate to the project directory**
   ```bash
   cd "C:\Users\RP017421\OneDrive - Zelis Healthcare\Testing_Projects\testing github"
   ```

2. **Set up Python virtual environment** (already configured)
   ```bash
   # Virtual environment is already created at .venv
   ```

3. **Install dependencies** (already installed)
   ```bash
   # Dependencies are already installed in the virtual environment
   ```

4. **Configure environment variables**
   - Create `.env` file in project root
   - Add your GitHub configuration:
   ```
   GITHUB_TOKEN=your_github_personal_access_token_here
   GITHUB_REPO=owner/repository-name
   ```

### JIRA Setup

1. **Export JIRA Data**:
   - Export tickets from JIRA as CSV or Excel file
   - Include columns: Key, Summary, Status, Assignee, Priority, Created, Status Category
   
2. **Upload to Dashboard**:
   - Use the JIRA upload button on the dashboard
   - Select your exported CSV/Excel file
   - Data will be processed and displayed immediately

### Running the Application

#### Option 1: Using VS Code Task
1. Open Command Palette (`Ctrl+Shift+P`)
2. Select "Tasks: Run Task"
3. Choose "Run GitHub PR Dashboard"

#### Option 2: Using VS Code Debugger
1. Press `F5` or go to Run and Debug panel
2. Select "Python: Flask App" configuration
3. Click the green play button

#### Option 3: Using Terminal
```bash
"C:/Users/RP017421/OneDrive - Zelis Healthcare/Testing_Projects/testing github/.venv/Scripts/python.exe" app.py
```

### Accessing the Dashboard

Once running, open your browser and navigate to:
```
http://localhost:5000
```

## Configuration

### GitHub API Setup

1. **Create a Personal Access Token**:
   - Go to GitHub Settings > Developer settings > Personal access tokens
   - Generate a new token with `repo` permissions
   - Copy the token to your `.env` file

2. **Set Repository**:
   - Update `GITHUB_REPO` in `.env` with format: `owner/repository-name`
   - Example: `microsoft/vscode`

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GITHUB_TOKEN` | GitHub Personal Access Token | Yes |
| `GITHUB_REPO` | Repository in format owner/repo | Yes |

## Usage

### Dashboard Cards

#### GitHub PR Cards:
- **Available PRs**: Shows open pull requests with reviewer assignments
- **Labeled PRs**: Filter PRs by labels (supports "None" for unlabeled)
- **Closed PRs**: Historical view of closed pull requests  
- **PR Reviewers**: Team workload distribution with pagination

#### JIRA Status Cards:
- **Six Status Cards**: Real-time counts for each JIRA status
- **Interactive**: Click cards to view filtered ticket lists
- **Pagination**: Navigate through large ticket datasets
- **Direct Links**: Jump to JIRA tickets with external links

### Advanced Features

- **Month Filtering**: Filter all data by specific months
- **Multi-Label Filtering**: Complex label combinations with dropdown
- **Search**: Find specific PRs or tickets quickly
- **Pagination**: Handle large datasets efficiently
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Real-time Refresh**: Update data without page reload

### Viewing Details

- Click any dashboard card to open a modal with detailed PR information
- Each PR shows:
  - Title and number
  - Author and creation date
  - Current state (open/closed)
  - Associated labels
  - Direct link to GitHub

## API Endpoints

### GitHub APIs
- `GET /` - Main dashboard page
- `GET /api/pr-stats` - PR statistics with filtering
- `GET /api/available-months` - Available months for filtering  
- `GET /api/available-labels` - All PR labels for dropdown
- `GET /api/reviewer-stats` - Reviewer workload statistics

### JIRA APIs
- `POST /upload/jira` - Upload JIRA export file
- `GET /api/jira/status` - JIRA status counts
- `GET /api/jira/tickets` - All JIRA tickets with filtering

## Development

### Project Structure

```
.
├── app.py                 # Main Flask application with GitHub & JIRA services
├── templates/
│   └── dashboard.html     # Comprehensive dashboard UI with all features
├── static/
│   └── uploads/          # JIRA file uploads directory
├── requirements.txt      # Python dependencies
├── .env                 # Environment configuration
├── .vscode/
│   ├── launch.json      # VS Code debug configuration
│   └── tasks.json       # VS Code build tasks
├── .github/
│   └── copilot-instructions.md  # Development guidelines
└── README.md           # This documentation
```

### Technologies Used

- **Backend**: Python Flask
- **Frontend**: HTML5, Bootstrap 5, Vanilla JavaScript
- **API**: GitHub REST API v3
- **Environment**: Python Virtual Environment

## Troubleshooting

### Common Issues

1. **GitHub API Rate Limiting**:
   - Ensure you're using a personal access token
   - Check rate limit status in GitHub API responses

2. **Repository Not Found**:
   - Verify `GITHUB_REPO` format in `.env`
   - Ensure your token has access to the repository

3. **Environment Variables Not Loading**:
   - Verify `.env` file exists in project root
   - Check that variables are not quoted unnecessarily

### Error Messages

- If you see "Error loading stats" or "Error loading pull requests", check:
  - Network connectivity
  - GitHub token validity
  - Repository accessibility
  - Console for detailed error messages

## Performance Optimizations

- **Parallel API Calls**: Fetch PR comments concurrently using ThreadPoolExecutor
- **Intelligent Caching**: Cache API responses for 15 minutes with smart invalidation
- **Selective Refresh**: JIRA-only refresh without affecting GitHub data
- **Pagination**: Limit displayed items (6 reviewers, 10 tickets per page)
- **Optimized UI**: Compact card designs and efficient event handling

## Current Capabilities

- **GitHub PRs**: Full management of 18+ PRs with filtering and pagination
- **JIRA Tickets**: Processing and display of 38+ tickets across 6 statuses
- **Multi-Repository**: Support for switching between repositories
- **Real-time Data**: Live updates with intelligent caching
- **Mobile Ready**: Responsive design for all device types

## License

This project is for demonstration purposes. Please ensure compliance with GitHub's API terms of service and JIRA data usage policies.
