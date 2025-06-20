# Gmail Automation Script

This project provides a standalone Python script to automate Gmail operations based on a set of rules. It integrates with the Gmail API to fetch emails, stores them in a local SQLite database, and then processes these emails by applying user-defined rules. The rules are configurable via a JSON file, allowing for flexible automation of actions like marking emails as read/unread or moving them to different mailboxes.

## Features

* **Gmail API Integration**: Securely authenticate with Gmail API using OAuth 2.0 to fetch and modify emails
* **Database Storage**: Store fetched email metadata in a SQLite database for efficient processing
* **Rule-Based Processing**: Define custom rules in a JSON file with various conditions (From, Subject, Message, Received Date/Time) and actions (Mark as read/unread, Move Message, Apply Label)
* **Flexible Rule Predicates**: Supports "All" (AND) and "Any" (OR) logic for combining multiple conditions
* **Object-Oriented Design**: Implemented using Python's OOP principles, with clear separation of concerns and design patterns
* **Unit Tests**: Comprehensive unit tests for core functionalities

## Project Structure

```
gmail_automation/
├── fetch_and_store.py      # Script to fetch emails from Gmail and store in DB
├── process_emails.py       # Script to read emails from DB, apply rules, and perform actions
├── gmail_client.py         # Handles Gmail API authentication and operations
├── database_manager.py     # Manages SQLite database interactions
├── rule_engine.py          # Defines rule structure, conditions, and actions
├── rules.json              # Configuration file for email processing rules
├── config.py               # Stores project-wide constants and configurations
├── .gitignore              # Specifies files/folders to ignore in Git (crucial for credentials)
├── tests/
│   ├── test_gmail_client.py    # Unit tests for GmailClient
│   ├── test_rule_engine.py     # Unit tests for RuleEngine components
│   └── test_database_manager.py# Unit tests for DatabaseManager
├── README.md               # This file
├── credentials.json        # Google API credentials (download from Google Cloud, ADD TO .gitignore)
├── token.json              # Generated after the first successful OAuth authentication (ADD TO .gitignore)
└── emails.db               # SQLite database file (created automatically, ADD TO .gitignore)
```

## Step-by-Step Setup and Run Instructions

Follow these steps to set up and run the Gmail automation script.

### 1. Clone the Project

First, clone this repository to your local machine:

```bash
git clone https://github.com/your-username/gmail_automation.git
cd gmail_automation
```

> **Note**: Replace `https://github.com/your-username/gmail_automation.git` with the actual URL of your repository.

### 2. Google Cloud Project Setup and API Credentials

To interact with the Gmail API, you need to set up a project in Google Cloud and obtain OAuth 2.0 credentials.

#### Go to Google Cloud Console

Open your web browser and navigate to [https://console.cloud.google.com/](https://console.cloud.google.com/).

#### Create a New Project

1. If you don't have a project, click on the project selector dropdown (usually at the top left, next to "Google Cloud") and select **"New Project"**
2. Give your project a name (e.g., "Gmail Automation Project") and click **"Create"**

#### Enable Gmail API

1. In the Google Cloud Console, use the search bar at the top and type **"Gmail API"**
2. Select **"Gmail API"** from the results and click the **"Enable"** button

#### Configure OAuth Consent Screen

1. Navigate to **"APIs & Services"** > **"OAuth consent screen"** from the left-hand navigation menu
2. **User Type**: Select **"External"** and click **"Create"**
3. **OAuth consent screen details**:
   * **App name**: Provide a descriptive name (e.g., "Gmail Automation App")
   * **User support email**: Enter your email address
   * **Developer contact information**: Enter your email address
4. Click **"SAVE AND CONTINUE"**

#### Scopes

1. Click **"ADD OR REMOVE SCOPES"**
2. Search for and select the following scopes:
   * `.../auth/gmail.readonly` (For fetching email metadata)
   * `.../auth/gmail.modify` (For marking as read/unread and moving messages)
3. Click **"UPDATE"**
4. Click **"SAVE AND CONTINUE"**

#### Test users

1. Under **"Test users"**, click **"ADD USERS"**
2. Enter your Google account email address(es) that you will use for testing
   > **Important**: This is crucial for the OAuth flow to work in "External" user type during testing
3. Click **"ADD"**
4. Click **"SAVE AND CONTINUE"**
5. **Summary**: Review the summary and click **"BACK TO DASHBOARD"**

#### Create OAuth Client ID Credentials

1. Navigate to **"APIs & Services"** > **"Credentials"** from the left-hand navigation menu
2. Click **"CREATE CREDENTIALS"** at the top and select **"OAuth client ID"**
3. **Application type**: Select **"Desktop app"**
4. **Name**: Provide a name for your OAuth client (e.g., "Gmail Automation Desktop Client")
5. Click **"CREATE"**
6. A dialog will appear showing your Client ID and Client Secret. Click **"DOWNLOAD JSON"**
7. Rename the downloaded file to `credentials.json` and place it in the root directory of your `gmail_automation` project

### 3. Python Environment Setup

#### Install Python

Ensure you have Python 3.9 or higher installed on your system. You can download it from [python.org](https://python.org).

#### Create a Virtual Environment

It's highly recommended to use a virtual environment to manage project dependencies.

```bash
python3 -m venv venv
```

> **Note**: Use `python` instead of `python3` if `python --version` shows Python 3.

#### Activate the Virtual Environment

**On Windows:**
```bash
.\venv\Scripts\activate
```

**On macOS/Linux:**
```bash
source venv/bin/activate
```

You should see `(venv)` at the beginning of your terminal prompt after activation.

#### Install Required Libraries

```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib beautifulsoup4
```

### 4. Database Setup (SQLite3)

This project uses SQLite3, which is built into Python. **No separate installation is required**.

The `emails.db` file will be automatically created in the project root directory when `database_manager.py` is initialized for the first time.

### 5. Configure rules.json

The `rules.json` file defines the conditions and actions for email processing. An example is provided below.

#### Location
Place this file in the root directory of your `gmail_automation` project.

#### Structure

* It's a JSON array where each element is a rule object
* **description**: A human-readable description of the rule
* **overall_predicate**: Can be `"all"` (AND logic - all conditions must be true) or `"any"` (OR logic - at least one condition must be true)
* **conditions**: An array of condition objects
  * **field**: The email field to check (`From`, `Subject`, `Message`, `Received Date/Time`)
  * **predicate**: The comparison operator (`contains`, `does not contain`, `equals`, `does not equal`, `less than`, `greater than`)
  * **value**: The value to compare against
    * For string fields, it's a string
    * For `Received Date/Time`, it's an object like `{"days": 2}` or `{"months": 1}`
* **actions**: An array of action objects
  * **type**: The action to perform (`Mark as Read`, `Mark as Unread`, `Move Message`, `Apply Label`)
  * **value**: *(Optional)* For `Move Message` or `Apply Label`, this is the name of the target mailbox/label (e.g., `"INBOX"`, `"Promotions"`, `"Important"`)

> **Important**: Make sure the mailbox/label name exactly matches a label in your Gmail.

#### Example rules.json

```json
[
  {
    "description": "Rule 1: Interview Emails from happyfox.hire.trakstar.com less than 2 days old",
    "overall_predicate": "all",
    "conditions": [
      {
        "field": "From",
        "predicate": "contains",
        "value": "happyfox.hire.trakstar.com"
      },
      {
        "field": "Subject",
        "predicate": "contains",
        "value": "Interview"
      },
      {
        "field": "Received Date/Time",
        "predicate": "less than",
        "value": { "days": 2 }
      }
    ],
    "actions": [
      {
        "type": "Move Message",
        "value": "INBOX"
      },
      {
        "type": "Mark as Read"
      },
      {
        "type": "Apply Label",
        "value": "Important"
      }
    ]
  },
  {
    "description": "Rule 2: Emails with 'Promotion' in subject or 'marketing@example.com' in From, mark unread and move to Promotions and label as 'Newsletter'",
    "overall_predicate": "any",
    "conditions": [
      {
        "field": "Subject",
        "predicate": "contains",
        "value": "Promotion"
      },
      {
        "field": "From",
        "predicate": "equals",
        "value": "marketing@example.com"
      }
    ],
    "actions": [
      {
        "type": "Mark as Unread"
      },
      {
        "type": "Move Message",
        "value": "Promotions"
      },
      {
        "type": "Apply Label",
        "value": "Newsletter"
      }
    ]
  },
  {
    "description": "Rule 3: Apply 'Archive_2024' label to emails from old-news@example.com",
    "overall_predicate": "all",
    "conditions": [
      {
        "field": "From",
        "predicate": "equals",
        "value": "old-news@example.com"
      }
    ],
    "actions": [
      {
        "type": "Apply Label",
        "value": "Archive_2024"
      },
      {
        "type": "Mark as Read"
      }
    ]
  }
]
```

### 6. Running the Scripts

This project consists of two separate scripts that you run sequentially:

#### Fetch and Store Emails

This script authenticates with Gmail, fetches emails from your inbox, and saves their metadata into the local `emails.db` database.

```bash
python fetch_and_store.py
```

> **First Run**: The first time you run this, a browser window will open, prompting you to authenticate with your Google account. Follow the prompts to grant the necessary permissions. After successful authentication, `token.json` will be created in your project directory, allowing subsequent runs to authenticate automatically.

#### Process Stored Emails

This script reads the emails currently stored in your `emails.db` database, applies the rules defined in `rules.json`, and then performs the specified actions (mark as read/unread, move message, apply label) via the Gmail API.

```bash
python process_emails.py
```

### 7. Running Tests

To run the unit tests, navigate to the project root directory in your activated virtual environment and execute:

```bash
python -m unittest discover tests
```

This will run all the tests defined in the `tests/` directory.

## Design Choices and OOP Concepts

### Modular Design
The project is divided into distinct modules (`gmail_client.py`, `database_manager.py`, `rule_engine.py`, `fetch_and_store.py`, `process_emails.py`) to separate concerns and improve maintainability. Each module has a focused responsibility.

### Classes for Domain Objects

* **Email**: Represents an email with its parsed attributes, acting as a clean data model
* **Condition**: Encapsulates a single rule condition (field, predicate, value)
* **Action**: Represents an action to be performed on an email
* **Rule**: Combines conditions and actions to define a complete processing rule

### Manager Classes

* **GmailClient**: Abstracts all interactions with the Google Gmail API, centralizing authentication and email manipulation logic
* **DatabaseManager**: Manages all operations related to the SQLite database, abstracting database connection and CRUD operations

### Strategy Pattern
The `Condition` and `Action` classes, coupled with the `Rule` class, embody aspects of the Strategy pattern.

* Different predicates within `Condition` (e.g., `"contains"`, `"equals"`) act as interchangeable algorithms for evaluating a specific field
* Similarly, actions (e.g., `"Mark as Read"`, `"Move Message"`, `"Apply Label"`) are distinct strategies for modifying an email. The `Action.execute` method dispatches to the appropriate concrete strategy (method on `GmailClient`) based on its `action_type`

### Factory Method (for Email Object Creation)
The `Email.from_db_row` class method serves as a Factory Method. It provides a static way to construct `Email` objects from a specific source (a dictionary representing a database row) without exposing the internal complexities of direct constructor calls or raw data parsing. This centralizes object creation logic for this particular conversion.

### Singleton (Implicit for DB/Gmail Client)
While not enforced with a strict Singleton design pattern (e.g., via metaclasses), the `GmailClient` and `DatabaseManager` classes are typically instantiated only once within each main script (`fetch_and_store.py` and `process_emails.py`), effectively acting as single points of contact for their respective services throughout the script's execution.
