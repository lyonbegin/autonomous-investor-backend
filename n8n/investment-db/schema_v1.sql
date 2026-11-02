-- Investment domain schema v1, separate database from n8n (NO modifications of n8n objects).
-- Matched to 2026-11-03 design draft: 6 schemas, 38 tables.
BEGIN;
CREATE SCHEMA IF NOT EXISTS platform;
CREATE SCHEMA IF NOT EXISTS catalog;
CREATE SCHEMA IF NOT EXISTS market;
CREATE SCHEMA IF NOT EXISTS research;
CREATE SCHEMA IF NOT EXISTS operations;
CREATE SCHEMA IF NOT EXISTS trading;
CREATE TABLE IF NOT EXISTS platform.artifacts(
 artifact_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), sha256 char(64) NOT NULL CHECK(sha256 ~ '^[a-f0-9]{64}$'),
 storage_uri text NOT NULL, media_type text NOT NULL, byte_length bigint NOT NULL CHECK(byte_length>=0),
 source_class text NOT NULL CHECK(source_class IN ('REAL_SOURCE','REAL_TV_EXPORT','REAL_TV_CAPTURE','GENERATED_PYTHON','GENERATED_CHART','MARKET_DATA','MODEL','REPORT','SYNTHETIC_TEST')),
 visibility text NOT NULL DEFAULT 'PRIVATE',created_at timestamptz NOT NULL DEFAULT now(),UNIQUE(sha256,byte_length)
);
CREATE TABLE IF NOT EXISTS platform.legacy_import_batches(
 batch_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),source_system text NOT NULL,source_db text NOT NULL,
 source_backup_ref text NOT NULL,status text NOT NULL DEFAULT 'INVENTORY',
 started_at timestamptz NOT NULL DEFAULT now(),finished_at timestamptz,
 expected_rows bigint,imported_rows bigint,rejected_rows bigint,
 report_artifact_id uuid REFERENCES platform.artifacts(artifact_id)
);
CREATE TABLE IF NOT EXISTS platform.legacy_id_map(
 batch_id uuid NOT NULL REFERENCES platform.legacy_import_batches(batch_id),
 source_table text NOT NULL,source_primary_key text NOT NULL,target_table text,target_primary_key text,
 source_content_sha char(64),status text NOT NULL CHECK(status IN('IMPORTED','ALREADY_EXISTS','CONFLICT','QUARANTINED')),
 error_detail text,PRIMARY KEY(batch_id,source_table,source_primary_key)
);
CREATE TABLE IF NOT EXISTS catalog.scripts(
 script_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),provider text NOT NULL,external_script_key text NOT NULL,
 script_kind text NOT NULL CHECK(script_kind IN('STRATEGY','INDICATOR','LIBRARY')),
 title text,canonical_url text,first_seen_at timestamptz NOT NULL DEFAULT now(),
 last_seen_at timestamptz NOT NULL DEFAULT now(),UNIQUE(provider,external_script_key)
);
CREATE TABLE IF NOT EXISTS catalog.script_versions(
 script_version_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),script_id uuid NOT NULL REFERENCES catalog.scripts(script_id),
 provider_version text,content_sha256 char(64) NOT NULL CHECK(content_sha256 ~ '^[a-f0-9]{64}$'),
 pine_major smallint CHECK(pine_major BETWEEN 4 AND 6),source_artifact_id uuid NOT NULL REFERENCES platform.artifacts(artifact_id),
 rights_state text NOT NULL DEFAULT 'PENDING_REVIEW',source_state text NOT NULL DEFAULT 'ACQUIRED',
 acquired_at timestamptz NOT NULL DEFAULT now(),source_captured_at timestamptz,
 UNIQUE(script_id,content_sha256)
);
CREATE INDEX IF NOT EXISTS idx_script_versions_latest ON catalog.script_versions(script_id,acquired_at DESC);
CREATE TABLE IF NOT EXISTS catalog.script_dependencies(
 dependency_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),from_version_id uuid NOT NULL REFERENCES catalog.script_versions(script_version_id),
 import_name text NOT NULL,required_script_id uuid REFERENCES catalog.scripts(script_id),
 resolved_version_id uuid REFERENCES catalog.script_versions(script_version_id),
 resolution_state text NOT NULL CHECK(resolution_state IN('PENDING','PINNED','MISSING','INCOMPATIBLE')),
 UNIQUE(from_version_id,import_name)
);
CREATE TABLE IF NOT EXISTS catalog.ingest_attempts(
 attempt_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),run_id uuid,provider text NOT NULL,requested_kind text NOT NULL,
 cursor text,started_at timestamptz NOT NULL DEFAULT now(),finished_at timestamptz,
 status text NOT NULL,items_seen integer,items_changed integer,error_code text
);
CREATE TABLE IF NOT EXISTS catalog.source_reviews(
 review_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),script_version_id uuid NOT NULL REFERENCES catalog.script_versions(script_version_id),
 decision text NOT NULL,evidence_artifact_id uuid REFERENCES platform.artifacts(artifact_id),
 decided_by text NOT NULL,decided_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS market.instruments(
 instrument_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),asset_class text NOT NULL,provider text NOT NULL,
 venue text NOT NULL,native_symbol text NOT NULL,contract_key text NOT NULL DEFAULT '',
 currency text,multiplier numeric(24,10),UNIQUE(provider,venue,native_symbol,contract_key)
);
CREATE TABLE IF NOT EXISTS market.dataset_snapshots(
 dataset_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),instrument_id uuid NOT NULL REFERENCES market.instruments(instrument_id),
 provider text NOT NULL,timeframe text NOT NULL,time_start timestamptz NOT NULL,time_end timestamptz NOT NULL,
 session_id text NOT NULL,exchange_timezone text NOT NULL,adjustment_policy text NOT NULL,revision text NOT NULL,
 bars_count bigint NOT NULL DEFAULT 0,artifact_id uuid NOT NULL REFERENCES platform.artifacts(artifact_id),
 content_sha256 char(64) NOT NULL,quality_state text NOT NULL DEFAULT 'PENDING',
 created_at timestamptz NOT NULL DEFAULT now(),CHECK(time_end>time_start),
 UNIQUE(instrument_id,provider,timeframe,time_start,time_end,session_id,adjustment_policy,content_sha256)
);
CREATE INDEX IF NOT EXISTS idx_dataset_lookup ON market.dataset_snapshots(instrument_id,timeframe,time_start,time_end);
CREATE TABLE IF NOT EXISTS market.data_quality_checks(
 check_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),dataset_id uuid NOT NULL REFERENCES market.dataset_snapshots(dataset_id),
 rule_code text NOT NULL,result text NOT NULL,details jsonb NOT NULL DEFAULT '{}'::jsonb,checked_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS research.conversions(
 conversion_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),script_version_id uuid NOT NULL REFERENCES catalog.script_versions(script_version_id),
 dependency_lock_hash char(64) NOT NULL,converter_version text NOT NULL,input_fingerprint char(64) NOT NULL,
 ir_artifact_id uuid REFERENCES platform.artifacts(artifact_id),python_artifact_id uuid REFERENCES platform.artifacts(artifact_id),
 status text NOT NULL CHECK(status IN('QUEUED','RUNNING','GENERATED','UNSUPPORTED','FAILED')),
 diagnostics jsonb NOT NULL DEFAULT '{}'::jsonb,started_at timestamptz NOT NULL DEFAULT now(),finished_at timestamptz,
 UNIQUE(script_version_id,dependency_lock_hash,converter_version,input_fingerprint)
);
CREATE TABLE IF NOT EXISTS research.tv_references(
 reference_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),script_version_id uuid NOT NULL REFERENCES catalog.script_versions(script_version_id),
 instrument_id uuid NOT NULL REFERENCES market.instruments(instrument_id),
 dataset_id uuid NOT NULL REFERENCES market.dataset_snapshots(dataset_id),timeframe text NOT NULL,
 parameters_hash char(64) NOT NULL,chart_settings_hash char(64) NOT NULL,
 tv_csv_artifact_id uuid NOT NULL REFERENCES platform.artifacts(artifact_id),
 tv_screenshot_artifact_id uuid NOT NULL REFERENCES platform.artifacts(artifact_id),
 acquisition_method text NOT NULL,capture_state text NOT NULL,captured_at timestamptz NOT NULL,comment text
);
CREATE INDEX IF NOT EXISTS idx_tv_ref_match ON research.tv_references(script_version_id,instrument_id,timeframe,dataset_id);
CREATE TABLE IF NOT EXISTS research.chart_comparisons(
 comparison_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),conversion_id uuid NOT NULL REFERENCES research.conversions(conversion_id),
 reference_id uuid NOT NULL REFERENCES research.tv_references(reference_id),
 comparison_algorithm_version text NOT NULL,
 status text NOT NULL CHECK(status IN('WAITING_REFERENCE','DATA_MISMATCH','NUMERIC_MISMATCH','NUMERIC_MATCH_REVIEW_REQUIRED','VERIFIED','REJECTED','UNSUPPORTED')),
 numeric_match boolean,signal_match boolean,mismatch_metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
 python_chart_artifact_id uuid REFERENCES platform.artifacts(artifact_id),
 mismatch_report_artifact_id uuid REFERENCES platform.artifacts(artifact_id),
 visual_verdict text NOT NULL DEFAULT 'PENDING',visual_reviewed_by text,visual_reviewed_at timestamptz,
 computed_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(conversion_id,reference_id,comparison_algorithm_version)
);
CREATE TABLE IF NOT EXISTS research.parameter_sets(
 parameter_set_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),param_hash char(64) UNIQUE NOT NULL,
 params jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS research.candidates(
 candidate_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 script_version_id uuid NOT NULL REFERENCES catalog.script_versions(script_version_id),
 conversion_id uuid NOT NULL REFERENCES research.conversions(conversion_id),
 instrument_id uuid NOT NULL REFERENCES market.instruments(instrument_id),
 timeframe text NOT NULL,parameter_set_id uuid NOT NULL REFERENCES research.parameter_sets(parameter_set_id),
 dataset_id uuid NOT NULL REFERENCES market.dataset_snapshots(dataset_id),evaluation_policy_version text NOT NULL,
 candidate_fingerprint char(64) NOT NULL UNIQUE,status text NOT NULL DEFAULT 'CREATED',
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS research.engine_jobs(
 job_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),candidate_id uuid NOT NULL REFERENCES research.candidates(candidate_id),
 engine_key text NOT NULL,operation_id text NOT NULL,engine_version text NOT NULL,
 idempotency_key text NOT NULL UNIQUE,
 state text NOT NULL CHECK(state IN('QUEUED','RUNNING','SUCCEEDED','FAILED','CANCELLED')),
 attempt integer NOT NULL DEFAULT 0,lease_epoch bigint NOT NULL DEFAULT 0,
 started_at timestamptz,ended_at timestamptz,error_code text
);
CREATE TABLE IF NOT EXISTS research.engine_results(
 job_id uuid PRIMARY KEY REFERENCES research.engine_jobs(job_id),
 result_artifact_id uuid REFERENCES platform.artifacts(artifact_id),
 metrics jsonb NOT NULL DEFAULT '{}'::jsonb,sample_type text NOT NULL,finished_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS research.evaluations(
 evaluation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),candidate_id uuid NOT NULL REFERENCES research.candidates(candidate_id),
 evaluation_round integer NOT NULL,policy_version text NOT NULL,out_of_sample boolean NOT NULL DEFAULT false,
 sample_count integer NOT NULL DEFAULT 0,score_json jsonb NOT NULL DEFAULT '{}'::jsonb,
 decision text NOT NULL,evidence_artifact_id uuid REFERENCES platform.artifacts(artifact_id),
 decided_at timestamptz NOT NULL DEFAULT now(),UNIQUE(candidate_id,evaluation_round,policy_version)
);
CREATE TABLE IF NOT EXISTS operations.workflow_bindings(
 binding_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),domain_function text NOT NULL,workflow_name text NOT NULL,
 n8n_workflow_id text NOT NULL,n8n_version text NOT NULL,graph_hash char(64) NOT NULL,
 active boolean NOT NULL DEFAULT false,UNIQUE(domain_function,n8n_workflow_id,n8n_version)
);
CREATE TABLE IF NOT EXISTS operations.pipeline_runs(
 pipeline_run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),requested_by text,status text NOT NULL,
 selected_script_version_id uuid REFERENCES catalog.script_versions(script_version_id),
 correlation_id text NOT NULL UNIQUE,policy_version text NOT NULL,
 initiated_at timestamptz NOT NULL DEFAULT now(),ended_at timestamptz,error_code text
);
CREATE TABLE IF NOT EXISTS operations.stage_runs(
 stage_run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 pipeline_run_id uuid NOT NULL REFERENCES operations.pipeline_runs(pipeline_run_id),
 stage_key text NOT NULL,stage_attempt integer NOT NULL DEFAULT 1,input_fingerprint char(64),
 status text NOT NULL,input_ref jsonb NOT NULL DEFAULT '{}'::jsonb,
 output_ref jsonb NOT NULL DEFAULT '{}'::jsonb,
 started_at timestamptz,finished_at timestamptz,error_code text,
 UNIQUE(pipeline_run_id,stage_key,stage_attempt)
);
CREATE TABLE IF NOT EXISTS operations.node_runs(
 node_run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),stage_run_id uuid NOT NULL REFERENCES operations.stage_runs(stage_run_id),
 workflow_binding_id uuid REFERENCES operations.workflow_bindings(binding_id),
 node_id text NOT NULL,node_name text,worker_job_id uuid,status text NOT NULL,input_ref jsonb,output_ref jsonb,
 duration_ms bigint,error_code text,occurred_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_nodes_stage ON operations.node_runs(stage_run_id,occurred_at);
CREATE TABLE IF NOT EXISTS operations.outbox_events(
 outbox_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),aggregate_type text NOT NULL,aggregate_id text NOT NULL,
 event_type text NOT NULL,payload jsonb NOT NULL,idempotency_key text NOT NULL UNIQUE,
 created_at timestamptz NOT NULL DEFAULT now(),dispatched_at timestamptz
);
CREATE TABLE IF NOT EXISTS operations.inbox_dedup(
 consumer_name text NOT NULL,idempotency_key text NOT NULL,
 consumed_at timestamptz NOT NULL DEFAULT now(),PRIMARY KEY(consumer_name,idempotency_key)
);
CREATE TABLE IF NOT EXISTS operations.audit_events(
 audit_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),correlation_id text NOT NULL,
 entity_type text NOT NULL,entity_id text NOT NULL,event_code text NOT NULL,
 details jsonb NOT NULL DEFAULT '{}'::jsonb,created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS trading.agents(
 agent_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),candidate_id uuid NOT NULL REFERENCES research.candidates(candidate_id),
 strategy_version_id uuid NOT NULL REFERENCES catalog.script_versions(script_version_id),
 agent_key char(64) NOT NULL UNIQUE,state text NOT NULL,created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS trading.agent_assignments(
 assignment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),agent_id uuid NOT NULL REFERENCES trading.agents(agent_id),
 slot_key text NOT NULL,lease_epoch bigint NOT NULL,lease_expires_at timestamptz NOT NULL,
 state text NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),ended_at timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_active_agent ON trading.agent_assignments(agent_id) WHERE state IN('ACTIVE','HALTED');
CREATE UNIQUE INDEX IF NOT EXISTS idx_active_slot ON trading.agent_assignments(slot_key) WHERE state IN('ACTIVE','HALTED');
CREATE TABLE IF NOT EXISTS trading.paper_accounts(
 account_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),account_scope text NOT NULL UNIQUE,
 currency text NOT NULL,state text NOT NULL DEFAULT 'ENABLED',mode text NOT NULL DEFAULT 'PAPER' CHECK(mode='PAPER')
);
CREATE TABLE IF NOT EXISTS trading.paper_sessions(
 session_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),agent_id uuid NOT NULL REFERENCES trading.agents(agent_id),
 account_id uuid NOT NULL REFERENCES trading.paper_accounts(account_id),
 risk_policy_version text NOT NULL,execution_profile_version text NOT NULL,
 state text NOT NULL,started_at timestamptz NOT NULL DEFAULT now(),ended_at timestamptz
);
CREATE TABLE IF NOT EXISTS trading.order_intents(
 order_intent_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),session_id uuid NOT NULL REFERENCES trading.paper_sessions(session_id),
 intent_key text NOT NULL,instrument_id uuid NOT NULL REFERENCES market.instruments(instrument_id),
 side text NOT NULL CHECK(side IN('BUY','SELL')),quantity numeric(30,12) NOT NULL CHECK(quantity>0),
 intent_payload jsonb NOT NULL DEFAULT '{}'::jsonb,created_at timestamptz NOT NULL DEFAULT now(),UNIQUE(session_id,intent_key)
);
CREATE TABLE IF NOT EXISTS trading.risk_decisions(
 risk_decision_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),order_intent_id uuid NOT NULL UNIQUE REFERENCES trading.order_intents(order_intent_id),
 risk_policy_version text NOT NULL,decision text NOT NULL,decision_detail jsonb NOT NULL DEFAULT '{}'::jsonb,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS trading.paper_orders(
 paper_order_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),order_intent_id uuid NOT NULL UNIQUE REFERENCES trading.order_intents(order_intent_id),
 status text NOT NULL,nautilus_order_ref text,created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS trading.paper_fills(
 fill_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),paper_order_id uuid NOT NULL REFERENCES trading.paper_orders(paper_order_id),
 execution_ref text NOT NULL UNIQUE,filled_at timestamptz NOT NULL,
 quantity numeric(30,12) NOT NULL CHECK(quantity>0),price numeric(30,12) NOT NULL CHECK(price>=0),
 fees numeric(30,12) NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS trading.ledger_entries(
 ledger_entry_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),session_id uuid NOT NULL REFERENCES trading.paper_sessions(session_id),
 journal_id uuid NOT NULL,account_code text NOT NULL,currency text NOT NULL,
 signed_amount numeric(38,12) NOT NULL,source_fill_id uuid REFERENCES trading.paper_fills(fill_id),
 occurred_at timestamptz NOT NULL,created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ledger_journal ON trading.ledger_entries(journal_id);
CREATE TABLE IF NOT EXISTS trading.position_snapshots(
 position_snapshot_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),session_id uuid NOT NULL REFERENCES trading.paper_sessions(session_id),
 instrument_id uuid NOT NULL REFERENCES market.instruments(instrument_id),as_of timestamptz NOT NULL,
 quantity numeric(30,12) NOT NULL,avg_price numeric(30,12),
 UNIQUE(session_id,instrument_id,as_of)
);
CREATE TABLE IF NOT EXISTS trading.pnl_snapshots(
 pnl_snapshot_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),session_id uuid NOT NULL REFERENCES trading.paper_sessions(session_id),
 as_of timestamptz NOT NULL,realized_pnl numeric(38,12) NOT NULL,
 unrealized_pnl numeric(38,12) NOT NULL,equity numeric(38,12) NOT NULL,
 UNIQUE(session_id,as_of)
);
CREATE TABLE IF NOT EXISTS trading.agent_review_decisions(
 review_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),agent_id uuid NOT NULL REFERENCES trading.agents(agent_id),
 evaluation_id uuid REFERENCES research.evaluations(evaluation_id),decision text NOT NULL,
 decision_reason jsonb NOT NULL,requires_approval boolean NOT NULL DEFAULT true,
 created_at timestamptz NOT NULL DEFAULT now()
);
COMMIT;
