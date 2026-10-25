CREATE LIGHTNING FILESTORE TABLE evidence_reviews FROM nextwise FORMAT csv OPTIONS (
  path 'dffs://nextwise/evidence_reviews.csv', delimiter ',', header 'true',
  inferSchema 'false', multiLine 'true', escape '"'
);
