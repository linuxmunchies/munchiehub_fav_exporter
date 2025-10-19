#!/usr/bin/env python3
import requests
import subprocess
import os
import sys
from urllib.parse import urlparse

# Configuration
FORGEJO_URL = 'http://10.1.1.5:9870'
FORGEJO_USER = 'gitfox'
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')  # Set this env var for private repos
FORGEJO_TOKEN = os.getenv('FORGEJO_TOKEN')  # Required for API access

if not FORGEJO_TOKEN:
    print("Error: FORGEJO_TOKEN environment variable is required.")
    sys.exit(1)

headers = {
    'Authorization': f'token {FORGEJO_TOKEN}',
    'Content-Type': 'application/json'
}

def create_repo(repo_name, description=''):
    url = f"{FORGEJO_URL}/api/v1/user/repos"
    data = {
        'name': repo_name,
        'description': description,
        'private': False,  # Adjust as needed
        'auto_init': False
    }
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 201:
        return response.json()['clone_url']
    else:
        print(f"Failed to create repo {repo_name}: {response.text}")
        return None

def migrate_repo(full_name, description=''):
    owner, repo = full_name.split('/')
    clone_url = f"https://github.com/{owner}/{repo}.git"
    if GITHUB_TOKEN:
        clone_url = f"https://x-access-token:{GITHUB_TOKEN}@github.com/{owner}/{repo}.git"

    # Create repo in Forgejo
    forgejo_clone_url = create_repo(repo, description)
    if not forgejo_clone_url:
        return False

    # Mirror clone from GitHub
    temp_dir = f"temp_mirror_{repo}"
    try:
        subprocess.run(['git', 'clone', '--mirror', clone_url, temp_dir], check=True)
        os.chdir(temp_dir)

        # Add Forgejo remote
        subprocess.run(['git', 'remote', 'add', 'forgejo', forgejo_clone_url], check=True)

        # Push mirror
        subprocess.run(['git', 'push', '--mirror', 'forgejo'], check=True)

        print(f"Successfully migrated {full_name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error migrating {full_name}: {e}")
        return False
    finally:
        os.chdir('..')
        if os.path.exists(temp_dir):
            subprocess.run(['rm', '-rf', temp_dir])

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 migrate_repos.py <list_file>")
        print("List file: one GitHub repo per line, format owner/repo")
        sys.exit(1)

    with open(sys.argv[1], 'r') as f:
        repos = [line.strip() for line in f if line.strip()]

    for repo in repos:
        migrate_repo(repo)