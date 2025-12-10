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

# Helper function to fetch guidelines
async def fetch_guidelines():
    """Fetch email guidelines from Google Doc if available."""
    if not google_docs_helper or not GUIDELINES_DOC_ID:
        return ""
    
    logger.info("Fetching email guidelines from Google Doc...")
    
    try:
        guidelines = google_docs_helper.get_document_text(GUIDELINES_DOC_ID)
        logger.info(f"Guidelines fetched successfully ({len(guidelines)} chars)")
        return guidelines
    except Exception as e:
        logger.warning(f"Could not fetch guidelines: {e}")
        return ""

# Helper function to build prompt with guidelines
def build_reply_prompt(sender, subject, email_content, guidelines):
    """Build prompt for generating email with guidelines."""
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
Please write a thoughtful, professional reply. Be concise but warm. Aim to reply in 3-4 short paragraphs maximum. Only provide the email body text, no subject line or signatures."""
     
    return prompt



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
        ),
        Tool(
            name="get_unread_and_draft_replies",
            description="Fetch unread emails and automatically create AI-powered draft replies for all emails sent directly to you (not CC'd)",
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
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    if name == "get_unread_emails":
        max_results = arguments.get("max_results", 10)
        
        try:
            emails = gmail_client.get_unread_emails(max_results=max_results)

            # Format the grouped results
            result = f"""📧 UNREAD EMAILS (Latest {max_results})

    📩 DIRECTLY TO YOU ({len(emails['to_me'])} emails):
    {json.dumps(emails['to_me'], indent=2)}

    📋 CC'D TO YOU ({len(emails['cc_me'])} emails):
    {json.dumps(emails['cc_me'], indent=2)}
    """

            return [
                TextContent(
                    type="text",
                    text=result
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
            guidelines = await fetch_guidelines()

            # Build the prompt with guidelines
            prompt = build_reply_prompt(sender, subject, email_content, guidelines)

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
    
    elif name == "get_unread_and_draft_replies":
        max_results = arguments.get("max_results", 10)

        try:
            # Fetch emails
            emails = gmail_client.get_unread_emails(max_results=max_results)
            to_me_emails = emails['to_me']
        
            if not to_me_emails:
                return [
                    TextContent(
                        type="text",
                        text="📭 No unread emails sent directly to you!"
                    )
                ]
            
            # Fetch guidelines once using helper
            guidelines = await fetch_guidelines()
            
            # Create drafts for all "To Me" emails
            results = []
            for email_item in to_me_emails:
                try:
                    logger.info(f"Creating draft for email from {email_item['from']}")
                    
                    # Build prompt using helper
                    prompt = build_reply_prompt(
                        email_item['from'],
                        email_item['subject'],
                        email_item['body'],
                        guidelines
                    )
                    
                    # Generate reply using Claude
                    message = anthropic_client.messages.create(
                        model="claude-sonnet-4-20250514",
                        max_tokens=1000,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    
                    generated_reply = message.content[0].text
                    
                    # Create draft in Gmail
                    gmail_client.create_draft_reply(
                        to_email=email_item['from'],
                        subject=email_item['subject'],
                        body=generated_reply
                    )
                    
                    results.append({
                        "from": email_item['from'],
                        "subject": email_item['subject'],
                        "status": "✅ Draft created",
                        "preview": generated_reply[:100] + "..."
                    })
                    
                except Exception as e:
                    logger.error(f"Error creating draft for {email_item['from']}: {e}")
                    results.append({
                        "from": email_item['from'],
                        "subject": email_item['subject'],
                        "status": f"❌ Failed: {str(e)}"
                    })
            
            # Format summary
            summary = f"""📧 Processed {len(to_me_emails)} emails sent directly to you:

    """
            for result in results:
                summary += f"\n{result['status']} - From: {result['from']}\n   Subject: {result['subject']}\n"
                if 'preview' in result:
                    summary += f"   Preview: {result['preview']}\n"
            
            summary += f"\n\n📋 Skipped {len(emails['cc_me'])} CC'd emails (no drafts created)"
            
            return [
                TextContent(
                    type="text",
                    text=summary
                )
            ]
        
        except Exception as e:
            logger.error(f"Error in get_unread_and_draft_replies: {e}")
            return [
                TextContent(
                    type="text",
                    text=f"Error: {str(e)}"
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