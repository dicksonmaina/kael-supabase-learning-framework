#!/usr/bin/env python3
"""
github_supabase_sync.py — Sync GitHub repos to Supabase and check Vercel deploy readiness.

Usage:
  python3 github_supabase_sync.py --report           # Print report only
  python3 github_supabase_sync.py --sync             # Sync to Supabase
  python3 github_supabase_sync.py --vercel-check     # Check Vercel configs
"""

import argparse
import json
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


def get_github_repos():
    """Get all non-fork repos from GitHub CLI"""
    try:
        output = subprocess.check_output(
            ['gh', 'repo', 'list', 'dicksonmaina', '--limit', '100',
             '--json', 'name,description,primaryLanguage,stargazerCount,forkCount,updatedAt,defaultBranchRef,isFork,url,pushedAt'],
            text=True
        )
        repos = json.loads(output)
        # Filter out forks
        return [r for r in repos if not r.get('isFork', False)]
    except subprocess.CalledProcessError as e:
        print(f"Error fetching GitHub repos: {e}")
        return []


def find_local_path(repo_name):
    """Find local path for a repo"""
    search_dirs = ['/home/riziki']
    for base_dir in search_dirs:
        base_path = Path(base_dir)
        if not base_path.exists():
            continue
        # Check direct match
        direct = base_path / repo_name
        if direct.exists() and (direct / '.git').exists():
            return str(direct.resolve())
        
        # Check subdirectories
        for item in base_path.iterdir():
            if item.is_dir() and item.name == repo_name and (item / '.git').exists():
                return str(item.resolve())
    
    return None


def check_vercel_config(local_path):
    """Check if repo has Vercel/Node.js deploy config"""
    if not local_path:
        return {
            'has_package_json': False,
            'has_vercel_config': False,
            'deploy_ready': False,
            'build_tool': None,
            'local_path': None
        }
    
    path = Path(local_path)
    package_json = path / 'package.json'
    vercel_json = path / 'vercel.json'
    next_config = path / 'next.config.js'
    nuxt_config = path / 'nuxt.config.js'
    vite_config = path / 'vite.config.js'
    
    has_package_json = package_json.exists()
    has_vercel_config = vercel_json.exists()
    
    build_tool = None
    if has_package_json:
        try:
            with open(package_json) as f:
                pkg = json.load(f)
            deps = {**pkg.get('dependencies', {}), **pkg.get('devDependencies', {})}
            if 'next' in deps:
                build_tool = 'Next.js'
            elif 'nuxt' in deps:
                build_tool = 'Nuxt'
            elif 'react' in deps and 'vite' in deps:
                build_tool = 'Vite+React'
            elif 'vite' in deps:
                build_tool = 'Vite'
            elif 'react' in deps:
                build_tool = 'React'
            elif 'express' in deps:
                build_tool = 'Express'
            elif 'fastify' in deps:
                build_tool = 'Fastify'
            elif 'nest' in deps:
                build_tool = 'NestJS'
            elif 'electron' in deps:
                build_tool = 'Electron'
        except:
            pass
    
    deploy_ready = has_package_json or has_vercel_config
    
    return {
        'has_package_json': has_package_json,
        'has_vercel_config': has_vercel_config,
        'deploy_ready': deploy_ready,
        'build_tool': build_tool,
        'local_path': local_path
    }


def get_last_commit_info(local_path):
    """Get last commit info from local git repo"""
    if not local_path:
        return None, None
    
    try:
        sha = subprocess.check_output(
            ['git', '-C', local_path, 'rev-parse', 'HEAD'],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
        
        msg = subprocess.check_output(
            ['git', '-C', local_path, 'log', '-1', '--format=%s'],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
        
        return sha[:7], msg
    except:
        return None, None


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


def check_table_exists(client, table_name):
    """Check if a table exists by trying to query it"""
    response = requests.get(
        f"{client['url']}/rest/v1/{table_name}?limit=0",
        headers=client['headers']
    )
    return response.status_code == 200


def create_repos_table(client):
    """Create the repos table via Supabase REST API if possible"""
    # Note: DDL via REST is not supported in standard Supabase
    # We'll return the SQL for manual execution
    sql = """
CREATE TABLE IF NOT EXISTS repos (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    full_name TEXT,
    description TEXT,
    language TEXT,
    stars INTEGER DEFAULT 0,
    last_commit_sha TEXT,
    last_commit_message TEXT,
    updated_at TIMESTAMPTZ,
    local_path TEXT,
    has_package_json BOOLEAN DEFAULT FALSE,
    has_vercel_config BOOLEAN DEFAULT FALSE,
    deploy_ready BOOLEAN DEFAULT FALSE,
    build_tool TEXT,
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_repos_name ON repos(name);
CREATE INDEX IF NOT EXISTS idx_repos_language ON repos(language);
CREATE INDEX IF NOT EXISTS idx_repos_deploy_ready ON repos(deploy_ready);
"""
    return sql


def upsert_repo(client, repo_data):
    """Insert or update a repo row"""
    data = {
        'name': repo_data['name'],
        'full_name': repo_data['full_name'],
        'description': repo_data['description'],
        'language': repo_data['language'],
        'stars': repo_data['stars'],
        'last_commit_sha': repo_data['last_commit_sha'],
        'last_commit_message': repo_data['last_commit_message'],
        'updated_at': repo_data['updated_at'],
        'local_path': repo_data['local_path'],
        'has_package_json': repo_data['has_package_json'],
        'has_vercel_config': repo_data['has_vercel_config'],
        'deploy_ready': repo_data['deploy_ready'],
        'build_tool': repo_data['build_tool'],
        'synced_at': datetime.now(timezone.utc).isoformat()
    }
    
    # Try upsert using PostgREST
    # First try to update if exists
    response = requests.post(
        f"{client['url']}/rest/v1/repos",
        headers=client['headers'],
        json=data
    )
    
    if response.status_code in [200, 201]:
        return 'inserted'
    
    # If insert fails (maybe exists), try patch
    if response.status_code == 409 or 'duplicate' in response.text.lower():
        response = requests.patch(
            f"{client['url']}/rest/v1/repos?name=eq.{repo_data['name']}",
            headers=client['headers'],
            json=data
        )
        if response.status_code == 204:
            return 'updated'
    
    return f'error: {response.status_code}'


def main():
    parser = argparse.ArgumentParser(description='Sync GitHub repos to Supabase')
    parser.add_argument('--report', action='store_true', help='Print report only')
    parser.add_argument('--sync', action='store_true', help='Sync to Supabase')
    parser.add_argument('--vercel-check', action='store_true', help='Check Vercel configs')
    args = parser.parse_args()
    
    # Get repos
    repos = get_github_repos()
    if not repos:
        print("No repos found or error fetching repos")
        sys.exit(1)
    
    print(f"Found {len(repos)} non-fork repos\n")
    
    # Process each repo
    results = []
    for repo in repos:
        name = repo['name']
        local_path = find_local_path(name)
        vercel_info = check_vercel_config(local_path)
        last_sha, last_msg = get_last_commit_info(local_path)
        
        # Use GitHub's pushedAt as updated_at if no local commit
        updated_at = repo.get('pushedAt', repo.get('updatedAt'))
        
        result = {
            'name': name,
            'full_name': repo.get('url', '').replace('https://github.com/', ''),
            'description': repo.get('description') or '',
            'language': repo.get('primaryLanguage', {}).get('name') if repo.get('primaryLanguage') else None,
            'stars': repo.get('stargazerCount', 0),
            'last_commit_sha': last_sha,
            'last_commit_message': last_msg,
            'updated_at': updated_at,
            'local_path': local_path,
            'has_package_json': vercel_info['has_package_json'],
            'has_vercel_config': vercel_info['has_vercel_config'],
            'deploy_ready': vercel_info['deploy_ready'],
            'build_tool': vercel_info['build_tool']
        }
        results.append(result)
    
    # Print report
    print("=" * 100)
    print(f"{'Repo':<30} {'Lang':<12} {'Stars':<6} {'Local':<6} {'pkg.json':<9} {'Vercel':<8} {'Deploy':<8} {'Supabase':<12}")
    print("=" * 100)
    
    for r in results:
        lang = (r['language'] or 'N/A')[:10]
        local = '✓' if r['local_path'] else '✗'
        pkg = '✓' if r['has_package_json'] else '✗'
        vercel = '✓' if r['has_vercel_config'] else '✗'
        deploy = '✓' if r['deploy_ready'] else '✗'
        print(f"{r['name']:<30} {lang:<12} {r['stars']:<6} {local:<6} {pkg:<9} {vercel:<8} {deploy:<8}")
    
    print("=" * 100)
    print(f"\nTotal repos: {len(results)}")
    print(f"Deploy-ready: {sum(1 for r in results if r['deploy_ready'])}")
    print(f"With local clone: {sum(1 for r in results if r['local_path'])}")
    
    # Show deploy-ready repos
    deploy_ready = [r for r in results if r['deploy_ready']]
    if deploy_ready:
        print(f"\nDeploy-ready repos (have package.json or vercel.json):")
        for r in deploy_ready:
            tool = f" ({r['build_tool']})" if r['build_tool'] else ""
            print(f"  - {r['name']}{tool}")
    
    # Show repos needing config
    not_ready = [r for r in results if not r['deploy_ready'] and r['local_path']]
    if not_ready:
        print(f"\nRepos with local clone but no deploy config:")
        for r in not_ready:
            print(f"  - {r['name']}")
    
    # Save full report
    report_path = Path(__file__).parent / 'github_report.json'
    with open(report_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nFull report saved to: {report_path}")
    
    # Sync to Supabase if requested
    if args.sync:
        print("\n--- Syncing to Supabase ---")
        try:
            env = load_env()
            client = get_supabase_client(env)
        except Exception as e:
            print(f"Error loading Supabase config: {e}")
            print("Please ensure .env.supabase exists with valid credentials")
            sys.exit(1)
        
        # Check if table exists
        if not check_table_exists(client, 'repos'):
            print("Table 'repos' does not exist. Creating...")
            sql = create_repos_table(client)
            print("Please run this SQL in Supabase Dashboard > SQL Editor:")
            print(sql)
            print("\nAfter creating the table, run this script again with --sync")
            sys.exit(1)
        
        # Insert/update repos
        synced = 0
        errors = 0
        for r in results:
            status = upsert_repo(client, r)
            if status == 'inserted':
                print(f"  ✓ Inserted: {r['name']}")
                synced += 1
            elif status == 'updated':
                print(f"  ↻ Updated: {r['name']}")
                synced += 1
            else:
                print(f"  ✗ Error: {r['name']} - {status}")
                errors += 1
        
        print(f"\nSync complete: {synced} synced, {errors} errors")
    
    # Vercel check if requested
    if args.vercel_check:
        print("\n--- Vercel Deploy Check ---")
        deploy_ready = [r for r in results if r['deploy_ready']]
        if deploy_ready:
            print("Repos ready for Vercel deploy:")
            for r in deploy_ready:
                print(f"  - {r['name']}: {r['build_tool'] or 'Generic Node.js'}")
        else:
            print("No repos are deploy-ready. Add package.json or vercel.json to enable Vercel deploys.")


if __name__ == '__main__':
    main()
