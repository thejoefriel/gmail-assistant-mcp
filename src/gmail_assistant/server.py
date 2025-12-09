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
base_path = Path(__file__).parent.parent.parent
credentials_path = base_path / "credentials.json"
token_path = base_path / "token.pickle"

google_docs_helper = None
if GUIDELINES_DOC_ID:
    google_docs_helper = GoogleDocsHelper(
        credentials_path=str(credentials_path),
        token_path=str(token_path)
    )
    logger.info("Google Docs helper initialized")
else:
    logger.warning("No GUIDELINES_DOC_ID set - will not use email guidelines")


# Create server instance
app = Server("gmail-assistant")

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="get_unread_emails",
            description="Fetch unread emails from Gmail",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "number",
                        "description": "Maximum number of emails to fetch (default: 10)",
                        "default": 10
                    }
                }
            }
        ),
        Tool(
            name="create_draft_reply",
            description="Generate an AI-powered draft reply to an email and save it in Gmail",
            inputSchema={
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "The ID of the email to reply to"
                    },
                    "email_content": {
                        "type": "string",
                        "description": "The content of the email to reply to"
                    },
                    "sender": {
                        "type": "string",
                        "description": "The sender of the original email"
                    },
                    "subject": {
                        "type": "string",
                        "description": "The subject of the original email"
                    }
                },
                "required": ["email_id", "email_content", "sender", "subject"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    if name == "get_unread_emails":
        max_results = arguments.get("max_results", 10)
        
        try:
            emails = gmail_client.get_unread_emails(max_results=max_results)
            
            return [
                TextContent(
                    type="text",
                    text=json.dumps(emails, indent=2)
                )
            ]
        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            return [
                TextContent(
                    type="text",
                    text=f"Error fetching emails: {str(e)}"
                )
            ]
    
    elif name == "create_draft_reply":  # FIXED INDENTATION - should be at same level as 'if name == "get_unread_emails"'
        email_id = arguments.get("email_id")
        email_content = arguments.get("email_content")
        sender = arguments.get("sender")
        subject = arguments.get("subject")
        
        try:
            # Fetch guidelines from Google Doc if available
            guidelines = ""
            if google_docs_helper and GUIDELINES_DOC_ID:
                logger.info("Fetching email guidelines from Google Doc...")
                try:
                    guidelines = google_docs_helper.get_document_text(GUIDELINES_DOC_ID)
                    logger.info(f"Guidelines fetched successfully ({len(guidelines)} chars)")
                except Exception as e:
                    logger.warning(f"Could not fetch guidelines: {e}")
                    guidelines = ""

            # Build the prompt with guidelines
            prompt = f"""Generate a professional and helpful email reply to the following email:

From: {sender}
Subject: {subject}

Email content:
{email_content}

"""
        
            if guidelines:
                prompt += f"""
IMPORTANT: Follow these email writing guidelines:

{guidelines}

"""
            prompt += """
Please write a thoughtful, professional reply. Be concise but warm. Only provide the email body text, no subject line or signatures."""
        

            # Use Anthropic API to generate reply
            logger.info("Requesting AI-generated reply via Anthropic API...")
            
            # Call Claude API directly
            message = anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            # Extract the generated reply
            generated_reply = message.content[0].text
            
            logger.info(f"Generated reply (first 100 chars): {generated_reply[:100]}...")
            
            # Create draft in Gmail
            gmail_client.create_draft_reply(
                to_email=sender,
                subject=subject,
                body=generated_reply
            )
            
            return [
                TextContent(
                    type="text",
                    text=f"✅ Draft reply created successfully!\n\nGenerated reply:\n{generated_reply}"
                )
            ]
            
        except Exception as e:
            logger.error(f"Error creating draft reply: {e}")
            return [
                TextContent(
                    type="text",
                    text=f"Error creating draft reply: {str(e)}"
                )
            ]
    
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