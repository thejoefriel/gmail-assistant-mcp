import logging
from mcp.types import Tool, TextContent
from gmail_client import GmailClient
from google_docs_helper import GoogleDocsHelper
from anthropic import Anthropic
from helpers.prompt_builder import fetch_guidelines, build_reply_prompt

logger = logging.getLogger("gmail-assistant")

def get_tool_definition() -> Tool:
    """Return the tool definition for MCP."""
    return Tool(
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

async def handle(
    gmail_client: GmailClient,
    anthropic_client: Anthropic,
    google_docs_helper: GoogleDocsHelper,
    guidelines_doc_id: str,
    arguments: dict
) -> list[TextContent]:
    """Handle the create_draft_reply tool call."""
    email_id = arguments.get("email_id")
    email_content = arguments.get("email_content")
    sender = arguments.get("sender")
    subject = arguments.get("subject")
    
    try:
        # Fetch guidelines
        guidelines = await fetch_guidelines(google_docs_helper, guidelines_doc_id)

        # Build the prompt
        prompt = build_reply_prompt(sender, subject, email_content, guidelines)

        # Generate reply
        logger.info("Requesting AI-generated reply via Anthropic API...")
        
        message = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        
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