-- Recovery definition reconstructed from the saved installed registration metadata.
CREATE LIGHTNING FILESTORE TABLE project_profiles FROM nextwise FORMAT csv OPTIONS (path 'dffs://nextwise/project_profiles.csv', delimiter ',', header 'true', inferSchema 'false', multiLine 'true');
