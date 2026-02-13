-- Migration: Add AI Enhancement Logging
-- Created: 2025-09-26
-- Purpose: Add comprehensive logging for AI enhancement process

-- Create AI enhancement logs table
CREATE TABLE ai_enhancement_logs (
    id SERIAL PRIMARY KEY,
    codebundle_id INTEGER NOT NULL,
    codebundle_slug VARCHAR(255) NOT NULL,
    
    -- Request details
    prompt_sent TEXT,
    system_prompt TEXT,
    model_used VARCHAR(100),
    service_provider VARCHAR(50),
    
    -- Response details
    ai_response_raw TEXT,
    ai_response_parsed JSON,
    
    -- Enhancement results
    enhanced_description TEXT,
    access_level VARCHAR(20),
    iam_requirements JSON,
    
    -- Status tracking
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    error_message TEXT,
    
    -- Metadata
    processing_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE,
    
    -- Manual editing support
    is_manually_edited BOOLEAN DEFAULT FALSE,
    manual_notes TEXT
);

-- Create indexes for performance
CREATE INDEX idx_ai_enhancement_logs_codebundle_id ON ai_enhancement_logs(codebundle_id);
CREATE INDEX idx_ai_enhancement_logs_codebundle_slug ON ai_enhancement_logs(codebundle_slug);
CREATE INDEX idx_ai_enhancement_logs_status ON ai_enhancement_logs(status);
CREATE INDEX idx_ai_enhancement_logs_created_at ON ai_enhancement_logs(created_at);
CREATE INDEX idx_ai_enhancement_logs_manually_edited ON ai_enhancement_logs(is_manually_edited);

-- Add foreign key constraint
ALTER TABLE ai_enhancement_logs 
ADD CONSTRAINT fk_ai_enhancement_logs_codebundle 
FOREIGN KEY (codebundle_id) REFERENCES codebundles(id) ON DELETE CASCADE;

-- Create trigger for updated_at
CREATE OR REPLACE FUNCTION update_ai_enhancement_logs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_ai_enhancement_logs_updated_at
    BEFORE UPDATE ON ai_enhancement_logs
    FOR EACH ROW
    EXECUTE FUNCTION update_ai_enhancement_logs_updated_at();
