#!/usr/bin/env python3
"""
Setup AI Configuration from Environment Variables
This script helps configure AI settings for testing without needing to use the admin UI
"""

import os
import sys
sys.path.insert(0, '/app')

from app.core.database import SessionLocal
from app.models.ai_config import AIConfiguration

def setup_ai_from_env():
    """Setup AI configuration from environment variables"""
    
    # Check what AI configuration we have in environment
    openai_key = os.getenv('OPENAI_API_KEY')
    azure_key = os.getenv('AZURE_OPENAI_API_KEY')
    azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    azure_deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')
    ai_provider = os.getenv('AI_SERVICE_PROVIDER', 'openai')
    ai_model = os.getenv('AI_MODEL', 'gpt-4')
    
    print("=== AI Configuration Setup ===")
    print(f"AI Service Provider: {ai_provider}")
    print(f"AI Model: {ai_model}")
    
    if ai_provider == 'azure-openai':
        print(f"Azure Endpoint: {azure_endpoint}")
        print(f"Azure Deployment: {azure_deployment}")
        print(f"Azure API Key: {'***' + azure_key[-4:] if azure_key else 'Not set'}")
        
        if not all([azure_key, azure_endpoint, azure_deployment]):
            print("ERROR: For Azure OpenAI, you need:")
            print("- AZURE_OPENAI_API_KEY")
            print("- AZURE_OPENAI_ENDPOINT") 
            print("- AZURE_OPENAI_DEPLOYMENT_NAME")
            return False
            
    else:
        print(f"OpenAI API Key: {'***' + openai_key[-4:] if openai_key else 'Not set'}")
        
        if not openai_key:
            print("ERROR: For OpenAI, you need:")
            print("- OPENAI_API_KEY")
            return False
    
    # Create database configuration
    db = SessionLocal()
    try:
        # Clear existing active configurations
        db.query(AIConfiguration).update({'is_active': False})
        
        # Create new configuration
        if ai_provider == 'azure-openai':
            config = AIConfiguration(
                service_provider='azure-openai',
                api_key=azure_key,
                model_name=ai_model,
                azure_endpoint=azure_endpoint,
                azure_deployment_name=azure_deployment,
                api_version=os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-15-preview'),
                enhancement_enabled=True,
                auto_enhance_new_bundles=False,
                is_active=True,
                created_by='environment-setup'
            )
        else:
            config = AIConfiguration(
                service_provider='openai',
                api_key=openai_key,
                model_name=ai_model,
                enhancement_enabled=True,
                auto_enhance_new_bundles=False,
                is_active=True,
                created_by='environment-setup'
            )
        
        db.add(config)
        db.commit()
        
        print(f"✅ AI Configuration created successfully!")
        print(f"   Provider: {config.service_provider}")
        print(f"   Model: {config.model_name}")
        print(f"   Enhancement Enabled: {config.enhancement_enabled}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating AI configuration: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def show_current_config():
    """Show current AI configuration"""
    db = SessionLocal()
    try:
        config = db.query(AIConfiguration).filter(AIConfiguration.is_active == True).first()
        
        if config:
            print("\\n=== Current Active AI Configuration ===")
            print(f"ID: {config.id}")
            print(f"Provider: {config.service_provider}")
            print(f"Model: {config.model_name}")
            print(f"Enhancement Enabled: {config.enhancement_enabled}")
            print(f"Created By: {config.created_by}")
            print(f"Created At: {config.created_at}")
            if config.service_provider == 'azure-openai':
                print(f"Azure Endpoint: {config.azure_endpoint}")
                print(f"Azure Deployment: {config.azure_deployment_name}")
        else:
            print("\\n❌ No active AI configuration found")
            
    finally:
        db.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Setup AI Configuration')
    parser.add_argument('--show', action='store_true', help='Show current configuration')
    parser.add_argument('--setup', action='store_true', help='Setup from environment variables')
    
    args = parser.parse_args()
    
    if args.show:
        show_current_config()
    elif args.setup:
        setup_ai_from_env()
    else:
        print("Usage:")
        print("  python setup_ai_env.py --show    # Show current config")
        print("  python setup_ai_env.py --setup   # Setup from env vars")
        print("\\nEnvironment variables for setup:")
        print("  OPENAI_API_KEY=your_key")
        print("  AI_SERVICE_PROVIDER=openai")
        print("  AI_MODEL=gpt-4")
        print("\\nOr for Azure:")
        print("  AZURE_OPENAI_API_KEY=your_key")
        print("  AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/")
        print("  AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment")
        print("  AI_SERVICE_PROVIDER=azure-openai")
