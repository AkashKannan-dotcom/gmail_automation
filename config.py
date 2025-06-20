# config.py

# --- Google API Configuration ---
# Path to your downloaded client_secret.json (or credentials.json) file.
# This file contains your OAuth 2.0 client ID and secret.
CREDENTIALS_FILE = 'credentials.json'

# Token file generated after the first successful authentication.
# This stores the user's refresh token for subsequent runs.
TOKEN_FILE = 'token.json'

# Scopes define the permissions your application needs from the user's Gmail account.
# 'https://www.googleapis.com/auth/gmail.readonly': Allows reading email metadata (headers, sender, subject, date).
# 'https://www.googleapis.com/auth/gmail.modify': Allows modifying emails (marking as read/unread, moving messages).
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.modify']

# --- Database Configuration ---
# Name of the SQLite database file. It will be created in the project root directory.
DATABASE_NAME = 'emails.db'

# --- Rule Engine Configuration ---
# Path to the JSON file containing the email processing rules.
RULES_FILE = 'rules.json'

# --- Email Fetching Configuration ---
# Maximum number of emails to fetch from the inbox.
MAX_EMAIL_FETCH_RESULTS = 50

# --- Folder ID Mapping ---
# Gmail uses label IDs for folders.
# Common ones include 'INBOX', 'STARRED', 'SENT', 'DRAFT', 'ALL_MAIL', 'TRASH', 'SPAM'.
# Custom labels (folders) will have unique IDs. This map is used for moving messages.
# The script will attempt to dynamically discover label IDs if not found,
# but it's good practice to map commonly used ones.
# Note: For 'Move Message' action, if the rule specifies a custom label name,
# the Gmail API requires the corresponding label ID. The GmailClient will handle this mapping.
# For example: {'Promotions': 'Label_1234567890'} (This would be dynamically found by GmailClient)
