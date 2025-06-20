# tests/test_gmail_client.py

import unittest
from unittest.mock import MagicMock, patch
import os
from datetime import datetime
import json
import base64
from bs4 import BeautifulSoup
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gmail_client import GmailClient
from config import TOKEN_FILE, CREDENTIALS_FILE


class TestGmailClient(unittest.TestCase):
    """
    Unit tests for the GmailClient class.
    Mocks external dependencies like Google API client and file system operations.
    """

    @patch('gmail_client.os.path.exists')
    @patch('gmail_client.InstalledAppFlow.from_client_secrets_file')
    @patch('gmail_client.build')
    @patch('gmail_client.open', MagicMock())
    def setUp(self, mock_build, mock_flow_from_file, mock_os_exists):
        """
        Set up for each test. Mocks authentication flow and Gmail API service.
        """
        # Mock the flow.run_local_server() return value (credentials object)
        self.mock_creds = MagicMock()
        self.mock_creds.valid = True
        self.mock_creds.expired = False
        self.mock_creds.to_json.return_value = '{"mock_token": "some_value"}'
        mock_flow_from_file.return_value.run_local_server.return_value = self.mock_creds

        # Configure the return value for gmail_client.build() directly
        self.mock_service = MagicMock()
        mock_build.return_value = self.mock_service

        # Configure common chained calls that GmailClient makes on the mock_service
        self.mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            'messages': [{'id': 'msg1', 'threadId': 'thread1'}, {'id': 'msg2', 'threadId': 'thread2'}]
        }

        # Mock for messages().get().execute()
        # Create a mock for the result of .get() call
        self.mock_get_response = MagicMock()
        self.mock_service.users.return_value.messages.return_value.get.return_value = self.mock_get_response

        # Set a default return value for execute() on this mock_get_response
        self.mock_get_response.execute.return_value = {
            'id': 'msg1',
            'threadId': 'thread1',
            'labelIds': ['INBOX', 'UNREAD'],
            'payload': {
                'headers': [
                    {'name': 'From', 'value': 'test_sender@example.com'},
                    {'name': 'Subject', 'value': 'Test Subject 1'},
                    {'name': 'Date', 'value': 'Wed, 18 Jun 2025 14:43:00 +0530'}
                ],
                'parts': [
                    {'mimeType': 'text/plain',
                     'body': {'data': base64.urlsafe_b64encode(b'Test plain text body').decode('utf-8')}},
                    {'mimeType': 'text/html', 'body': {
                        'data': base64.urlsafe_b64encode(b'<html><body><p>Test HTML body</p></body></html>').decode(
                            'utf-8')}}
                ]
            }
        }

        self.mock_service.users.return_value.messages.return_value.modify.return_value.execute.return_value = {}
        self.mock_service.users.return_value.labels.return_value.list.return_value.execute.return_value = {
            'labels': [
                {'id': 'INBOX', 'name': 'INBOX'},
                {'id': 'Label_1', 'name': 'Promotions'},
                {'id': 'Label_2', 'name': 'Important'},
                {'id': 'Label_3', 'name': 'Newsletter'},
                {'id': 'Label_4', 'name': 'Archive_2024'}
            ]
        }

        # Ensure credentials.json exists for the flow to be created
        mock_os_exists.side_effect = lambda x: x == CREDENTIALS_FILE

        self.client = GmailClient()

    def tearDown(self):
        """Clean up after each test if necessary."""
        pass

    def test_authentication_success(self):
        """Test if authentication completes successfully."""
        self.assertIsNotNone(self.client.service)

    def test_get_emails_success(self):
        """Test successful fetching of email IDs."""
        messages = self.client.get_emails(query='is:unread')
        self.assertIsInstance(messages, list)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]['id'], 'msg1')
        self.mock_service.users.return_value.messages.return_value.list.assert_called_once_with(
            userId='me', q='is:unread', maxResults=50
        )

    def test_get_emails_no_messages(self):
        """Test fetching when no messages are found."""
        self.mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            'messages': []
        }
        messages = self.client.get_emails()
        self.assertEqual(messages, [])

    def test_get_email_details_success(self):
        """Test successful retrieval and parsing of email details."""
        # This test relies on the default mock_get_response.execute.return_value from setUp
        details = self.client.get_email_details('msg1')
        self.assertIsNotNone(details)
        self.assertEqual(details['id'], 'msg1')
        self.assertEqual(details['From'], 'test_sender@example.com')
        self.assertEqual(details['Subject'], 'Test Subject 1')
        self.assertIsInstance(details['Received Date/Time'], datetime)
        self.assertEqual(details['Received Date/Time'].year, 2025)
        self.assertIn('Test plain text body', details['Message Body'])
        self.mock_service.users.return_value.messages.return_value.get.assert_called_once_with(
            userId='me', id='msg1', format='full'
        )

    @patch('gmail_client.BeautifulSoup', wraps=BeautifulSoup)
    def test_get_message_body_html_fallback(self, mock_bs4):
        """Test message body extraction when only HTML part is available."""
        html_payload = {
            'headers': [
                {'name': 'From', 'value': 'test@example.com'},
                {'name': 'Subject', 'value': 'HTML Only Email'},
                {'name': 'Date', 'value': 'Wed, 18 Jun 2025 14:43:00 +0530'}
            ],
            'parts': [
                {
                    'mimeType': 'text/html',
                    'body': {
                        'data': base64.urlsafe_b64encode(
                            b'<html><body><h1>Hello</h1><p>World</p></body></html>'
                        ).decode('utf-8')
                    }
                }
            ]
        }

        users_mock = self.mock_service.users.return_value
        messages_mock = users_mock.messages.return_value
        get_mock = messages_mock.get.return_value
        get_mock.execute.return_value = {
            'id': 'msg_html',
            'threadId': 'thread123',
            'labelIds': ['INBOX'],
            'payload': html_payload
        }

        details = self.client.get_email_details('msg_html')
        self.assertIsNotNone(details)
        self.assertIn('Hello', details['Message Body'])
        self.assertIn('World', details['Message Body'])
        mock_bs4.assert_called_once()
        messages_mock.get.assert_called_once_with(userId='me', id='msg_html', format='full')

    def test_get_message_body_plain_priority(self):
        """Test message body extraction prioritizes plain text over HTML."""
        plain_html_payload = {
            'headers': [
                {'name': 'From', 'value': 'test@example.com'},
                {'name': 'Subject', 'value': 'Plain Then HTML'},
                {'name': 'Date', 'value': 'Wed, 18 Jun 2025 14:43:00 +0530'}
            ],
            'parts': [
                {
                    'mimeType': 'text/plain',
                    'body': {
                        'data': base64.urlsafe_b64encode(
                            b'Plain text preferred'
                        ).decode('utf-8')
                    }
                },
                {
                    'mimeType': 'text/html',
                    'body': {
                        'data': base64.urlsafe_b64encode(
                            b'<html><body>HTML content</body></html>'
                        ).decode('utf-8')
                    }
                }
            ]
        }

        users_mock = self.mock_service.users.return_value
        messages_mock = users_mock.messages.return_value
        get_mock = messages_mock.get.return_value
        get_mock.execute.return_value = {
            'id': 'msg_plain_html',
            'threadId': 'thread456',
            'labelIds': ['INBOX'],
            'payload': plain_html_payload
        }

        details = self.client.get_email_details('msg_plain_html')
        self.assertIsNotNone(details)
        self.assertEqual('Plain text preferred', details['Message Body'])
        messages_mock.get.assert_called_once_with(userId='me', id='msg_plain_html', format='full')

    def test_mark_as_read_success(self):
        """Test marking an email as read."""
        self.mock_service.users().messages().modify.reset_mock()  # Reset mock for this test
        result = self.client.mark_as_read('msg1')
        self.assertTrue(result)
        self.mock_service.users.return_value.messages.return_value.modify.assert_called_once_with(
            userId='me', id='msg1', body={'removeLabelIds': ['UNREAD']}
        )

    def test_mark_as_unread_success(self):
        """Test marking an email as unread."""
        self.mock_service.users().messages().modify.reset_mock()  # Reset mock for this test
        result = self.client.mark_as_unread('msg1')
        self.assertTrue(result)
        self.mock_service.users.return_value.messages.return_value.modify.assert_called_once_with(
            userId='me', id='msg1', body={'addLabelIds': ['UNREAD']}
        )

    def test_move_message_success(self):
        """Test moving a message to a valid label."""
        self.mock_service.users().messages().modify.reset_mock()  # Reset modify mock
        self.mock_service.users().labels().list.return_value.execute.reset_mock()  # Reset labels list mock

        # Configure the mock for current message labels for this specific test's move
        self.mock_get_response.execute.return_value = {'id': 'msg_moved_test', 'labelIds': ['INBOX']}

        result = self.client.move_message('msg_moved_test', 'Promotions')
        self.assertTrue(result)
        self.mock_service.users().labels().list.assert_called_once()  # Should be called to get label ID
        self.mock_service.users().messages().modify.assert_called_once_with(
            userId='me', id='msg_moved_test', body={'removeLabelIds': ['INBOX'], 'addLabelIds': ['Label_1']}
        )

    def test_move_message_invalid_mailbox(self):
        """Test moving a message to a non-existent mailbox."""
        self.mock_service.users.return_value.labels.return_value.list.return_value.execute.return_value = {
            'labels': []  # No labels available to simulate non-existent
        }
        self.mock_service.users().messages().modify.reset_mock()  # Reset mock for modify
        result = self.client.move_message('msg1', 'NonExistentMailbox')
        self.assertFalse(result)
        self.mock_service.users.return_value.messages.return_value.modify.assert_not_called()

    def test_apply_label_success(self):
        """Test applying a label to a message."""
        self.mock_service.users().messages().return_value.modify.reset_mock()  # Reset modify mock
        self.mock_service.users().labels().list.return_value.execute.reset_mock()  # Reset labels list mock

        result = self.client.apply_label('msg1', 'Important')
        self.assertTrue(result)
        self.mock_service.users().labels().list.assert_called_once()  # Should be called to get label ID
        self.mock_service.users().messages().modify.assert_called_once_with(
            userId='me', id='msg1', body={'addLabelIds': ['Label_2']}
        )

    def test_apply_label_invalid_label(self):
        """Test applying a non-existent label."""
        self.mock_service.users.return_value.labels.return_value.list.return_value.execute.return_value = {
            'labels': []  # No labels available to simulate non-existent
        }
        self.mock_service.users().messages().modify.reset_mock()  # Reset modify mock
        result = self.client.apply_label('msg1', 'NonExistentLabel')
        self.assertFalse(result)
        self.mock_service.users.return_value.messages.return_value.modify.assert_not_called()

    @patch('gmail_client.os.path.exists', return_value=True)
    @patch('gmail_client.Credentials.from_authorized_user_file')
    @patch('gmail_client.build')
    def test_authentication_from_token_file(self, mock_build, mock_creds_from_file, mock_os_exists):
        """Test authentication directly from an existing token.json."""
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds.expired = False
        mock_creds.to_json.return_value = '{"mock_token": "some_value"}'
        mock_creds_from_file.return_value = mock_creds

        mock_build.return_value = MagicMock()

        client = GmailClient()
        self.assertIsNotNone(client.service)
        mock_creds_from_file.assert_called_once_with(TOKEN_FILE, ['https://www.googleapis.com/auth/gmail.readonly',
                                                                  'https://www.googleapis.com/auth/gmail.modify'])
        self.assertFalse(client.creds.expired)

    @patch('gmail_client.os.path.exists', side_effect=lambda x: x == TOKEN_FILE)
    @patch('gmail_client.Credentials.from_authorized_user_file')
    @patch('gmail_client.build')
    def test_authentication_refresh_token(self, mock_build, mock_creds_from_file, mock_os_exists):
        """Test authentication when token exists but is expired, triggering refresh."""
        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = 'some_refresh_token'
        mock_creds.to_json.return_value = '{"mock_token": "some_value"}'

        def simulate_creds_refresh(*args, **kwargs):
            mock_creds.valid = True
            mock_creds.expired = False

        mock_creds.refresh.side_effect = simulate_creds_refresh

        mock_creds_from_file.return_value = mock_creds

        mock_build.return_value = MagicMock()

        with patch('gmail_client.Request') as MockRequest:
            client = GmailClient()
            self.assertIsNotNone(client.service)
            mock_creds.refresh.assert_called_once_with(MockRequest.return_value)
            self.assertFalse(client.creds.expired)
            self.assertTrue(client.creds.valid)


if __name__ == '__main__':
    unittest.main()
