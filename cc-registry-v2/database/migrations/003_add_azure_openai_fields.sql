-- Migration: Add Azure OpenAI specific fields to ai_configurations table
-- Created: 2024-09-26

-- Add Azure OpenAI specific fields
ALTER TABLE ai_configurations 
ADD COLUMN azure_endpoint VARCHAR(500),
ADD COLUMN azure_deployment_name VARCHAR(100),
ADD COLUMN api_version VARCHAR(20) DEFAULT '2024-02-15-preview';

-- Create index on service provider for filtering
CREATE INDEX idx_ai_configurations_service_provider ON ai_configurations(service_provider);
