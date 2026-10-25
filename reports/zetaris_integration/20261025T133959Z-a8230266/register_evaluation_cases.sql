CREATE LIGHTNING FILESTORE TABLE evaluation_cases FROM nextwise FORMAT csv OPTIONS (
  path 'dffs://nextwise/evaluation_cases.csv', delimiter ',', header 'true',
  inferSchema 'false', multiLine 'true', escape '"'
);
