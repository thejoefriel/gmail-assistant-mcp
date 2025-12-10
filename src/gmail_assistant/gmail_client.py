import imaplib
import smtplib
import datetime
import email
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

logger = logging.getLogger("gmail-assistant")

class GmailClient:
    def __init__(self, email_address: str, app_password: str):
        self.email_address = email_address
        self.app_password = app_password
        self.imap = None
    
    def connect(self):
        """Connect to Gmail via IMAP."""
        try:
            self.imap = imaplib.IMAP4_SSL("imap.gmail.com")
            self.imap.login(self.email_address, self.app_password)
            logger.info("Successfully connected to Gmail")
        except Exception as e:
            logger.error(f"Failed to connect to Gmail: {e}")
            raise
    
    def get_unread_emails(self, max_results: int = 10):
        """Fetch unread emails."""
        if not self.imap:
            self.connect()
        
        # Select inbox
        self.imap.select("INBOX")
        
        # Search for unread emails
        status, messages = self.imap.search(None, "UNSEEN")
        
        if status != "OK":
            return {"to_me": [], "cc_me": []}
        
        email_ids = messages[0].split()
        email_ids = email_ids[-max_results:]  # Get latest N emails
        
        to_me = []
        cc_me = []
        
        for email_id in email_ids:
            try:
                # Fetch email data
                status, msg_data = self.imap.fetch(email_id, "(RFC822)")
                
                if status != "OK":
                    continue
                
                # Parse email
                msg = email.message_from_bytes(msg_data[0][1])
                
                # Decode subject
                subject = self._decode_header(msg["Subject"])
                from_addr = msg["From"]
                date = msg["Date"]

                # Get To and CC fields - they might be tuples or strings
                to_field = msg.get("To", "")
                cc_field = msg.get("Cc", "")

                # Convert to string if tuple
                if isinstance(to_field, tuple):
                    to_field = ", ".join(str(x) for x in to_field)
                if isinstance(cc_field, tuple):
                    cc_field = ", ".join(str(x) for x in cc_field)

                # Ensure they're strings
                to_field = str(to_field) if to_field else ""
                cc_field = str(cc_field) if cc_field else ""
                
                # Get email body
                body = self._get_email_body(msg)

                email_data = {
                "id": email_id.decode(),
                "from": from_addr,
                "subject": subject,
                "date": date,
                "to": to_field,
                "cc": cc_field,
                "body": body[:2000] if body else ""
            }
                
            # Check if user email is in To or CC field
                if self.email_address.lower() in to_field.lower():
                    to_me.append(email_data)
                elif self.email_address.lower() in cc_field.lower():
                    cc_me.append(email_data)
                else:
                    # If we can't determine, put in to_me as default
                    to_me.append(email_data)
            except Exception as e:
                logger.error(f"Error processing email {email_id}: {e}")
                continue
        return {"to_me": to_me, "cc_me": cc_me}
    
    def _decode_header(self, header):
        """Decode email header."""
        if header is None:
            return ""
        decoded = decode_header(header)
        return "".join([
            text.decode(encoding or "utf-8") if isinstance(text, bytes) else text
            for text, encoding in decoded
        ])
    
    def _get_email_body(self, msg):
        """Extract email body."""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    return part.get_payload(decode=True).decode()
        else:
            return msg.get_payload(decode=True).decode()
        return ""
    
    def create_draft_reply(self, to_email: str, subject: str, body: str, in_reply_to: str = None):
        """Create a draft reply in Gmail using SMTP."""
        try:
            # Connect to Gmail SMTP
            smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465)
            smtp.login(self.email_address, self.app_password)
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.email_address
            msg['To'] = to_email
            msg['Subject'] = f"Re: {subject}" if not subject.startswith("Re:") else subject
            
            # Add In-Reply-To header if provided
            if in_reply_to:
                msg['In-Reply-To'] = in_reply_to
                msg['References'] = in_reply_to
            
            # Add body
            msg.attach(MIMEText(body, 'plain'))
            
            # Connect to IMAP to save as draft
            if not self.imap:
                self.connect()
            
            # Save to Drafts folder
            self.imap.select('[Gmail]/Drafts')
            self.imap.append(
                '[Gmail]/Drafts',
                '',
                imaplib.Time2Internaldate(datetime.datetime.now(datetime.timezone.utc)),
                msg.as_bytes()
            )
            
            smtp.quit()
            logger.info(f"Draft reply created for {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating draft reply: {e}")
            raise
            
    def close(self):
        """Close IMAP connection."""
        if self.imap:
            self.imap.close()
            self.imap.logout()