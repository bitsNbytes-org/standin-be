#!/usr/bin/env python3
"""
Fixed JIRA Populator Script
---------------------------
Fixed version that handles:
- Atlassian Document Format (ADF) for descriptions
- Proper project validation
- Removed priority field issues
- Better error handling
"""

import os, sys, time, base64, json, re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import requests

# -----------------------------
# Configuration - edit or use env vars
# -----------------------------
CONFIG = {
    "JIRA_BASE_URL": os.getenv("JIRA_BASE_URL", "https://standin.atlassian.net/"),
    "PROJECT_KEY": os.getenv("JIRA_PROJECT_KEY", "KAN"),
    "JIRA_EMAIL": os.getenv("JIRA_EMAIL", "aravindbalan222@gmail.com"),
    "JIRA_API_TOKEN": os.getenv("JIRA_API_TOKEN", "ATATT3xFfGF0i61xcJnoPABm-2le2X4Y6PSijCONk4pqlAAG9l8jOVWUb1CGhyLqffX0L_K4xfMKCJsfL3PN_Ydr_RxFQ5VXOQm4N88NugSWseRJfB2yAoz2tmYRN33EjO9DBSfUjwBwfZ7x_mAUMNo1U5C_m05SWaUOBUpe2kxF3bzV8kdESLM=BAA51F44"),
    "ISSUE_REPORTER": os.getenv("JIRA_EMAIL", "aravindbalan222@gmail.com"),
    "DEFAULT_ASSIGNEE": None,  # accountId if desired
    "DRY_RUN": os.getenv("DRY_RUN", "false").lower() == "true",
    "USE_SUBTASKS": True,
    "DEPLOYMENT_EPIC_SUMMARY": "Platform: Infrastructure Setup",
    "OUTPUT_FILE": os.getenv("OUTPUT_FILE", "created_issues.json"),
    "DONE_TRANSITION_KEYWORDS": ["done", "resolve", "resolved", "close", "closed", "complete", "completed"],
}

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}

def get_auth(config: Dict[str, Any]) -> str:
    """Get authentication header"""
    email = config["JIRA_EMAIL"]
    token = config["JIRA_API_TOKEN"]
    credentials = f"{email}:{token}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"

def jira_get(endpoint: str, config: Dict[str, Any]) -> Optional[requests.Response]:
    """Make GET request to JIRA"""
    url = config["JIRA_BASE_URL"].rstrip("/") + endpoint
    headers = HEADERS.copy()
    headers["Authorization"] = get_auth(config)
    
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        return resp
    except requests.exceptions.RequestException as e:
        print(f"HTTP request error: {e}")
        return None

def jira_post(endpoint: str, config: Dict[str, Any], payload: Dict[str, Any]) -> Optional[requests.Response]:
    """Make POST request to JIRA"""
    url = config["JIRA_BASE_URL"].rstrip("/") + endpoint
    headers = HEADERS.copy()
    headers["Authorization"] = get_auth(config)
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        return resp
    except requests.exceptions.RequestException as e:
        print(f"HTTP request error: {e}")
        return None

def validate_project(config: Dict[str, Any]) -> bool:
    """Validate that the project exists and is accessible"""
    print(f"Validating project: {config['PROJECT_KEY']}")
    resp = jira_get(f"/rest/api/3/project/{config['PROJECT_KEY']}", config)
    if resp is None:
        print("Failed to validate project: Network error")
        return False
    if resp.status_code == 200:
        project_data = resp.json()
        print(f"Project validated: {project_data.get('name', 'Unknown')}")
        return True
    else:
        print(f"Project validation failed: {resp.status_code} - {resp.text}")
        return False

def create_adf_description(text: str) -> Dict[str, Any]:
    """Create Atlassian Document Format description"""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": text
                    }
                ]
            }
        ]
    }

def find_epic_link_field(config: Dict[str, Any]) -> Optional[str]:
    """Find the Epic Link custom field"""
    print("Discovering Epic Link field...")
    resp = jira_get("/rest/api/3/field", config)
    if resp is None:
        return None
    if resp.status_code != 200:
        print("Warning: failed to list fields:", resp.status_code, resp.text)
        return None
    fields = resp.json()
    for f in fields:
        name = f.get("name", "").lower()
        if "epic" in name and "link" in name:
            print("Found epic link field:", f["id"])
            return f["id"]
        if f.get("name", "").lower() in ("epic name", "epic-name"):
            print("Found epic name field:", f["id"])
            return f["id"]
    print("Epic Link field not found automatically.")
    return None

def create_issue(config: Dict[str, Any], fields: Dict[str, Any]) -> Optional[str]:
    """Create a JIRA issue"""
    payload = {"fields": fields}
    if config.get("DRY_RUN"):
        print("[DRY RUN] create_issue payload:", json.dumps(payload, indent=2, default=str))
        return f"DRY-{int(time.time())%10000}"
    
    resp = jira_post("/rest/api/3/issue", config, payload)
    if resp is None:
        print("No response from create_issue (network error).")
        return None
    if resp.status_code in (200, 201):
        key = resp.json().get("key")
        print("Created:", key)
        return key
    else:
        print("Failed to create issue:", resp.status_code, resp.text)
        return None

def get_transitions(issue_key: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get available transitions for an issue"""
    resp = jira_get(f"/rest/api/3/issue/{issue_key}/transitions", config)
    if resp is None:
        return []
    if resp.status_code != 200:
        print(f"Failed to fetch transitions for {issue_key}:", resp.status_code, resp.text)
        return []
    return resp.json().get("transitions", [])

def find_transition_by_name(transitions: List[Dict[str, Any]], target_names: List[str]) -> Optional[str]:
    """Find a transition by name"""
    for t in transitions:
        name = t.get("name", "").lower()
        for target in target_names:
            if target.lower() in name:
                return t.get("id")
    return None

def find_done_transition(transitions: List[Dict[str, Any]], config: Dict[str, Any]) -> Optional[str]:
    """Find a transition that represents 'done'"""
    keywords = config.get("DONE_TRANSITION_KEYWORDS", [])
    for t in transitions:
        name = t.get("name", "").lower()
        for kw in keywords:
            if kw in name:
                return t.get("id")
    # fallback: if any transition has status category 'done' -> use it
    for t in transitions:
        to = t.get("to", {})
        if to.get("statusCategory") and to["statusCategory"].get("key") == "done":
            return t.get("id")
    return None

def transition_issue(issue_key: str, transition_id: str, config: Dict[str, Any]) -> bool:
    """Transition an issue to a new status"""
    payload = {"transition": {"id": transition_id}}
    if config.get("DRY_RUN"):
        print(f"[DRY RUN] Transition {issue_key} -> transition id {transition_id}")
        return True
    resp = jira_post(f"/rest/api/3/issue/{issue_key}/transitions", config, payload)
    if resp is None:
        return False
    if resp.status_code in (200, 204):
        print(f"Transitioned {issue_key} using id {transition_id}")
        return True
    else:
        print(f"Failed to transition {issue_key}:", resp.status_code, resp.text)
        return False

def main():
    """Main function"""
    cfg = CONFIG
    if not cfg["JIRA_BASE_URL"] or not cfg["PROJECT_KEY"]:
        print("Set JIRA_BASE_URL and JIRA_PROJECT_KEY")
        sys.exit(1)

    # Validate project first
    if not validate_project(cfg):
        print("Project validation failed. Please check your project key and permissions.")
        sys.exit(1)

    epic_field = find_epic_link_field(cfg)

    today = datetime.now().date()  # Fixed deprecation warning
    past_date = (today - timedelta(days=30)).isoformat()
    future_date = (today + timedelta(days=30)).isoformat()

    created = {
        "epics": [],
        "features": [],
        "tasks": [],
        "subtasks": [],
        "bugs": [],
        "future": [],
        "todo": [],
        "in_progress": [],
        "in_qa": []
    }

    # 1) Create epics
    epics = [
        {
            "summary": cfg.get("DEPLOYMENT_EPIC_SUMMARY"), 
            "description": "Comprehensive infrastructure setup for our e-commerce platform including AWS ECS container orchestration, RDS database management, Redis caching layer, Application Load Balancer configuration, API Gateway setup, and GitHub Actions CI/CD pipeline. This epic covers the foundational infrastructure needed to support our microservices architecture."
        },
        {
            "summary": "Platform: Performance & Monitoring", 
            "description": "Implement comprehensive monitoring, logging, and performance optimization across all services. Includes CloudWatch dashboards, custom metrics, alerting systems, log aggregation, performance profiling, and capacity planning to ensure optimal system performance and reliability."
        },
        {
            "summary": "User Experience Enhancement", 
            "description": "Improve user interface, user journey optimization, accessibility features, mobile responsiveness, and overall user experience across all customer touchpoints including web, mobile, and API interactions."
        },
        {
            "summary": "Security & Compliance", 
            "description": "Implement security best practices, compliance requirements, data protection measures, authentication enhancements, authorization improvements, and security monitoring to ensure platform security and regulatory compliance."
        }
    ]
    for e in epics:
        fields = {
            "project": {"key": cfg["PROJECT_KEY"]},
            "summary": e["summary"],
            "description": create_adf_description(e["description"]),
            "issuetype": {"name": "Epic"},
        }
        # If epic-name field exists, try to set
        if epic_field:
            fields[epic_field] = e["summary"][:50]
        key = create_issue(cfg, fields)
        if key:
            created["epics"].append({"key": key, "summary": e["summary"]})
        time.sleep(0.25)

    # 2) Features in different states
    # Completed features (Done)
    completed_features = [
        {
            "summary": "Catalog Service - Product browsing & search",
            "description": f"Implemented comprehensive product catalog service with advanced search capabilities, filtering, categorization, and product recommendations. Features include Elasticsearch integration, faceted search, product image management, and inventory tracking. Completed on {past_date}."
        },
        {
            "summary": "User Service - Authentication & profiles", 
            "description": f"Built user management service with JWT authentication, OAuth2 integration, user profiles, role-based access control, and account management features. Includes password reset, email verification, and social login capabilities. Completed on {past_date}."
        }
    ]
    
    # Features in progress
    in_progress_features = [
        {
            "summary": "Coupon Service - Discounts & promotions",
            "description": "Developing comprehensive discount and promotion management system. Includes percentage and fixed amount discounts, BOGO offers, seasonal promotions, bulk discount tiers, and coupon code generation. Currently implementing the promotion engine and validation logic."
        },
        {
            "summary": "Order Service - Order lifecycle management",
            "description": "Building order management system with order creation, status tracking, inventory reservation, order modification capabilities, and integration with payment and shipping services. Currently working on order state machine and notification system."
        }
    ]
    
    # Features in QA
    qa_features = [
        {
            "summary": "Payment Service - Payment processing & integration",
            "description": "Payment processing service with multiple gateway support (Stripe, PayPal, Square), PCI compliance, fraud detection, refund processing, and subscription billing. Currently in QA testing phase with focus on edge cases and error handling."
        }
    ]
    
    # Process completed features
    for f in completed_features:
        fields = {
            "project": {"key": cfg["PROJECT_KEY"]},
            "summary": f["summary"],
            "description": create_adf_description(f["description"]),
            "issuetype": {"name": "Story"},
        }
        if epic_field and created["epics"]:
            fields[epic_field] = created["epics"][0]["key"]
        key = create_issue(cfg, fields)
        if key:
            created["features"].append(key)
            transitions = get_transitions(key, cfg)
            tid = find_done_transition(transitions, cfg)
            if tid:
                transition_issue(key, tid, cfg)
        time.sleep(0.2)
    
    # Process in-progress features
    for f in in_progress_features:
        fields = {
            "project": {"key": cfg["PROJECT_KEY"]},
            "summary": f["summary"],
            "description": create_adf_description(f["description"]),
            "issuetype": {"name": "Story"},
        }
        if epic_field and created["epics"]:
            fields[epic_field] = created["epics"][0]["key"]
        key = create_issue(cfg, fields)
        if key:
            created["in_progress"].append(key)
            transitions = get_transitions(key, cfg)
            tid = find_transition_by_name(transitions, ["in progress", "in-progress", "progress"])
            if tid:
                transition_issue(key, tid, cfg)
        time.sleep(0.2)
    
    # Process QA features
    for f in qa_features:
        fields = {
            "project": {"key": cfg["PROJECT_KEY"]},
            "summary": f["summary"],
            "description": create_adf_description(f["description"]),
            "issuetype": {"name": "Story"},
        }
        if epic_field and created["epics"]:
            fields[epic_field] = created["epics"][0]["key"]
        key = create_issue(cfg, fields)
        if key:
            created["in_qa"].append(key)
            transitions = get_transitions(key, cfg)
            tid = find_transition_by_name(transitions, ["qa", "testing", "test", "review"])
            if tid:
                transition_issue(key, tid, cfg)
        time.sleep(0.2)

    # 3) Tasks in different states
    # Completed tasks
    completed_tasks = [
        {
            "summary": "Prepare Terraform for VPC and ECS",
            "description": f"Created comprehensive Infrastructure as Code using Terraform for AWS VPC setup, ECS cluster configuration, security groups, and networking components. Includes multi-AZ deployment, private/public subnet configuration, and ECS service definitions. Completed on {past_date}."
        }
    ]
    
    # Tasks in progress
    in_progress_tasks = [
        {
            "summary": "RDS Schema migration scripts",
            "description": "Developing database migration scripts and baseline schema for all microservices. Includes version control for schema changes, rollback procedures, data migration tools, and automated deployment scripts. Currently working on catalog service schema."
        },
        {
            "summary": "Implement CI/CD Pipeline",
            "description": "Building comprehensive CI/CD pipeline using GitHub Actions. Includes automated testing, code quality checks, security scanning, Docker image building, and deployment automation to staging and production environments."
        }
    ]
    
    # Tasks in QA
    qa_tasks = [
        {
            "summary": "Performance Testing Setup",
            "description": "Setting up comprehensive performance testing framework using JMeter and K6. Includes load testing scenarios, stress testing, capacity planning, and performance monitoring integration. Currently in QA review phase."
        }
    ]
    
    # Process completed tasks
    for t in completed_tasks:
        fields = {
            "project": {"key": cfg["PROJECT_KEY"]},
            "summary": t["summary"],
            "description": create_adf_description(t["description"]),
            "issuetype": {"name": "Task"},
        }
        if epic_field and created["epics"]:
            fields[epic_field] = created["epics"][0]["key"]
        key = create_issue(cfg, fields)
        if key:
            created["tasks"].append(key)
            transitions = get_transitions(key, cfg)
            tid = find_done_transition(transitions, cfg)
            if tid:
                transition_issue(key, tid, cfg)
        time.sleep(0.2)
    
    # Process in-progress tasks
    for t in in_progress_tasks:
        fields = {
            "project": {"key": cfg["PROJECT_KEY"]},
            "summary": t["summary"],
            "description": create_adf_description(t["description"]),
            "issuetype": {"name": "Task"},
        }
        if epic_field and created["epics"]:
            fields[epic_field] = created["epics"][0]["key"]
        key = create_issue(cfg, fields)
        if key:
            created["in_progress"].append(key)
            transitions = get_transitions(key, cfg)
            tid = find_transition_by_name(transitions, ["in progress", "in-progress", "progress"])
            if tid:
                transition_issue(key, tid, cfg)
        time.sleep(0.2)
    
    # Process QA tasks
    for t in qa_tasks:
        fields = {
            "project": {"key": cfg["PROJECT_KEY"]},
            "summary": t["summary"],
            "description": create_adf_description(t["description"]),
            "issuetype": {"name": "Task"},
        }
        if epic_field and created["epics"]:
            fields[epic_field] = created["epics"][1]["key"]  # Link to monitoring epic
        key = create_issue(cfg, fields)
        if key:
            created["in_qa"].append(key)
            transitions = get_transitions(key, cfg)
            tid = find_transition_by_name(transitions, ["qa", "testing", "test", "review"])
            if tid:
                transition_issue(key, tid, cfg)
        time.sleep(0.2)

    # 4) Create elaborate subtasks for different parent tasks
    # Get the first in-progress task as parent for deployment subtasks
    parent_task = created["in_progress"][0] if created["in_progress"] else None
    if cfg.get("USE_SUBTASKS") and parent_task:
        deployment_subtasks = [
            {
                "summary": "Define subnets & CIDR blocks",
                "description": "Design and implement VPC subnet architecture with proper CIDR allocation for public/private subnets across multiple availability zones. Includes subnet tagging, route table configuration, and IP address planning."
            },
            {
                "summary": "Create security groups and NACLs",
                "description": "Configure security groups for ECS services, RDS instances, Redis clusters, and ALB. Implement Network ACLs for additional security layer and define ingress/egress rules following least privilege principle."
            },
            {
                "summary": "Setup ECS cluster and services",
                "description": "Create ECS cluster with EC2 launch type, configure auto-scaling groups, service discovery, and task definitions. Includes container registry setup and service mesh configuration."
            },
            {
                "summary": "Configure Application Load Balancer",
                "description": "Setup ALB with target groups, health checks, SSL certificates, and routing rules. Configure listener rules for different services and implement sticky sessions where needed."
            },
            {
                "summary": "Setup RDS and Redis infrastructure",
                "description": "Create RDS instances with read replicas, Redis cluster configuration, backup strategies, and monitoring setup. Includes parameter group tuning and security configuration."
            }
        ]
        
        for s in deployment_subtasks:
            fields = {
                "project": {"key": cfg["PROJECT_KEY"]},
                "summary": s["summary"],
                "description": create_adf_description(s["description"]),
                "issuetype": {"name": "Sub-task"},
                "parent": {"key": parent_task},
            }
            key = create_issue(cfg, fields)
            if key:
                created["subtasks"].append(key)
                # Keep deployment subtasks in TODO
            time.sleep(0.2)
    
    # Create subtasks for CI/CD task (if exists)
    cicd_task = created["in_progress"][1] if len(created["in_progress"]) > 1 else None
    if cicd_task:
        cicd_subtasks = [
            {
                "summary": "Setup GitHub Actions workflows",
                "description": "Create GitHub Actions workflows for automated testing, building, and deployment. Includes matrix builds for multiple environments, artifact management, and notification integration."
            },
            {
                "summary": "Implement automated testing pipeline",
                "description": "Configure automated unit tests, integration tests, and end-to-end tests. Includes test coverage reporting, test result analysis, and quality gates for deployment."
            },
            {
                "summary": "Setup Docker image building and registry",
                "description": "Configure Docker image building with multi-stage builds, security scanning, and automated pushing to ECR. Includes image tagging strategies and cleanup policies."
            },
            {
                "summary": "Configure deployment automation",
                "description": "Implement automated deployment to staging and production environments. Includes blue-green deployments, rollback procedures, and deployment validation."
            }
        ]
        
        for s in cicd_subtasks:
            fields = {
                "project": {"key": cfg["PROJECT_KEY"]},
                "summary": s["summary"],
                "description": create_adf_description(s["description"]),
                "issuetype": {"name": "Sub-task"},
                "parent": {"key": cicd_task},
            }
            key = create_issue(cfg, fields)
            if key:
                created["subtasks"].append(key)
                # Transition some CI/CD subtasks to In Progress
                transitions = get_transitions(key, cfg)
                tid = find_transition_by_name(transitions, ["in progress", "in-progress", "progress"])
                if tid:
                    transition_issue(key, tid, cfg)
            time.sleep(0.2)

    # 5) Bugs in different states
    completed_bugs = [
        {
            "summary": "Payment gateway timeout under load",
            "description": f"Fixed timeout issues in payment gateway integration during high load scenarios. Implemented connection pooling, retry logic with exponential backoff, and circuit breaker pattern. Root cause was insufficient connection pool size and missing timeout configurations. Resolved on {past_date}."
        },
        {
            "summary": "Duplicate order on retry",
            "description": f"Resolved duplicate order creation issue caused by retry logic. Implemented idempotency keys, order state validation, and proper transaction handling. Added order deduplication logic and improved error handling. Fixed on {past_date}."
        }
    ]
    
    qa_bugs = [
        {
            "summary": "Memory leak in catalog service",
            "description": "Identified memory leak in product search functionality. Suspected cause is improper handling of Elasticsearch connections and query result caching. Currently in QA testing phase to verify fix effectiveness and performance impact."
        }
    ]
    
    # Process completed bugs
    for b in completed_bugs:
        fields = {
            "project": {"key": cfg["PROJECT_KEY"]},
            "summary": b["summary"],
            "description": create_adf_description(b["description"]),
            "issuetype": {"name": "Bug"},
        }
        if epic_field and created["epics"]:
            fields[epic_field] = created["epics"][1]["key"]  # link to monitoring epic
        key = create_issue(cfg, fields)
        if key:
            created["bugs"].append(key)
            transitions = get_transitions(key, cfg)
            tid = find_done_transition(transitions, cfg)
            if tid:
                transition_issue(key, tid, cfg)
        time.sleep(0.2)
    
    # Process QA bugs
    for b in qa_bugs:
        fields = {
            "project": {"key": cfg["PROJECT_KEY"]},
            "summary": b["summary"],
            "description": create_adf_description(b["description"]),
            "issuetype": {"name": "Bug"},
        }
        if epic_field and created["epics"]:
            fields[epic_field] = created["epics"][1]["key"]  # link to monitoring epic
        key = create_issue(cfg, fields)
        if key:
            created["in_qa"].append(key)
            transitions = get_transitions(key, cfg)
            tid = find_transition_by_name(transitions, ["qa", "testing", "test", "review"])
            if tid:
                transition_issue(key, tid, cfg)
        time.sleep(0.2)

    # 6) Future stories and TODO items
    future_stories = [
        {
            "summary": "Multi-region deployment",
            "description": "Implement multi-region deployment strategy for disaster recovery and improved global performance. Includes cross-region data replication, failover mechanisms, and traffic routing optimization."
        },
        {
            "summary": "Advanced analytics dashboard",
            "description": "Develop comprehensive analytics dashboard with real-time metrics, business intelligence reports, customer behavior analysis, and predictive analytics using machine learning models."
        }
    ]
    
    todo_items = [
        {
            "summary": "Implement API rate limiting",
            "description": "Add comprehensive API rate limiting and throttling mechanisms to prevent abuse and ensure fair usage. Includes per-user limits, burst handling, and integration with Redis for distributed rate limiting."
        },
        {
            "summary": "Setup automated security scanning",
            "description": "Implement automated security scanning in CI/CD pipeline including SAST, DAST, dependency vulnerability scanning, and container image security analysis. Integrate with security tools and reporting."
        },
        {
            "summary": "Implement feature flags system",
            "description": "Build feature flag management system for controlled feature rollouts, A/B testing, and emergency feature toggles. Includes dashboard for flag management and analytics integration."
        },
        {
            "summary": "Setup disaster recovery procedures",
            "description": "Create comprehensive disaster recovery procedures including backup strategies, recovery time objectives, failover procedures, and regular DR testing protocols."
        }
    ]
    
    # Process future stories (mark as done)
    for f in future_stories:
        fields = {
            "project": {"key": cfg["PROJECT_KEY"]},
            "summary": f["summary"],
            "description": create_adf_description(f["description"]),
            "issuetype": {"name": "Story"},
        }
        if epic_field and created["epics"]:
            fields[epic_field] = created["epics"][2]["key"]  # link to UX epic
        key = create_issue(cfg, fields)
        if key:
            created["future"].append(key)
            transitions = get_transitions(key, cfg)
            tid = find_done_transition(transitions, cfg)
            if tid:
                transition_issue(key, tid, cfg)
        time.sleep(0.2)
    
    # Process TODO items (keep in TODO)
    for t in todo_items:
        fields = {
            "project": {"key": cfg["PROJECT_KEY"]},
            "summary": t["summary"],
            "description": create_adf_description(t["description"]),
            "issuetype": {"name": "Story"},
        }
        if epic_field and created["epics"]:
            fields[epic_field] = created["epics"][3]["key"]  # link to security epic
        key = create_issue(cfg, fields)
        if key:
            created["todo"].append(key)
            # Keep in TODO - no transition
        time.sleep(0.2)

    # Save results
    print("\n--- Summary of created issues ---")
    print(json.dumps(created, indent=2))
    
    with open(cfg["OUTPUT_FILE"], "w") as f:
        json.dump(created, f, indent=2)
    print(f"Saved created keys to {cfg['OUTPUT_FILE']}")

    print("\nNotes:")
    print(f"- Created {len(created['epics'])} epics with comprehensive descriptions")
    print(f"- Features: {len(created['features'])} completed, {len(created['in_progress'])} in progress, {len(created['in_qa'])} in QA")
    print(f"- Tasks: {len(created['tasks'])} completed, {len(created['in_progress'])} in progress, {len(created['in_qa'])} in QA")
    print(f"- Created {len(created['subtasks'])} subtasks with detailed descriptions")
    print(f"- Bugs: {len(created['bugs'])} completed, {len(created['in_qa'])} in QA")
    print(f"- Future stories: {len(created['future'])} completed")
    print(f"- TODO items: {len(created['todo'])} items ready for development")
    print("- Issues distributed across different statuses: Done, In Progress, In QA, and To Do")
    print("- All descriptions use Atlassian Document Format (ADF)")

if __name__ == "__main__":
    main()
