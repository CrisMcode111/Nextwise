-- Run after exact CSV and numeric-conversion validation. Raw tables remain STRING.
-- Zero claims means a known absence of accepted claims; measurements never default to zero.
WITH claim_counts AS (
    SELECT investigation_id, source_id, draft_sha256,
           COUNT(*) AS accepted_claim_count
    FROM nextwise.evidence_claims
    WHERE claim_kind = 'publisher_claim'
    GROUP BY investigation_id, source_id, draft_sha256
), typed_cases AS (
    SELECT investigation_id, run_id, draft_sha256, actual_model,
           evaluation_status, approval_json, decision_json, monetary_cost_json,
           CASE WHEN schema_valid = '\\N' THEN NULL ELSE CAST(schema_valid AS BIGINT) END AS schema_value,
           CASE WHEN quality_pass = '\\N' THEN NULL ELSE CAST(quality_pass AS BIGINT) END AS quality_value,
           CASE WHEN duration_seconds = '\\N' THEN NULL ELSE CAST(duration_seconds AS DECIMAL(20,6)) END AS seconds_value,
           CASE WHEN prompt_tokens = '\\N' THEN NULL ELSE CAST(prompt_tokens AS BIGINT) END AS prompt_value,
           CASE WHEN completion_tokens = '\\N' THEN NULL ELSE CAST(completion_tokens AS BIGINT) END AS completion_value,
           CASE WHEN total_tokens = '\\N' THEN NULL ELSE CAST(total_tokens AS BIGINT) END AS total_value
    FROM nextwise.evaluation_cases
), pilot AS (
    SELECT investigation_id, run_id, draft_sha256, actual_model,
           evaluation_status, approval_json, decision_json, monetary_cost_json,
           COUNT(*) AS attempted_cases,
           CASE WHEN COUNT(schema_value) = COUNT(*) THEN SUM(schema_value) END AS schema_valid_cases,
           CASE WHEN COUNT(quality_value) = COUNT(*) THEN SUM(quality_value) END AS quality_pass_cases,
           CASE WHEN COUNT(seconds_value) = COUNT(*) THEN SUM(seconds_value) END AS request_seconds,
           CASE WHEN COUNT(prompt_value) = COUNT(*) THEN SUM(prompt_value) END AS reported_prompt_tokens,
           CASE WHEN COUNT(completion_value) = COUNT(*) THEN SUM(completion_value) END AS reported_completion_tokens,
           CASE WHEN COUNT(total_value) = COUNT(*) THEN SUM(total_value) END AS reported_total_tokens
    FROM typed_cases
    GROUP BY investigation_id, run_id, draft_sha256, actual_model,
             evaluation_status, approval_json, decision_json, monetary_cost_json
)
SELECT p.project_id, p.project_name, p.stage,
       CASE WHEN p.team_size = '\\N' THEN NULL ELSE CAST(p.team_size AS BIGINT) END AS team_size,
       p.constraints_json, i.investigation_id, i.question,
       i.decision_json AS investigation_decision_json,
       r.review_status, r.approval_status, r.decision_json AS review_decision_json,
       r.readiness_status, r.reviewed_draft_sha256,
       s.source_id, s.requested_url, s.retrieved_at_utc, s.publication_date_json,
       COALESCE(c.accepted_claim_count, 0) AS accepted_publisher_claim_count,
       e.run_id, e.actual_model, e.evaluation_status,
       e.approval_json AS pilot_approval_json,
       e.decision_json AS pilot_decision_json,
       e.monetary_cost_json AS pilot_monetary_cost_json,
       e.attempted_cases, e.schema_valid_cases, e.quality_pass_cases,
       e.request_seconds, e.reported_prompt_tokens,
       e.reported_completion_tokens, e.reported_total_tokens
FROM nextwise.project_profiles p
JOIN nextwise.investigations i ON i.project_id = p.project_id
JOIN nextwise.evidence_reviews r
  ON r.investigation_id = i.investigation_id AND r.project_id = p.project_id
JOIN nextwise.sources s ON s.investigation_id = i.investigation_id
LEFT JOIN claim_counts c
  ON c.investigation_id = i.investigation_id
 AND c.source_id = s.source_id
 AND c.draft_sha256 = r.reviewed_draft_sha256
JOIN pilot e
  ON e.investigation_id = i.investigation_id
 AND e.draft_sha256 = r.reviewed_draft_sha256
WHERE p.project_id = 'ai-raw-gourmet'
  AND i.investigation_id = 'nemotron-lightning-requirements-extraction'
  AND e.run_id = '20261024T151413Z-fdf0c15b'
ORDER BY s.source_id
