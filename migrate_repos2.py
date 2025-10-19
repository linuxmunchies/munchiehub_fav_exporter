#!/usr/bin/env python3
"""
GitHub to Forgejo Migration Script - Lightweight Version
Migrates only code and releases to avoid timeouts.
"""

import os
import sys
import requests
import time
from typing import List, Tuple, Optional

def check_environment() -> Tuple[str, str, Optional[str]]:
    """Check for required environment variables and exit if missing."""
    forgejo_token = os.getenv('FORGEJO_TOKEN')
    
    if not forgejo_token:
        print("Error: FORGEJO_TOKEN environment variable is required", file=sys.stderr)
        sys.exit(1)
    
    forgejo_url = os.getenv('FORGEJO_URL', 'http://localhost:3000')
    github_token = os.getenv('GITHUB_TOKEN')
    
    if not github_token:
        print("Warning: GITHUB_TOKEN not set. You may hit GitHub rate limits.", file=sys.stderr)
        print("Create a token at: https://github.com/settings/tokens/new", file=sys.stderr)
        print()
    
    return forgejo_url, forgejo_token, github_token

def read_repos_from_file(filename: str) -> List[str]:
    """Read repository names from text file."""
    try:
        with open(filename, 'r') as f:
            repos = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        return repos
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

def migrate_repository(forgejo_url: str, forgejo_token: str, github_repo: str,
                       github_token: Optional[str] = None, owner: str = None, 
                       mirror: bool = False) -> bool:
    """
    Migrate a single repository from GitHub to Forgejo (lightweight mode).
    Only migrates code and releases - skips issues, PRs, wiki, etc.
    
    Args:
        forgejo_url: Base URL of Forgejo instance
        forgejo_token: Forgejo API token
        github_repo: GitHub repo in format "owner/repo"
        github_token: GitHub personal access token
        owner: Forgejo owner/organization
        mirror: Whether to create a mirror
    
    Returns:
        True if successful, False otherwise
    """
    api_endpoint = f"{forgejo_url.rstrip('/')}/api/v1/repos/migrate"
    
    # Parse GitHub repo name
    try:
        github_owner, repo_name = github_repo.split('/')
    except ValueError:
        print(f"Error: Invalid repo format '{github_repo}'. Expected 'owner/repo'", file=sys.stderr)
        return False
    
    github_url = f"https://github.com/{github_repo}"
    
    # Lightweight migration payload - only code and releases
    payload = {
        "clone_addr": github_url,
        "repo_name": repo_name,
        "mirror": mirror,
        "private": False,
        "description": f"Migrated from {github_url}",
        "issues": False,           # Skip issues
        "pull_requests": False,     # Skip PRs
        "releases": True,           # Keep releases (small)
        "wiki": False,              # Skip wiki
        "milestones": False,        # Skip milestones
        "labels": False,            # Skip labels
        "service": "github"
    }
    
    # Add GitHub authentication
    if github_token:
        payload["auth_token"] = github_token
        payload["auth_username"] = github_owner
    
    # Add owner if specified
    if owner:
        payload["repo_owner"] = owner
    
    headers = {
        "Authorization": f"token {forgejo_token}",
        "Content-Type": "application/json"
    }
    
    try:
        print(f"Migrating {github_repo}...", end=" ", flush=True)
        response = requests.post(api_endpoint, json=payload, headers=headers, timeout=120)
        
        if response.status_code in (200, 201):
            print("✓ Success")
            return True
        elif response.status_code == 409:
            print("⚠ Already exists")
            return True
        else:
            print(f"✗ Failed (HTTP {response.status_code})")
            try:
                error_data = response.json()
                error_msg = error_data.get('message', 'Unknown error')
                print(f"  Error: {error_msg}", file=sys.stderr)
                
                if "rate limit" in error_msg.lower():
                    print("  Hint: Set GITHUB_TOKEN environment variable", file=sys.stderr)
            except:
                print(f"  Response: {response.text}", file=sys.stderr)
            return False
            
    except requests.exceptions.Timeout:
        print("✗ Timeout", file=sys.stderr)
        return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Network error: {e}", file=sys.stderr)
        return False

def main():
    """Main migration workflow."""
    forgejo_url, forgejo_token, github_token = check_environment()
    
    repos_file = os.getenv('REPOS_FILE', 'repos.txt')
    forgejo_owner = os.getenv('FORGEJO_OWNER', None)
    mirror_mode = os.getenv('MIRROR', 'false').lower() == 'true'
    delay_seconds = int(os.getenv('DELAY_SECONDS', '10'))
    
    print(f"Forgejo Migration Tool (Lightweight Mode)")
    print(f"{'='*60}")
    print(f"Forgejo URL:     {forgejo_url}")
    print(f"Repos file:      {repos_file}")
    print(f"Mirror mode:     {mirror_mode}")
    print(f"Owner:           {forgejo_owner or 'current user'}")
    print(f"GitHub auth:     {'✓' if github_token else '✗'}")
    print(f"Migrating:       Code + Releases only")
    print(f"Skipping:        Issues, PRs, Wiki, Milestones, Labels")
    print(f"Delay:           {delay_seconds}s")
    print(f"{'='*60}\n")
    
    repos = read_repos_from_file(repos_file)
    
    if not repos:
        print("No repositories found in file", file=sys.stderr)
        sys.exit(1)
    
    print(f"Found {len(repos)} repositories to migrate\n")
    
    success_count = 0
    failure_count = 0
    
    for i, repo in enumerate(repos, 1):
        print(f"[{i}/{len(repos)}] ", end="")
        if migrate_repository(forgejo_url, forgejo_token, repo, github_token, forgejo_owner, mirror_mode):
            success_count += 1
        else:
            failure_count += 1
        
        if repo != repos[-1]:
            time.sleep(delay_seconds)
    
    print(f"\n{'='*60}")
    print(f"Migration complete!")
    print(f"Successful:  {success_count}")
    print(f"Failed:      {failure_count}")
    print(f"{'='*60}")
    
    sys.exit(0 if failure_count == 0 else 1)

if __name__ == "__main__":
    main()
