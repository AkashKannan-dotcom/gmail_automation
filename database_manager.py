# database_manager.py

import sqlite3
import json
from datetime import datetime

# Import configuration constants
from config import DATABASE_NAME


class DatabaseManager:
    """
    Manages SQLite database operations for storing and retrieving email data.

    This class handles database connection, table creation, and CRUD operations
    for email records. It serializes and deserializes date objects for storage.
    """

    def __init__(self, db_name=DATABASE_NAME):
        """
        Initializes the DatabaseManager and establishes a connection to the SQLite database.
        Creates the 'emails' table if it does not exist.

        Args:
            db_name (str): The name of the SQLite database file.
        """
        self.db_name = db_name
        self.conn = None
        self.cursor = None
        self._connect()
        self._create_table()

    def _connect(self):
        """Establishes a connection to the SQLite database."""
        try:
            self.conn = sqlite3.connect(self.db_name)
            self.conn.row_factory = sqlite3.Row  # Allows accessing columns by name
            self.cursor = self.conn.cursor()
            print(f"Connected to database: {self.db_name}")
        except sqlite3.Error as e:
            print(f"Error connecting to database: {e}")
            raise  # Re-raise the exception to indicate a critical error

    def _create_table(self):
        """
        Creates the 'emails' table in the database if it doesn't already exist.
        The table schema is designed to store relevant email metadata.
        """
        try:
            self.cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS emails (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT,
                    "from" TEXT,
                    subject TEXT,
                    received_date_time TEXT, -- Stored as ISO format string
                    message_body TEXT,
                    label_ids TEXT -- Stored as JSON string
                )
            ''')
            self.conn.commit()
            print("Table 'emails' ensured to exist.")
        except sqlite3.Error as e:
            print(f"Error creating table: {e}")
            self.conn.rollback()
            raise

    def insert_email(self, email_data):
        """
        Inserts a single email record into the 'emails' table.
        If an email with the same ID already exists, it updates the existing record.

        Args:
            email_data (dict): A dictionary containing email details.
                               Expected keys: 'id', 'threadId', 'From', 'Subject',
                               'Received Date/Time' (datetime object), 'Message Body', 'labelIds'.
        Returns:
            bool: True if the operation was successful, False otherwise.
        """
        try:
            # Convert datetime object to ISO format string for storage
            received_dt = email_data.get('Received Date/Time')
            if isinstance(received_dt, datetime):
                received_date_time_str = received_dt.isoformat()
            elif isinstance(received_dt, str):
                received_date_time_str = received_dt  # Assume it's already in ISO format
            else:
                received_date_time_str = None
            # Convert list of label_ids to JSON string for storage
            label_ids_json = json.dumps(email_data.get('labelIds', []))

            self.cursor.execute(f'''
                INSERT OR REPLACE INTO emails (id, thread_id, "from", subject, received_date_time, message_body, label_ids)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                email_data['id'],
                email_data['threadId'],
                email_data['From'],
                email_data['Subject'],
                received_date_time_str,
                email_data['Message Body'],
                label_ids_json
            ))
            self.conn.commit()
            # print(f"Email {email_data['id']} inserted/updated successfully.")
            return True
        except sqlite3.Error as e:
            print(f"Error inserting/updating email {email_data.get('id')}: {e}")
            self.conn.rollback()
            return False

    def insert_many_emails(self, email_data_list):
        """
        Inserts multiple email records into the 'emails' table in a single transaction.
        If an email with the same ID already exists, it updates the existing record.
        The 'Received Date/Time' field in email_data_list is expected to already be an ISO string.

        Args:
            email_data_list (list): A list of dictionaries, where each dictionary
                                    contains email details. The 'Received Date/Time'
                                    should already be a string (from Email.to_dict()).
        Returns:
            int: The number of emails successfully inserted/updated.
        """
        if not email_data_list:
            print("No emails provided for bulk insertion.")
            return 0

        data_to_insert = []
        for email_data in email_data_list:
            received_date_time_str = email_data['Received Date/Time']
            label_ids_json = json.dumps(email_data.get('labelIds', []))
            data_to_insert.append((
                email_data['id'],
                email_data['threadId'],
                email_data['From'],
                email_data['Subject'],
                received_date_time_str,
                email_data['Message Body'],
                label_ids_json
            ))

        try:
            if self.cursor is None:
                raise sqlite3.Error("Database cursor is not available. Connection may be closed or failed.")

            self.cursor.executemany(f'''
                INSERT OR REPLACE INTO emails (id, thread_id, "from", subject, received_date_time, message_body, label_ids)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', data_to_insert)
            self.conn.commit()
            print(f"Successfully performed bulk insert/update of {len(email_data_list)} emails.")
            return len(email_data_list)
        except (sqlite3.Error, AttributeError) as e:
            print(f"Error during bulk insertion of emails: {e}")
            if self.conn:
                self.conn.rollback()
            return 0

    def get_all_emails(self):
        """
        Retrieves all email records from the 'emails' table.

        Returns:
            list: A list of dictionaries, where each dictionary represents an email.
                  Date strings are converted back to datetime objects and
                  label_ids JSON strings are converted back to lists.
        """
        try:
            self.cursor.execute('SELECT * FROM emails')
            rows = self.cursor.fetchall()
            emails = []
            for row in rows:
                email_dict = dict(row)  # Convert Row object to dictionary

                # Convert received_date_time string back to datetime object
                if email_dict['received_date_time']:
                    email_dict['received_date_time'] = datetime.fromisoformat(email_dict['received_date_time'])

                # Convert label_ids JSON string back to list
                if email_dict['label_ids']:
                    try:
                        email_dict['label_ids'] = json.loads(email_dict['label_ids'])
                    except json.JSONDecodeError:
                        email_dict['label_ids'] = []  # Handle malformed JSON
                else:
                    email_dict['label_ids'] = []

                # Remap keys to match expected format for RuleEngine if needed
                # Current keys are snake_case from DB. RuleEngine expects PascalCase for fields.
                # It's better to process this mapping when building Email objects for RuleEngine.
                emails.append(email_dict)
            return emails
        except sqlite3.Error as e:
            print(f"Error fetching all emails: {e}")
            return []

    def close_connection(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()
            print("Database connection closed.")

