# Gmail Assistant MCP

MCP server that integrates with Gmail to fetch unread emails and generate draft emails using Claude.
Also connects with a Google Doc file that outlines my writing style and useful context.

## How it works

- Ask Claude to fetch emails
- Ask Claude to draft replies to any of those emails

## Requirements

- Python 3.10+
- Gmail account with App Password enabled
- Anthropic API key
- Google Cloud project with Docs API enabled (optional, for guidelines)

## Installation

1. Clone the repo
2. Create an activate virtual environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies

4. Set up Gmail App Password (via https://myaccount.google.com/security)

5. Set up Google Docs API for guidelines (via https://console.cloud.google.com/)
   a. Create a project
   b. Enable Google Docs API
   c. Create credentials
   d. Download credentials as `credentials.json` in project root

## Configuration

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "gmail-assistant": {
      "command": "/path/to/gmail-assistant-mcp/venv/bin/python",
      "args": ["/path/to/gmail-assistant-mcp/src/gmail_assistant/server.py"],
      "env": {
        "EMAIL_USER": "your.email@gmail.com",
        "EMAIL_APP_PASSWORD": "your-app-password",
        "ANTHROPIC_API_KEY": "your-anthropic-api-key",
        "GUIDELINES_DOC_ID": "your-google-doc-id-optional"
      }
    }
  }
}
```
