# tests/test_database_manager.py

import unittest
import os
from datetime import datetime
import json
from database_manager import DatabaseManager
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestDatabaseManager(unittest.TestCase):
    """
    Unit tests for the DatabaseManager class.
    Uses an in-memory SQLite database for testing to avoid file system side effects.
    """

    # Define an in-memory database name for testing
    TEST_DB_NAME = ':memory:'

    def setUp(self):
        """
        Set up an in-memory database for each test.
        """
        self.db_manager = DatabaseManager(db_name=self.TEST_DB_NAME)
        # Ensure the table is created for the new in-memory DB
        self.db_manager._create_table()  # Call explicitly if needed, though constructor already does this

    def tearDown(self):
        """
        Close the database connection after each test.
        """
        self.db_manager.close_connection()

    def test_connection_and_table_creation(self):
        """
        Test if the database connection is established and the table is created.
        """
        self.assertIsNotNone(self.db_manager.conn)
        self.assertIsNotNone(self.db_manager.cursor)

        # Verify if the 'emails' table exists
        self.db_manager.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='emails';")
        self.assertIsNotNone(self.db_manager.cursor.fetchone())

    def test_insert_email(self):
        """
        Test inserting a new email record.
        """
        email_data = {
            'id': 'test_id_1',
            'threadId': 'thread_id_1',
            'From': 'sender@example.com',
            'Subject': 'Test Subject 1',
            'Received Date/Time': datetime(2023, 1, 15, 10, 30, 0),
            'Message Body': 'This is the body of the test email 1.',
            'labelIds': ['INBOX', 'UNREAD']
        }

        self.assertTrue(self.db_manager.insert_email(email_data))

        # Verify insertion
        self.db_manager.cursor.execute("SELECT * FROM emails WHERE id='test_id_1'")
        row = self.db_manager.cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row['id'], 'test_id_1')
        self.assertEqual(row['from'], 'sender@example.com')
        self.assertEqual(row['subject'], 'Test Subject 1')
        self.assertEqual(row['received_date_time'], email_data['Received Date/Time'].isoformat())
        self.assertEqual(row['message_body'], 'This is the body of the test email 1.')
        self.assertEqual(json.loads(row['label_ids']), ['INBOX', 'UNREAD'])

    def test_insert_email_replace_existing(self):
        """
        Test inserting an email with an existing ID, which should update the record.
        """
        email_data_original = {
            'id': 'test_id_2',
            'threadId': 'thread_id_2',
            'From': 'old@example.com',
            'Subject': 'Old Subject',
            'Received Date/Time': datetime(2023, 2, 1, 9, 0, 0),
            'Message Body': 'Old body.',
            'labelIds': ['INBOX']
        }
        self.db_manager.insert_email(email_data_original)

        email_data_updated = {
            'id': 'test_id_2',  # Same ID
            'threadId': 'thread_2_updated',  # Updated thread ID
            'From': 'new@example.com',  # Updated sender
            'Subject': 'New Subject',
            'Received Date/Time': datetime(2023, 2, 1, 10, 0, 0),
            'Message Body': 'New body content.',
            'labelIds': ['INBOX', 'IMPORTANT']  # Updated labels
        }
        self.assertTrue(self.db_manager.insert_email(email_data_updated))

        # Verify update
        self.db_manager.cursor.execute("SELECT * FROM emails WHERE id='test_id_2'")
        row = self.db_manager.cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row['id'], 'test_id_2')
        self.assertEqual(row['from'], 'new@example.com')
        self.assertEqual(row['subject'], 'New Subject')
        self.assertEqual(row['thread_id'], 'thread_2_updated')
        self.assertEqual(json.loads(row['label_ids']), ['INBOX', 'IMPORTANT'])

        # Ensure only one record exists for this ID
        self.db_manager.cursor.execute("SELECT COUNT(*) FROM emails WHERE id='test_id_2'")
        self.assertEqual(self.db_manager.cursor.fetchone()[0], 1)

    def test_get_all_emails_empty(self):
        """
        Test retrieving all emails when the table is empty.
        """
        emails = self.db_manager.get_all_emails()
        self.assertEqual(len(emails), 0)

    def test_get_all_emails_with_data(self):
        """
        Test retrieving all emails when there is data in the table.
        """
        email_data_1 = {
            'id': 'test_id_3',
            'threadId': 'thread_id_3',
            'From': 'a@example.com',
            'Subject': 'Subject A',
            'Received Date/Time': datetime(2023, 3, 1, 11, 0, 0),
            'Message Body': 'Body A',
            'labelIds': ['INBOX']
        }
        email_data_2 = {
            'id': 'test_id_4',
            'threadId': 'thread_id_4',
            'From': 'b@example.com',
            'Subject': 'Subject B',
            'Received Date/Time': datetime(2023, 3, 2, 12, 0, 0),
            'Message Body': 'Body B',
            'labelIds': ['SENT', 'STARRED']
        }
        self.db_manager.insert_email(email_data_1)
        self.db_manager.insert_email(email_data_2)

        emails = self.db_manager.get_all_emails()
        self.assertEqual(len(emails), 2)

        # Verify content and type conversions
        email1 = next(e for e in emails if e['id'] == 'test_id_3')
        self.assertEqual(email1['from'], 'a@example.com')
        self.assertIsInstance(email1['received_date_time'], datetime)
        self.assertEqual(email1['received_date_time'], email_data_1['Received Date/Time'])
        self.assertEqual(email1['label_ids'], ['INBOX'])

        email2 = next(e for e in emails if e['id'] == 'test_id_4')
        self.assertEqual(email2['subject'], 'Subject B')
        self.assertIsInstance(email2['received_date_time'], datetime)
        self.assertEqual(email2['label_ids'], ['SENT', 'STARRED'])

    def test_get_all_emails_malformed_json_label_ids(self):
        """
        Test handling of malformed JSON for label_ids.
        """
        # Use the db_manager's connection established in setUp
        self.db_manager.cursor.execute(f'''
            INSERT OR REPLACE INTO emails (id, thread_id, "from", subject, received_date_time, message_body, label_ids)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            'malformed_id',
            'thread',
            'mal@formed.com',
            'Malformed',
            datetime.now().isoformat(),
            'Body',
            '{invalid json'  # This is the malformed JSON string
        ))
        self.db_manager.conn.commit()

        emails = self.db_manager.get_all_emails()
        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0]['id'], 'malformed_id')
        self.assertEqual(emails[0]['label_ids'], [])  # Should default to empty list

    def test_insert_many_emails_success(self):
        """
        Test successful bulk insertion of multiple email records.
        """
        emails_data = [
            {
                'id': 'bulk_id_1',
                'threadId': 'bulk_thread_1',
                'From': 'bulk_sender1@example.com',
                'Subject': 'Bulk Subject 1',
                'Received Date/Time': datetime(2024, 1, 1, 12, 0, 0),
                'Message Body': 'This is bulk email 1.',
                'labelIds': ['INBOX']
            },
            {
                'id': 'bulk_id_2',
                'threadId': 'bulk_thread_2',
                'From': 'bulk_sender2@example.com',
                'Subject': 'Bulk Subject 2',
                'Received Date/Time': datetime(2024, 1, 2, 13, 0, 0),
                'Message Body': 'This is bulk email 2.',
                'labelIds': ['STARRED']
            }
        ]

        inserted_count = self.db_manager.insert_many_emails(emails_data)
        self.assertEqual(inserted_count, 2)

        # Verify insertion by fetching all and checking count and content
        fetched_emails = self.db_manager.get_all_emails()
        # Filter for the bulk inserted ones to avoid conflict with other tests
        bulk_emails = [e for e in fetched_emails if e['id'].startswith('bulk_id_')]
        self.assertEqual(len(bulk_emails), 2)

        email1 = next(e for e in bulk_emails if e['id'] == 'bulk_id_1')
        self.assertEqual(email1['from'], 'bulk_sender1@example.com')
        self.assertEqual(email1['subject'], 'Bulk Subject 1')
        self.assertEqual(email1['received_date_time'], datetime(2024, 1, 1, 12, 0, 0))
        self.assertEqual(email1['message_body'], 'This is bulk email 1.')
        self.assertEqual(email1['label_ids'], ['INBOX'])

    def test_insert_many_emails_empty_list(self):
        """
        Test handling of an empty list for bulk insertion.
        """
        inserted_count = self.db_manager.insert_many_emails([])
        self.assertEqual(inserted_count, 0)

        # Ensure no records were added
        emails = self.db_manager.get_all_emails()
        # Filter out any records that might have been inserted by other tests' setUp/tearDown cycles
        # More robust to just check count after _this_ test's setup, which is currently done implicitly.
        self.db_manager.cursor.execute("SELECT COUNT(*) FROM emails")
        self.assertEqual(self.db_manager.cursor.fetchone()[0], 0)

    def test_insert_many_emails_error_handling(self):
        """
        Test error handling during bulk insertion.
        Simulate an error by closing the connection prematurely.
        """
        emails_data = [
            {
                'id': 'error_id_1',
                'threadId': 'error_thread_1',
                'From': 'error_sender@example.com',
                'Subject': 'Error Subject 1',
                'Received Date/Time': datetime(2024, 2, 1, 10, 0, 0),
                'Message Body': 'This should fail.',
                'labelIds': ['INBOX']
            }
        ]

        # Simulate a database error by making the connection invalid
        self.db_manager.conn.close()
        self.db_manager.conn = None  # Explicitly set to None to simulate broken connection
        self.db_manager.cursor = None  # Also invalidate cursor

        # The method should catch the error and return 0
        inserted_count = self.db_manager.insert_many_emails(emails_data)
        self.assertEqual(inserted_count, 0)


if __name__ == '__main__':
    unittest.main()
