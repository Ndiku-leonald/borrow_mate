"""Drives the CLI with scripted input to make sure every menu path works."""

import unittest

from borrowmate.cli import BorrowMateCLI
from borrowmate.seed import build_demo_community


def run_cli(*answers):
    community = build_demo_community()
    inputs = iter(answers)
    output = []
    BorrowMateCLI(community, input_fn=lambda _: next(inputs),
                  output_fn=output.append).run()
    return "\n".join(output), community


class CliTests(unittest.TestCase):
    def test_views_render(self):
        text, _ = run_cli("U001", "1", "2", "", "3", "4", "5", "0")
        self.assertIn("Scientific calculator", text)
        self.assertIn("Items currently taken", text)
        self.assertIn("COMPETING", text)
        self.assertIn("LATE", text)

    def test_lender_accepts_request_and_rival_is_declined(self):
        # Stacey (U003) owns the extension cable with two competing requests.
        text, c = run_cli("U003", "8", "L003", "y", "4", "0")
        self.assertIn("Accepted", text)
        self.assertEqual(c.loans.conflicts(), [])

    def test_errors_are_friendly(self):
        text, _ = run_cli("U001", "7", "I999", "0")
        self.assertIn("! No item with id 'I999'", text)

    def test_return_overdue_item(self):
        # Keitha (U002) confirms Leo returned the iron (L002), condition Good.
        text, c = run_cli("U002", "10", "L002", "2", "0")
        self.assertIn("late", text)
        self.assertEqual(c.loans.overdue_loans(), [])


class PluginTests(unittest.TestCase):
    def test_plugin_entries_appear_in_menu_and_run(self):
        from borrowmate.cli.plugin import MenuPlugin

        class HelloPlugin(MenuPlugin):
            def menu_entries(self, cli):
                return [("Say hello", lambda: cli.say(f"Hello {cli.user.full_name}"))]

        community = build_demo_community()
        output = []
        inputs = iter(["U001", "16", "0"])   # option 16 = first plugin entry for students
        BorrowMateCLI(community, input_fn=lambda _: next(inputs), output_fn=output.append,
                      plugins=[HelloPlugin(community)]).run()
        self.assertIn("Hello Leo Ndikuryayo", "\n".join(output))


if __name__ == "__main__":
    unittest.main()
