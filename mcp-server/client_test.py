#!/usr/bin/env python3
"""
Test client for RunWhen Registry MCP Server

This script tests the MCP server by sending various queries and displaying results.
"""
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_list_codebundles():
    """Test the list_codebundles tool"""
    print("\n" + "="*80)
    print("TEST 1: List all codebundles and codecollections in markdown form")
    print("="*80)
    
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"],
        env=None
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Call list_codebundles tool
            result = await session.call_tool(
                "list_codebundles",
                arguments={"format": "markdown"}
            )
            
            # Display results
            for content in result.content:
                print(content.text)


async def test_search_kubernetes():
    """Test searching for kubernetes troubleshooting codebundles"""
    print("\n" + "="*80)
    print("TEST 2: Search for kubernetes troubleshooting codebundles")
    print("="*80)
    
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"],
        env=None
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Search for kubernetes troubleshooting
            result = await session.call_tool(
                "search_codebundles",
                arguments={
                    "query": "kubernetes pods troubleshooting",
                    "max_results": 5
                }
            )
            
            for content in result.content:
                print(content.text)


async def test_find_library():
    """Test finding library for running shell scripts"""
    print("\n" + "="*80)
    print("TEST 3: Which library do I use to run a shell script?")
    print("="*80)
    
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"],
        env=None
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Find library info
            result = await session.call_tool(
                "find_library_info",
                arguments={
                    "query": "run shell script command line",
                    "category": "all"
                }
            )
            
            for content in result.content:
                print(content.text)


async def test_development_requirements():
    """Test getting development requirements for secrets"""
    print("\n" + "="*80)
    print("TEST 4: Development requirements for using secrets")
    print("="*80)
    
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"],
        env=None
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Get development requirements
            result = await session.call_tool(
                "get_development_requirements",
                arguments={
                    "feature": "secrets"
                }
            )
            
            for content in result.content:
                print(content.text)


async def test_list_tools():
    """Test listing available tools"""
    print("\n" + "="*80)
    print("Available MCP Tools")
    print("="*80)
    
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"],
        env=None
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # List tools
            tools = await session.list_tools()
            
            print(f"\nFound {len(tools.tools)} tool(s):\n")
            for tool in tools.tools:
                print(f"📦 {tool.name}")
                print(f"   {tool.description}")
                print()


async def main():
    """Run all tests"""
    print("\n🚀 RunWhen Registry MCP Server - Test Suite")
    print("="*80)
    
    try:
        # List available tools
        await test_list_tools()
        
        # Run tests
        await test_list_codebundles()
        await test_search_kubernetes()
        await test_find_library()
        await test_development_requirements()
        
        print("\n" + "="*80)
        print("✅ All tests completed successfully!")
        print("="*80 + "\n")
    
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

