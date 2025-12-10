import logging
from google_docs_helper import GoogleDocsHelper

logger = logging.getLogger("gmail-assistant")

async def fetch_guidelines(google_docs_helper: GoogleDocsHelper, guidelines_doc_id: str) -> str:
    """Fetch email guidelines from Google Doc if available."""
    if not google_docs_helper or not guidelines_doc_id:
        return ""
    
    logger.info("Fetching email guidelines from Google Doc...")
    
    try:
        guidelines = google_docs_helper.get_document_text(guidelines_doc_id)
        logger.info(f"Guidelines fetched successfully ({len(guidelines)} chars)")
        return guidelines
    except Exception as e:
        logger.warning(f"Could not fetch guidelines: {e}")
        return ""

def build_reply_prompt(sender: str, subject: str, email_content: str, guidelines: str) -> str:
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
Please write a thoughtful, professional reply. Keep it concise and focused - aim for 2-3 short paragraphs maximum. Be warm but efficient. Only provide the email body text, no subject line or signatures.

IMPORTANT: Keep your response under 200 words. Get straight to the point."""
     
    return prompt