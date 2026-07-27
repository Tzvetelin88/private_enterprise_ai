-- MCP tool registry and audit log
-- Run after: 001_create_documents_chunks.sql

CREATE TABLE IF NOT EXISTS mcp_tools (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT        NOT NULL UNIQUE,
    description   TEXT,
    server_type   TEXT        NOT NULL,   -- 'local' | 'remote'
    server_url    TEXT,                   -- null for local tools
    input_schema  JSONB       NOT NULL DEFAULT '{}',
    output_schema JSONB       NOT NULL DEFAULT '{}',
    enabled       BOOLEAN     NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mcp_audit_log (
    id          BIGSERIAL   PRIMARY KEY,
    tool_name   TEXT        NOT NULL,
    input       JSONB,
    output      JSONB,
    latency_ms  INT,
    success     BOOLEAN     NOT NULL,
    error       TEXT,
    called_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mcp_audit_log_called_at ON mcp_audit_log (called_at DESC);
CREATE INDEX IF NOT EXISTS idx_mcp_audit_log_tool_name ON mcp_audit_log (tool_name);
