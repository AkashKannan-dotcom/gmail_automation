# process_emails.py

from database_manager import DatabaseManager
from rule_engine import RuleEngine, Email
from gmail_client import GmailClient


def process_stored_emails():
    """
    Retrieves emails from the local database, applies rules from rules.json,
    and performs actions via the Gmail API.
    """
    print("Starting email processing script...")

    # 1. Initialize Database Manager (to read emails)
    db_manager = None
    try:
        db_manager = DatabaseManager()
    except Exception as e:
        print(f"Failed to initialize DatabaseManager: {e}")
        print("Please check your database configuration.")
        return  # Exit if DBManager cannot be initialized

    # 2. Initialize Gmail Client (to perform actions)
    # The processing script also needs to authenticate to perform actions like mark as read/unread, move, apply label.
    gmail_client = None
    try:
        gmail_client = GmailClient()
    except Exception as e:
        print(f"Failed to initialize GmailClient for processing actions: {e}")
        print("Please ensure your 'credentials.json' is correctly set up and you have internet access.")
        db_manager.close_connection()  # Close DB connection before exiting
        return  # Exit if GmailClient cannot be initialized

    # 3. Retrieve Emails from Database
    print("\nRetrieving emails from the database...")
    db_emails_raw = db_manager.get_all_emails()

    if not db_emails_raw:
        print("No emails found in the database to process.")
        db_manager.close_connection()
        del gmail_client
        return

    # Convert raw database rows into Email objects
    emails_to_process = [Email.from_db_row(row) for row in db_emails_raw]
    print(f"Retrieved {len(emails_to_process)} emails from the database for processing.")

    # 4. Initialize Rule Engine and Process Emails
    print("\nInitializing Rule Engine and processing emails...")
    rule_engine = RuleEngine()  # This will load rules from rules.json

    if rule_engine.rules:
        rule_engine.process_emails(emails_to_process, gmail_client)
    else:
        print("No rules configured. Email processing skipped.")

    # 5. Clean Up
    db_manager.close_connection()
    del gmail_client
    print("\nEmail processing script finished.")


if __name__ == "__main__":
    process_stored_emails()
