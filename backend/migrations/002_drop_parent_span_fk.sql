-- =============================================================
-- 002_drop_parent_span_fk.sql
-- Drop the parent_span_id foreign key.
--
-- Why: spans arrive over HTTP and can land before their parents
-- (children finish first, async ordering, retries). A strict FK
-- causes false rejections. We treat parent_span_id as a soft link
-- and let the dashboard handle missing parents gracefully.
-- =============================================================

ALTER TABLE spans DROP CONSTRAINT spans_parent_span_id_fkey;