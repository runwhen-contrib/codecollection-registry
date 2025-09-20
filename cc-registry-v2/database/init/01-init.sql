-- Initialize CodeCollection Registry Database
-- This script runs when the PostgreSQL container starts for the first time

-- Create database (already created by POSTGRES_DB env var)
-- CREATE DATABASE codecollection_registry;

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Grant permissions to user
GRANT ALL PRIVILEGES ON DATABASE codecollection_registry TO "user";

-- Log initialization
SELECT 'CodeCollection Registry database initialized successfully' AS status;

