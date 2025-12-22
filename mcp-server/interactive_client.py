#!/usr/bin/env python3
"""
Interactive CLI client for RunWhen Registry MCP Server

Allows you to interactively query the MCP server from the command line.
"""
import asyncio
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def interactive_session():
    """Run an interactive query session"""
    print("\n🚀 RunWhen Registry MCP - Interactive Client")
    print("="*80)
    print("\nAvailable commands:")
    print("  1. list      - List all codebundles and codecollections")
    print("  2. search    - Search for codebundles")
    print("  3. details   - Get codebundle details")
    print("  4. libs      - Find library information")
    print("  5. docs      - Get development requirements")
    print("  6. collections - List codecollections")
    print("  7. tools     - List all available MCP tools")
    print("  q. quit      - Exit")
    print("="*80 + "\n")
    
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"],
        env=None
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            while True:
                try:
                    command = input("\n📝 Enter command (1-7, or q): ").strip().lower()
                    
                    if command in ['q', 'quit', 'exit']:
                        print("\n👋 Goodbye!\n")
                        break
                    
                    elif command in ['1', 'list']:
                        print("\n📋 Listing all codebundles...\n")
                        result = await session.call_tool(
                            "list_codebundles",
                            arguments={"format": "markdown"}
                        )
                        for content in result.content:
                            print(content.text)
                    
                    elif command in ['2', 'search']:
                        query = input("🔍 Enter search query: ").strip()
                        if query:
                            print(f"\n🔍 Searching for: {query}\n")
                            result = await session.call_tool(
                                "search_codebundles",
                                arguments={"query": query, "max_results": 5}
                            )
                            for content in result.content:
                                print(content.text)
                    
                    elif command in ['3', 'details']:
                        slug = input("📦 Enter codebundle slug: ").strip()
                        if slug:
                            print(f"\n📦 Getting details for: {slug}\n")
                            result = await session.call_tool(
                                "get_codebundle_details",
                                arguments={"slug": slug}
                            )
                            for content in result.content:
                                print(content.text)
                    
                    elif command in ['4', 'libs']:
                        query = input("📚 Enter library query: ").strip()
                        if query:
                            print(f"\n📚 Searching libraries for: {query}\n")
                            result = await session.call_tool(
                                "find_library_info",
                                arguments={"query": query, "category": "all"}
                            )
                            for content in result.content:
                                print(content.text)
                    
                    elif command in ['5', 'docs']:
                        feature = input("📖 Enter feature/topic: ").strip()
                        if feature:
                            print(f"\n📖 Getting docs for: {feature}\n")
                            result = await session.call_tool(
                                "get_development_requirements",
                                arguments={"feature": feature}
                            )
                            for content in result.content:
                                print(content.text)
                    
                    elif command in ['6', 'collections']:
                        print("\n📚 Listing codecollections...\n")
                        result = await session.call_tool(
                            "list_codecollections",
                            arguments={"format": "markdown"}
                        )
                        for content in result.content:
                            print(content.text)
                    
                    elif command in ['7', 'tools']:
                        print("\n🔧 Available MCP Tools:\n")
                        tools = await session.list_tools()
                        for tool in tools.tools:
                            print(f"📦 {tool.name}")
                            print(f"   {tool.description}\n")
                    
                    else:
                        print("❌ Invalid command. Try 1-7, or q to quit.")
                
                except KeyboardInterrupt:
                    print("\n\n👋 Goodbye!\n")
                    break
                except Exception as e:
                    print(f"\n❌ Error: {e}\n")


if __name__ == "__main__":
    try:
        asyncio.run(interactive_session())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!\n")
        sys.exit(0)

