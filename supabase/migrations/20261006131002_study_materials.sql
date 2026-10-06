-- Extend schema for Downloads study corpus

-- Study materials table
CREATE TABLE IF NOT EXISTS study_materials (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    filename TEXT NOT NULL,
    file_type TEXT,
    size_bytes BIGINT DEFAULT 0,
    subject TEXT,
    title TEXT,
    extracted_text TEXT,
    source_path TEXT,
    corpus_path TEXT,
    indexed BOOLEAN DEFAULT FALSE,
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(filename, source_path)
);

CREATE INDEX IF NOT EXISTS idx_study_materials_subject ON study_materials(subject);
CREATE INDEX IF NOT EXISTS idx_study_materials_file_type ON study_materials(file_type);
CREATE INDEX IF NOT EXISTS idx_study_materials_indexed ON study_materials(indexed) WHERE indexed = FALSE;

-- Enable RLS
ALTER TABLE study_materials ENABLE ROW LEVEL SECURITY;

-- Service role full access
CREATE POLICY "Service role full access" ON study_materials FOR ALL USING (auth.role() = 'service_role');

-- Anon read access
CREATE POLICY "Anon can read study_materials" ON study_materials FOR SELECT USING (auth.role() = 'anon');
