CREATE LIGHTNING FILESTORE TABLE investigations FROM nextwise FORMAT csv OPTIONS (
  path 'dffs://nextwise/investigations.csv', delimiter ',', header 'true',
  inferSchema 'false', multiLine 'true', escape '"'
);
