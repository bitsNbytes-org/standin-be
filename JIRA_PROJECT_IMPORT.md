# JIRA Project Import Documentation

## Overview

The enhanced JIRA service now supports importing entire projects, including all epics, stories, tasks, subtasks, and bugs. This functionality allows you to bulk import all issues from a JIRA project into your database and MinIO storage.

## New Features

### 1. Project-Wide Import
- Import all issues from a JIRA project in a single operation
- Organize issues by type (Epics, Stories, Tasks, Subtasks, Bugs)
- Store both formatted text content and structured JSON data
- Automatic MinIO upload and database storage

### 2. Enhanced JIRA Service Methods

#### `fetch_all_project_issues(project_key, max_results=1000)`
Fetches all issues from a specified project using JQL.

#### `fetch_project_issues_by_type(project_key, issue_type, max_results=500)`
Fetches issues of a specific type from a project.

#### `get_project_info(project_key)`
Retrieves project metadata and information.

#### `process_project_issues(project_key, bucket="jira-project-docs")`
Processes all issues from a project and organizes them by type.

#### `format_issue_for_storage(issue_data, include_subtasks=True)`
Formats issue data for database and MinIO storage with enhanced metadata.

## API Endpoints

### 1. Import Entire Project
```http
POST /api/jira/project/import
```

**Request Body:**
```json
{
  "project_key": "PROJECT-KEY",
  "bucket": "jira-project-docs",
  "include_subtasks": true,
  "max_results": 1000
}
```

**Response:**
```json
{
  "project_key": "PROJECT-KEY",
  "project_name": "Project Name",
  "total_issues": 150,
  "issues_by_type": {
    "epics": 5,
    "stories": 45,
    "tasks": 30,
    "subtasks": 60,
    "bugs": 10,
    "other": 0
  },
  "document_ids": [1, 2, 3, ...],
  "processed_count": 148,
  "failed_count": 2,
  "message": "Successfully processed 148 out of 150 issues from project 'Project Name'"
}
```

### 2. Get Project Information
```http
GET /api/jira/project/{project_key}/info
```

**Response:**
```json
{
  "project_key": "PROJECT-KEY",
  "project_name": "Project Name",
  "total_issues": 150,
  "issues_by_type": {
    "epics": 5,
    "stories": 45,
    "tasks": 30,
    "subtasks": 60,
    "bugs": 10,
    "other": 0
  },
  "issues_by_type_data": {
    "epics": [
      {"key": "PROJECT-1", "summary": "Epic Summary"},
      ...
    ],
    "stories": [...],
    ...
  }
}
```

## Usage Examples

### 1. Using cURL

#### Import entire project:
```bash
curl -X POST "http://localhost:8000/api/jira/project/import" \
  -H "Content-Type: application/json" \
  -d '{
    "project_key": "PROJECT-KEY",
    "bucket": "jira-project-docs",
    "include_subtasks": true,
    "max_results": 1000
  }'
```

#### Get project info:
```bash
curl -X GET "http://localhost:8000/api/jira/project/PROJECT-KEY/info"
```

### 2. Using Python

```python
import requests

# Import entire project
response = requests.post(
    "http://localhost:8000/api/jira/project/import",
    json={
        "project_key": "PROJECT-KEY",
        "bucket": "jira-project-docs",
        "include_subtasks": True,
        "max_results": 1000
    }
)

if response.status_code == 200:
    result = response.json()
    print(f"Imported {result['processed_count']} issues")
    print(f"Project: {result['project_name']}")
    print(f"Issues by type: {result['issues_by_type']}")
```

### 3. Using the Test Script

Run the provided test script:
```bash
python test_jira_project_import.py
```

## Data Storage

### Database Storage
Each issue is stored as a `Document` record with:
- `content`: JSON object containing all issue metadata
- `filename`: Generated filename (e.g., `jira-PROJECT-123-issue-summary.txt`)
- `bucket`: Specified bucket name
- `external_link`: Link to the original JIRA issue

### MinIO Storage
Each issue is stored as a text file containing:
- Issue metadata (key, summary, type, status, etc.)
- Formatted description
- Subtask information (if included)
- Project and epic information

### JSON Content Structure
```json
{
  "issue_key": "PROJECT-123",
  "summary": "Issue Summary",
  "description": "Issue Description",
  "issue_type": "Story",
  "status": "In Progress",
  "priority": "High",
  "assignee": "John Doe",
  "reporter": "Jane Smith",
  "project_name": "Project Name",
  "project_key": "PROJECT",
  "epic_name": "Epic Name",
  "epic_link": "PROJECT-1",
  "created": "2024-01-01T00:00:00.000Z",
  "updated": "2024-01-15T00:00:00.000Z",
  "subtasks": [
    {
      "key": "PROJECT-124",
      "summary": "Subtask Summary",
      "status": "Done"
    }
  ]
}
```

## Configuration

Ensure your JIRA credentials are properly configured in `config.py`:

```python
JIRA_URL = "https://your-domain.atlassian.net"
JIRA_USER = "your-email@example.com"
JIRA_TOKEN = "your-api-token"
```

## Error Handling

The service includes comprehensive error handling:
- Individual issue processing failures don't stop the entire import
- Failed issues are counted and reported
- Detailed error logging for debugging
- Graceful handling of missing fields or permissions

## Performance Considerations

- Large projects may take time to process
- Consider using `max_results` parameter for testing
- Subtasks are fetched individually, which may impact performance for projects with many subtasks
- Rate limiting is handled by the JIRA API

## Testing

Use the provided test script to verify functionality:

```bash
# Test connection
curl -X GET "http://localhost:8000/api/jira/test"

# Test project info
curl -X GET "http://localhost:8000/api/jira/project/PROJECT-KEY/info"

# Test project import
python test_jira_project_import.py
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**: Verify JIRA credentials in config
2. **Permission Errors**: Ensure API token has project access
3. **Rate Limiting**: JIRA may throttle requests for large projects
4. **Missing Fields**: Some custom fields may not be accessible

### Debug Mode

Enable debug logging to see detailed processing information:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Future Enhancements

- Incremental sync capabilities
- Custom field mapping
- Issue relationship tracking
- Bulk update functionality
- Export to other formats
