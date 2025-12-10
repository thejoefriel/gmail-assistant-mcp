import asyncio
import logging
import os
import json
from pathlib import Path
from anthropic import Anthropic
from mcp.server import Server
from mcp.types import Tool, TextContent
from gmail_client import GmailClient
from google_docs_helper import GoogleDocsHelper

# Import tools
from tools import get_unread_emails, create_draft_reply, get_unread_and_draft_replies

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gmail-assistant")

# Get credentials from environment (set by MCP client)
GMAIL_EMAIL = os.getenv("EMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GUIDELINES_DOC_ID = os.getenv("GUIDELINES_DOC_ID")


if not GMAIL_EMAIL or not GMAIL_APP_PASSWORD:
    raise ValueError("EMAIL_USER and EMAIL_APP_PASSWORD must be set in MCP client config")

if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY must be set in MCP client config")

logger.info(f"Gmail Assistant starting for {GMAIL_EMAIL}")

# Create Gmail client
gmail_client = GmailClient(GMAIL_EMAIL, GMAIL_APP_PASSWORD)

# Create Anthropic client
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)  # Changed from 'anthropic' to 'anthropic_client'

# Create Google Docs helper
credentials_path = Path.home() / "mcp-servers/gmail-assistant-mcp/credentials.json"
token_path = Path.home() / "mcp-servers/gmail-assistant-mcp/token.pickle"

google_docs_helper = None
if GUIDELINES_DOC_ID:
    if credentials_path.exists() and token_path.exists():
        google_docs_helper = GoogleDocsHelper(
            credentials_path=str(credentials_path),
            token_path=str(token_path)
        )
        logger.info("Google Docs helper initialized")
    else:
        logger.warning("Google Docs credentials or token file does not exist - will not use email guidelines")
else:
    logger.warning("No GUIDELINES_DOC_ID set - will not use email guidelines")


# Create server instance
app = Server("gmail-assistant")

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        get_unread_emails.get_tool_definition(),
        create_draft_reply.get_tool_definition(),
        get_unread_and_draft_replies.get_tool_definition()
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    if name == "get_unread_emails":
        return await get_unread_emails.handle(gmail_client, arguments)
    
    elif name == "create_draft_reply":  # FIXED INDENTATION - should be at same level as 'if name == "get_unread_emails"'
        return await create_draft_reply.handle(
            gmail_client,
            anthropic_client,
            google_docs_helper,
            GUIDELINES_DOC_ID,
            arguments
        )
    
    elif name == "get_unread_and_draft_replies":
        return await get_unread_and_draft_replies.handle(
            gmail_client,
            anthropic_client,
            google_docs_helper,
            GUIDELINES_DOC_ID,
            arguments
        )

    raise ValueError(f"Unknown tool: {name}")

async def main():
    """Run the server."""
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        logger.info(f"Gmail Assistant MCP server running for {GMAIL_EMAIL}")
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())