"""Choosing a template from the last-message preview."""
import re
import unittest

from linkedin_bots.messaging.domain.routing import Routing, TemplateRoute


def _routing(default_regex=None, rules=()):
    return Routing(
        default="default-templates", default_source="message.txt",
        rules=tuple(TemplateRoute(re.compile(p), f"{name}-templates", name)
                    for p, name in rules),
        fallback=re.compile(default_regex) if default_regex else None)


class TemplateRoutingTest(unittest.TestCase):
    def test_no_rules_means_every_card_gets_the_default(self):
        routing = _routing()
        for preview in ("anything at all", "", None):
            templates, source, matched = routing.choose(preview)
            self.assertEqual((templates, source, matched),
                             ("default-templates", "message.txt", None))

    def test_default_regex_alone_still_filters(self):
        routing = _routing(default_regex=r".*há 7.*")
        self.assertEqual(routing.choose("Você: há 7 anos")[1], "message.txt")
        self.assertEqual(routing.choose("Você: ontem")[0], None)

    def test_custom_rule_picks_its_own_template(self):
        """The flag combination from the feature request."""
        routing = _routing(default_regex=r".*há 7.*",
                        rules=[(r".*for 7.*", "message_english.txt")])

        self.assertEqual(routing.choose("You: for 7 years")[1],
                         "message_english.txt")
        self.assertEqual(routing.choose("Você: há 7 anos")[1],
                         "message.txt")
        self.assertIsNone(routing.choose("You: thanks!")[0])

    def test_custom_rules_are_checked_in_order(self):
        routing = _routing(rules=[(r"7", "first.txt"), (r"7 years", "second.txt")])
        self.assertEqual(routing.choose("for 7 years")[1], "first.txt")

    def test_custom_rules_win_over_the_default_regex(self):
        routing = _routing(default_regex=r"7", rules=[(r"7", "custom.txt")])
        self.assertEqual(routing.choose("for 7 years")[1], "custom.txt")

    def test_custom_rules_alone_skip_everything_else(self):
        """No --last-message-regex: only the custom patterns get messaged."""
        routing = _routing(rules=[(r".*for 7.*", "message_english.txt")])
        self.assertEqual(routing.choose("You: for 7 years")[1],
                         "message_english.txt")
        self.assertIsNone(routing.choose("Você: há 7 anos")[0])

    def test_unreadable_preview_is_skipped_when_rules_exist(self):
        routing = _routing(rules=[(r".", "any.txt")])
        self.assertIsNone(routing.choose(None)[0])

    def test_matched_pattern_is_reported_for_logging(self):
        routing = _routing(default_regex=r".*há 7.*",
                        rules=[(r".*for 7.*", "message_english.txt")])
        self.assertEqual(routing.choose("You: for 7 years")[2], ".*for 7.*")
        self.assertEqual(routing.choose("Você: há 7 anos")[2], ".*há 7.*")

    def test_rule_patterns_are_listed_in_evaluation_order(self):
        routing = _routing(default_regex="default",
                        rules=[("a", "a.txt"), ("b", "b.txt")])
        self.assertEqual(routing.patterns(), ["a", "b", "default"])
