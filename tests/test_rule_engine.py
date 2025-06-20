# tests/test_rule_engine.py

import unittest
from unittest.mock import MagicMock, patch
import os
import json
from datetime import datetime, timedelta, timezone
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rule_engine import Email, Condition, Action, Rule, RuleEngine

# Define a mock rules.json content for testing
MOCK_RULES_CONTENT = [
    {
        "description": "Test Rule 1: All conditions match",
        "overall_predicate": "all",
        "conditions": [
            {"field": "From", "predicate": "contains", "value": "test@example.com"},
            {"field": "Subject", "predicate": "equals", "value": "Meeting Invite"},
            {"field": "Received Date/Time", "predicate": "less than", "value": {"days": 7}}
        ],
        "actions": [
            {"type": "Mark as Read"}
        ]
    },
    {
        "description": "Test Rule 2: Any condition matches",
        "overall_predicate": "any",
        "conditions": [
            {"field": "From", "predicate": "equals", "value": "spam@bad.com"},
            {"field": "Message", "predicate": "contains", "value": "viagra"}
        ],
        "actions": [
            {"type": "Move Message", "value": "Spam"},
            {"type": "Mark as Unread"}
        ]
    },
    {
        "description": "Test Rule 3: Date Greater Than",
        "overall_predicate": "all",
        "conditions": [
            {"field": "Received Date/Time", "predicate": "greater than", "value": {"days": 30}}
        ],
        "actions": [
            {"type": "Move Message", "value": "Archive"}
        ]
    },
    {
        "description": "Test Rule 4: Message Body Contains",
        "overall_predicate": "all",
        "conditions": [
            {"field": "Message", "predicate": "contains", "value": "important update"}
        ],
        "actions": [
            {"type": "Mark as Read"}
        ]
    },
    {
        "description": "Test Rule 5: From does not contain",
        "overall_predicate": "all",
        "conditions": [
            {"field": "From", "predicate": "does not contain", "value": "safe.com"}
        ],
        "actions": [
            {"type": "Mark as Unread"}
        ]
    },
    {
        "description": "Test Rule 6: Subject does not equal",
        "overall_predicate": "all",
        "conditions": [
            {"field": "Subject", "predicate": "does not equal", "value": "Daily Report"}
        ],
        "actions": [
            {"type": "Mark as Read"}
        ]
    }
]


class TestEmail(unittest.TestCase):
    """Unit tests for the Email data model."""

    def test_email_initialization_and_to_dict(self):
        now = datetime.now(timezone.utc)
        email_obj = Email(
            id='e1', thread_id='t1', from_address='a@b.com', subject='Sub',
            received_date_time=now, message_body='Body', label_ids=['INBOX']
        )
        self.assertEqual(email_obj.id, 'e1')
        self.assertEqual(email_obj.received_date_time, now)

        # Test to_dict
        email_dict = email_obj.to_dict()
        self.assertEqual(email_dict['id'], 'e1')
        self.assertEqual(email_dict['Received Date/Time'], now.isoformat())
        self.assertEqual(email_dict['labelIds'], ['INBOX'])

    def test_email_from_db_row(self):
        iso_dt = '2023-01-01T12:00:00'
        db_row = {
            'id': 'e2', 'thread_id': 't2', 'from': 'x@y.com', 'subject': 'Old Sub',
            'received_date_time': iso_dt, 'message_body': 'Old Body', 'label_ids': ['SENT']
        }
        email_obj = Email.from_db_row(db_row)
        self.assertEqual(email_obj.id, 'e2')
        self.assertEqual(email_obj.from_address, 'x@y.com')
        self.assertIsInstance(email_obj.received_date_time, datetime)
        self.assertEqual(email_obj.received_date_time, datetime.fromisoformat(iso_dt))
        self.assertEqual(email_obj.label_ids, ['SENT'])


class TestCondition(unittest.TestCase):
    """Unit tests for the Condition class and its evaluation logic."""

    def setUp(self):
        # Create a mock email object for testing conditions
        self.email = Email(
            id='test_email_id',
            thread_id='test_thread_id',
            from_address='sender@example.com',
            subject='Important Update - Meeting Details',
            received_date_time=datetime.now(timezone.utc) - timedelta(days=3),  # 3 days old
            message_body='Hello team,\n\nThis is an important update regarding the project. Please review the attached document.\n\nRegards,\nManager',
            label_ids=['INBOX', 'UNREAD']
        )
        self.old_email = Email(
            id='old_email_id',
            thread_id='old_thread_id',
            from_address='old@archive.com',
            subject='Old News',
            received_date_time=datetime.now(timezone.utc) - timedelta(days=40),  # 40 days old
            message_body='This is an old email.',
            label_ids=['ARCHIVE']
        )
        self.no_body_email = Email(
            id='no_body_id',
            thread_id='no_body_thread',
            from_address='no_body@test.com',
            subject='No Body Here',
            received_date_time=datetime.now(timezone.utc),
            message_body=None,  # Simulate missing message body
            label_ids=[]
        )
        self.case_sensitive_email = Email(
            id='case_id',
            thread_id='case_thread',
            from_address='JOHN.DOE@example.com',
            subject='CASE STUDY',
            received_date_time=datetime.now(timezone.utc),
            message_body='This text is MIXED case.',
            label_ids=[]
        )

    def test_contains_match(self):
        cond = Condition("From", "contains", "example.com")
        self.assertTrue(cond.evaluate(self.email))

        cond = Condition("Subject", "contains", "Meeting")
        self.assertTrue(cond.evaluate(self.email))

        cond = Condition("Message", "contains", "attached document")
        self.assertTrue(cond.evaluate(self.email))

        cond = Condition("From", "contains", "JOHN.DOE")  # Should be case-insensitive
        self.assertTrue(cond.evaluate(self.case_sensitive_email))

        cond = Condition("Message", "contains", "mixed case")  # Should be case-insensitive
        self.assertTrue(cond.evaluate(self.case_sensitive_email))

    def test_contains_no_match(self):
        cond = Condition("From", "contains", "nonexistent.com")
        self.assertFalse(cond.evaluate(self.email))

        cond = Condition("Subject", "contains", "Invoice")
        self.assertFalse(cond.evaluate(self.email))

        cond = Condition("Message", "contains", "nonexistent phrase")
        self.assertFalse(cond.evaluate(self.email))

        cond = Condition("Message", "contains", "project")  # Test when message body is None
        self.assertFalse(cond.evaluate(self.no_body_email))

    def test_does_not_contain_match(self):
        cond = Condition("From", "does not contain", "nonexistent.com")
        self.assertTrue(cond.evaluate(self.email))

        cond = Condition("Subject", "does not contain", "Invoice")
        self.assertTrue(cond.evaluate(self.email))

    def test_does_not_contain_no_match(self):
        cond = Condition("From", "does not contain", "example.com")
        self.assertFalse(cond.evaluate(self.email))

        cond = Condition("Subject", "does not contain", "Update")
        self.assertFalse(cond.evaluate(self.email))

    def test_equals_match(self):
        cond = Condition("From", "equals", "sender@example.com")
        self.assertTrue(cond.evaluate(self.email))

        cond = Condition("Subject", "equals", "Important Update - Meeting Details")
        self.assertTrue(cond.evaluate(self.email))

        cond = Condition("From", "equals", "john.doe@example.com")  # Case-insensitive
        self.assertTrue(cond.evaluate(self.case_sensitive_email))

        cond = Condition("Subject", "equals", "case study")  # Case-insensitive
        self.assertTrue(cond.evaluate(self.case_sensitive_email))

    def test_equals_no_match(self):
        cond = Condition("From", "equals", "different@example.com")
        self.assertFalse(cond.evaluate(self.email))

        cond = Condition("Subject", "equals", "Just a normal email")
        self.assertFalse(cond.evaluate(self.email))

        cond = Condition("Message", "equals", "This is exactly the body.")  # Full text equality
        self.assertFalse(cond.evaluate(self.email))  # Should be false as it's partial

    def test_does_not_equal_match(self):
        cond = Condition("From", "does not equal", "different@example.com")
        self.assertTrue(cond.evaluate(self.email))

        cond = Condition("From", "does not equal", "john.doe@test.com")  # Case-insensitive
        self.assertTrue(cond.evaluate(self.case_sensitive_email))

    def test_does_not_equal_no_match(self):
        cond = Condition("From", "does not equal", "sender@example.com")
        self.assertFalse(cond.evaluate(self.email))

        cond = Condition("Subject", "does not equal", "important update - meeting details")  # Case-insensitive
        self.assertFalse(cond.evaluate(self.email))

    def test_less_than_days_match(self):
        # Email is 3 days old, rule is "less than 7 days old" (meaning received more recently than 7 days ago)
        cond = Condition("Received Date/Time", "less than", {"days": 7})
        self.assertTrue(cond.evaluate(self.email))

        # Email is 3 days old, rule is "less than 2 days old" (meaning received more recently than 2 days ago)
        # This should be false, as it's older than 2 days but still less than 7 days old.
        cond = Condition("Received Date/Time", "less than", {"days": 2})
        self.assertFalse(cond.evaluate(self.email))  # Email is older than 2 days

    def test_less_than_days_no_match(self):
        # Email is 40 days old, rule is "less than 30 days old"
        cond = Condition("Received Date/Time", "less than", {"days": 30})
        self.assertFalse(cond.evaluate(self.old_email))

    def test_greater_than_days_match(self):
        # Email is 40 days old, rule is "greater than 30 days old" (meaning received earlier than 30 days ago)
        cond = Condition("Received Date/Time", "greater than", {"days": 30})
        self.assertTrue(cond.evaluate(self.old_email))

    def test_greater_than_days_no_match(self):
        # Email is 3 days old, rule is "greater than 7 days old"
        cond = Condition("Received Date/Time", "greater than", {"days": 7})
        self.assertFalse(cond.evaluate(self.email))

    def test_unknown_field(self):
        cond = Condition("NonExistentField", "equals", "value")
        # Should return False and print a warning
        with self.assertLogs('root', level='WARNING') as cm:  # Capture log output
            self.assertFalse(cond.evaluate(self.email))
        self.assertIn("Unknown field 'NonExistentField'", cm.output[0])

    def test_unknown_predicate(self):
        cond = Condition("Subject", "unknown_predicate", "value")
        # Should return False and print a warning
        with self.assertLogs('root', level='WARNING') as cm:
            self.assertFalse(cond.evaluate(self.email))
        self.assertIn("Unknown predicate 'unknown_predicate'", cm.output[0])


class TestAction(unittest.TestCase):
    """Unit tests for the Action class."""

    def setUp(self):
        self.mock_gmail_client = MagicMock()
        self.email_id = "mock_email_id_123"

    def test_mark_as_read_action(self):
        action = Action("Mark as Read")
        action.execute(self.mock_gmail_client, self.email_id)
        self.mock_gmail_client.mark_as_read.assert_called_once_with(self.email_id)

    def test_mark_as_unread_action(self):
        action = Action("Mark as Unread")
        action.execute(self.mock_gmail_client, self.email_id)
        self.mock_gmail_client.mark_as_unread.assert_called_once_with(self.email_id)

    def test_move_message_action(self):
        action = Action("Move Message", value="Promotions")
        action.execute(self.mock_gmail_client, self.email_id)
        self.mock_gmail_client.move_message.assert_called_once_with(self.email_id, "Promotions")

    def test_move_message_action_no_value(self):
        action = Action("Move Message")  # No value provided
        result = action.execute(self.mock_gmail_client, self.email_id)
        self.assertFalse(result)  # Should fail as no destination is given
        self.mock_gmail_client.move_message.assert_not_called()

    def test_unknown_action(self):
        action = Action("NonExistentAction")
        result = action.execute(self.mock_gmail_client, self.email_id)
        self.assertFalse(result)
        self.mock_gmail_client.mark_as_read.assert_not_called()
        self.mock_gmail_client.mark_as_unread.assert_not_called()
        self.mock_gmail_client.move_message.assert_not_called()


class TestRule(unittest.TestCase):
    """Unit tests for the Rule class (combining conditions and actions)."""

    def setUp(self):
        self.mock_gmail_client = MagicMock()
        self.email_matching_all = Email(
            id='email_all_match',
            thread_id='t_all',
            from_address='test@example.com',
            subject='Meeting Invite',
            received_date_time=datetime.now(timezone.utc) - timedelta(days=1),  # 1 day old (less than 7)
            message_body='Hello team, this is a test email.',
            label_ids=['INBOX']
        )
        self.email_matching_any = Email(
            id='email_any_match',
            thread_id='t_any',
            from_address='safe@good.com',
            subject='Normal Subject',
            received_date_time=datetime.now(timezone.utc),
            message_body='Buy viagra now!',
            label_ids=['INBOX']
        )
        self.email_not_matching = Email(
            id='email_no_match',
            thread_id='t_none',
            from_address='nomatch@domain.com',
            subject='Regular Update',
            received_date_time=datetime.now(timezone.utc) - timedelta(days=10),  # too old for 'less than 7'
            message_body='This email contains no special words.',
            label_ids=['INBOX']
        )

        # Rule definitions
        self.rule_all_match_data = MOCK_RULES_CONTENT[0]
        self.rule_any_match_data = MOCK_RULES_CONTENT[1]

        # Create Condition and Action objects for the rules
        self.conditions_all = [
            Condition(c['field'], c['predicate'], c['value']) for c in self.rule_all_match_data['conditions']
        ]
        self.actions_all = [
            Action(a['type'], a.get('value')) for a in self.rule_all_match_data['actions']
        ]

        self.conditions_any = [
            Condition(c['field'], c['predicate'], c['value']) for c in self.rule_any_match_data['conditions']
        ]
        self.actions_any = [
            Action(a['type'], a.get('value')) for a in self.rule_any_match_data['actions']
        ]

    def test_rule_matches_all_predicate(self):
        rule = Rule(
            description=self.rule_all_match_data['description'],
            overall_predicate=self.rule_all_match_data['overall_predicate'],
            conditions=self.conditions_all,
            actions=self.actions_all
        )
        self.assertTrue(rule.matches(self.email_matching_all))
        self.assertFalse(rule.matches(self.email_not_matching))  # Fails date and sender

    def test_rule_matches_any_predicate(self):
        rule = Rule(
            description=self.rule_any_match_data['description'],
            overall_predicate=self.rule_any_match_data['overall_predicate'],
            conditions=self.conditions_any,
            actions=self.actions_any
        )
        self.assertTrue(rule.matches(self.email_matching_any))
        self.assertFalse(rule.matches(self.email_not_matching))

    def test_rule_execute_actions(self):
        rule = Rule(
            description=self.rule_all_match_data['description'],
            overall_predicate=self.rule_all_match_data['overall_predicate'],
            conditions=self.conditions_all,
            actions=self.actions_all
        )
        rule.execute_actions(self.mock_gmail_client, self.email_matching_all.id)
        self.mock_gmail_client.mark_as_read.assert_called_once_with(self.email_matching_all.id)
        self.mock_gmail_client.mark_as_unread.assert_not_called()  # Should not be called for this rule
        self.mock_gmail_client.move_message.assert_not_called()  # Should not be called for this rule

    def test_rule_execute_multiple_actions(self):
        rule = Rule(
            description=self.rule_any_match_data['description'],
            overall_predicate=self.rule_any_match_data['overall_predicate'],
            conditions=self.conditions_any,
            actions=self.actions_any
        )
        rule.execute_actions(self.mock_gmail_client, self.email_matching_any.id)
        self.mock_gmail_client.move_message.assert_called_once_with(self.email_matching_any.id, "Spam")
        self.mock_gmail_client.mark_as_unread.assert_called_once_with(self.email_matching_any.id)


class TestRuleEngine(unittest.TestCase):
    """Unit tests for the RuleEngine class."""

    @patch('builtins.open', new_callable=unittest.mock.mock_open, read_data=json.dumps(MOCK_RULES_CONTENT))
    @patch('os.path.exists', return_value=True)
    def test_load_rules_success(self, mock_exists, mock_open):
        engine = RuleEngine(rules_file="mock_rules.json")
        self.assertEqual(len(engine.rules), len(MOCK_RULES_CONTENT))
        self.assertIsInstance(engine.rules[0], Rule)
        self.assertEqual(engine.rules[0].description, "Test Rule 1: All conditions match")

    @patch('os.path.exists', return_value=False)
    def test_load_rules_file_not_found(self, mock_exists):
        engine = RuleEngine(rules_file="non_existent_rules.json")
        self.assertEqual(len(engine.rules), 0)

    @patch('builtins.open', new_callable=unittest.mock.mock_open, read_data='{"invalid json"')
    @patch('os.path.exists', return_value=True)
    def test_load_rules_invalid_json(self, mock_exists, mock_open):
        engine = RuleEngine(rules_file="invalid_rules.json")
        self.assertEqual(len(engine.rules), 0)

    def test_process_emails(self):
        mock_gmail_client = MagicMock()

        # Setup mock for GmailClient methods used by actions
        mock_gmail_client.mark_as_read.return_value = True
        mock_gmail_client.mark_as_unread.return_value = True
        mock_gmail_client.move_message.return_value = True

        email1 = Email(  # Matches Rule 1 (Mark as Read)
            id='e1', thread_id='t1', from_address='tester@example.com',
            subject='Meeting Invite', received_date_time=datetime.now(timezone.utc) - timedelta(days=1),
            message_body='This is a test email.', label_ids=[]
        )
        email2 = Email(  # Matches Rule 2 (Move to Spam, Mark as Unread)
            id='e2', thread_id='t2', from_address='normal@sender.com',
            subject='Regular Newsletter', received_date_time=datetime.now(timezone.utc),
            message_body='Click here for viagra deals!', label_ids=[]
        )
        email3 = Email(  # Matches Rule 3 (Archive)
            id='e3', thread_id='t3', from_address='old@company.com',
            subject='Old Report', received_date_time=datetime.now(timezone.utc) - timedelta(days=60),
            message_body='Old document here.', label_ids=[]
        )
        email4 = Email(  # Matches Rule 4 (Mark as Read)
            id='e4', thread_id='t4', from_address='new@info.com',
            subject='Important Announcement', received_date_time=datetime.now(timezone.utc),
            message_body='This is an important update from the team.', label_ids=[]
        )
        email5 = Email(  # Matches Rule 5 (Mark as Unread)
            id='e5', thread_id='t5', from_address='malicious@domain.org',
            subject='Warning', received_date_time=datetime.now(timezone.utc),
            message_body='Click this link for prize!', label_ids=[]
        )
        email6 = Email(  # Does not match Rule 6 (Mark as Read)
            id='e6', thread_id='t6', from_address='daily@report.com',
            subject='Daily Report', received_date_time=datetime.now(timezone.utc),
            message_body='Your daily report is ready.', label_ids=[]
        )
        email7 = Email(  # Matches Rule 6 (Mark as Read)
            id='e7', thread_id='t7', from_address='daily@report.com',
            subject='Weekly Report', received_date_time=datetime.now(timezone.utc),
            message_body='Your weekly report is ready.', label_ids=[]
        )

        emails_to_process = [email1, email2, email3, email4, email5, email6, email7]

        # Use mock_open to provide the rules.json content
        with patch('builtins.open', new_callable=unittest.mock.mock_open, read_data=json.dumps(MOCK_RULES_CONTENT)), \
                patch('os.path.exists', return_value=True):
            engine = RuleEngine(rules_file="mock_rules.json")
            engine.process_emails(emails_to_process, mock_gmail_client)

        # Assertions for each email based on mock rules
        # email1 matches Rule 1: Mark as Read
        mock_gmail_client.mark_as_read.assert_any_call('e1')

        # email2 matches Rule 2: Move to Spam, Mark as Unread
        mock_gmail_client.move_message.assert_any_call('e2', 'Spam')
        mock_gmail_client.mark_as_unread.assert_any_call('e2')

        # email3 matches Rule 3: Move to Archive
        mock_gmail_client.move_message.assert_any_call('e3', 'Archive')

        # email4 matches Rule 4: Mark as Read
        mock_gmail_client.mark_as_read.assert_any_call('e4')

        # email5 matches Rule 5: Mark as Unread
        mock_gmail_client.mark_as_unread.assert_any_call('e5')

        # email6 does NOT match Rule 6: No actions triggered for e6 by Rule 6, as Subject is 'Daily Report'
        # The specific check would be that if no other rule matches, no actions are called.
        # This test ensures calls happened only for matching rules.

        # email7 matches Rule 6: Mark as Read
        mock_gmail_client.mark_as_read.assert_any_call('e7')

        # Verify total calls (simplified: check if expected methods were called at least once)
        self.assertTrue(mock_gmail_client.mark_as_read.called)
        self.assertTrue(mock_gmail_client.mark_as_unread.called)
        self.assertTrue(mock_gmail_client.move_message.called)

        # Verify specific counts for demonstration
        # Expected mark_as_read calls: (7 calls)
        self.assertEqual(mock_gmail_client.mark_as_read.call_count, 7)
        # Expected mark_as_unread calls: (8 calls)
        self.assertEqual(mock_gmail_client.mark_as_unread.call_count, 8)
        # Expected move_message calls: e2, e3 (2 calls)
        self.assertEqual(mock_gmail_client.move_message.call_count, 2)


if __name__ == '__main__':
    unittest.main()

