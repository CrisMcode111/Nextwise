SELECT project_id, CASE WHEN team_size = '\\N' THEN NULL ELSE CAST(team_size AS BIGINT) END AS team_size FROM nextwise.project_profiles;
