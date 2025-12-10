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

async def handle(
    gmail_client: GmailClient,
    anthropic_client: Anthropic,
    google_docs_helper: GoogleDocsHelper,
    guidelines_doc_id: str,
    arguments: dict
) -> list[TextContent]:
    """Handle the get_unread_and_draft_replies tool call."""
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
        
        # Fetch guidelines once
        guidelines = await fetch_guidelines(google_docs_helper, guidelines_doc_id)
        
        # Create drafts for all "To Me" emails
        results = []
        for email_item in to_me_emails:
            try:
                logger.info(f"Creating draft for email from {email_item['from']}")
                
                # Build prompt
                prompt = build_reply_prompt(
                    email_item['from'],
                    email_item['subject'],
                    email_item['body'],
                    guidelines
                )
                
                # Generate reply
                message = anthropic_client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1000,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                generated_reply = message.content[0].text
                
                # Create draft
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