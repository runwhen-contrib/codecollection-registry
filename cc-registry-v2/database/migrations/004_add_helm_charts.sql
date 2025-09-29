-- Migration: Add Helm chart version management
-- Created: 2024-12-19

-- Create helm_charts table
CREATE TABLE helm_charts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    repository_url VARCHAR(500) NOT NULL,
    description TEXT,
    home_url VARCHAR(500),
    source_urls JSON DEFAULT '[]',
    maintainers JSON DEFAULT '[]',
    keywords JSON DEFAULT '[]',
    last_synced_at TIMESTAMP,
    sync_enabled BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create helm_chart_versions table
CREATE TABLE helm_chart_versions (
    id SERIAL PRIMARY KEY,
    chart_id INTEGER NOT NULL REFERENCES helm_charts(id) ON DELETE CASCADE,
    version VARCHAR(50) NOT NULL,
    app_version VARCHAR(50),
    description TEXT,
    created_date TIMESTAMP,
    digest VARCHAR(100),
    default_values JSON DEFAULT '{}',
    values_schema JSON DEFAULT '{}',
    is_latest BOOLEAN DEFAULT FALSE,
    is_prerelease BOOLEAN DEFAULT FALSE,
    is_deprecated BOOLEAN DEFAULT FALSE,
    synced_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chart_id, version)
);

-- Create helm_chart_templates table
CREATE TABLE helm_chart_templates (
    id SERIAL PRIMARY KEY,
    chart_version_id INTEGER NOT NULL REFERENCES helm_chart_versions(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    category VARCHAR(50),
    template_values JSON DEFAULT '{}',
    required_fields JSON DEFAULT '[]',
    is_default BOOLEAN DEFAULT FALSE,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_helm_charts_name ON helm_charts(name);
CREATE INDEX idx_helm_charts_active ON helm_charts(is_active);
CREATE INDEX idx_helm_chart_versions_chart_id ON helm_chart_versions(chart_id);
CREATE INDEX idx_helm_chart_versions_version ON helm_chart_versions(version);
CREATE INDEX idx_helm_chart_versions_latest ON helm_chart_versions(is_latest);
CREATE INDEX idx_helm_chart_versions_active ON helm_chart_versions(is_active);
CREATE INDEX idx_helm_chart_templates_version_id ON helm_chart_templates(chart_version_id);
CREATE INDEX idx_helm_chart_templates_category ON helm_chart_templates(category);

-- Insert default runwhen-local chart
INSERT INTO helm_charts (name, repository_url, description, home_url, source_urls, keywords, is_active, sync_enabled)
VALUES (
    'runwhen-local',
    'https://runwhen-contrib.github.io/helm-charts',
    'RunWhen Local troubleshooting and automation platform for Kubernetes',
    'https://github.com/runwhen-contrib/helm-charts',
    '["https://github.com/runwhen-contrib/helm-charts"]',
    '["kubernetes", "troubleshooting", "automation", "runwhen"]',
    TRUE,
    TRUE
);
