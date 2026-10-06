---
name: downloads-books-passive-learning
description: |
  Passive learning skill built from the user's Downloads study corpus.
  Supports random review, search, and lightweight flashcard review from local files.
  Use when the user wants to study from their Downloads books/notes or run passive
  review sessions across health sciences, data science, algorithms, nursing, parasitology,
  anatomy, public health, and related coursework.
version: 0.1.0
---

# Downloads Books Passive Learning

## Purpose
Turn the local Downloads corpus into low-friction passive study sessions:
- quick reviews of random topics
- on-demand search across unified notes
- lightweight flashcard review
- rerunnable ingestion from `study-materials/downloads-books/corpus/`

## Source Material
- Local corpus at `study-materials/downloads-books/corpus/`
- Compressed archive at `Downloads/compressed/`

## Core Capabilities
1. `ingest` — rebuild unified notes from corpus files
2. `review` — pick a random chunk or topic from the corpus
3. `search` — grep-style search in unified notes
4. `cards` — show or export flashcards from `flashcards.jsonl`
5. `stats` — corpus stats and source count

## Dependencies
- Python standard library
- Optional: `pdftotext` for PDF extraction
- Optional: `python-docx` for DOCX extraction

## Corpus Files
- `study-materials/downloads-books/build/unified.md`
- `study-materials/downloads-books/build/manifest.json`
- `study-materials/downloads-books/build/sources.json`

## Usage
```bash
# Run from workspace root
python3 skills/downloads-books-passive-learning/scripts/downloads_passive.py stats
python3 skills/downloads-books-passive-learning/scripts/downloads_passive.py review
python3 skills/downloads-books-passive-learning/scripts/downloads_passive.py search "topic"
python3 skills/downloads-books-passive-learning/scripts/downloads_passive.py cards --count 10
python3 skills/downloads-books-passive-learning/scripts/downloads_passive.py ingest
```

## Ingestion Behavior
- Scans `study-materials/downloads-books/corpus/` for supported files
- Extracts text from PDF, DOCX, PPTX, TXT, MD
- Writes `build/unified.md`, `build/manifest.json`, `build/sources.json`
- Skips missing optional dependencies gracefully

## Notes
- This skill is optimized for local, offline use.
- For large-context study, prefer chunked review over loading the full unified.md.
- Source files are personal study materials; keep them local and backed up.
