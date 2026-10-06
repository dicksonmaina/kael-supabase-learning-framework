#!/usr/bin/env python3
"""
learning_ingest.py — Capture learning sessions, actions, and pattern observations into Supabase.

Usage:
  python3 learning_ingest.py --source wealth-routine --topic "Pattern F" --action "Built checklist" --outcome "Reusable artifact"
"""

import argparse
import sys
from datetime import date, datetime, timezone
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


def create_learning_session(client, source, topic, duration_minutes=None, notes='', tags=None):
    """Create a learning session"""
    data = {
        'date': date.today().isoformat(),
        'source': source,
        'topic': topic,
        'duration_minutes': duration_minutes,
        'notes': notes,
        'tags': tags or []
    }
    
    response = requests.post(
        f"{client['url']}/rest/v1/learning_sessions",
        headers=client['headers'],
        json=data
    )
    
    if response.status_code in [200, 201]:
        result = response.json()
        if isinstance(result, list) and result:
            return result[0]['id']
        elif isinstance(result, dict):
            return result.get('id')
    return None


def create_learning_action(client, session_id, action_type, description, outcome='', 
                          pattern_applied='', roi_estimate='unknown'):
    """Create a learning action linked to a session"""
    if not session_id:
        return None
    
    data = {
        'session_id': session_id,
        'action_type': action_type,
        'description': description,
        'outcome': outcome,
        'pattern_applied': pattern_applied,
        'roi_estimate': roi_estimate
    }
    
    response = requests.post(
        f"{client['url']}/rest/v1/learning_actions",
        headers=client['headers'],
        json=data
    )
    
    if response.status_code in [200, 201]:
        result = response.json()
        if isinstance(result, list) and result:
            return result[0]['id']
        elif isinstance(result, dict):
            return result.get('id')
    return None


def log_pattern(client, pattern_name, pattern_category, context='', action_taken=False,
                action_description='', outcome='', repetition_count=1, status='active'):
    """Log a pattern observation"""
    data = {
        'pattern_name': pattern_name,
        'pattern_category': pattern_category,
        'observed_at': date.today().isoformat(),
        'context': context,
        'action_taken': action_taken,
        'action_description': action_description,
        'outcome': outcome,
        'repetition_count': repetition_count,
        'status': status
    }
    
    response = requests.post(
        f"{client['url']}/rest/v1/patterns_log",
        headers=client['headers'],
        json=data
    )
    
    if response.status_code in [200, 201]:
        result = response.json()
        if isinstance(result, list) and result:
            return result[0]['id']
        elif isinstance(result, dict):
            return result.get('id')
    return None


def main():
    parser = argparse.ArgumentParser(description='Ingest learning data into Supabase')
    parser.add_argument('--source', required=True, help='Learning source (e.g., wealth-routine, code-fluency)')
    parser.add_argument('--topic', required=True, help='Topic studied')
    parser.add_argument('--duration', type=int, help='Duration in minutes')
    parser.add_argument('--notes', default='', help='Free-form notes')
    parser.add_argument('--tags', nargs='+', help='Tags')
    parser.add_argument('--action-type', help='Action type: build, fix, write, share, review, deploy')
    parser.add_argument('--action', help='Action description')
    parser.add_argument('--outcome', default='', help='Action outcome')
    parser.add_argument('--pattern', help='Pattern applied')
    parser.add_argument('--roi', default='unknown', choices=['high', 'medium', 'low', 'unknown'])
    parser.add_argument('--pattern-name', help='Pattern name for pattern logging')
    parser.add_argument('--pattern-category', help='Pattern category: money-mechanics, code, security, linux, agent')
    parser.add_argument('--context', help='Context where pattern was observed')
    parser.add_argument('--action-taken', action='store_true', help='Whether action was taken on pattern')
    args = parser.parse_args()
    
    try:
        env = load_env()
        client = get_supabase_client(env)
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)
    
    # Create learning session
    session_id = create_learning_session(
        client, args.source, args.topic,
        duration_minutes=args.duration,
        notes=args.notes,
        tags=args.tags
    )
    
    if session_id:
        print(f"✓ Learning session created: {session_id}")
    else:
        print("✗ Failed to create learning session")
    
    # Create learning action if provided
    if args.action and session_id:
        action_id = create_learning_action(
            client, session_id, args.action_type or 'write',
            args.action, outcome=args.outcome,
            pattern_applied=args.pattern, roi_estimate=args.roi
        )
        if action_id:
            print(f"✓ Learning action created: {action_id}")
        else:
            print("✗ Failed to create learning action")
    
    # Log pattern if provided
    if args.pattern_name:
        pattern_id = log_pattern(
            client, args.pattern_name, args.pattern_category or 'code',
            context=args.context, action_taken=args.action_taken,
            action_description=args.action, outcome=args.outcome
        )
        if pattern_id:
            print(f"✓ Pattern logged: {pattern_id}")
        else:
            print("✗ Failed to log pattern")


if __name__ == '__main__':
    main()
