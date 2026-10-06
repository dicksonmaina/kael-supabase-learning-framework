#!/usr/bin/env python3
"""
pipeline.py — Orchestrate repo sync + learning ingest into Supabase.

Usage:
  python3 pipeline.py --mode full         # Full sync: repos + learning
  python3 pipeline.py --mode repos        # Repo sync only
  python3 pipeline.py --mode learning     # Learning ingest only
"""

import argparse
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
    """Load Supabase credentials"""
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


def get_supabase_client(env):
    """Create Supabase REST API client"""
    return {
        'url': env['SUPABASE_URL'].rstrip('/'),
        'headers': {
            'apikey': env['SUPABASE_SERVICE_ROLE_KEY'],
            'Authorization': f"Bearer {env['SUPABASE_SERVICE_ROLE_KEY']}",
            'Content-Type': 'application/json'
        }
    }


def log_pipeline_run(client, mode, status, items_processed=0, error=''):
    """Log pipeline execution to chunk_deliveries table"""
    data = {
        'track': f'pipeline-{mode}',
        'chunk_index': 0,
        'title': f'Pipeline run: {mode}',
        'status': status,
        'delivered_at': datetime.now(timezone.utc).isoformat()
    }
    
    response = requests.post(
        f"{client['url']}/rest/v1/chunk_deliveries",
        headers=client['headers'],
        json=data
    )
    return response.status_code in [200, 201]


def run_repo_sync(mode='incremental'):
    """Run repo sync script"""
    script_path = Path(__file__).parent / 'repo_sync.py'
    cmd = [sys.executable, str(script_path)]
    if mode == 'full':
        cmd.append('--full')
    else:
        cmd.append('--incremental')
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0, result.stdout, result.stderr


def run_learning_ingest():
    """Run learning ingest (placeholder for actual ingestion logic)"""
    # This would be called by other skills after learning sessions
    # For now, it's a no-op placeholder
    return True, "Learning ingest ready", ""


def main():
    parser = argparse.ArgumentParser(description='Supabase ingest pipeline')
    parser.add_argument('--mode', choices=['full', 'repos', 'learning'], 
                       default='full', help='Pipeline mode')
    parser.add_argument('--repo-mode', choices=['full', 'incremental'],
                       default='incremental', help='Repo sync mode')
    args = parser.parse_args()
    
    try:
        env = load_env()
        client = get_supabase_client(env)
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)
    
    print(f"Starting pipeline: {args.mode}")
    start_time = datetime.now()
    
    success = True
    items_processed = 0
    error_msg = ""
    
    try:
        if args.mode in ['full', 'repos']:
            print("\n[1/2] Syncing repositories...")
            repo_success, stdout, stderr = run_repo_sync(args.repo_mode)
            print(stdout)
            if stderr:
                print(stderr, file=sys.stderr)
            if not repo_success:
                success = False
                error_msg = f"Repo sync failed: {stderr}"
        
        if args.mode in ['full', 'learning']:
            print("\n[2/2] Processing learning data...")
            learn_success, stdout, stderr = run_learning_ingest()
            print(stdout)
            if not learn_success:
                success = False
                error_msg = f"Learning ingest failed: {stderr}"
    
    except Exception as e:
        success = False
        error_msg = str(e)
    
    # Log pipeline run
    status = 'success' if success else 'failed'
    log_pipeline_run(client, args.mode, status, items_processed, error_msg)
    
    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"\nPipeline complete: {status} ({elapsed:.1f}s)")
    
    if not success:
        print(f"Error: {error_msg}")
        sys.exit(1)


if __name__ == '__main__':
    main()
