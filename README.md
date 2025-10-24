# GitHub PR Dashboard

A Python Flask web application for monitoring GitHub Pull Requests with interactive dashboard cards and filtering capabilities.

## Features

- **Dashboard Cards**: Display PR statistics with visual cards showing:
  - Available (open) PRs count
  - PRs filtered by label criteria
  - Closed PRs count
- **Interactive Cards**: Click any card to view detailed PR lists
- **Month-based Filtering**: Filter all data by specific months
- **Label Filtering**: Filter PRs by specific labels
- **Responsive Design**: Bootstrap-based responsive UI
- **Real-time Data**: Fetches live data from GitHub API

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
   - Copy `.env.example` to `.env`
   - Edit `.env` and add your GitHub configuration:
   ```
   GITHUB_TOKEN=your_github_personal_access_token_here
   GITHUB_REPO=owner/repository-name
   ```

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

- **Available PRs**: Shows count of open pull requests
- **Labeled PRs**: Shows count of PRs matching selected label criteria
- **Closed PRs**: Shows count of closed pull requests

### Filtering

- **Month Filter**: Select a specific month to filter all data
- **Label Filter**: Enter comma-separated labels to filter PRs
- **Combined Filtering**: Use both month and label filters together

### Viewing Details

- Click any dashboard card to open a modal with detailed PR information
- Each PR shows:
  - Title and number
  - Author and creation date
  - Current state (open/closed)
  - Associated labels
  - Direct link to GitHub

## API Endpoints

- `GET /` - Main dashboard page
- `GET /api/pr-stats` - Get PR statistics (supports month and labels params)
- `GET /api/prs` - Get detailed PR list (supports type, month, and labels params)
- `GET /api/available-months` - Get list of available months from PRs

## Development

### Project Structure

```
.
├── app.py                 # Main Flask application
├── templates/
│   └── dashboard.html     # Dashboard UI template
├── static/               # Static files (currently empty)
├── requirements.txt      # Python dependencies
├── .env.example         # Environment variables template
├── .vscode/
│   ├── launch.json      # VS Code debug configuration
│   └── tasks.json       # VS Code tasks
└── README.md           # This file
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

## License

This project is for demonstration purposes. Please ensure compliance with GitHub's API terms of service.