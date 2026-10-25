CREATE LIGHTNING FILESTORE TABLE sources FROM nextwise FORMAT csv OPTIONS (
  path 'dffs://nextwise/sources.csv', delimiter ',', header 'true',
  inferSchema 'false', multiLine 'true', escape '"'
);
