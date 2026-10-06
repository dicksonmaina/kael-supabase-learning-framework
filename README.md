# Kael Supabase Learning Framework

A reproducible framework for ingesting study materials into Supabase, organizing them into learning programs, and making them queryable via REST or SQL.

## What This Is

- **Supabase schema**: existing tables + optional extensions
- **Ingest pipeline**: extracts text from PDF/DOCX/PPTX and inserts into `learning_sources_pub`
- **Learning programs**: topic-based organization via the `topic` column
- **Passive-learning skill**: local skill for reviewing/searching compressed study materials
- **Full-text search**: uses Postgres `tsvector` via Supabase

## Live Architecture

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `learning_sources_pub` | Master source registry | `path`, `title`, `topic`, `kind`, `license_class`, `content_preview`, `search_vector`, `updated_at` |
| `learning_sessions_pub` | Learning activity / progress | `source_id`, `session_type`, `status`, `created_at` |
| `chunk_deliveries` | Chunked content delivery log | `track`, `chunk_index`, `title`, `delivered_at`, `status` |
| `pipeline_progress` | Ingestion / pipeline state | `track`, `next_chunk`, `last_delivered`, `updated_at` |

## Quick Start

1. Clone this repo
2. Copy `.env.example` to `.env.supabase` and fill in your Supabase URL + service role key
3. Install dependencies: `pip install requests python-docx`
4. Place your study materials in `study-materials/downloads-books/corpus/`
5. Run ingest: `python3 supabase-ingest/scripts/downloads_supabase_ingest.py ingest`

## Learning Programs

Organize materials by setting the `topic` field during ingest. Example topics:

- `Health Promotion`
- `Public Health`
- `Data Science & Programming`
- `Parasitology`
- `Anatomy & Physiology`
- `Computer & Networking`
- `Assignments`
- `AI & Engineering`
- `General`
- `Emergency Management`
- `Digital Literacy`

## Query Examples

```sql
-- List all programs
SELECT DISTINCT topic FROM learning_sources_pub ORDER BY topic;

-- Get all materials for a program
SELECT * FROM learning_sources_pub WHERE topic = 'Health Promotion' ORDER BY title;

-- Full-text search
SELECT * FROM learning_sources_pub WHERE search_vector @@ websearch_to_tsquery('english', 'parasitology');
```

## Updating

Re-run the ingest script to refresh content_preview and metadata:

```bash
python3 supabase-ingest/scripts/downloads_supabase_ingest.py ingest
```

## Files

- `supabase-ingest/scripts/downloads_supabase_ingest.py` — main Downloads ingest
- `supabase-ingest/scripts/learning_ingest.py` — generic learning ingest
- `supabase-ingest/scripts/bulk_ingest_375.sql` — bulk SQL template
- `skills/downloads-books-passive-learning/` — local passive-learning skill
- `study-materials/downloads-books/corpus/sample/` — sample files for reference

## License

MIT
