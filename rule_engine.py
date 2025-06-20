# rule_engine.py

import json
from datetime import datetime, timedelta
import os
import logging
from datetime import timezone
from config import RULES_FILE

logger = logging.getLogger(__name__)


class Email:
    """
    Represents an email message with its parsed attributes.

    This class acts as a data model for emails, making it easier to
    access various properties (From, Subject, Message Body, Received Date/Time, etc.)
    consistently across the application, especially for rule evaluation.
    """

    def __init__(self, id, thread_id, from_address, subject, received_date_time, message_body, label_ids=None):
        """
        Initializes an Email object.

        Args:
            id (str): Unique ID of the email.
            thread_id (str): ID of the conversation thread.
            from_address (str): Sender's email address (e.g., "Sender Name <sender@example.com>").
            subject (str): Subject of the email.
            received_date_time (datetime): Datetime object representing when the email was received.
            message_body (str): Plain text content of the email body.
            label_ids (list, optional): List of Gmail label IDs associated with the email. Defaults to None.
        """
        self.id = id
        self.thread_id = thread_id
        self.from_address = from_address
        self.subject = subject
        self.received_date_time = received_date_time
        self.message_body = message_body
        self.label_ids = label_ids if label_ids is not None else []

    def to_dict(self):
        """
        Converts the Email object to a dictionary, suitable for database storage
        or display. Datetime objects are converted to ISO format strings.

        Returns:
            dict: A dictionary representation of the email.
        """
        return {
            'id': self.id,
            'threadId': self.thread_id,
            'From': self.from_address,
            'Subject': self.subject,
            'Received Date/Time': self.received_date_time.isoformat() if self.received_date_time else None,
            'Message Body': self.message_body,
            'labelIds': self.label_ids
        }

    @classmethod
    def from_db_row(cls, row_dict):
        """
        Creates an Email object from a dictionary representing a database row.
        Converts date string back to datetime object.

        Args:
            row_dict (dict): A dictionary where keys are column names from the database.

        Returns:
            Email: An Email object.
        """
        received_dt = None
        if row_dict.get('received_date_time'):
            if isinstance(row_dict['received_date_time'], str):
                received_dt = datetime.fromisoformat(row_dict['received_date_time'])
            elif isinstance(row_dict['received_date_time'], datetime):
                received_dt = row_dict['received_date_time']  # Already a datetime object from DBManager

        return cls(
            id=row_dict['id'],
            thread_id=row_dict['thread_id'],
            from_address=row_dict['from'],
            subject=row_dict['subject'],
            received_date_time=received_dt,
            message_body=row_dict['message_body'],
            label_ids=row_dict.get('label_ids', [])
        )


class Condition:
    """
    Represents a single condition within a rule (e.g., From contains "example.com").

    This class encapsulates the field to check, the predicate (operator), and the
    value to compare against. It also provides the logic to evaluate itself
    against a given Email object.
    """

    def __init__(self, field, predicate, value):
        """
        Initializes a Condition object.

        Args:
            field (str): The email field to check (e.g., "From", "Subject", "Message", "Received Date/Time").
            predicate (str): The comparison predicate (e.g., "contains", "equals", "less than").
            value (any): The value to compare against.
        """
        self.field = field
        self.predicate = predicate
        self.value = value

    def evaluate(self, email_obj):
        """
        Evaluates this condition against an Email object.

        Args:
            email_obj (Email): The Email object to evaluate.

        Returns:
            bool: True if the condition matches, False otherwise.
        """
        email_value = self._get_email_field_value(email_obj, self.field)

        # Handle cases where email_value might be None
        if email_value is None and self.predicate not in ["equals", "does not equal"]:
            # For predicates like 'contains', 'less than' etc., if email_value is None,
            # it typically means the condition cannot be met, so return False.
            # However, for 'equals/does not equal', None can be a valid comparison.
            return False

        if self.predicate == "contains":
            return self.value.lower() in (email_value or "").lower() if isinstance(email_value, str) else False
        elif self.predicate == "does not contain":
            return self.value.lower() not in (email_value or "").lower() if isinstance(email_value, str) else False
        elif self.predicate == "equals":
            # Case-insensitive comparison for strings
            if isinstance(email_value, str) and isinstance(self.value, str):
                return email_value.lower() == self.value.lower()
            return email_value == self.value
        elif self.predicate == "does not equal":
            # Case-insensitive comparison for strings
            if isinstance(email_value, str) and isinstance(self.value, str):
                return email_value.lower() != self.value.lower()
            return email_value != self.value
        elif self.predicate == "less than":
            if self.field == "Received Date/Time" and isinstance(email_value, datetime):
                if isinstance(self.value, dict):
                    if "days" in self.value:
                        threshold_date = datetime.now(timezone.utc) - timedelta(days=self.value["days"])
                        return email_value > threshold_date  # Email is MORE recent than threshold, i.e., "less than X days old"
                    elif "months" in self.value:
                        # Simple month calculation: subtract days equivalent to months
                        # TODO: change  this to use dateutils.relativedelta
                        approx_days = self.value["months"] * 30.44  # Average days in a month
                        threshold_date = datetime.now(timezone.utc) - timedelta(days=approx_days)
                        return email_value > threshold_date
            return False
        elif self.predicate == "greater than":
            if self.field == "Received Date/Time" and isinstance(email_value, datetime):
                if isinstance(self.value, dict):
                    if "days" in self.value:
                        threshold_date = datetime.now(timezone.utc) - timedelta(days=self.value["days"])
                        # Email is OLDER than threshold, i.e., "greater than X days old"
                        return email_value < threshold_date
                    elif "months" in self.value:
                        approx_days = self.value["months"] * 30.44
                        threshold_date = datetime.now(timezone.utc) - timedelta(days=approx_days)
                        return email_value < threshold_date
            return False
        else:
            logger.warning(f"Warning: Unknown predicate '{self.predicate}' for field '{self.field}'. Condition will not be met.")
            return False

    def _get_email_field_value(self, email_obj, field_name):
        """
        Helper method to retrieve the correct attribute from the Email object
        based on the field name specified in the rule.

        Args:
            email_obj (Email): The email object.
            field_name (str): The name of the field (e.g., "From", "Subject").

        Returns:
            any: The value of the corresponding email field.
        """
        if field_name == "From":
            return email_obj.from_address
        elif field_name == "Subject":
            return email_obj.subject
        elif field_name == "Message":
            return email_obj.message_body
        elif field_name == "Received Date/Time":
            return email_obj.received_date_time
        else:
            logger.warning(f"Warning: Unknown field '{field_name}'. Cannot evaluate condition.")
            return None


class Action:
    """
    Represents an action to be performed on an email (e.g., Mark as Read, Move Message, Apply Label).

    This class encapsulates the type of action and any associated value (like a mailbox name or label name).
    It defines the interface for executing the action via a GmailClient.
    """

    def __init__(self, action_type, value=None):
        """
        Initializes an Action object.

        Args:
            action_type (str): The type of action (e.g., "Mark as Read", "Move Message", "Apply Label").
            value (any, optional): The value associated with the action (e.g., mailbox name, label name). Defaults to None.
        """
        self.action_type = action_type
        self.value = value

    def execute(self, gmail_client, email_id):
        """
        Executes the action on a given email using the provided GmailClient.

        Args:
            gmail_client (GmailClient): An instance of the GmailClient to interact with the API.
            email_id (str): The ID of the email on which to perform the action.

        Returns:
            bool: True if the action was successful, False otherwise.
        """
        if self.action_type == "Mark as Read":
            return gmail_client.mark_as_read(email_id)
        elif self.action_type == "Mark as Unread":
            return gmail_client.mark_as_unread(email_id)
        elif self.action_type == "Move Message":
            if self.value:
                return gmail_client.move_message(email_id, self.value)
            else:
                print(f"Error: Missing destination mailbox for 'Move Message' action for email {email_id}.")
                return False
        elif self.action_type == "Apply Label":
            if self.value:
                return gmail_client.apply_label(email_id, self.value)
            else:
                print(f"Error: Missing label name for 'Apply Label' action for email {email_id}.")
                return False
        else:
            logger.warning(f"Warning: Unknown action type '{self.action_type}'. Action not executed for email {email_id}.")
            return False


class Rule:
    """
    Represents a complete rule, consisting of a set of conditions, an overall predicate
    ("all" or "any"), and a set of actions to perform if the conditions are met.

    This class provides the logic to check if an email matches the rule's conditions
    and to execute the associated actions.
    """

    def __init__(self, description, overall_predicate, conditions, actions):
        """
        Initializes a Rule object.

        Args:
            description (str): A descriptive name for the rule.
            overall_predicate (str): "all" (AND) or "any" (OR) for combining conditions.
            conditions (list): A list of Condition objects.
            actions (list): A list of Action objects.
        """
        self.description = description
        self.overall_predicate = overall_predicate.lower()  # Ensure lowercase for comparison
        self.conditions = conditions
        self.actions = actions

    def matches(self, email_obj):
        """
        Checks if the given email matches the conditions of this rule.

        Args:
            email_obj (Email): The Email object to check.

        Returns:
            bool: True if the email matches the rule, False otherwise.
        """
        if not self.conditions:
            return True  # No conditions means it always matches

        evaluated_conditions = [condition.evaluate(email_obj) for condition in self.conditions]

        if self.overall_predicate == "all":
            return all(evaluated_conditions)  # All conditions must be True
        elif self.overall_predicate == "any":
            return any(evaluated_conditions)  # At least one condition must be True
        else:
            logger.warning(f"Warning: Unknown overall predicate '{self.overall_predicate}'. Rule will not match.")
            return False

    def execute_actions(self, gmail_client, email_id):
        """
        Executes all actions associated with this rule for a given email.

        Args:
            gmail_client (GmailClient): An instance of the GmailClient.
            email_id (str): The ID of the email to perform actions on.

        Returns:
            bool: True if all actions were successfully executed, False otherwise.
        """
        print(f"Executing actions for email {email_id} based on rule: '{self.description}'")
        all_succeeded = True
        for action in self.actions:
            if not action.execute(gmail_client, email_id):
                all_succeeded = False
                print(f"Action '{action.action_type}' failed for email {email_id}.")
        return all_succeeded


class RuleEngine:
    """
    Manages the loading and application of multiple rules.

    This class is responsible for loading rules from a JSON file and providing
    a method to process a list of emails against all loaded rules.
    """

    def __init__(self, rules_file=RULES_FILE):
        """
        Initializes the RuleEngine and loads rules from the specified JSON file.

        Args:
            rules_file (str): Path to the JSON file containing rule definitions.
        """
        self.rules_file = rules_file
        self.rules = self._load_rules()

    def _load_rules(self):
        """
        Loads rules from the JSON file and parses them into Rule objects.

        Returns:
            list: A list of Rule objects. Returns an empty list if the file is not found
                  or parsing fails.
        """
        rules = []
        if not os.path.exists(self.rules_file):
            print(f"Error: Rules file '{self.rules_file}' not found.")
            return []

        try:
            with open(self.rules_file, 'r', encoding='utf-8') as f:
                rules_data = json.load(f)

            for rule_data in rules_data:
                conditions = []
                for cond_data in rule_data.get('conditions', []):
                    conditions.append(Condition(
                        field=cond_data['field'],
                        predicate=cond_data['predicate'],
                        value=cond_data['value']
                    ))

                actions = []
                for action_data in rule_data.get('actions', []):
                    actions.append(Action(
                        action_type=action_data['type'],
                        value=action_data.get('value')
                    ))

                rules.append(Rule(
                    description=rule_data.get('description', 'Untitled Rule'),
                    overall_predicate=rule_data.get('overall_predicate', 'all'),
                    conditions=conditions,
                    actions=actions
                ))
            print(f"Successfully loaded {len(rules)} rules from '{self.rules_file}'.")
            return rules
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from rules file '{self.rules_file}': {e}")
            return []
        except KeyError as e:
            print(f"Error: Missing key in rule definition in '{self.rules_file}': {e}. Please check rule structure.")
            return []
        except Exception as e:
            print(f"An unexpected error occurred while loading rules: {e}")
            return []

    def process_emails(self, emails, gmail_client):
        """
        Iterates through a list of emails and applies all loaded rules.
        If an email matches a rule, its associated actions are executed.

        Args:
            emails (list): A list of Email objects to process.
            gmail_client (GmailClient): An instance of the GmailClient for executing actions.
        """
        if not self.rules:
            print("No rules loaded. Skipping email processing.")
            return

        print(f"\nStarting to process {len(emails)} emails with {len(self.rules)} rules...")
        for email_obj in emails:
            print(f"\nProcessing email ID: {email_obj.id}, Subject: '{email_obj.subject}'")
            for rule in self.rules:
                if rule.matches(email_obj):
                    print(f"  Email matches rule: '{rule.description}'")
                    rule.execute_actions(gmail_client, email_obj.id)
                else:
                    print(f"  Email does NOT match rule: '{rule.description}'")
        print("\nEmail processing complete.")
