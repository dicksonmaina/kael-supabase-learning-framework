-- Supabase Ingest: Useful Queries
-- Run these in Supabase Dashboard > SQL Editor

-- 1. What patterns have I acted on?
SELECT pattern_name, action_taken, outcome, repetition_count, observed_at
FROM patterns_log
WHERE status = 'acted'
ORDER BY observed_at DESC;

-- 2. Which repos am I most active in?
SELECT r.name, r.language, COUNT(c.id) as commits, 
       MAX(c.committed_at) as last_commit,
       COUNT(f.id) as files_tracked
FROM repositories r
LEFT JOIN repo_commits c ON r.id = c.repo_id
LEFT JOIN repo_files f ON r.id = f.repo_id
GROUP BY r.id, r.name, r.language
ORDER BY commits DESC;

-- 3. What did I learn this week?
SELECT ls.date, ls.source, ls.topic, ls.tags,
       la.action_type, la.description, la.outcome, la.roi_estimate
FROM learning_sessions ls
JOIN learning_actions la ON ls.id = la.session_id
WHERE ls.date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY ls.date DESC, la.created_at DESC;

-- 4. Repo file type distribution
SELECT extension, language, COUNT(*) as count,
       SUM(size_bytes) / 1024.0 / 1024.0 as size_mb
FROM repo_files
WHERE repo_id = '<repo-uuid>'
GROUP BY extension, language
ORDER BY count DESC;

-- 5. Commit activity by author
SELECT author_name, author_email, COUNT(*) as commits,
       MIN(committed_at) as first_commit,
       MAX(committed_at) as last_commit
FROM repo_commits
GROUP BY author_name, author_email
ORDER BY commits DESC;

-- 6. Patterns I'm repeating without acting (antipattern risk)
SELECT pattern_name, pattern_category, context, repetition_count, observed_at
FROM patterns_log
WHERE action_taken = FALSE
  AND repetition_count >= 2
  AND status = 'active'
ORDER BY repetition_count DESC, observed_at DESC;

-- 7. Learning ROI summary
SELECT source, 
       COUNT(*) as sessions,
       COUNT(la.id) as actions,
       SUM(CASE WHEN la.roi_estimate = 'high' THEN 1 ELSE 0 END) as high_roi,
       SUM(CASE WHEN la.roi_estimate = 'medium' THEN 1 ELSE 0 END) as medium_roi,
       SUM(CASE WHEN la.roi_estimate = 'low' THEN 1 ELSE 0 END) as low_roi
FROM learning_sessions ls
LEFT JOIN learning_actions la ON ls.id = la.session_id
GROUP BY source
ORDER BY sessions DESC;

-- 8. Recent commit activity timeline
SELECT DATE(committed_at) as date, COUNT(*) as commits
FROM repo_commits
WHERE committed_at >= NOW() - INTERVAL '30 days'
GROUP BY DATE(committed_at)
ORDER BY date DESC;

-- 9. Repos not synced in last 7 days
SELECT name, language, last_synced_at, sync_status
FROM repositories
WHERE last_synced_at < NOW() - INTERVAL '7 days'
   OR last_synced_at IS NULL
ORDER BY last_synced_at ASC NULLS FIRST;

-- 10. Pattern categories breakdown
SELECT pattern_category, 
       COUNT(*) as total,
       SUM(CASE WHEN action_taken THEN 1 ELSE 0 END) as acted,
       SUM(CASE WHEN NOT action_taken THEN 1 ELSE 0 END) as not_acted
FROM patterns_log
GROUP BY pattern_category
ORDER BY total DESC;
