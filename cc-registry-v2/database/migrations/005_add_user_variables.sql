-- Add user_variables field to codebundles table
-- This stores parsed RW.Core.Import User Variable data from Robot Framework files

-- Add user_variables column as JSONB
ALTER TABLE codebundles 
ADD COLUMN IF NOT EXISTS user_variables JSONB DEFAULT '[]'::jsonb;

-- Add index on user_variables for faster queries
CREATE INDEX IF NOT EXISTS idx_codebundles_user_variables 
ON codebundles USING GIN (user_variables);

-- Add comment
COMMENT ON COLUMN codebundles.user_variables IS 'Parsed user variables from RW.Core.Import User Variable calls - includes name, type, description, pattern, example, default';
