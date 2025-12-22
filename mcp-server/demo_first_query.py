#!/usr/bin/env python3
"""
Demonstration of the first query: "list all codebundles and codecollections in markdown form"

This script demonstrates the MVP working exactly as requested.
"""
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def demo_first_query():
    """Demonstrate the first query as requested by the user"""
    
    print("\n" + "="*80)
    print("🎯 DEMO: First Query Test")
    print("="*80)
    print("\nQuery: 'list all codebundles and codecollections in markdown form'")
    print("\n" + "="*80 + "\n")
    
    # Start MCP server
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"],
        env=None
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize session
            await session.initialize()
            
            # Execute the first query
            result = await session.call_tool(
                "list_codebundles",
                arguments={"format": "markdown"}
            )
            
            # Display results
            for content in result.content:
                print(content.text)
            
            print("\n" + "="*80)
            print("✅ First query completed successfully!")
            print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(demo_first_query())

