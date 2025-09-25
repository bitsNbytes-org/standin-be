#!/usr/bin/env python3
"""
Test script for JIRA project import functionality
"""

import requests
import json
from config import settings

def test_jira_project_import():
    """Test the JIRA project import endpoint"""
    
    # Configuration
    base_url = "http://localhost:8000"
    project_key = "TEST"  # Replace with your actual project key
    
    print(f"Testing JIRA project import for project: {project_key}")
    print("=" * 60)
    
    # Test 1: Get project info (without importing)
    print("\n1. Getting project information...")
    try:
        response = requests.get(f"{base_url}/api/jira/project/{project_key}/info")
        if response.status_code == 200:
            project_info = response.json()
            print(f"✅ Project: {project_info['project_name']}")
            print(f"   Total Issues: {project_info['total_issues']}")
            print(f"   Issues by Type: {json.dumps(project_info['issues_by_type'], indent=2)}")
        else:
            print(f"❌ Failed to get project info: {response.status_code} - {response.text}")
            return
    except Exception as e:
        print(f"❌ Error getting project info: {e}")
        return
    
    # Test 2: Import project issues
    print(f"\n2. Importing all issues from project {project_key}...")
    try:
        import_request = {
            "project_key": project_key,
            "bucket": "jira-project-docs",
            "include_subtasks": True,
            "max_results": 1000
        }
        
        response = requests.post(
            f"{base_url}/api/jira/project/import",
            json=import_request
        )
        
        if response.status_code == 200:
            import_result = response.json()
            print(f"✅ Import completed successfully!")
            print(f"   Project: {import_result['project_name']}")
            print(f"   Total Issues: {import_result['total_issues']}")
            print(f"   Processed: {import_result['processed_count']}")
            print(f"   Failed: {import_result['failed_count']}")
            print(f"   Document IDs: {len(import_result['document_ids'])} documents created")
            print(f"   Message: {import_result['message']}")
            
            # Show issues by type
            print(f"\n   Issues by Type:")
            for issue_type, count in import_result['issues_by_type'].items():
                if count > 0:
                    print(f"     {issue_type}: {count}")
        else:
            print(f"❌ Failed to import project: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ Error importing project: {e}")
    
    print("\n" + "=" * 60)
    print("Test completed!")

def test_jira_connection():
    """Test JIRA connection"""
    base_url = "http://localhost:8000"
    
    print("Testing JIRA connection...")
    try:
        response = requests.get(f"{base_url}/api/jira/test")
        if response.status_code == 200:
            print("✅ JIRA connection is working")
            return True
        else:
            print(f"❌ JIRA connection failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error testing JIRA connection: {e}")
        return False

if __name__ == "__main__":
    print("JIRA Project Import Test")
    print("=" * 60)
    
    # Test connection first
    if test_jira_connection():
        # Test project import
        test_jira_project_import()
    else:
        print("Please check your JIRA configuration and ensure the server is running.")
