#!/usr/bin/env python3
"""
Simple test script to verify the release models work correctly
"""

import sys
import os
from datetime import datetime

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_release_models():
    """Test that the release models can be imported and instantiated"""
    try:
        from app.models.release import CodeCollectionRelease, ReleaseCodebundle
        from app.models.code_collection import CodeCollection
        
        print("✅ Successfully imported release models")
        
        # Test model instantiation
        release = CodeCollectionRelease(
            codecollection_id=1,
            tag_name="v1.0.0",
            git_ref="v1.0.0",
            release_name="Initial Release",
            description="First stable release",
            is_latest=True,
            is_prerelease=False,
            release_date=datetime.utcnow()
        )
        
        print("✅ Successfully created CodeCollectionRelease instance")
        
        codebundle = ReleaseCodebundle(
            release_id=1,
            name="sample-codebundle",
            slug="sample-codebundle",
            display_name="Sample CodeBundle",
            description="A sample codebundle for testing",
            task_count=3,
            sli_count=1
        )
        
        print("✅ Successfully created ReleaseCodebundle instance")
        
        # Test model attributes
        assert release.tag_name == "v1.0.0"
        assert release.is_latest == True
        assert codebundle.task_count == 3
        
        print("✅ Model attributes working correctly")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_api_models():
    """Test that the API router models work"""
    try:
        from app.routers.releases import (
            ReleaseCodebundleResponse, 
            CodeCollectionReleaseResponse,
            CodeCollectionWithReleasesResponse
        )
        
        print("✅ Successfully imported API response models")
        
        # Test response model creation
        release_response = CodeCollectionReleaseResponse(
            id=1,
            tag_name="v1.0.0",
            git_ref="v1.0.0",
            release_name="Test Release",
            description="Test description",
            is_latest=True,
            is_prerelease=False,
            release_date=datetime.utcnow(),
            synced_at=datetime.utcnow(),
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            codebundle_count=5
        )
        
        print("✅ Successfully created API response model")
        
        return True
        
    except ImportError as e:
        print(f"❌ API Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ API Error: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Testing Release System Components\n")
    
    success = True
    
    print("1. Testing Release Models...")
    if not test_release_models():
        success = False
    
    print("\n2. Testing API Models...")
    if not test_api_models():
        success = False
    
    print(f"\n{'✅ All tests passed!' if success else '❌ Some tests failed!'}")
    
    if success:
        print("\n🎉 Release system is ready to use!")
        print("\nNext steps:")
        print("1. Start the backend server")
        print("2. Use the Admin panel to sync releases")
        print("3. View collections with releases in the frontend")
    
    return success

if __name__ == "__main__":
    main()




