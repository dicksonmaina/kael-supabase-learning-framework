-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Repositories table
CREATE TABLE IF NOT EXISTS repositories (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    name TEXT NOT NULL,
    full_name TEXT UNIQUE,
    local_path TEXT NOT NULL,
    description TEXT,
    language TEXT,
    last_synced_at TIMESTAMPTZ,
    sync_status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_repositories_full_name ON repositories(full_name);
CREATE INDEX idx_repositories_sync_status ON repositories(sync_status);

-- Repo commits table
CREATE TABLE IF NOT EXISTS repo_commits (
    id BIGSERIAL PRIMARY KEY,
    repo_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    sha TEXT NOT NULL,
    short_sha TEXT,
    message TEXT NOT NULL,
    author_name TEXT,
    author_email TEXT,
    committed_at TIMESTAMPTZ NOT NULL,
    files_changed INTEGER DEFAULT 0,
    insertions INTEGER DEFAULT 0,
    deletions INTEGER DEFAULT 0,
    summary TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(repo_id, sha)
);

CREATE INDEX idx_repo_commits_repo_id ON repo_commits(repo_id);
CREATE INDEX idx_repo_commits_committed_at ON repo_commits(committed_at DESC);
CREATE INDEX idx_repo_commits_author ON repo_commits(author_name);

-- Repo files table
CREATE TABLE IF NOT EXISTS repo_files (
    id BIGSERIAL PRIMARY KEY,
    repo_id UUID NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    filename TEXT NOT NULL,
    extension TEXT,
    size_bytes BIGINT DEFAULT 0,
    language TEXT,
    last_modified_at TIMESTAMPTZ,
    content_hash TEXT,
    indexed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(repo_id, path)
);

CREATE INDEX idx_repo_files_repo_id ON repo_files(repo_id);
CREATE INDEX idx_repo_files_extension ON repo_files(extension);
CREATE INDEX idx_repo_files_indexed ON repo_files(indexed) WHERE indexed = FALSE;

-- Learning sessions table
CREATE TABLE IF NOT EXISTS learning_sessions (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    source TEXT NOT NULL,
    topic TEXT NOT NULL,
    duration_minutes INTEGER,
    notes TEXT,
    tags TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_learning_sessions_date ON learning_sessions(date DESC);
CREATE INDEX idx_learning_sessions_source ON learning_sessions(source);
CREATE INDEX idx_learning_sessions_tags ON learning_sessions USING GIN(tags);

-- Learning actions table
CREATE TABLE IF NOT EXISTS learning_actions (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES learning_sessions(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,
    description TEXT NOT NULL,
    outcome TEXT,
    pattern_applied TEXT,
    roi_estimate TEXT DEFAULT 'unknown',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_learning_actions_session_id ON learning_actions(session_id);
CREATE INDEX idx_learning_actions_roi ON learning_actions(roi_estimate);

-- Patterns log table
CREATE TABLE IF NOT EXISTS patterns_log (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    pattern_name TEXT NOT NULL,
    pattern_category TEXT NOT NULL,
    observed_at DATE NOT NULL DEFAULT CURRENT_DATE,
    context TEXT,
    action_taken BOOLEAN DEFAULT FALSE,
    action_description TEXT,
    outcome TEXT,
    repetition_count INTEGER DEFAULT 1,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_patterns_log_category ON patterns_log(pattern_category);
CREATE INDEX idx_patterns_log_status ON patterns_log(status);
CREATE INDEX idx_patterns_log_observed_at ON patterns_log(observed_at DESC);

-- Row Level Security (RLS) policies
ALTER TABLE repositories ENABLE ROW LEVEL SECURITY;
ALTER TABLE repo_commits ENABLE ROW LEVEL SECURITY;
ALTER TABLE repo_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE learning_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE learning_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE patterns_log ENABLE ROW LEVEL SECURITY;

-- Allow service role full access
CREATE POLICY "Service role full access" ON repositories FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON repo_commits FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON repo_files FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON learning_sessions FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON learning_actions FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Service role full access" ON patterns_log FOR ALL USING (auth.role() = 'service_role');

-- Allow anon read access for public data (optional, adjust as needed)
CREATE POLICY "Anon can read repositories" ON repositories FOR SELECT USING (auth.role() = 'anon');
CREATE POLICY "Anon can read commits" ON repo_commits FOR SELECT USING (auth.role() = 'anon');
CREATE POLICY "Anon can read files" ON repo_files FOR SELECT USING (auth.role() = 'anon');
CREATE POLICY "Anon can read learning" ON learning_sessions FOR SELECT USING (auth.role() = 'anon');
CREATE POLICY "Anon can read patterns" ON patterns_log FOR SELECT USING (auth.role() = 'anon');
