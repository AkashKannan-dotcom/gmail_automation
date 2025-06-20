# gmail_client.py

import os
import base64
import email
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from bs4 import BeautifulSoup

# Import configuration constants
from config import CREDENTIALS_FILE, TOKEN_FILE, SCOPES, MAX_EMAIL_FETCH_RESULTS


class GmailClient:
    """
    Manages authentication and interactions with the Gmail API.

    This class handles OAuth 2.0 flow for user authorization, fetches email lists,
    retrieves full email content, and performs actions like marking as read/unread
    and moving messages, and applying labels.
    """

    def __init__(self):
        """
        Initializes the GmailClient, authenticates with Gmail API,
        and builds the service object.
        """
        self.creds = None
        self.service = self._authenticate()
        self.label_id_map = {}  # Cache for label name to ID mapping

    def _authenticate(self):
        """
        Handles OAuth 2.0 authentication flow with Gmail API.

        It first tries to load existing credentials from `TOKEN_FILE`. If not found
        or expired, it initiates the web-based authorization flow using
        `CREDENTIALS_FILE`.

        Returns:
            googleapiclient.discovery.Resource: The authenticated Gmail API service object.
        Raises:
            IOError: If `credentials.json` is not found.
            Exception: For other authentication-related errors.
        """
        print("Authenticating with Gmail API...")

        # The token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists(TOKEN_FILE):
            self.creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        # If there are no (valid) credentials available, let the user log in.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                if not os.path.exists(CREDENTIALS_FILE):
                    raise IOError(
                        f"'{CREDENTIALS_FILE}' not found. "
                        "Please download your OAuth client JSON from Google Cloud Console "
                        "and place it in the project directory."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                self.creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(TOKEN_FILE, 'w') as token:
                token.write(self.creds.to_json())

        try:
            service = build('gmail', 'v1', credentials=self.creds)
            print("Gmail API authentication successful.")
            return service
        except HttpError as error:
            print(f"An HTTP error occurred during authentication: {error}")
            raise
        except Exception as e:
            print(f"An unexpected error occurred during authentication: {e}")
            raise

    def get_emails(self, query='in:inbox', max_results=MAX_EMAIL_FETCH_RESULTS):
        """
        Fetches a list of email messages from the user's Gmail account.

        Args:
            query (str): Gmail search query string (e.g., 'in:inbox', 'is:unread', 'from:sender@example.com').
            max_results (int): Maximum number of email messages to retrieve.

        Returns:
            list: A list of dictionaries, where each dictionary represents an email
                  with 'id', 'threadId', and 'labelIds' (if available).
                  Returns an empty list if no messages are found or an error occurs.
        """
        print(f"Fetching emails with query '{query}' (max results: {max_results})...")
        try:
            # Call the Gmail API to fetch messages
            results = self.service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
            messages = results.get('messages', [])

            if not messages:
                print('No messages found.')
                return []

            print(f'Fetched {len(messages)} message IDs.')
            return messages

        except HttpError as error:
            print(f'An HTTP error occurred while fetching emails: {error}')
            return []
        except Exception as e:
            print(f"An unexpected error occurred while fetching emails: {e}")
            return []

    def get_email_details(self, message_id):
        """
        Retrieves the full details of a specific email message.

        Args:
            message_id (str): The ID of the email message to retrieve.

        Returns:
            dict: A dictionary containing parsed email details (id, threadId, From,
                  Subject, Received Date/Time, Message Body, labelIds).
                  Returns None if the message cannot be retrieved or parsed.
        """
        try:
            # Fetch full message payload
            message = self.service.users().messages().get(userId='me', id=message_id, format='full').execute()

            headers = message['payload']['headers']
            msg_data = {
                'id': message['id'],
                'threadId': message['threadId'],
                'labelIds': message.get('labelIds', []),
                'From': None,
                'Subject': None,
                'Received Date/Time': None,
                'Message Body': None,
            }

            for header in headers:
                if header['name'] == 'From':
                    msg_data['From'] = header['value']
                elif header['name'] == 'Subject':
                    msg_data['Subject'] = header['value']
                elif header['name'] == 'Date':
                    try:
                        # Parse date string to datetime object
                        # Example format: 'Wed, 18 Jun 2025 14:43:00 +0530'
                        parsed_date = email.utils.parsedate_to_datetime(header['value'])
                        msg_data['Received Date/Time'] = parsed_date
                    except ValueError:
                        msg_data['Received Date/Time'] = None  # Could not parse date

            # Extract message body
            msg_data['Message Body'] = self._get_message_body(message['payload'])

            return msg_data

        except HttpError as error:
            print(f'An HTTP error occurred while getting email details for {message_id}: {error}')
            return None
        except Exception as e:
            print(f"An unexpected error occurred while getting email details for {message_id}: {e}")
            return None

    def _get_message_body(self, payload):
        """
        Extracts the plain text message body from the email payload.

        Handles various MIME types (text/plain, text/html, multipart).
        Prioritizes text/plain, then converts HTML to text if only HTML is available.

        Args:
            payload (dict): The 'payload' dictionary from a Gmail message.

        Returns:
            str: The plain text content of the email body, or an empty string if not found.
        """
        parts = payload.get('parts')
        if parts:
            # Look for text/plain part first
            for part in parts:
                mime_type = part.get('mimeType')
                if mime_type == 'text/plain':
                    data = part['body'].get('data')
                    if data:
                        return base64.urlsafe_b64decode(data).decode('utf-8')
                elif mime_type == 'multipart/alternative':
                    # Recursively search in multipart alternatives
                    text_body = self._get_message_body(part)
                    if text_body:
                        return text_body

            # If no text/plain, try to extract from text/html
            for part in parts:
                mime_type = part.get('mimeType')
                if mime_type == 'text/html':
                    data = part['body'].get('data')
                    if data:
                        html_content = base64.urlsafe_b64decode(data).decode('utf-8')
                        soup = BeautifulSoup(html_content, 'html.parser')
                        return soup.get_text()  # Convert HTML to plain text

        # Fallback for messages with no parts (e.g., simple text emails)
        body = payload.get('body')
        if body and body.get('data'):
            return base64.urlsafe_b64decode(body['data']).decode('utf-8')

        return ""  # Return empty string if no body content is found

    def _get_label_id(self, label_name):
        """
        Retrieves the ID for a given Gmail label name.
        Caches results to avoid repeated API calls.

        Args:
            label_name (str): The display name of the Gmail label (e.g., 'Inbox', 'Promotions').

        Returns:
            str: The ID of the label, or None if the label is not found.
        """
        if label_name in self.label_id_map:
            return self.label_id_map[label_name]

        print(f"Attempting to find label ID for '{label_name}'...")
        try:
            results = self.service.users().labels().list(userId='me').execute()
            labels = results.get('labels', [])

            for label in labels:
                if label['name'].upper() == label_name.upper():  # Case-insensitive match
                    self.label_id_map[label_name] = label['id']  # Cache the ID
                    print(f"Found label ID for '{label_name}': {label['id']}")
                    return label['id']
            print(f"Label '{label_name}' not found.")
            return None
        except HttpError as error:
            print(f"An HTTP error occurred while listing labels: {error}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred while getting label ID: {e}")
            return None

    def mark_as_read(self, message_id):
        """
        Marks an email message as read.

        Args:
            message_id (str): The ID of the email message to mark as read.

        Returns:
            bool: True if successful, False otherwise.
        """
        print(f"Marking email {message_id} as read...")
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            print(f"Email {message_id} marked as read successfully.")
            return True
        except HttpError as error:
            print(f"An HTTP error occurred while marking email {message_id} as read: {error}")
            return False
        except Exception as e:
            print(f"An unexpected error occurred while marking email {message_id} as read: {e}")
            return False

    def mark_as_unread(self, message_id):
        """
        Marks an email message as unread.

        Args:
            message_id (str): The ID of the email message to mark as unread.

        Returns:
            bool: True if successful, False otherwise.
        """
        print(f"Marking email {message_id} as unread...")
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'addLabelIds': ['UNREAD']}
            ).execute()
            print(f"Email {message_id} marked as unread successfully.")
            return True
        except HttpError as error:
            print(f"An HTTP error occurred while marking email {message_id} as unread: {error}")
            return False
        except Exception as e:
            print(f"An unexpected error occurred while marking email {message_id} as unread: {e}")
            return False

    def move_message(self, message_id, destination_mailbox):
        """
        Moves an email message to a specified mailbox (label).
        This involves removing it from INBOX (if present) and adding to the destination.

        Args:
            message_id (str): The ID of the email message to move.
            destination_mailbox (str): The name of the target mailbox/label (e.g., 'INBOX', 'Promotions').

        Returns:
            bool: True if successful, False otherwise.
        """
        print(f"Moving email {message_id} to '{destination_mailbox}'...")
        # First, find the label ID for the destination mailbox
        label_id = self._get_label_id(destination_mailbox)

        if not label_id:
            print(f"Could not move email {message_id}: Destination mailbox '{destination_mailbox}' not found or invalid.")
            return False

        try:
            # To move a message, we first remove it from its current labels (like INBOX if it's there)
            # and then add it to the destination label.
            # Note: Removing from 'INBOX' and adding to another label automatically moves it.
            # If the email is already in the destination mailbox, this operation might still succeed
            # but won't change anything.
            current_message = self.service.users().messages().get(userId='me', id=message_id, format='metadata').execute()
            current_label_ids = current_message.get('labelIds', [])

            labels_to_remove = []
            # 'INBOX' is a special label. If moving from INBOX, remove it.
            if 'INBOX' in current_label_ids and destination_mailbox.upper() != 'INBOX':
                labels_to_remove.append('INBOX')

            labels_to_add = [label_id]

            body = {
                'removeLabelIds': labels_to_remove,
                'addLabelIds': labels_to_add
            }

            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body=body
            ).execute()
            print(f"Email {message_id} moved to '{destination_mailbox}' successfully.")
            return True
        except HttpError as error:
            print(f"An HTTP error occurred while moving email {message_id}: {error}")
            return False
        except Exception as e:
            print(f"An unexpected error occurred while moving email {message_id}: {e}")
            return False

    def apply_label(self, message_id, label_name):
        """
        Applies a specified label to an email message.

        Args:
            message_id (str): The ID of the email message to apply the label to.
            label_name (str): The name of the label to apply (e.g., 'Important', 'Work', 'Newsletter').

        Returns:
            bool: True if successful, False otherwise.
        """
        print(f"Applying label '{label_name}' to email {message_id}...")
        label_id = self._get_label_id(label_name)

        if not label_id:
            print(f"Could not apply label to email {message_id}: Label '{label_name}' not found or invalid.")
            return False

        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'addLabelIds': [label_id]}
            ).execute()
            print(f"Label '{label_name}' applied to email {message_id} successfully.")
            return True
        except HttpError as error:
            print(f"An HTTP error occurred while applying label '{label_name}' to email {message_id}: {error}")
            return False
        except Exception as e:
            print(f"An unexpected error occurred while applying label '{label_name}' to email {message_id}: {e}")
            return False
