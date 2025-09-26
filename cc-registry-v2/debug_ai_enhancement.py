#!/usr/bin/env python3
"""
Debug script to test AI enhancement directly
"""
import sys
import os
sys.path.append('/app')

from app.core.database import SessionLocal
from app.models import Codebundle
from app.services.ai_service import get_ai_service

def test_ai_enhancement():
    """Test AI enhancement with debug output"""
    db = SessionLocal()
    
    try:
        # Get the codebundle
        codebundle = db.query(Codebundle).filter(Codebundle.id == 166).first()
        if not codebundle:
            print("❌ Codebundle not found")
            return
            
        print(f"✅ Found codebundle: {codebundle.name}")
        print(f"   Slug: {codebundle.slug}")
        print(f"   Platform: {codebundle.discovery_platform}")
        print(f"   Resource Types: {codebundle.discovery_resource_types}")
        print(f"   Tasks: {codebundle.tasks}")
        
        # Get AI service
        ai_service = get_ai_service(db)
        if not ai_service:
            print("❌ AI service not available")
            return
            
        print(f"✅ AI service available: {ai_service.is_enabled()}")
        
        # Test context preparation
        try:
            context = ai_service._prepare_codebundle_context(codebundle)
            print(f"✅ Context prepared:")
            for key, value in context.items():
                print(f"   {key}: {value}")
        except Exception as e:
            print(f"❌ Context preparation failed: {e}")
            import traceback
            traceback.print_exc()
            return
            
        # Test prompt generation
        try:
            from app.services.ai_prompts import AIPrompts
            prompt = AIPrompts.get_codebundle_prompt(context)
            print(f"✅ Prompt generated (length: {len(prompt)})")
            print(f"   First 200 chars: {prompt[:200]}...")
        except Exception as e:
            print(f"❌ Prompt generation failed: {e}")
            import traceback
            traceback.print_exc()
            return
            
        print("✅ All components working - the issue might be in the actual AI API call")
        
    finally:
        db.close()

if __name__ == "__main__":
    test_ai_enhancement()
