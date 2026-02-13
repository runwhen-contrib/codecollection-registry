#!/usr/bin/env python3
"""
Test script to create Azure OpenAI configuration and test AI enhancement
"""
import requests
import json
import time

# Configuration
API_BASE_URL = "http://localhost:8001/api/v1"
ADMIN_TOKEN = "admin-dev-token"

def create_azure_openai_config():
    """Create Azure OpenAI configuration"""
    
    print("🔧 Creating Azure OpenAI configuration...")
    
    config_data = {
        "service_provider": "azure-openai",
        "api_key": "your-azure-openai-token-here",  # Replace with actual token
        "model_name": "gpt-4",
        "azure_endpoint": "https://your-resource.openai.azure.com",  # Replace with actual endpoint
        "azure_deployment_name": "gpt-4",  # Replace with actual deployment name
        "api_version": "2024-02-15-preview",
        "enhancement_enabled": True,
        "auto_enhance_new_bundles": False,
        "max_requests_per_hour": 1000,
        "max_concurrent_requests": 5
    }
    
    response = requests.post(
        f"{API_BASE_URL}/admin/ai/config",
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json"},
        json=config_data
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Azure OpenAI configuration created: ID {result['id']}")
        return result['id']
    else:
        print(f"❌ Failed to create configuration: {response.status_code} - {response.text}")
        return None

def test_azure_enhancement():
    """Test AI enhancement with Azure OpenAI"""
    
    print("🚀 Testing AI enhancement with Azure OpenAI...")
    
    # Find a test CodeBundle
    response = requests.get(f"{API_BASE_URL}/codebundles")
    if response.status_code == 200:
        codebundles = response.json()
        if codebundles:
            test_cb = codebundles[0]
            print(f"📋 Testing with CodeBundle: {test_cb['name']} (ID: {test_cb['id']})")
            
            # Trigger enhancement
            enhance_response = requests.post(
                f"{API_BASE_URL}/admin/ai/enhance",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json"},
                json={"codebundle_ids": [test_cb['id']]}
            )
            
            if enhance_response.status_code == 200:
                task_data = enhance_response.json()
                task_id = task_data.get("task_id")
                print(f"✅ Enhancement task started: {task_id}")
                
                # Monitor task
                for i in range(30):
                    status_response = requests.get(
                        f"{API_BASE_URL}/admin/ai/enhance/status/{task_id}",
                        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"}
                    )
                    
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        state = status_data.get("state", "UNKNOWN")
                        print(f"📊 Task status: {state}")
                        
                        if state in ["SUCCESS", "FAILURE"]:
                            if state == "SUCCESS":
                                result = status_data.get("result", {})
                                print("🎯 Enhancement completed!")
                                print(f"   Enhanced Description: {result.get('enhanced_description', 'N/A')[:100]}...")
                                print(f"   Access Level: {result.get('access_level', 'N/A')}")
                                print(f"   IAM Requirements: {len(result.get('iam_requirements', []))} items")
                            else:
                                print(f"❌ Enhancement failed: {status_data.get('result', 'Unknown error')}")
                            break
                    
                    time.sleep(2)
                else:
                    print("⏰ Task monitoring timeout")
            else:
                print(f"❌ Failed to start enhancement: {enhance_response.status_code} - {enhance_response.text}")
        else:
            print("❌ No CodeBundles found for testing")
    else:
        print(f"❌ Failed to fetch CodeBundles: {response.status_code}")

def main():
    print("🤖 Azure OpenAI Configuration Test")
    print("=" * 50)
    
    # Step 1: Create Azure OpenAI config
    config_id = create_azure_openai_config()
    
    if config_id:
        print("\n" + "=" * 50)
        # Step 2: Test enhancement
        test_azure_enhancement()
    
    print("\n" + "=" * 50)
    print("💡 To use this with real Azure OpenAI:")
    print("   1. Replace 'your-azure-openai-token-here' with your actual API key")
    print("   2. Replace 'https://your-resource.openai.azure.com' with your endpoint")
    print("   3. Replace deployment name with your actual deployment")
    print("   4. Run this script again")

if __name__ == "__main__":
    main()
