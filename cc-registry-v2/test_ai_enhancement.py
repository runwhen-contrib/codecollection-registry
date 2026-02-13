#!/usr/bin/env python3
"""
Quick test script to trigger AI enhancement for a specific CodeBundle
"""
import requests
import json
import time

# Configuration
API_BASE_URL = "http://localhost:8001/api/v1"
ADMIN_TOKEN = "admin-dev-token"

def trigger_enhancement_for_codebundle(codebundle_id: int):
    """Trigger AI enhancement for a specific CodeBundle"""
    
    print(f"🚀 Triggering AI enhancement for CodeBundle ID: {codebundle_id}")
    
    # Trigger enhancement
    response = requests.post(
        f"{API_BASE_URL}/ai/enhance",
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
        json={"codebundle_ids": [codebundle_id]}
    )
    
    if response.status_code == 200:
        result = response.json()
        task_id = result.get("task_id")
        print(f"✅ Enhancement task started: {task_id}")
        
        # Monitor task status
        for i in range(30):  # Wait up to 30 seconds
            status_response = requests.get(
                f"{API_BASE_URL}/ai/enhance/status/{task_id}",
                headers={"Authorization": f"Bearer {ADMIN_TOKEN}"}
            )
            
            if status_response.status_code == 200:
                status_data = status_response.json()
                state = status_data.get("state", "UNKNOWN")
                print(f"📊 Task status: {state}")
                
                if state in ["SUCCESS", "FAILURE"]:
                    print(f"🎯 Task completed with status: {state}")
                    if state == "SUCCESS":
                        print("✅ AI enhancement completed successfully!")
                    else:
                        print(f"❌ AI enhancement failed: {status_data.get('result', 'Unknown error')}")
                    break
                    
            time.sleep(2)
        else:
            print("⏰ Task monitoring timeout - check task status manually")
            
    else:
        print(f"❌ Failed to trigger enhancement: {response.status_code} - {response.text}")

def find_codebundle_by_name(name_pattern: str):
    """Find CodeBundle ID by name pattern"""
    
    print(f"🔍 Searching for CodeBundle with name containing: '{name_pattern}'")
    
    response = requests.get(f"{API_BASE_URL}/codebundles")
    
    if response.status_code == 200:
        codebundles = response.json()
        matches = [cb for cb in codebundles if name_pattern.lower() in cb.get("name", "").lower()]
        
        if matches:
            print(f"📋 Found {len(matches)} matching CodeBundles:")
            for cb in matches:
                print(f"  - ID: {cb['id']}, Name: {cb['name']}, Status: {cb.get('enhancement_status', 'unknown')}")
            return matches[0]["id"]  # Return first match
        else:
            print(f"❌ No CodeBundles found matching '{name_pattern}'")
            return None
    else:
        print(f"❌ Failed to fetch CodeBundles: {response.status_code}")
        return None

def main():
    print("🤖 AI Enhancement Test Script")
    print("=" * 40)
    
    # Find K8s Chaos Namespace CodeBundle
    codebundle_id = find_codebundle_by_name("chaos")
    
    if not codebundle_id:
        # Try alternative search
        codebundle_id = find_codebundle_by_name("k8s")
    
    if codebundle_id:
        trigger_enhancement_for_codebundle(codebundle_id)
    else:
        print("❌ Could not find a suitable CodeBundle to enhance")
        print("💡 Try running this script with a specific CodeBundle ID:")
        print("   python test_ai_enhancement.py --id <codebundle_id>")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 2 and sys.argv[1] == "--id":
        try:
            codebundle_id = int(sys.argv[2])
            trigger_enhancement_for_codebundle(codebundle_id)
        except ValueError:
            print("❌ Invalid CodeBundle ID. Please provide a number.")
    else:
        main()

