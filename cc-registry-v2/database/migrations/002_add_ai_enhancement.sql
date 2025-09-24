-- Migration: Add AI enhancement fields and configuration
-- Created: 2024-12-19

-- Add AI enhancement fields to codebundles table
ALTER TABLE codebundles 
ADD COLUMN ai_enhanced_description TEXT,
ADD COLUMN access_level VARCHAR(20) DEFAULT 'unknown',
ADD COLUMN minimum_iam_requirements JSON DEFAULT '[]';

-- Create AI configuration table
CREATE TABLE ai_configurations (
    id SERIAL PRIMARY KEY,
    service_provider VARCHAR(50) DEFAULT 'openai',
    api_key VARCHAR(500),
    model_name VARCHAR(100) DEFAULT 'gpt-4',
    enhancement_enabled BOOLEAN DEFAULT FALSE,
    auto_enhance_new_bundles BOOLEAN DEFAULT FALSE,
    enhancement_prompt_template TEXT,
    max_requests_per_hour INTEGER DEFAULT 100,
    max_concurrent_requests INTEGER DEFAULT 5,
    created_by VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index on active AI configurations
CREATE INDEX idx_ai_configurations_active ON ai_configurations(is_active);

-- Create index on codebundle access level for filtering
CREATE INDEX idx_codebundles_access_level ON codebundles(access_level);

-- Create index on enhancement status for monitoring
CREATE INDEX idx_codebundles_enhancement_status ON codebundles(enhancement_status);

