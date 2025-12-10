import json
import logging
from mcp.types import Tool, TextContent
from gmail_client import GmailClient

logger = logging.getLogger("gmail-assistant")

def get_tool_definition() -> Tool:
    """Return the tool definition for MCP."""
    return Tool(
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
    )

async def handle(gmail_client: GmailClient, arguments: dict) -> list[TextContent]:
    """Handle the get_unread_emails tool call."""
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