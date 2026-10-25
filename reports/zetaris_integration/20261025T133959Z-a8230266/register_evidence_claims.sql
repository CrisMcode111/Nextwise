CREATE LIGHTNING FILESTORE TABLE evidence_claims FROM nextwise FORMAT csv OPTIONS (
  path 'dffs://nextwise/evidence_claims.csv', delimiter ',', header 'true',
  inferSchema 'false', multiLine 'true', escape '"'
);
