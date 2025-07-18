# fetch_and_store.py

from gmail_client import GmailClient
from database_manager import DatabaseManager
from rule_engine import Email  # Only need Email class for object creation
# import time # No longer needed for individual inserts
from datetime import datetime  # For date parsing safeguard
import email.utils  # For robust date parsing


def fetch_and_store_emails():
    """
    Authenticates with Gmail API, fetches emails, and stores their details
    in the local SQLite database using bulk insertion for efficiency.
    """
    print("Starting email fetching and storage script...")

    # 1. Initialize Gmail Client
    gmail_client = None
    try:
        gmail_client = GmailClient()
    except Exception as e:
        print(f"Failed to initialize GmailClient: {e}")
        print("Please ensure your 'credentials.json' is correctly set up and you have internet access.")
        return  # Exit if GmailClient cannot be initialized

    # 2. Initialize Database Manager
    db_manager = None
    try:
        db_manager = DatabaseManager()
    except Exception as e:
        print(f"Failed to initialize DatabaseManager: {e}")
        print("Please check your database configuration.")
        if gmail_client:
            del gmail_client
        return  # Exit if DBManager cannot be initialized

    # 3. Fetch Emails from Gmail
    print("\nFetching emails from Gmail...")
    #TODO: Fetching from 'in:inbox' for now. Can be modified to fetch 'all_mail' etc.
    gmail_messages_ids = gmail_client.get_emails(query='in:inbox')

    emails_to_store_in_db = []
    if gmail_messages_ids:
        print(f"Fetched {len(gmail_messages_ids)} message IDs from Gmail.")
        for msg_id_dict in gmail_messages_ids:
            message_id = msg_id_dict['id']
            email_details = gmail_client.get_email_details(message_id)

            if email_details:
                # --- Safeguard for 'Received Date/Time' type consistency ---
                received_dt = email_details.get('Received Date/Time')
                if isinstance(received_dt, str):
                    try:
                        parsed_dt = email.utils.parsedate_to_datetime(received_dt)
                        if parsed_dt:
                            received_dt = parsed_dt
                        else:
                            received_dt = None
                    except (ValueError, TypeError):
                        received_dt = None
                elif not isinstance(received_dt, datetime):
                    received_dt = None
                # --- End Safeguard ---

                email_obj = Email(
                    id=email_details['id'],
                    thread_id=email_details['threadId'],
                    from_address=email_details['From'],
                    subject=email_details['Subject'],
                    received_date_time=received_dt,
                    message_body=email_details['Message Body'],
                    label_ids=email_details['labelIds']
                )
                emails_to_store_in_db.append(email_obj.to_dict())

        # Perform bulk insert after collecting all email data
        if emails_to_store_in_db:
            stored_count = db_manager.insert_many_emails(emails_to_store_in_db)
            print(f"Successfully processed and stored {stored_count} emails in the database.")
        else:
            print("No valid emails found to store after fetching.")
    else:
        print("No emails found in Gmail to store.")

    # Clean Up
    db_manager.close_connection()
    print("Email fetching and storage script finished.")


if __name__ == "__main__":
    fetch_and_store_emails()
