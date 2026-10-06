#!/usr/bin/env python3
"""
downloads_supabase_ingest.py — Ingest Downloads corpus into existing learning_sources_pub table.

Usage:
  python3 downloads_supabase_ingest.py --ingest
  python3 downloads_supabase_ingest.py --ingest --dry-run
  python3 downloads_supabase_ingest.py --stats
"""

import argparse
import hashlib
import json
import os
import re
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
        raise FileNotFoundError(".env.supabase not found")
    
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


def detect_subject(filename: str) -> str:
    """Rough subject detection from filename"""
    name = filename.lower()
    if any(k in name for k in ['anatomy', 'physiology', 'muscular', 'skeletal', 'cell']):
        return 'Anatomy & Physiology'
    if any(k in name for k in ['parasitology', 'helminth', 'protozoan', 'ectoparasite', 'leishmania', 'giardia', 'entamoeba']):
        return 'Parasitology'
    if any(k in name for k in ['health promotion', 'counseling', 'communication', 'lesson 1', 'lesson 3', 'lessons,6,7,8,9', 'lessson 1', 'supplement']):
        return 'Health Promotion'
    if any(k in name for k in ['data science', 'python', 'machine learning', 'ml ', 'eda', 'data wrangling', 'module2', 'module3', 'module4', 'module5', 'module6', 'module7', 'module8']):
        return 'Data Science & Programming'
    if any(k in name for k in ['computer network', 'ucu 112', 'ucu 104', 'bdu221', 'system analysis']):
        return 'Computer & Networking'
    if any(k in name for k in ['biostatistics', 'pph 102', 'pph 416', 'immunization', 'child health']):
        return 'Public Health'
    if any(k in name for k in ['baswe', 'ai engineering', 'spark']):
        return 'AI & Engineering'
    if any(k in name for k in ['digital literacy']):
        return 'Digital Literacy'
    if any(k in name for k in ['incident']):
        return 'Emergency Management'
    if any(k in name for k in ['assignment']):
        return 'Assignments'
    return 'General'


def detect_kind(suffix: str) -> str:
    """Map file extension to kind"""
    mapping = {
        '.pdf': 'book',
        '.docx': 'note',
        '.doc': 'note',
        '.pptx': 'slides',
        '.ppt': 'slides',
        '.txt': 'note',
        '.md': 'note',
    }
    return mapping.get(suffix.lower(), 'note')


def extract_text(path: Path) -> str:
    """Extract text from study material file"""
    suffix = path.suffix.lower()
    try:
        if suffix == '.pdf':
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tf:
                tf.close()
                res = subprocess.run(
                    ['pdftotext', '-layout', str(path), tf.name],
                    capture_output=True,
                    text=True,
                )
                if res.returncode == 0:
                    text = Path(tf.name).read_text(errors='ignore')
                else:
                    text = ''
                Path(tf.name).unlink(missing_ok=True)
                return text
        elif suffix == '.docx':
            try:
                from docx import Document
            except ImportError:
                return '[docx extraction unavailable: install python-docx]'
            doc = Document(str(path))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        elif suffix == '.pptx':
            try:
                from pptx import Presentation
            except ImportError:
                return '[pptx extraction unavailable: install python-pptx]'
            prs = Presentation(str(path))
            parts = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, 'text') and shape.text.strip():
                        parts.append(shape.text.strip())
            return "\n\n".join(parts)
        else:
            return path.read_text(errors='ignore')
    except Exception as exc:
        return f'[ERROR extracting {path.name}: {exc}]'


def iter_corpus_files(corpus_dir: Path):
    if not corpus_dir.exists():
        return []
    return sorted([p for p in corpus_dir.iterdir() if p.is_file()])


def cmd_stats(args: argparse.Namespace) -> int:
    files = iter_corpus_files(args.corpus)
    print(f"Corpus files: {len(files)}")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    env = load_env()
    client = get_supabase_client(env)
    corpus = args.corpus
    dry_run = args.dry_run
    
    files = iter_corpus_files(corpus)
    if not files:
        print("No corpus files found.")
        return 0
    
    print(f"Ingesting {len(files)} files...")
    inserted = 0
    skipped = 0
    errors = 0
    
    for path in files:
        subject = detect_subject(path.name)
        kind = detect_kind(path.suffix)
        text = extract_text(path)
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
        size_bytes = path.stat().st_size
        
        # Truncate preview to avoid huge rows
        preview = text[:4000] if text else ''
        
        data = {
            'path': str(path),
            'title': path.stem,
            'topic': subject,
            'kind': kind,
            'license_class': 'unknown',
            'content_preview': preview,
        }
        
        if dry_run:
            print(f"DRY RUN: {path.name} -> {subject} ({kind})")
            inserted += 1
            continue
        
        try:
            response = requests.post(
                f"{client['url']}/rest/v1/learning_sources_pub",
                headers=client['headers'],
                json=data
            )
            if response.status_code in [200, 201]:
                inserted += 1
                if inserted % 10 == 0:
                    print(f"  Inserted {inserted}/{len(files)}")
            elif response.status_code == 409:
                skipped += 1
            else:
                errors += 1
                print(f"  Error {response.status_code}: {path.name} - {response.text[:200]}")
        except Exception as exc:
            errors += 1
            print(f"  Exception: {path.name} - {exc}")
    
    print(f"\nIngest complete: {inserted} inserted, {skipped} skipped, {errors} errors")
    return 0 if errors == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Downloads corpus ingest for Supabase')
    parser.add_argument('command', choices=['ingest', 'stats'])
    parser.add_argument('--corpus', type=Path, default=Path('/home/riziki/.openclaw/workspace-hermesrizikibot/study-materials/downloads-books/corpus'))
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing')
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    handlers = {
        'ingest': cmd_ingest,
        'stats': cmd_stats,
    }
    return handlers[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
