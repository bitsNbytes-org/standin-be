#!/usr/bin/env python3
"""
jira_populate_with_transitions.py
--------------------------------
Populate a Jira project with Epics, past features, tasks, subtasks, bugs, and future plans.
Behavior:
 - Creates two Epics (Infrastructure + Monitoring).
 - Creates past features (Catalog, User, Coupon, Order, Payment) and moves them to DONE if possible.
 - Creates Tasks and Sub-tasks. Sub-tasks under the "Deployment" task remain in TODO.
 - Creates Bugs and moves them to DONE.
 - Creates Future plan stories and moves them to DONE.
 - Leaves the "Deploy services to AWS ECS (prod)" epic (Deployment Epic) and its subtasks in the default state (To Do).
 - Saves created issue keys and responses to `created_issues.json`.

Important:
 - DRY_RUN=True by default (no network calls). Set DRY_RUN=false to actually create issues.
 - The script attempts to discover "Epic Link" custom field and transition ids.
 - To transition an issue to DONE the script looks for transitions whose name matches (case-insensitive)
   one of: done, resolve, resolved, close, closed, complete, completed.
 - You must have sufficient permissions (create issue + transition issues) and API token must have scope.
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
    "JIRA_BEARER_TOKEN": os.getenv("JIRA_BEARER_TOKEN", None),
    "ISSUE_REPORTER": os.getenv("JIRA_EMAIL", "aravindbalan222@gmail.com"),
    "DEFAULT_ASSIGNEE": None,  # accountId if desired
    "DRY_RUN": os.getenv("DRY_RUN", "false").lower() == "true",
    "USE_SUBTASKS": True,
    # Name (summary) of the epic that should be kept in TODO (deployment epic)
    "DEPLOYMENT_EPIC_SUMMARY": "Platform: Infrastructure Setup",
    # Filename to persist created keys
    "OUTPUT_FILE": os.getenv("OUTPUT_FILE", "created_issues.json"),
    # Transition name fuzzy matches that indicate "done"
    "DONE_TRANSITION_KEYWORDS": ["done", "resolve", "resolved", "close", "closed", "complete", "completed"],
}

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# -----------------------------
# Helper functions
# -----------------------------
def build_auth_header(config: Dict[str, Any]) -> Dict[str, str]:
    if config.get("JIRA_BEARER_TOKEN"):
        return {"Authorization": f"Bearer {config['JIRA_BEARER_TOKEN']}"}
    email = config.get("JIRA_EMAIL")
    token = config.get("JIRA_API_TOKEN")
    if not email or not token:
        raise ValueError("Provide JIRA_EMAIL and JIRA_API_TOKEN, or JIRA_BEARER_TOKEN")
    userpass = f"{email}:{token}".encode("utf-8")
    b64 = base64.b64encode(userpass).decode("utf-8")
    return {"Authorization": f"Basic {b64}"}

def jira_request(method: str, path: str, config: Dict[str, Any], payload: Dict[str, Any] = None, params: Dict[str,Any]=None) -> Optional[requests.Response]:
    url = config["JIRA_BASE_URL"].rstrip("/") + path
    headers = {**HEADERS, **build_auth_header(config)}
    if config.get("DRY_RUN"):
        print(f"[DRY RUN] {method} {url}")
        if payload:
            print("[DRY RUN] payload:", json.dumps(payload, indent=2, default=str))
        return None
    try:
        if method.upper() == "GET":
            return requests.get(url, headers=headers, params=params, timeout=30)
        elif method.upper() == "POST":
            return requests.post(url, headers=headers, json=payload, timeout=30)
        elif method.upper() == "PUT":
            return requests.put(url, headers=headers, json=payload, timeout=30)
        else:
            raise ValueError("Unsupported method")
    except Exception as e:
        print("HTTP request error:", e)
        return None

def jira_get(path: str, config: Dict[str,Any], params: Dict[str,Any]=None) -> Optional[requests.Response]:
    return jira_request("GET", path, config, params=params)

def jira_post(path: str, config: Dict[str,Any], payload: Dict[str,Any]) -> Optional[requests.Response]:
    return jira_request("POST", path, config, payload=payload)

# Discover Epic Link field
def find_epic_link_field(config: Dict[str,Any]) -> Optional[str]:
    print("Discovering Epic Link field...")
    resp = jira_get("/rest/api/3/field", config)
    if resp is None:
        return None
    if resp.status_code != 200:
        print("Warning: failed to list fields:", resp.status_code, resp.text)
        return None
    fields = resp.json()
    for f in fields:
        name = f.get("name","").lower()
        if "epic" in name and "link" in name:
            print("Found epic link field:", f["id"])
            return f["id"]
        # "Epic Name" is sometimes used for the epic name field - also return that for epics
        if f.get("name","").lower() in ("epic name", "epic-name"):
            print("Found epic name field:", f["id"])
            return f["id"]
    print("Epic Link field not found automatically.")
    return None

def create_issue(config: Dict[str,Any], fields: Dict[str,Any]) -> Optional[str]:
    payload = {"fields": fields}
    if config.get("DRY_RUN"):
        print("[DRY RUN] create_issue payload:", json.dumps(payload, indent=2, default=str))
        # return a fake key for dry-run to allow linking
        return f"DRY-{int(time.time())%10000}"
    resp = jira_post("/rest/api/3/issue", config, payload)
    if resp is None:
        print("No response from create_issue (network error).")
        return None
    if resp.status_code in (200,201):
        key = resp.json().get("key")
        print("Created:", key)
        return key
    else:
        print("Failed to create issue:", resp.status_code, resp.text)
        return None

def get_transitions(issue_key: str, config: Dict[str,Any]) -> List[Dict[str,Any]]:
    resp = jira_get(f"/rest/api/3/issue/{issue_key}/transitions", config)
    if resp is None:
        return []
    if resp.status_code != 200:
        print(f"Failed to fetch transitions for {issue_key}:", resp.status_code, resp.text)
        return []
    return resp.json().get("transitions", [])

def find_done_transition(transitions: List[Dict[str,Any]], config: Dict[str,Any]) -> Optional[str]:
    keywords = config.get("DONE_TRANSITION_KEYWORDS", [])
    for t in transitions:
        name = t.get("name","").lower()
        for kw in keywords:
            if kw in name:
                return t.get("id")
    # fallback: if any transition has status category 'done' -> use it
    for t in transitions:
        to = t.get("to", {})
        if to.get("statusCategory") and to["statusCategory"].get("key") == "done":
            return t.get("id")
    return None

def transition_issue(issue_key: str, transition_id: str, config: Dict[str,Any]) -> bool:
    payload = {"transition": {"id": transition_id}}
    if config.get("DRY_RUN"):
        print(f"[DRY RUN] Transition {issue_key} -> transition id {transition_id}")
        return True
    resp = jira_post(f"/rest/api/3/issue/{issue_key}/transitions", config, payload)
    if resp is None:
        return False
    if resp.status_code in (200,204):
        print(f"Transitioned {issue_key} using id {transition_id}")
        return True
    else:
        print(f"Failed to transition {issue_key}:", resp.status_code, resp.text)
        return False

# -----------------------------
# Main
# -----------------------------
def main():
    cfg = CONFIG
    if not cfg["JIRA_BASE_URL"] or not cfg["PROJECT_KEY"]:
        print("Set JIRA_BASE_URL and JIRA_PROJECT_KEY")
        sys.exit(1)

    epic_field = find_epic_link_field(cfg)

    today = datetime.utcnow().date()
    past_date = (today - timedelta(days=30)).isoformat()
    future_date = (today + timedelta(days=30)).isoformat()

    created = {
        "epics": [],
        "features": [],
        "tasks": [],
        "subtasks": [],
        "bugs": [],
        "future": []
    }

    # 1) Create epics
    epics = [
        {"summary": cfg.get("DEPLOYMENT_EPIC_SUMMARY"), "description": "Infra for ECS, RDS, Redis, ALB, API Gateway, GitHub Actions."},
        {"summary": "Platform: Performance & Monitoring", "description": "Monitoring, logging and performance tuning."},
    ]
    for e in epics:
        fields = {
            "project": {"key": cfg["PROJECT_KEY"]},
            "summary": e["summary"],
            "description": e["description"],
            "issuetype": {"name": "Epic"},
        }
        # If epic-name field exists (epic_field may also be epic name), try to set
        if epic_field:
            fields[epic_field] = e["summary"][:50]
        key = create_issue(cfg, fields)
        if key:
            created["epics"].append({"key": key, "summary": e["summary"]})
        time.sleep(0.25)

    # 2) Past features (should be marked Done)
    features = [
        "Catalog Service - Product browsing & search",
        "User Service - Authentication & profiles",
        "Coupon Service - Discounts & promotions",
        "Order Service - Order lifecycle management",
        "Payment Service - Payment processing & integration",
    ]
    for f in features:
        fields = {
            "project": {"key": cfg["PROJECT_KEY"]},
            "summary": f,
            "description": f"Completed feature. Marked completed on {past_date}.",
            "issuetype": {"name": "Story"},
        }
        # link to first epic if possible
        if epic_field and created["epics"]:
            fields[epic_field] = created["epics"][0]["key"]
        key = create_issue(cfg, fields)
        if key:
            created["features"].append(key)
            # attempt to transition to done
            transitions = get_transitions(key, cfg)
            tid = find_done_transition(transitions, cfg)
            if tid:
                transition_issue(key, tid, cfg)
            else:
                print(f"No suitable 'done' transition found for {key}; leaving as created.")
        time.sleep(0.2)

    # 3) Tasks
    tasks = [
        {"summary": "Prepare Terraform for VPC and ECS", "desc": "IaC for network and ECS cluster."},
        {"summary": "RDS Schema migration scripts", "desc": "DB migration scripts and baseline schema."},
    ]
    for t in tasks:
        fields = {
            "project": {"key": cfg["PROJECT_KEY"]},
            "summary": t["summary"],
            "description": t["desc"],
            "issuetype": {"name": "Task"},
        }
        if epic_field and created["epics"]:
            fields[epic_field] = created["epics"][0]["key"]
        key = create_issue(cfg, fields)
        if key:
            created["tasks"].append(key)
            # transition task to done (not the deployment task)
            transitions = get_transitions(key, cfg)
            tid = find_done_transition(transitions, cfg)
            if tid:
                transition_issue(key, tid, cfg)
        time.sleep(0.2)

    # 4) Create subtasks under the deployment task only, but leave them in TODO.
    # We'll pick the first created task as the deployment-related parent
    parent_task = created["tasks"][0] if created["tasks"] else None
    if cfg.get("USE_SUBTASKS") and parent_task:
        subtasks = [
            {"summary": "Define subnets & CIDR", "desc": "Define private/public subnets."},
            {"summary": "Create security groups", "desc": "Security groups for ECS, RDS, Redis."},
        ]
        for s in subtasks:
            fields = {
                "project": {"key": cfg["PROJECT_KEY"]},
                "summary": s["summary"],
                "description": s["desc"],
                "issuetype": {"name": "Sub-task"},
                "parent": {"key": parent_task},
            }
            key = create_issue(cfg, fields)
            if key:
                created["subtasks"].append(key)
            # IMPORTANT: do NOT transition these - keep in default (To Do)
            time.sleep(0.2)

    # 5) Bugs -> create and move to done
    bugs = [
        {"summary": "Payment gateway timeout under load", "desc": "Observed timeouts during load tests."},
        {"summary": "Duplicate order on retry", "desc": "Retry logic creates duplicates."},
    ]
    for b in bugs:
        fields = {
            "project": {"key": cfg["PROJECT_KEY"]},
            "summary": b["summary"],
            "description": b["desc"],
            "issuetype": {"name": "Bug"},
            "priority": {"name": "High"},
        }
        if epic_field and created["epics"]:
            # attach to monitoring epic (second epic) to keep deployment epic separate
            if len(created["epics"]) > 1:
                fields[epic_field] = created["epics"][1]["key"]
        key = create_issue(cfg, fields)
        if key:
            created["bugs"].append(key)
            transitions = get_transitions(key, cfg)
            tid = find_done_transition(transitions, cfg)
            if tid:
                transition_issue(key, tid, cfg)
        time.sleep(0.2)

    # 6) Future plans -> create and move to done (these are considered 'past' for your request)
    future_issues = [
        {"summary": "Deploy services to AWS ECS (prod)", "description": "Production rollout to ECS cluster.", "duedate": (today + timedelta(days=10)).isoformat()},
        {"summary": "Setup ALB and API Gateway with WAF", "description": "Secure edge with WAF and route traffic to ECS.", "duedate": (today + timedelta(days=20)).isoformat()},
    ]
    for fp in future_issues:
        fields = {
            "project": {"key": cfg["PROJECT_KEY"]},
            "summary": fp["summary"],
            "description": fp["description"],
            "issuetype": {"name": "Story"},
            "duedate": fp["duedate"]
        }
        if epic_field and created["epics"]:
            fields[epic_field] = created["epics"][0]["key"]
        key = create_issue(cfg, fields)
        if key:
            created["future"].append(key)
            transitions = get_transitions(key, cfg)
            tid = find_done_transition(transitions, cfg)
            if tid:
                transition_issue(key, tid, cfg)
        time.sleep(0.25)

    # 7) Finally, ensure DEPLOYMENT EPIC exists and if found, DO NOT transition it (leave in To Do)
    deployment_epic_summary = cfg.get("DEPLOYMENT_EPIC_SUMMARY")
    deployment_epic_key = None
    for ep in created["epics"]:
        if ep["summary"] == deployment_epic_summary:
            deployment_epic_key = ep["key"]
            break

    print("\n--- Summary of created issues ---")
    print(json.dumps(created, indent=2))
    # Save to file
    try:
        with open(cfg.get("OUTPUT_FILE","created_issues.json"), "w") as fh:
            json.dump({"config": {"DRY_RUN": cfg.get("DRY_RUN")}, "created": created}, fh, indent=2)
        print("Saved created keys to", cfg.get("OUTPUT_FILE"))
    except Exception as e:
        print("Failed to write output file:", e)

    print("\nNotes:")
    print("- Deployment epic (summary) left in default state:", deployment_epic_summary, "key:", deployment_epic_key)
    print("- Subtasks under the first task (deployment subtasks) were left in default state (To Do).")
    print("- All other created issues attempted to be transitioned to Done using fuzzy transition name matching.")
    if cfg.get("DRY_RUN"):
        print("\nDRY_RUN is enabled. No changes were made. Set DRY_RUN=false and provide credentials to run for real.")

if __name__ == "__main__":
    main()
