#!/usr/bin/env python3
"""
Web-based testing client for RunWhen MCP Server with Azure OpenAI integration

This provides a simple web interface to test the MCP server with LLM-powered responses.
"""
import os
import json
import logging
from typing import Dict, Any, List

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import httpx
from openai import AzureOpenAI
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(title="RunWhen MCP Test Client")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration from environment variables
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://mcp-http:8000")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

# Initialize Azure OpenAI client
openai_client = None
if AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY:
    openai_client = AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION
    )
    logger.info(f"Azure OpenAI configured: {AZURE_OPENAI_ENDPOINT}")
else:
    logger.warning("Azure OpenAI not configured - LLM features disabled")


# ============================================================================
# Web Interface
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the web interface"""
    return HTML_INTERFACE


@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "mcp_server": MCP_SERVER_URL,
        "llm_configured": openai_client is not None
    }


# ============================================================================
# MCP Server Proxy
# ============================================================================

@app.get("/api/mcp/tools")
async def get_mcp_tools():
    """Get available MCP tools"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{MCP_SERVER_URL}/tools")
        return response.json()


@app.post("/api/mcp/call")
async def call_mcp_tool(request: Request):
    """Call an MCP tool"""
    body = await request.json()
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{MCP_SERVER_URL}/tools/call",
            json=body
        )
        return response.json()


# ============================================================================
# LLM Integration
# ============================================================================

@app.post("/api/query")
async def query_with_llm(request: Request):
    """
    Query using LLM with MCP server context
    
    Takes a natural language query, searches the MCP server,
    and returns an LLM-powered response.
    """
    if not openai_client:
        raise HTTPException(
            status_code=503,
            detail="Azure OpenAI not configured. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY"
        )
    
    body = await request.json()
    user_query = body.get("query", "")
    
    if not user_query:
        raise HTTPException(status_code=400, detail="Query is required")
    
    try:
        # Step 1: Search MCP server for relevant codebundles
        logger.info(f"Searching MCP for: {user_query}")
        
        async with httpx.AsyncClient() as client:
            mcp_response = await client.post(
                f"{MCP_SERVER_URL}/tools/call",
                json={
                    "tool_name": "search_codebundles",
                    "arguments": {
                        "query": user_query,
                        "max_results": 5
                    }
                }
            )
            mcp_data = mcp_response.json()
        
        if not mcp_data.get("success"):
            raise HTTPException(status_code=500, detail="MCP search failed")
        
        search_results = mcp_data.get("result", "No results found")
        
        # Step 2: Create prompt for LLM
        system_prompt = """You are a helpful assistant that helps users find and understand RunWhen CodeBundles.

You have access to a registry of CodeBundles which are automation scripts for various platforms (Kubernetes, AWS, GCP, Azure, etc.).

When answering questions:
1. Recommend specific CodeBundles from the search results
2. Explain what each CodeBundle does
3. Provide practical guidance on which to use
4. Be concise but informative

If no relevant CodeBundles are found, explain that and suggest alternative approaches."""

        user_prompt = f"""User Question: {user_query}

Search Results from CodeBundle Registry:
{search_results}

Please provide a helpful response based on these search results."""

        # Step 3: Call Azure OpenAI
        logger.info("Calling Azure OpenAI...")
        
        response = openai_client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=800
        )
        
        llm_response = response.choices[0].message.content
        
        return {
            "success": True,
            "query": user_query,
            "llm_response": llm_response,
            "search_results": search_results,
            "model": AZURE_OPENAI_DEPLOYMENT
        }
        
    except httpx.HTTPError as e:
        logger.error(f"HTTP error: {e}")
        raise HTTPException(status_code=503, detail=f"MCP server error: {str(e)}")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# HTML Interface
# ============================================================================

HTML_INTERFACE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RunWhen MCP Test Client</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        header {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        
        h1 {
            color: #333;
            margin-bottom: 10px;
        }
        
        .subtitle {
            color: #666;
            font-size: 14px;
        }
        
        .main-content {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .panel {
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        .panel h2 {
            color: #333;
            margin-bottom: 15px;
            font-size: 20px;
        }
        
        .query-box {
            grid-column: 1 / -1;
        }
        
        textarea {
            width: 100%;
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 16px;
            font-family: inherit;
            resize: vertical;
            min-height: 100px;
        }
        
        textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            margin-top: 15px;
            transition: transform 0.2s;
        }
        
        button:hover {
            transform: translateY(-2px);
        }
        
        button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        
        .response {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
            margin-top: 15px;
            white-space: pre-wrap;
            line-height: 1.6;
        }
        
        .error {
            background: #fee;
            border-left-color: #f44;
            color: #c00;
        }
        
        .loading {
            text-align: center;
            padding: 20px;
            color: #667eea;
        }
        
        .examples {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 15px;
        }
        
        .example {
            background: #f0f0f0;
            padding: 8px 15px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            transition: background 0.2s;
        }
        
        .example:hover {
            background: #e0e0e0;
        }
        
        .status {
            display: flex;
            gap: 15px;
            margin-top: 15px;
            font-size: 14px;
        }
        
        .status-item {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }
        
        .status-dot.green {
            background: #4caf50;
        }
        
        .status-dot.red {
            background: #f44336;
        }
        
        @media (max-width: 768px) {
            .main-content {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🚀 RunWhen MCP Test Client</h1>
            <p class="subtitle">AI-powered CodeBundle search with Azure OpenAI</p>
            <div class="status">
                <div class="status-item">
                    <div class="status-dot" id="mcp-status"></div>
                    <span>MCP Server</span>
                </div>
                <div class="status-item">
                    <div class="status-dot" id="llm-status"></div>
                    <span>Azure OpenAI</span>
                </div>
            </div>
        </header>
        
        <div class="main-content">
            <div class="panel query-box">
                <h2>Ask a Question</h2>
                <textarea 
                    id="query" 
                    placeholder="Example: Which codebundle should I use for troubleshooting Kubernetes pods?"
                ></textarea>
                
                <button onclick="submitQuery()" id="submit-btn">
                    🔍 Search with AI
                </button>
                
                <div class="examples">
                    <div class="example" onclick="setExample(this)">
                        Which codebundle is best for Kubernetes troubleshooting?
                    </div>
                    <div class="example" onclick="setExample(this)">
                        How do I monitor AWS EKS clusters?
                    </div>
                    <div class="example" onclick="setExample(this)">
                        Show me tools for database health checks
                    </div>
                    <div class="example" onclick="setExample(this)">
                        What libraries do I use to run shell scripts?
                    </div>
                </div>
            </div>
            
            <div class="panel">
                <h2>AI Response</h2>
                <div id="llm-response"></div>
            </div>
            
            <div class="panel">
                <h2>Raw Search Results</h2>
                <div id="raw-results"></div>
            </div>
        </div>
    </div>
    
    <script>
        // Check health on load
        async function checkHealth() {
            try {
                const response = await fetch('/health');
                const data = await response.json();
                
                document.getElementById('mcp-status').className = 'status-dot green';
                document.getElementById('llm-status').className = 
                    data.llm_configured ? 'status-dot green' : 'status-dot red';
                    
                if (!data.llm_configured) {
                    document.getElementById('llm-response').innerHTML = 
                        '<div class="response error">⚠️ Azure OpenAI not configured. Set environment variables.</div>';
                }
            } catch (e) {
                document.getElementById('mcp-status').className = 'status-dot red';
                document.getElementById('llm-status').className = 'status-dot red';
            }
        }
        
        function setExample(element) {
            document.getElementById('query').value = element.textContent.trim();
        }
        
        async function submitQuery() {
            const query = document.getElementById('query').value.trim();
            
            if (!query) {
                alert('Please enter a question');
                return;
            }
            
            const submitBtn = document.getElementById('submit-btn');
            const llmDiv = document.getElementById('llm-response');
            const rawDiv = document.getElementById('raw-results');
            
            submitBtn.disabled = true;
            llmDiv.innerHTML = '<div class="loading">🤔 Thinking...</div>';
            rawDiv.innerHTML = '<div class="loading">🔍 Searching...</div>';
            
            try {
                const response = await fetch('/api/query', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ query })
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Request failed');
                }
                
                const data = await response.json();
                
                llmDiv.innerHTML = `<div class="response">${escapeHtml(data.llm_response)}</div>`;
                rawDiv.innerHTML = `<div class="response"><pre>${escapeHtml(data.search_results)}</pre></div>`;
                
            } catch (error) {
                llmDiv.innerHTML = `<div class="response error">❌ Error: ${error.message}</div>`;
                rawDiv.innerHTML = '';
            } finally {
                submitBtn.disabled = false;
            }
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // Allow Enter to submit (with Shift+Enter for new line)
        document.getElementById('query').addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submitQuery();
            }
        });
        
        // Check health on load
        checkHealth();
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    
    logger.info(f"Starting MCP Test Client on port {port}")
    logger.info(f"MCP Server: {MCP_SERVER_URL}")
    logger.info(f"Azure OpenAI: {'Configured' if openai_client else 'Not configured'}")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )

