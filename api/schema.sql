CREATE TABLE IF NOT EXISTS schema_versions (version integer PRIMARY KEY);
CREATE TABLE IF NOT EXISTS recordings (
    id uuid PRIMARY KEY,
    title text NOT NULL,
    storage_name text NOT NULL UNIQUE,
    sha256 text NOT NULL,
    duration double precision NOT NULL CHECK (duration > 0 AND duration <= 120),
    status text NOT NULL CHECK (status IN ('queued', 'transcribing', 'extracting', 'ready', 'cancelled', 'failed')),
    segments jsonb NOT NULL DEFAULT '[]',
    error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS commitments (
    id uuid PRIMARY KEY,
    recording_id uuid NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
    segment_id integer NOT NULL,
    text text NOT NULL,
    owner text NOT NULL DEFAULT '',
    due_date date,
    kind text NOT NULL CHECK (kind IN ('action', 'question')),
    accepted boolean NOT NULL DEFAULT false,
    version integer NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS recordings_queue ON recordings (created_at) WHERE status = 'queued';
CREATE INDEX IF NOT EXISTS commitments_recording ON commitments (recording_id);
INSERT INTO schema_versions (version) VALUES (1) ON CONFLICT DO NOTHING;

-- Version 2: per-recording opt-in provider and grounded source evidence.
ALTER TABLE recordings ADD COLUMN IF NOT EXISTS provider text NOT NULL DEFAULT 'fixture' CHECK (provider IN ('fixture','gemini'));
ALTER TABLE recordings ADD COLUMN IF NOT EXISTS provenance jsonb NOT NULL DEFAULT '{}';
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS source_quote text NOT NULL DEFAULT '';
ALTER TABLE commitments ADD COLUMN IF NOT EXISTS date_expression text NOT NULL DEFAULT '';
INSERT INTO schema_versions (version) VALUES (2) ON CONFLICT DO NOTHING;
