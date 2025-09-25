import os
import re
import json
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
import requests
from config import settings


class JiraService:
    def __init__(self):
        self.base_url = settings.JIRA_URL
        self.username = settings.JIRA_USER
        self.token = settings.JIRA_TOKEN
        self.auth = (self.username, self.token)

    def extract_issue_key_from_url(self, url: str) -> Optional[str]:
        """Extract issue key from JIRA URL"""
        try:
            # Handle different URL formats
            # Format 1: https://domain.atlassian.net/browse/PROJECT-123
            # Format 2: https://domain.atlassian.net/jira/browse/PROJECT-123
            # Format 3: https://domain.atlassian.net/projects/PROJECT/issues/PROJECT-123
            
            parsed_url = urlparse(url)
            
            # Check for browse pattern
            browse_match = re.search(r'/browse/([A-Z]+-\d+)', parsed_url.path)
            if browse_match:
                return browse_match.group(1)
            
            # Check for issues pattern
            issues_match = re.search(r'/issues/([A-Z]+-\d+)', parsed_url.path)
            if issues_match:
                return issues_match.group(1)
            
            return None
        except Exception as e:
            print(f"Error extracting issue key from URL: {e}")
            return None

    def fetch_issue_by_url(self, url: str) -> Dict[str, Any]:
        """Fetch JIRA issue by URL"""
        issue_key = self.extract_issue_key_from_url(url)
        if not issue_key:
            raise ValueError(f"Could not extract issue key from URL: {url}")
        
        return self.fetch_issue_by_key(issue_key)

    def fetch_issue_by_key(self, issue_key: str) -> Dict[str, Any]:
        """Fetch JIRA issue by key"""
        try:
            url = f"{self.base_url}/rest/api/2/issue/{issue_key}"
            response = requests.get(url, auth=self.auth)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error fetching issue {issue_key}: {str(e)}")

    def fetch_issue_subtasks(self, issue_key: str) -> List[Dict[str, Any]]:
        """Fetch subtasks for a JIRA issue"""
        try:
            url = f"{self.base_url}/rest/api/2/search"
            params = {
                "jql": f"parent = {issue_key}",
                "expand": "changelog"
            }
            response = requests.get(url, auth=self.auth, params=params)
            response.raise_for_status()
            return response.json().get("issues", [])
        except requests.exceptions.RequestException as e:
            print(f"Error fetching subtasks for {issue_key}: {str(e)}")
            return []

    def format_issue_content(self, issue_data: Dict[str, Any], subtasks: List[Dict[str, Any]] = None) -> Dict[str, str]:
        """Format issue data into readable content"""
        fields = issue_data.get("fields", {})
        
        # Extract basic information
        issue_key = issue_data.get("key", "Unknown")
        summary = fields.get("summary", "No summary")
        description = fields.get("description", "No description")
        issue_type = fields.get("issuetype", {}).get("name", "Unknown")
        status = fields.get("status", {}).get("name", "Unknown")
        priority = fields.get("priority", {}).get("name", "Unknown")
        assignee = fields.get("assignee", {}).get("displayName", "Unassigned")
        reporter = fields.get("reporter", {}).get("displayName", "Unknown")
        created = fields.get("created", "Unknown")
        updated = fields.get("updated", "Unknown")
        
        # Extract project information
        project = fields.get("project", {})
        project_name = project.get("name", "Unknown Project")
        project_key = project.get("key", "Unknown")
        
        # Format description (remove HTML if present)
        if description:
            description = self.clean_html_content(description)
        
        # Build simple content summary
        content_lines = [
            f"JIRA Issue: {issue_key}",
            f"Summary: {summary}",
            f"Type: {issue_type}",
            f"Status: {status}",
            f"Priority: {priority}",
            f"Assignee: {assignee}",
            f"Project: {project_name}",
            f"",
            f"Description: {description}"
        ]
        
        # Add subtasks if available
        if subtasks:
            content_lines.append("")
            content_lines.append("Subtasks:")
            for subtask in subtasks:
                subtask_fields = subtask.get("fields", {})
                subtask_key = subtask.get("key", "Unknown")
                subtask_summary = subtask_fields.get("summary", "No summary")
                subtask_status = subtask_fields.get("status", {}).get("name", "Unknown")
                content_lines.append(f"- {subtask_key}: {subtask_summary} ({subtask_status})")
        
        # Create filename
        safe_summary = re.sub(r'[^\w\s-]', '', summary).strip()
        safe_summary = re.sub(r'[-\s]+', '-', safe_summary)
        filename = f"jira-{issue_key}-{safe_summary}.txt"
        
        # Create JSON content for database storage (simplified format)
        json_content = {
            "page_id": issue_key,  # Using issue_key as page_id for consistency
            "title": summary,
            "content": "\n".join(content_lines),
            "url": f"{self.base_url}/browse/{issue_key}",
            "source": "jira"
        }
        
        return {
            "title": f"{issue_key}: {summary}",
            "content": "\n".join(content_lines),
            "filename": filename,
            "issue_key": issue_key,
            "project_name": project_name,
            "json_content": json_content
        }

    def clean_html_content(self, html_content: str) -> str:
        """Clean HTML content and convert to plain text"""
        if not html_content:
            return ""
        
        # Simple HTML tag removal
        import re
        # Remove HTML tags
        clean_text = re.sub(r'<[^>]+>', '', html_content)
        # Decode HTML entities
        clean_text = clean_text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        # Clean up whitespace
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        return clean_text

    def search_issues_by_jql(self, jql: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """Search issues using JQL"""
        try:
            url = f"{self.base_url}/rest/api/2/search"
            params = {
                "jql": jql,
                "maxResults": max_results,
                "expand": "changelog"
            }
            response = requests.get(url, auth=self.auth, params=params)
            response.raise_for_status()
            return response.json().get("issues", [])
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error searching issues with JQL '{jql}': {str(e)}")

    def fetch_all_project_issues(self, project_key: str, max_results: int = 1000) -> List[Dict[str, Any]]:
        """Fetch all issues from a project"""
        try:
            url = f"{self.base_url}/rest/api/2/search"
            params = {
                "jql": f"project = {project_key}",
                "maxResults": max_results,
                "expand": "changelog,subtasks"
            }
            response = requests.get(url, auth=self.auth, params=params)
            response.raise_for_status()
            return response.json().get("issues", [])
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error fetching all issues for project '{project_key}': {str(e)}")

    def fetch_project_issues_by_type(self, project_key: str, issue_type: str, max_results: int = 500) -> List[Dict[str, Any]]:
        """Fetch issues of specific type from a project"""
        try:
            url = f"{self.base_url}/rest/api/2/search"
            params = {
                "jql": f"project = {project_key} AND issuetype = '{issue_type}'",
                "maxResults": max_results,
                "expand": "changelog,subtasks"
            }
            response = requests.get(url, auth=self.auth, params=params)
            response.raise_for_status()
            return response.json().get("issues", [])
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error fetching {issue_type} issues for project '{project_key}': {str(e)}")

    def get_project_info(self, project_key: str) -> Dict[str, Any]:
        """Get project information"""
        try:
            url = f"{self.base_url}/rest/api/2/project/{project_key}"
            response = requests.get(url, auth=self.auth)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error fetching project info for '{project_key}': {str(e)}")

    def process_project_issues(self, project_key: str, bucket: str = "jira-project-docs") -> Dict[str, Any]:
        """Process all issues from a project and return summary"""
        try:
            # Get project info
            project_info = self.get_project_info(project_key)
            project_name = project_info.get("name", project_key)
            
            # Fetch all issues
            all_issues = self.fetch_all_project_issues(project_key)
            
            # Organize issues by type
            issues_by_type = {
                "epics": [],
                "stories": [],
                "tasks": [],
                "subtasks": [],
                "bugs": [],
                "other": []
            }
            
            for issue in all_issues:
                issue_type = issue.get("fields", {}).get("issuetype", {}).get("name", "").lower()
                
                if issue_type == "epic":
                    issues_by_type["epics"].append(issue)
                elif issue_type == "story":
                    issues_by_type["stories"].append(issue)
                elif issue_type == "task":
                    issues_by_type["tasks"].append(issue)
                elif issue_type == "sub-task":
                    issues_by_type["subtasks"].append(issue)
                elif issue_type == "bug":
                    issues_by_type["bugs"].append(issue)
                else:
                    issues_by_type["other"].append(issue)
            
            return {
                "project_key": project_key,
                "project_name": project_name,
                "total_issues": len(all_issues),
                "issues_by_type": {k: len(v) for k, v in issues_by_type.items()},
                "all_issues": all_issues,
                "issues_by_type_data": issues_by_type
            }
            
        except Exception as e:
            raise Exception(f"Error processing project issues: {str(e)}")

    def format_issue_for_storage(self, issue_data: Dict[str, Any], include_subtasks: bool = True) -> Dict[str, Any]:
        """Format issue data for database and MinIO storage"""
        fields = issue_data.get("fields", {})
        
        # Extract basic information
        issue_key = issue_data.get("key", "Unknown")
        summary = fields.get("summary", "No summary")
        description = fields.get("description", "No description")
        issue_type = fields.get("issuetype", {}).get("name", "Unknown")
        status = fields.get("status", {}).get("name", "Unknown")
        priority = fields.get("priority", {}).get("name", "Unknown")
        assignee = fields.get("assignee", {}).get("displayName", "Unassigned")
        reporter = fields.get("reporter", {}).get("displayName", "Unknown")
        created = fields.get("created", "Unknown")
        updated = fields.get("updated", "Unknown")
        
        # Extract project information
        project = fields.get("project", {})
        project_name = project.get("name", "Unknown Project")
        project_key = project.get("key", "Unknown")
        
        # Extract epic information if available
        epic_link = fields.get("customfield_10014", "No epic")  # Epic Link field
        epic_name = fields.get("customfield_10015", "No epic")  # Epic Name field
        
        # Format description (remove HTML if present)
        if description:
            description = self.clean_html_content(description)
        
        # Fetch subtasks if requested
        subtasks = []
        if include_subtasks:
            subtasks = self.fetch_issue_subtasks(issue_key)
        
        # Build content
        content_lines = [
            f"# JIRA Issue: {issue_key}",
            f"",
            f"**Summary:** {summary}",
            f"**Type:** {issue_type}",
            f"**Status:** {status}",
            f"**Priority:** {priority}",
            f"**Assignee:** {assignee}",
            f"**Reporter:** {reporter}",
            f"**Project:** {project_name} ({project_key})",
            f"**Epic:** {epic_name}",
            f"**Created:** {created}",
            f"**Updated:** {updated}",
            f"",
            f"## Description",
            f"{description}",
            f""
        ]
        
        # Add subtasks if available
        if subtasks:
            content_lines.extend([
                f"## Subtasks",
                f""
            ])
            for subtask in subtasks:
                subtask_fields = subtask.get("fields", {})
                subtask_key = subtask.get("key", "Unknown")
                subtask_summary = subtask_fields.get("summary", "No summary")
                subtask_status = subtask_fields.get("status", {}).get("name", "Unknown")
                content_lines.extend([
                    f"- **{subtask_key}:** {subtask_summary} ({subtask_status})"
                ])
            content_lines.append("")
        
        # Create filename
        safe_summary = re.sub(r'[^\w\s-]', '', summary).strip()
        safe_summary = re.sub(r'[-\s]+', '-', safe_summary)
        filename = f"jira-{issue_key}-{safe_summary}.txt"
        
        # Create JSON content for database storage
        content = {
            "issue_key": issue_key,
            "summary": summary,
            "description": description,
            "issue_type": issue_type,
            "status": status,
            "priority": priority,
            "assignee": assignee,
            "reporter": reporter,
            "project_name": project_name,
            "project_key": project_key,
            "epic_name": epic_name,
            "epic_link": epic_link,
            "created": created,
            "updated": updated,
            "subtasks": [
                {
                    "key": st.get("key"),
                    "summary": st.get("fields", {}).get("summary"),
                    "status": st.get("fields", {}).get("status", {}).get("name")
                } for st in subtasks
            ] if subtasks else []
        }
        
        return {
            "title": f"{issue_key}: {summary}",
            "content": "\n".join(content_lines),
            "filename": filename,
            "issue_key": issue_key,
            "project_name": project_name,
            "project_key": project_key,
            "issue_type": issue_type,
            "status": status,
            "content": content
        }

    def fetch_board_issues(self, project_key: str, board_id: str = None) -> Dict[str, Any]:
        """Fetch all issues from a JIRA board/project with subtasks and comments"""
        try:
            # Get all issues for the project
            jql = f"project = {project_key}"
            issues = self.search_issues_by_jql(jql, max_results=1000)
            
            all_issues_data = []
            total_issues = len(issues)
            
            for i, issue in enumerate(issues):
                print(f"Processing issue {i+1}/{total_issues}: {issue.get('key', 'Unknown')}")
                
                # Get detailed issue information
                issue_key = issue.get('key')
                if not issue_key:
                    continue
                
                detailed_issue = self.fetch_issue_by_key(issue_key)
                if not detailed_issue:
                    continue
                
                # Get subtasks
                subtasks = self.fetch_issue_subtasks(issue_key)
                
                # Get comments
                comments = self.fetch_issue_comments(issue_key)
                
                # Format issue content
                issue_data = {
                    "issue": detailed_issue,
                    "subtasks": subtasks,
                    "comments": comments,
                    "issue_key": issue_key
                }
                
                all_issues_data.append(issue_data)
            
            # Create comprehensive content
            content_lines = [
                f"# JIRA Board Import: {project_key}",
                f"Total Issues: {total_issues}",
                f"Import Date: {self._get_current_timestamp()}",
                "",
                "---",
                ""
            ]
            
            for issue_data in all_issues_data:
                issue = issue_data["issue"]
                issue_key = issue_data["issue_key"]
                subtasks = issue_data["subtasks"]
                comments = issue_data["comments"]
                
                # Add issue header
                summary = issue.get("fields", {}).get("summary", "No Summary")
                status = issue.get("fields", {}).get("status", {}).get("name", "Unknown")
                issue_type = issue.get("fields", {}).get("issuetype", {}).get("name", "Unknown")
                
                content_lines.extend([
                    f"## {issue_key}: {summary}",
                    f"**Type:** {issue_type} | **Status:** {status}",
                    ""
                ])
                
                # Add issue description
                description = issue.get("fields", {}).get("description", "")
                if description:
                    clean_description = self.clean_html_content(str(description))
                    content_lines.extend([
                        "### Description:",
                        clean_description,
                        ""
                    ])
                
                # Add subtasks
                if subtasks:
                    content_lines.extend([
                        "### Subtasks:",
                        ""
                    ])
                    for subtask in subtasks:
                        subtask_key = subtask.get("key", "Unknown")
                        subtask_summary = subtask.get("fields", {}).get("summary", "No Summary")
                        subtask_status = subtask.get("fields", {}).get("status", {}).get("name", "Unknown")
                        content_lines.extend([
                            f"- **{subtask_key}:** {subtask_summary} ({subtask_status})"
                        ])
                    content_lines.append("")
                
                # Add comments
                if comments:
                    content_lines.extend([
                        "### Comments:",
                        ""
                    ])
                    for comment in comments:
                        author = comment.get("author", {}).get("displayName", "Unknown")
                        created = comment.get("created", "Unknown Date")
                        body = comment.get("body", "")
                        clean_body = self.clean_html_content(str(body))
                        content_lines.extend([
                            f"**{author}** ({created}):",
                            clean_body,
                            ""
                        ])
                
                content_lines.extend(["---", ""])
            
            # Create filename
            safe_project = re.sub(r'[^\w\s-]', '', project_key).strip()
            filename = f"jira-board-{safe_project}-{self._get_current_timestamp()}.txt"
            
            # Create JSON content for database
            json_content = {
                "project_key": project_key,
                "board_id": board_id,
                "total_issues": total_issues,
                "import_timestamp": self._get_current_timestamp(),
                "issues": all_issues_data,
                "url": f"{self.base_url}/jira/software/projects/{project_key}/boards/{board_id}" if board_id else f"{self.base_url}/browse/{project_key}"
            }
            
            return {
                "title": f"JIRA Board Import: {project_key}",
                "content": "\n".join(content_lines),
                "filename": filename,
                "project_key": project_key,
                "board_id": board_id,
                "total_issues": total_issues,
                "json_content": json_content
            }
            
        except Exception as e:
            raise Exception(f"Error fetching board issues: {str(e)}")

    def fetch_issue_comments(self, issue_key: str) -> List[Dict[str, Any]]:
        """Fetch comments for a specific issue"""
        try:
            url = f"{self.base_url}/rest/api/3/issue/{issue_key}/comment"
            response = requests.get(url, auth=self.auth, headers={"Accept": "application/json"})
            
            if response.status_code == 200:
                data = response.json()
                return data.get("comments", [])
            else:
                print(f"Failed to fetch comments for {issue_key}: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"Error fetching comments for {issue_key}: {str(e)}")
            return []

    def _get_current_timestamp(self) -> str:
        """Get current timestamp in a readable format"""
        from datetime import datetime
        return datetime.utcnow().strftime("%Y%m%d-%H%M%S")
