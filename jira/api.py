from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Document
from schemas import (
    JiraIssueRequest,
    JiraIssueResponse,
    JiraSearchRequest,
    JiraSearchResponse,
    JiraProjectImportRequest,
    JiraProjectImportResponse,
)
from services.jira_service import JiraService
from minio_client import upload_file_content, create_bucket_if_not_exists
import logging

logger = logging.getLogger(__name__)

router = APIRouter()



@router.post("/search", response_model=JiraSearchResponse)
def search_jira_issues(
    request: JiraSearchRequest, db: Session = Depends(get_db)
):
    """
    Search JIRA issues using JQL and save them to MinIO and database
    """
    try:
        # Initialize JIRA service
        jira_service = JiraService()

        # Search issues using JQL
        logger.info(f"Searching JIRA issues with JQL: {request.jql}")
        issues = jira_service.search_issues_by_jql(
            request.jql, request.max_results
        )

        if not issues:
            return JiraSearchResponse(
                document_ids=[],
                total_found=0,
                message="No issues found matching the JQL query",
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
                    content_data["content"], content_data["filename"]
                )

                if upload_success:
                    # Save document metadata to database
                    document = Document(
                        content=content_data["json_content"],
                        filename=content_data["filename"],
                        bucket=request.bucket,
                        external_link=f"{jira_service.base_url}/browse/{content_data['issue_key']}",
                    )

                    db.add(document)
                    db.commit()
                    db.refresh(document)

                    document_ids.append(document.id)
                    logger.info(
                        f"Successfully created document {document.id} for issue {content_data['issue_key']}"
                    )

            except Exception as e:
                logger.error(
                    f"Error processing issue {issue_data.get('key', 'Unknown')}: {str(e)}"
                )
                continue

        return JiraSearchResponse(
            document_ids=document_ids,
            total_found=len(issues),
            message=f"Successfully processed {len(document_ids)} out of {len(issues)} issues",
        )

    except Exception as e:
        logger.error(f"Error searching JIRA issues: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to search JIRA issues: {str(e)}"
        )


@router.get("/test")
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
        raise HTTPException(
            status_code=500, detail=f"JIRA connection failed: {str(e)}"
        )


@router.get("/issue/{issue_key}")
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
            "subtasks": subtasks,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch JIRA issue: {str(e)}"
        )



@router.get("/project/{project_key}/info")
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
                k: [
                    {
                        "key": issue.get("key"),
                        "summary": issue.get("fields", {}).get("summary"),
                    }
                    for issue in v
                ]
                for k, v in project_data["issues_by_type_data"].items()
            },
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get JIRA project info: {str(e)}",
        )
