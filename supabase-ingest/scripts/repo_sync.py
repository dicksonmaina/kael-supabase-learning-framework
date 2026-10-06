#!/usr/bin/env python3
"""
repo_sync.py — Discover, hash, and sync git repositories into Supabase.

Usage:
  python3 repo_sync.py --full              # Full sync of all discovered repos
  python3 repo_sync.py --incremental       # Only sync changed repos
  python3 repo_sync.py --repo /path/to/repo # Sync a single repo
"""

import argparse
import hashlib
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)


def load_env():
    """Load Supabase credentials from .env.supabase"""
    env_path = Path(__file__).resolve().parent.parent.parent / ".env.supabase"
    if not env_path.exists():
        # Try workspace root
        env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env.supabase"
    
    if not env_path.exists():
        raise FileNotFoundError(f".env.supabase not found at {env_path}")
    
    env = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env[key.strip()] = value.strip()
    return env


def get_supabase_client(env):
    """Create Supabase REST API client"""
    return {
        'url': env['SUPABASE_URL'].rstrip('/'),
        'headers': {
            'apikey': env['SUPABASE_SERVICE_ROLE_KEY'],
            'Authorization': f"Bearer {env['SUPABASE_SERVICE_ROLE_KEY']}",
            'Content-Type': 'application/json',
            'Prefer': 'return=representation'
        }
    }


def discover_repos(base_dirs):
    """Find all git repositories in given directories"""
    repos = []
    for base_dir in base_dirs:
        base_path = Path(base_dir)
        if not base_path.exists():
            continue
        for item in base_path.iterdir():
            if item.is_dir() and (item / '.git').exists():
                repos.append(str(item.resolve()))
    return sorted(repos)


def get_repo_info(repo_path):
    """Extract metadata from a git repository"""
    try:
        # Get remote URL
        remote_url = subprocess.check_output(
            ['git', '-C', repo_path, 'remote', 'get-url', 'origin'],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
        
        # Get current branch
        branch = subprocess.check_output(
            ['git', '-C', repo_path, 'branch', '--show-current'],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
        
        # Get description
        try:
            description = subprocess.check_output(
                ['git', '-C', repo_path, 'config', '--get', 'remote.origin.url'],
                stderr=subprocess.DEVNULL, text=True
            ).strip()
        except:
            description = ""
        
        # Get language from file extensions
        language = detect_language(repo_path)
        
        return {
            'remote_url': remote_url,
            'branch': branch,
            'description': description,
            'language': language
        }
    except subprocess.CalledProcessError:
        return None


def detect_language(repo_path):
    """Detect primary language from file extensions"""
    ext_counts = {}
    for root, dirs, files in os.walk(repo_path):
        # Skip .git directory
        dirs[:] = [d for d in dirs if d != '.git']
        for file in files:
            ext = Path(file).suffix.lower()
            if ext:
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
    
    if not ext_counts:
        return "unknown"
    
    # Map extensions to languages
    lang_map = {
        '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript',
        '.go': 'Go', '.rs': 'Rust', '.java': 'Java', '.cpp': 'C++',
        '.c': 'C', '.rb': 'Ruby', '.php': 'PHP', '.swift': 'Swift',
        '.kt': 'Kotlin', '.scala': 'Scala', '.sql': 'SQL',
        '.html': 'HTML', '.css': 'CSS', '.json': 'JSON',
        '.yaml': 'YAML', '.yml': 'YAML', '.md': 'Markdown'
    }
    
    lang_counts = {}
    for ext, count in ext_counts.items():
        lang = lang_map.get(ext, ext)
        lang_counts[lang] = lang_counts.get(lang, 0) + count
    
    return max(lang_counts, key=lang_counts.get) if lang_counts else "unknown"


def get_file_hash(filepath):
    """SHA256 hash of file contents"""
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def get_recent_commits(repo_path, limit=50):
    """Get recent commits from git log"""
    try:
        output = subprocess.check_output(
            ['git', '-C', repo_path, 'log', f'--max-count={limit}', 
             '--format=%H|%h|%s|%an|%ae|%ai|%b'],
            stderr=subprocess.DEVNULL, text=True
        )
        commits = []
        for line in output.strip().split('\n'):
            if not line:
                continue
            parts = line.split('|', 6)
            if len(parts) >= 6:
                commits.append({
                    'sha': parts[0],
                    'short_sha': parts[1],
                    'message': parts[2],
                    'author_name': parts[3],
                    'author_email': parts[4],
                    'committed_at': parts[5].strip(),
                    'summary': parts[6] if len(parts) > 6 else ''
                })
        return commits
    except subprocess.CalledProcessError:
        return []


def get_recent_files(repo_path, limit=100):
    """Get recently modified files"""
    files = []
    for root, dirs, filenames in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d != '.git']
        for filename in filenames:
            filepath = Path(root) / filename
            rel_path = filepath.relative_to(repo_path)
            try:
                stat = filepath.stat()
                files.append({
                    'path': str(rel_path),
                    'filename': filename,
                    'extension': filepath.suffix.lower(),
                    'size_bytes': stat.st_size,
                    'last_modified_at': datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat()
                })
            except OSError:
                continue
    return sorted(files, key=lambda x: x['last_modified_at'], reverse=True)[:limit]


def upsert_repo(client, repo_path, repo_info):
    """Upsert repository metadata"""
    name = Path(repo_path).name
    full_name = repo_info['remote_url'].replace('.git', '').split('/')[-1] if repo_info else name
    
    data = {
        'name': name,
        'full_name': full_name,
        'local_path': repo_path,
        'description': repo_info.get('description', '') if repo_info else '',
        'language': repo_info.get('language', 'unknown') if repo_info else 'unknown',
        'last_synced_at': datetime.now(timezone.utc).isoformat(),
        'sync_status': 'active'
    }
    
    response = requests.post(
        f"{client['url']}/rest/v1/repositories",
        headers=client['headers'],
        json=data
    )
    
    if response.status_code in [200, 201]:
        result = response.json()
        if isinstance(result, list) and result:
            return result[0]['id']
        elif isinstance(result, dict):
            return result.get('id')
    
    # Try to get existing repo
    response = requests.get(
        f"{client['url']}/rest/v1/repositories?local_path=eq.{repo_path}",
        headers=client['headers']
    )
    if response.status_code == 200:
        data = response.json()
        if data:
            # Update last_synced_at
            repo_id = data[0]['id']
            requests.patch(
                f"{client['url']}/rest/v1/repositories?id=eq.{repo_id}",
                headers=client['headers'],
                json={'last_synced_at': datetime.now(timezone.utc).isoformat()}
            )
            return repo_id
    
    return None


def sync_commits(client, repo_id, repo_path):
    """Sync recent commits for a repo"""
    commits = get_recent_commits(repo_path)
    if not commits:
        return 0
    
    synced = 0
    for commit in commits:
        data = {
            'repo_id': repo_id,
            'sha': commit['sha'],
            'short_sha': commit['short_sha'],
            'message': commit['message'],
            'author_name': commit['author_name'],
            'author_email': commit['author_email'],
            'committed_at': commit['committed_at'],
            'summary': commit['summary']
        }
        
        response = requests.post(
            f"{client['url']}/rest/v1/repo_commits",
            headers=client['headers'],
            json=data
        )
        if response.status_code in [200, 201]:
            synced += 1
    
    return synced


def sync_files(client, repo_id, repo_path):
    """Sync recent files for a repo"""
    files = get_recent_files(repo_path)
    if not files:
        return 0
    
    synced = 0
    for file_info in files:
        data = {
            'repo_id': repo_id,
            **file_info
        }
        
        response = requests.post(
            f"{client['url']}/rest/v1/repo_files",
            headers=client['headers'],
            json=data
        )
        if response.status_code in [200, 201]:
            synced += 1
    
    return synced


def sync_repo(client, repo_path, full=False):
    """Sync a single repository"""
    print(f"Syncing: {repo_path}")
    repo_info = get_repo_info(repo_path)
    if not repo_info:
        print(f"  Skipping (not a valid git repo)")
        return 0
    
    repo_id = upsert_repo(client, repo_path, repo_info)
    if not repo_id:
        print(f"  Failed to upsert repo")
        return 0
    
    commits_synced = sync_commits(client, repo_id, repo_path)
    files_synced = sync_files(client, repo_id, repo_path)
    
    print(f"  ✓ {commits_synced} commits, {files_synced} files synced")
    return commits_synced + files_synced


def main():
    parser = argparse.ArgumentParser(description='Sync git repos to Supabase')
    parser.add_argument('--full', action='store_true', help='Full sync of all repos')
    parser.add_argument('--incremental', action='store_true', help='Incremental sync')
    parser.add_argument('--repo', type=str, help='Sync single repo by path')
    parser.add_argument('--base-dir', type=str, nargs='+', 
                       default=['/home/riziki'],
                       help='Base directories to search for repos')
    args = parser.parse_args()
    
    try:
        env = load_env()
        client = get_supabase_client(env)
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)
    
    if args.repo:
        # Sync single repo
        sync_repo(client, args.repo, full=args.full)
    else:
        # Discover and sync all repos
        repos = discover_repos(args.base_dir)
        print(f"Discovered {len(repos)} repositories")
        
        total_synced = 0
        for repo_path in repos:
            try:
                count = sync_repo(client, repo_path, full=args.full)
                total_synced += count
            except Exception as e:
                print(f"  Error: {e}")
        
        print(f"\nTotal synced: {total_synced} items across {len(repos)} repos")


if __name__ == '__main__':
    main()
