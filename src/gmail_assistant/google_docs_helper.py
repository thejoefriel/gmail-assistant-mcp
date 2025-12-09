import os
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import logging

logger = logging.getLogger("gmail-assistant")

SCOPES = ['https://www.googleapis.com/auth/documents.readonly']

class GoogleDocsHelper:
    def __init__(self, credentials_path, token_path):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.creds = None
        self.service = None
        
    def authenticate(self):
        """Authenticate with Google Docs API."""
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                self.creds = pickle.load(token)
        
        # If credentials are invalid or don't exist, authenticate
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES)
                self.creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open(self.token_path, 'wb') as token:
                pickle.dump(self.creds, token)
        
        self.service = build('docs', 'v1', credentials=self.creds)
        logger.info("Successfully authenticated with Google Docs API")
    
    def get_document_text(self, document_id):
        """Fetch text content from a Google Doc."""
        if not self.service:
            self.authenticate()
        
        try:
            # Get the document
            document = self.service.documents().get(documentId=document_id).execute()
            
            # Extract text from the document
            doc_content = document.get('body').get('content')
            text = self._read_structural_elements(doc_content)
            
            logger.info(f"Successfully fetched document (length: {len(text)} chars)")
            return text
            
        except Exception as e:
            logger.error(f"Error fetching Google Doc: {e}")
            raise
    
    def _read_structural_elements(self, elements):
        """Recursively read structural elements to extract text."""
        text = ''
        for element in elements:
            if 'paragraph' in element:
                for elem in element.get('paragraph').get('elements'):
                    if 'textRun' in elem:
                        text += elem.get('textRun').get('content')
            elif 'table' in element:
                # Handle tables if needed
                for row in element.get('table').get('tableRows'):
                    for cell in row.get('tableCells'):
                        text += self._read_structural_elements(cell.get('content'))
        return text