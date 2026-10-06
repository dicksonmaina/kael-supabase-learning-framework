# Supabase Ingest — Repo Sync + Learning Memory Pipeline

> Goal: turn your local work into queryable memory. Every commit, every learning moment, every pattern — structured, searchable, and connected.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     YOUR WORKSPACE                          │
│  Repos (~50) · Notes · CTF writeups · Study materials      │
└──────────────────────┬──────────────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          │    INGEST PIPELINE      │
          │                         │
          │  ┌─────────────────┐   │
          │  │  repo_sync.py   │   │  Discovers repos, reads commits/files
          │  └────────┬────────┘   │  Writes to Supabase
          │           │            │
          │  ┌────────┴────────┐   │
          │  │ learning_ingest │   │  Captures learning from notes/routine
          │  └────────┬────────┘   │
          │           │            │
          │  ┌────────┴────────┐   │
          │  │  pipeline.py    │   │  Orchestrates, deduplicates, logs
          │  └────────────────┘   │
          └────────────┬────────────┘
                       │
          ┌────────────┴────────────┐
          │     SUPABASE             │
          │  ┌───────────────────┐  │
          │  │ repositories      │  │  Repo metadata
          │  ├───────────────────┤  │
          │  │ repo_commits      │  │  Commit history
          │  ├───────────────────┤  │
          │  │ repo_files        │  │  File index per repo
          │  ├───────────────────┤  │
          │  │ learning_sessions │  │  Daily learning logs
          │  ├───────────────────┤  │
          │  │ learning_actions  │  │  Micro-actions taken
          │  ├───────────────────┤  │
          │  │ patterns_log      │  │  Pattern observations
          │  └───────────────────┘  │
          └────────────────────────┘
```

---

## Tables

### repositories
One row per repo. Metadata only; deep data goes in child tables.

| Column | Type | Purpose |
|--------|------|---------|
| id | uuid | Primary key |
| name | text | Repo name |
| full_name | text | e.g., `riziki/poultry-farm-system` |
| local_path | text | Absolute path on disk |
| description | text | From repo metadata |
| language | text | Primary language |
| last_synced_at | timestamptz | Last successful sync |
| sync_status | text | `active`, `archived`, `error` |
| created_at | timestamptz | When first discovered |

### repo_commits
Every commit from every synced repo.

| Column | Type | Purpose |
|--------|------|---------|
| id | bigint | Auto-increment primary key |
| repo_id | uuid | FK → repositories |
| sha | text | Full commit hash |
| short_sha | text | 7-char short hash |
| message | text | Commit message |
| author_name | text | Commit author |
| author_email | text | Author email |
| committed_at | timestamptz | Commit timestamp |
| files_changed | integer | Number of files in commit |
| insertions | integer | Lines added |
| deletions | integer | Lines deleted |
| summary | text | AI-generated or rule-based summary |
| created_at | timestamptz | When ingested |

### repo_files
File tree index per repo. Updated on each sync.

| Column | Type | Purpose |
|--------|------|---------|
| id | bigint | Auto-increment primary key |
| repo_id | uuid | FK → repositories |
| path | text | File path relative to repo root |
| filename | text | Basename |
| extension | text | File extension |
| size_bytes | bigint | File size |
| language | text | Detected language |
| last_modified_at | timestamptz | From filesystem |
| content_hash | text | SHA256 of content (for change detection) |
| indexed | boolean | Whether content was ingested into search |
| created_at | timestamptz | First seen |
| updated_at | timestamptz | Last changed |

### learning_sessions
Daily/weekly learning logs.

| Column | Type | Purpose |
|--------|------|---------|
| id | uuid | Primary key |
| date | date | Session date |
| source | text | `wealth-routine`, `code-fluency`, `ctf`, `study`, `manual` |
| topic | text | What was studied |
| duration_minutes | integer | Optional |
| notes | text | Free-form notes |
| tags | text[] | Categorization tags |
| created_at | timestamptz | Record timestamp |

### learning_actions
Micro-actions taken based on learning.

| Column | Type | Purpose |
|--------|------|---------|
| id | uuid | Primary key |
| session_id | uuid | FK → learning_sessions |
| action_type | text | `build`, `fix`, `write`, `share`, `review`, `deploy` |
| description | text | What was done |
| outcome | text | Result or observation |
| pattern_applied | text | Which pattern triggered this |
| roi_estimate | text | `high`, `medium`, `low`, `unknown` |
| created_at | timestamptz | Action timestamp |

### patterns_log
Pattern recognition observations.

| Column | Type | Purpose |
|--------|------|---------|
| id | uuid | Primary key |
| pattern_name | text | e.g., `Pattern F`, `Input Validation` |
| pattern_category | text | `money-mechanics`, `code`, `security`, `linux`, `agent` |
| observed_at | date | When noticed |
| context | text | Where it showed up |
| action_taken | boolean | Did you act on it? |
| action_description | text | If acted |
| outcome | text | Result |
| repetition_count | integer | How many times seen |
| status | text | `active`, `acted`, `antipattern`, `retired` |
| created_at | timestamptz | First logged |

---

## Setup

### 1. Apply Database Migrations

```bash
# From workspace root
bash supabase-ingest/scripts/setup-db.sh
```

This creates all tables, indexes, and RLS policies.

### 2. Configure Environment

```bash
# .env.supabase already exists in workspace root
# For standalone use:
cp supabase-ingest/.env.example supabase-ingest/.env
# Edit with your Supabase credentials
```

### 3. Sync Repos

```bash
# Full sync of all discovered repos
python3 supabase-ingest/scripts/repo_sync.py --full

# Sync only changed repos (faster)
python3 supabase-ingest/scripts/repo_sync.py --incremental

# Sync a single repo
python3 supabase-ingest/scripts/repo_sync.py --repo /home/riziki/OpenClaw
```

### 4. Record Learning

```bash
# From wealth-routine or code-fluency completion
python3 supabase-ingest/scripts/learning_ingest.py \
  --source wealth-routine \
  --topic "Pattern F: Skills to Product" \
  --action "Built SokoHub debugging checklist" \
  --outcome "Reusable artifact created, can share with team" \
  --pattern "Pattern F" \
  --roi high
```

### 5. Run Full Pipeline

```bash
# Orchestrates repo sync + learning ingest + deduplication
python3 supabase-ingest/scripts/pipeline.py --mode full
```

---

## Scheduled Pipeline

Recommended cron schedule:

```
# Repo sync: every 6 hours
0 */6 * * * python3 /home/riziki/.openclaw/workspace-hermesrizikibot/supabase-ingest/scripts/pipeline.py --mode repos

# Learning ingest: after each study session
# Triggered by wealth-routine / code-fluency / master-pipeline completions
```

---

## Querying Your Memory

```sql
-- What patterns have I acted on?
SELECT pattern_name, action_taken, outcome, repetition_count
FROM patterns_log
WHERE status = 'acted'
ORDER BY observed_at DESC;

-- Which repos am I most active in?
SELECT r.name, COUNT(c.id) as commits, MAX(c.committed_at) as last_commit
FROM repositories r
LEFT JOIN repo_commits c ON r.id = c.repo_id
GROUP BY r.id, r.name
ORDER BY commits DESC;

-- What did I learn this week?
SELECT date, topic, source, roi_estimate
FROM learning_sessions ls
JOIN learning_actions la ON ls.id = la.session_id
WHERE date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY date DESC;

-- Repo file type distribution
SELECT extension, COUNT(*) as count
FROM repo_files
WHERE repo_id = '<repo-uuid>'
GROUP BY extension
ORDER BY count DESC;
```

---

## Anti-Patterns

1. **Sync without dedup:** Always check `content_hash` before writing. Duplicate files bloat storage.
2. **Sync while writing:** Use filesystem mtime, not size, to detect changes. Size can lag.
3. **Ingest without context:** Every learning entry needs a source and date. Undated learning is noise.
4. **Over-sync:** Full sync every hour wastes API calls. Incremental is default for a reason.

---

## Integration with Existing Skills

- **wealth-patterns:** After completing daily routine, call `learning_ingest.py` with `--source wealth-routine`
- **code-fluency:** After each module, log the concept learned and any micro-action taken
- **master-pipeline:** Each chunk delivery can log to `learning_sessions` automatically

---

## Files

```
supabase-ingest/
├── SKILL.md               # This file
├── .env.example           # Environment template
├── scripts/
│   ├── setup-db.sh        # Apply migrations
│   ├── repo_sync.py       # Repo discovery + sync
│   ├── learning_ingest.py # Learning capture
│   └── pipeline.py        # Orchestrator
├── migrations/
│   └── 001_initial.sql    # Table definitions
└── queries/
    └── useful_queries.sql # Pre-built queries
```

---

*This skill turns your local activity into a queryable knowledge graph. The goal is not to collect data—it’s to be able to ask: “What patterns am I actually acting on? Which repos drive my learning? Where is my time going?”*
