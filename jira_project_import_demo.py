#!/usr/bin/env python3
"""
Example script demonstrating JIRA project import functionality
"""

import requests
import json
import time
from typing import Dict, Any

class JiraProjectImporter:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        
    def test_connection(self) -> bool:
        """Test JIRA connection"""
        try:
            response = requests.get(f"{self.base_url}/api/jira/test")
            return response.status_code == 200
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False
    
    def get_project_info(self, project_key: str) -> Dict[str, Any]:
        """Get project information without importing"""
        try:
            response = requests.get(f"{self.base_url}/api/jira/project/{project_key}/info")
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"Failed to get project info: {response.status_code} - {response.text}")
        except Exception as e:
            raise Exception(f"Error getting project info: {e}")
    
    def import_project(self, project_key: str, bucket: str = "jira-project-docs", 
                      include_subtasks: bool = True, max_results: int = 1000) -> Dict[str, Any]:
        """Import entire project"""
        try:
            payload = {
                "project_key": project_key,
                "bucket": bucket,
                "include_subtasks": include_subtasks,
                "max_results": max_results
            }
            
            print(f"Starting import of project: {project_key}")
            print(f"Payload: {json.dumps(payload, indent=2)}")
            
            response = requests.post(f"{self.base_url}/api/jira/project/import", json=payload)
            
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"Import failed: {response.status_code} - {response.text}")
        except Exception as e:
            raise Exception(f"Error importing project: {e}")
    
    def import_specific_issue_types(self, project_key: str, issue_types: list, 
                                 bucket: str = "jira-project-docs") -> Dict[str, Any]:
        """Import specific issue types using JQL"""
        results = {}
        
        for issue_type in issue_types:
            try:
                jql = f"project = {project_key} AND issuetype = '{issue_type}'"
                payload = {
                    "jql": jql,
                    "bucket": bucket,
                    "max_results": 500
                }
                
                print(f"Importing {issue_type} issues...")
                response = requests.post(f"{self.base_url}/api/jira/search", json=payload)
                
                if response.status_code == 200:
                    results[issue_type] = response.json()
                    print(f"✅ {issue_type}: {results[issue_type]['total_found']} issues found")
                else:
                    print(f"❌ {issue_type}: Failed - {response.status_code}")
                    
            except Exception as e:
                print(f"❌ {issue_type}: Error - {e}")
                results[issue_type] = {"error": str(e)}
        
        return results

def main():
    """Main function demonstrating the JIRA project import functionality"""
    
    # Configuration
    PROJECT_KEY = "TEST"  # Replace with your actual project key
    BASE_URL = "http://localhost:8000"
    
    print("JIRA Project Import Demo")
    print("=" * 50)
    
    # Initialize importer
    importer = JiraProjectImporter(BASE_URL)
    
    # Test connection
    print("\n1. Testing JIRA connection...")
    if not importer.test_connection():
        print("❌ JIRA connection failed. Please check your configuration.")
        return
    print("✅ JIRA connection successful")
    
    # Get project info
    print(f"\n2. Getting project information for: {PROJECT_KEY}")
    try:
        project_info = importer.get_project_info(PROJECT_KEY)
        print(f"✅ Project: {project_info['project_name']}")
        print(f"   Total Issues: {project_info['total_issues']}")
        print(f"   Issues by Type:")
        for issue_type, count in project_info['issues_by_type'].items():
            if count > 0:
                print(f"     {issue_type}: {count}")
    except Exception as e:
        print(f"❌ Failed to get project info: {e}")
        return
    
    # Ask user what to do
    print(f"\n3. What would you like to do?")
    print("   a) Import entire project")
    print("   b) Import specific issue types")
    print("   c) Exit")
    
    choice = input("Enter your choice (a/b/c): ").lower().strip()
    
    if choice == 'a':
        # Import entire project
        print(f"\n4. Importing entire project: {PROJECT_KEY}")
        try:
            result = importer.import_project(PROJECT_KEY)
            print(f"✅ Import completed!")
            print(f"   Project: {result['project_name']}")
            print(f"   Total Issues: {result['total_issues']}")
            print(f"   Processed: {result['processed_count']}")
            print(f"   Failed: {result['failed_count']}")
            print(f"   Documents Created: {len(result['document_ids'])}")
            print(f"   Message: {result['message']}")
        except Exception as e:
            print(f"❌ Import failed: {e}")
    
    elif choice == 'b':
        # Import specific issue types
        print(f"\n4. Importing specific issue types from: {PROJECT_KEY}")
        issue_types = ['Epic', 'Story', 'Task', 'Bug']
        
        try:
            results = importer.import_specific_issue_types(PROJECT_KEY, issue_types)
            
            print(f"\nImport Summary:")
            total_imported = 0
            for issue_type, result in results.items():
                if 'error' not in result:
                    count = result.get('total_found', 0)
                    total_imported += count
                    print(f"   {issue_type}: {count} issues imported")
                else:
                    print(f"   {issue_type}: Error - {result['error']}")
            
            print(f"\nTotal issues imported: {total_imported}")
            
        except Exception as e:
            print(f"❌ Import failed: {e}")
    
    elif choice == 'c':
        print("Exiting...")
        return
    
    else:
        print("Invalid choice. Exiting...")
        return
    
    print(f"\n" + "=" * 50)
    print("Demo completed!")

if __name__ == "__main__":
    main()
