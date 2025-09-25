from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Document
from schemas import (
    JiraIssueRequest, JiraIssueResponse, 
    JiraSearchRequest, JiraSearchResponse,
    JiraProjectImportRequest, JiraProjectImportResponse
)
from jira_service import JiraService
from minio_client import upload_file_content, create_bucket_if_not_exists
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/jira/pull", response_model=JiraIssueResponse)
def pull_jira_issue(
    request: JiraIssueRequest, 
    db: Session = Depends(get_db)
):
    """
    Pull a JIRA issue by URL and save it to MinIO and database
    """
    try:
        # Initialize JIRA service
        jira_service = JiraService()
        
        # Fetch issue data from JIRA
        logger.info(f"Fetching JIRA issue from URL: {request.url}")
        issue_data = jira_service.fetch_issue_by_url(request.url)
        
        # Fetch subtasks if requested
        subtasks = []
        if request.include_subtasks:
            issue_key = jira_service.extract_issue_key_from_url(request.url)
            if issue_key:
                subtasks = jira_service.fetch_issue_subtasks(issue_key)
        
        # Format content
        content_data = jira_service.format_issue_content(issue_data, subtasks)
        
        # Ensure bucket exists
        create_bucket_if_not_exists()
        
        # Upload content to MinIO
        logger.info(f"Uploading content to MinIO: {content_data['filename']}")
        upload_success = upload_file_content(
            content_data['content'], 
            content_data['filename']
        )
        
        if not upload_success:
            raise HTTPException(
                status_code=500, 
                detail="Failed to upload content to MinIO"
            )
        
        # Save document metadata to database
        document = Document(
            content=content_data['json_content'],
            filename=content_data['filename'],
            bucket=request.bucket,
            external_link=request.url
        )
        
        db.add(document)
        db.commit()
        db.refresh(document)
        
        logger.info(f"Successfully created document with ID: {document.id}")
        
        return JiraIssueResponse(
            document_id=document.id,
            title=content_data['title'],
            filename=content_data['filename'],
            issue_key=content_data['issue_key'],
            project_name=content_data['project_name'],
            message=f"Successfully pulled JIRA issue '{content_data['issue_key']}' and saved as document {document.id}"
        )
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error pulling JIRA issue: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to pull JIRA issue: {str(e)}")


@router.post("/jira/search", response_model=JiraSearchResponse)
def search_jira_issues(
    request: JiraSearchRequest, 
    db: Session = Depends(get_db)
):
    """
    Search JIRA issues using JQL and save them to MinIO and database
    """
    try:
        # Initialize JIRA service
        jira_service = JiraService()
        
        # Search issues using JQL
        logger.info(f"Searching JIRA issues with JQL: {request.jql}")
        issues = jira_service.search_issues_by_jql(request.jql, request.max_results)
        
        if not issues:
            return JiraSearchResponse(
                document_ids=[],
                total_found=0,
                message="No issues found matching the JQL query"
            )
        
        # Ensure bucket exists
        create_bucket_if_not_exists()
        
        document_ids = []
        
        # Process each issue
        for issue_data in issues:
            try:
                # Format content for this issue
                content_data = jira_service.format_issue_content(issue_data)
                
                # Upload content to MinIO
                upload_success = upload_file_content(
                    content_data['content'], 
                    content_data['filename']
                )
                
                if upload_success:
                    # Save document metadata to database
                    document = Document(
                        content=content_data['json_content'],
                        filename=content_data['filename'],
                        bucket=request.bucket,
                        external_link=f"{jira_service.base_url}/browse/{content_data['issue_key']}"
                    )
                    
                    db.add(document)
                    db.commit()
                    db.refresh(document)
                    
                    document_ids.append(document.id)
                    logger.info(f"Successfully created document {document.id} for issue {content_data['issue_key']}")
                
            except Exception as e:
                logger.error(f"Error processing issue {issue_data.get('key', 'Unknown')}: {str(e)}")
                continue
        
        return JiraSearchResponse(
            document_ids=document_ids,
            total_found=len(issues),
            message=f"Successfully processed {len(document_ids)} out of {len(issues)} issues"
        )
        
    except Exception as e:
        logger.error(f"Error searching JIRA issues: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to search JIRA issues: {str(e)}")


@router.get("/jira/test")
def test_jira_connection():
    """
    Test JIRA connection
    """
    try:
        jira_service = JiraService()
        # Try to make a simple API call
        url = f"{jira_service.base_url}/rest/api/2/myself"
        response = jira_service.auth
        # This will raise an exception if connection fails
        return {"status": "success", "message": "JIRA connection is working"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"JIRA connection failed: {str(e)}")


@router.get("/jira/issue/{issue_key}")
def get_jira_issue_by_key(issue_key: str):
    """
    Get JIRA issue details by key (without saving to database)
    """
    try:
        jira_service = JiraService()
        issue_data = jira_service.fetch_issue_by_key(issue_key)
        subtasks = jira_service.fetch_issue_subtasks(issue_key)
        content_data = jira_service.format_issue_content(issue_data, subtasks)
        
        return {
            "issue_data": issue_data,
            "formatted_content": content_data,
            "subtasks": subtasks
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch JIRA issue: {str(e)}")


@router.post("/jira/project/import", response_model=JiraProjectImportResponse)
def import_jira_project(
    request: JiraProjectImportRequest, 
    db: Session = Depends(get_db)
):
    """
    Import all issues from a JIRA project and save them to MinIO and database
    """
    try:
        # Initialize JIRA service
        jira_service = JiraService()
        
        # Process all issues from the project
        logger.info(f"Processing all issues from project: {request.project_key}")
        project_data = jira_service.process_project_issues(request.project_key)
        
        if not project_data["all_issues"]:
            return JiraProjectImportResponse(
                project_key=request.project_key,
                project_name=project_data["project_name"],
                total_issues=0,
                issues_by_type={},
                document_ids=[],
                processed_count=0,
                failed_count=0,
                message=f"No issues found in project '{request.project_key}'"
            )
        
        # Ensure bucket exists
        create_bucket_if_not_exists()
        
        document_ids = []
        failed_count = 0
        
        # Process each issue
        for issue_data in project_data["all_issues"]:
            try:
                # Format content for this issue
                content_data = jira_service.format_issue_for_storage(
                    issue_data, 
                    request.include_subtasks
                )
                
                # Upload content to MinIO
                upload_success = upload_file_content(
                    content_data['content'], 
                    content_data['filename']
                )
                
                if upload_success:
                    # Save document metadata to database
                    document = Document(
                        content=content_data['json_content'],
                        filename=content_data['filename'],
                        bucket=request.bucket,
                        external_link=f"{jira_service.base_url}/browse/{content_data['issue_key']}"
                    )
                    
                    db.add(document)
                    db.commit()
                    db.refresh(document)
                    
                    document_ids.append(document.id)
                    logger.info(f"Successfully created document {document.id} for issue {content_data['issue_key']}")
                else:
                    failed_count += 1
                    logger.error(f"Failed to upload content for issue {content_data['issue_key']}")
                
            except Exception as e:
                failed_count += 1
                logger.error(f"Error processing issue {issue_data.get('key', 'Unknown')}: {str(e)}")
                continue
        
        processed_count = len(document_ids)
        
        return JiraProjectImportResponse(
            project_key=request.project_key,
            project_name=project_data["project_name"],
            total_issues=project_data["total_issues"],
            issues_by_type=project_data["issues_by_type"],
            document_ids=document_ids,
            processed_count=processed_count,
            failed_count=failed_count,
            message=f"Successfully processed {processed_count} out of {project_data['total_issues']} issues from project '{project_data['project_name']}'"
        )
        
    except Exception as e:
        logger.error(f"Error importing JIRA project: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to import JIRA project: {str(e)}")


@router.get("/jira/project/{project_key}/info")
def get_jira_project_info(project_key: str):
    """
    Get JIRA project information and issue summary (without saving to database)
    """
    try:
        jira_service = JiraService()
        project_data = jira_service.process_project_issues(project_key)
        
        return {
            "project_key": project_data["project_key"],
            "project_name": project_data["project_name"],
            "total_issues": project_data["total_issues"],
            "issues_by_type": project_data["issues_by_type"],
            "issues_by_type_data": {
                k: [{"key": issue.get("key"), "summary": issue.get("fields", {}).get("summary")} 
                    for issue in v] 
                for k, v in project_data["issues_by_type_data"].items()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get JIRA project info: {str(e)}")