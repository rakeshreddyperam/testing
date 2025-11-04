# GitHub PR Dashboard<<<<<<< HEAD

# GitHub PR Dashboard

A Python Flask web application for monitoring GitHub Pull Requests with interactive dashboard cards and filtering capabilities.

A Python Flask web application for monitoring GitHub Pull Requests with interactive dashboard cards and filtering capabilities.

## Features

## Features

- **Dashboard Cards**: Display PR statistics with visual cards showing:

  - Available (open) PRs count- **Dashboard Cards**: Display PR statistics with visual cards showing:

  - PRs filtered by label criteria  - Available (open) PRs count

  - Closed PRs count  - PRs filtered by label criteria

- **Smart Test Analyzer**: Intelligent test recommendation system based on ticket descriptions  - Closed PRs count

- **Interactive Cards**: Click any card to view detailed PR lists- **Interactive Cards**: Click any card to view detailed PR lists

- **Month-based Filtering**: Filter all data by specific months- **Month-based Filtering**: Filter all data by specific months

- **Label Filtering**: Filter PRs by specific labels- **Label Filtering**: Filter PRs by specific labels

- **Responsive Design**: Bootstrap-based responsive UI with enhanced footer- **Responsive Design**: Bootstrap-based responsive UI

- **Real-time Data**: Fetches live data from GitHub API- **Real-time Data**: Fetches live data from GitHub API



## Recent Updates (v2.1.0)## Setup Instructions



- ✨ Added Smart Test Analyzer for intelligent test recommendations### Prerequisites

- 📊 Enhanced dashboard footer with version information

- 🧹 Cleaned up legacy Jira integration files- Python 3.8 or higher

- 🎨 Improved UI styling and visual enhancements- GitHub Personal Access Token

- Git repository access

## Setup Instructions

### Installation

### Prerequisites

1. **Clone or navigate to the project directory**

- Python 3.8 or higher   ```bash

- GitHub Personal Access Token   cd "C:\Users\RP017421\OneDrive - Zelis Healthcare\Testing_Projects\testing github"

- Git repository access   ```



### Installation2. **Set up Python virtual environment** (already configured)

   ```bash

1. **Clone or navigate to the project directory**   # Virtual environment is already created at .venv

   ```bash   ```

   cd "C:\Users\RP017421\OneDrive - Zelis Healthcare\Testing_Projects\testing github"

   ```3. **Install dependencies** (already installed)

   ```bash

2. **Set up Python virtual environment** (already configured)   # Dependencies are already installed in the virtual environment

   ```bash   ```

   # Virtual environment is already created at .venv

   ```4. **Configure environment variables**

   - Copy `.env.example` to `.env`

3. **Install dependencies** (already installed)   - Edit `.env` and add your GitHub configuration:

   ```bash   ```

   # Dependencies are already installed in the virtual environment   GITHUB_TOKEN=your_github_personal_access_token_here

   ```   GITHUB_REPO=owner/repository-name

   ```

4. **Configure environment variables**

   - Copy `.env.example` to `.env`### Running the Application

   - Edit `.env` and add your GitHub configuration:

   ```#### Option 1: Using VS Code Task

   GITHUB_TOKEN=your_github_personal_access_token_here1. Open Command Palette (`Ctrl+Shift+P`)

   GITHUB_REPO=owner/repository-name2. Select "Tasks: Run Task"

   ```3. Choose "Run GitHub PR Dashboard"



### Running the Application#### Option 2: Using VS Code Debugger

1. Press `F5` or go to Run and Debug panel

#### Option 1: Using VS Code Task2. Select "Python: Flask App" configuration

1. Open Command Palette (`Ctrl+Shift+P`)3. Click the green play button

2. Select "Tasks: Run Task"

3. Choose "Run GitHub PR Dashboard"#### Option 3: Using Terminal

```bash

#### Option 2: Using VS Code Debugger"C:/Users/RP017421/OneDrive - Zelis Healthcare/Testing_Projects/testing github/.venv/Scripts/python.exe" app.py

1. Press `F5` or go to Run and Debug panel```

2. Select "Python: Flask App" configuration

3. Click the green play button### Accessing the Dashboard



#### Option 3: Using TerminalOnce running, open your browser and navigate to:

```bash```

"C:/Users/RP017421/OneDrive - Zelis Healthcare/Testing_Projects/testing github/.venv/Scripts/python.exe" app.pyhttp://localhost:5000

``````



### Accessing the Dashboard## Configuration



Once running, open your browser and navigate to:### GitHub API Setup

```

http://localhost:50001. **Create a Personal Access Token**:

```   - Go to GitHub Settings > Developer settings > Personal access tokens

   - Generate a new token with `repo` permissions

## Configuration   - Copy the token to your `.env` file



### GitHub API Setup2. **Set Repository**:

   - Update `GITHUB_REPO` in `.env` with format: `owner/repository-name`

1. **Create a Personal Access Token**:   - Example: `microsoft/vscode`

   - Go to GitHub Settings > Developer settings > Personal access tokens

   - Generate a new token with `repo` permissions### Environment Variables

   - Copy the token to your `.env` file

| Variable | Description | Required |

2. **Set Repository**:|----------|-------------|----------|

   - Update `GITHUB_REPO` in `.env` with format: `owner/repository-name`| `GITHUB_TOKEN` | GitHub Personal Access Token | Yes |

   - Example: `microsoft/vscode`| `GITHUB_REPO` | Repository in format owner/repo | Yes |



### Environment Variables## Usage



| Variable | Description | Required |### Dashboard Cards

|----------|-------------|----------|

| `GITHUB_TOKEN` | GitHub Personal Access Token | Yes |- **Available PRs**: Shows count of open pull requests

| `GITHUB_REPO` | Repository in format owner/repo | Yes |- **Labeled PRs**: Shows count of PRs matching selected label criteria

- **Closed PRs**: Shows count of closed pull requests

## Usage

### Filtering

### Dashboard Cards

- **Month Filter**: Select a specific month to filter all data

- **Available PRs**: Shows count of open pull requests- **Label Filter**: Enter comma-separated labels to filter PRs

- **Labeled PRs**: Shows count of PRs matching selected label criteria- **Combined Filtering**: Use both month and label filters together

- **Closed PRs**: Shows count of closed pull requests

- **Smart Test Analyzer**: Analyze ticket descriptions for test recommendations### Viewing Details



### Smart Test Analyzer- Click any dashboard card to open a modal with detailed PR information

- Each PR shows:

1. Paste your ticket description in the text area  - Title and number

2. Select ticket type (Bug Fix, Feature, Security, etc.)  - Author and creation date

3. Choose priority level (Low, Medium, High, Critical)  - Current state (open/closed)

4. Click "Analyze for Testing" to get intelligent recommendations  - Associated labels

  - Direct link to GitHub

### Filtering

## API Endpoints

- **Month Filter**: Select a specific month to filter all data

- **Label Filter**: Enter comma-separated labels to filter PRs- `GET /` - Main dashboard page

- **Combined Filtering**: Use both month and label filters together- `GET /api/pr-stats` - Get PR statistics (supports month and labels params)

- `GET /api/prs` - Get detailed PR list (supports type, month, and labels params)

### Viewing Details- `GET /api/available-months` - Get list of available months from PRs



- Click any dashboard card to open a modal with detailed PR information## Development

- Each PR shows:

  - Title and number### Project Structure

  - Author and creation date

  - Current state (open/closed)```

  - Associated labels.

  - Direct link to GitHub├── app.py                 # Main Flask application

├── templates/

## API Endpoints│   └── dashboard.html     # Dashboard UI template

├── static/               # Static files (currently empty)

- `GET /` - Main dashboard page├── requirements.txt      # Python dependencies

- `GET /api/pr-stats` - Get PR statistics (supports month and labels params)├── .env.example         # Environment variables template

- `GET /api/prs` - Get detailed PR list (supports type, month, and labels params)├── .vscode/

- `GET /api/available-months` - Get list of available months from PRs│   ├── launch.json      # VS Code debug configuration

- `POST /api/analyze-ticket` - Smart test analysis for ticket descriptions│   └── tasks.json       # VS Code tasks

└── README.md           # This file

## Development```



### Project Structure### Technologies Used



```- **Backend**: Python Flask

.- **Frontend**: HTML5, Bootstrap 5, Vanilla JavaScript

├── app.py                 # Main Flask application- **API**: GitHub REST API v3

├── templates/- **Environment**: Python Virtual Environment

│   └── dashboard.html     # Dashboard UI template

├── static/               # Static files (currently empty)## Troubleshooting

├── requirements.txt      # Python dependencies

├── .env.example         # Environment variables template### Common Issues

├── .vscode/

│   ├── launch.json      # VS Code debug configuration1. **GitHub API Rate Limiting**:

│   └── tasks.json       # VS Code tasks   - Ensure you're using a personal access token

└── README.md           # This file   - Check rate limit status in GitHub API responses

```

2. **Repository Not Found**:

### Technologies Used   - Verify `GITHUB_REPO` format in `.env`

   - Ensure your token has access to the repository

- **Backend**: Python Flask

- **Frontend**: HTML5, Bootstrap 5, Vanilla JavaScript3. **Environment Variables Not Loading**:

- **API**: GitHub REST API v3   - Verify `.env` file exists in project root

- **AI/ML**: Intelligent test analysis with keyword matching   - Check that variables are not quoted unnecessarily

- **Environment**: Python Virtual Environment

### Error Messages

## Testing

- If you see "Error loading stats" or "Error loading pull requests", check:

This project includes comprehensive testing features:  - Network connectivity

- **PR Dashboard Testing**: Live GitHub API integration testing  - GitHub token validity

- **Smart Test Analyzer**: Intelligent test recommendation validation  - Repository accessibility

- **UI Component Testing**: Interactive dashboard element testing  - Console for detailed error messages



## Pull Request for Testing## License



This branch (`test/pr-dashboard-enhancement`) includes:This project is for demonstration purposes. Please ensure compliance with GitHub's API terms of service.

- Enhanced footer with version information and current date=======

- Updated documentation with recent changes# testing

- Version bump to v2.1.0 for tracking purposes>>>>>>> 2e757797419a55de53922c3967321397240bd3d7


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

This project is for demonstration and testing purposes. Please ensure compliance with GitHub's API terms of service.