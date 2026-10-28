#!/usr/bin/env python3
"""Phase 1 regression tests for the evidence-first guardrail (mock only).

No network, no Meta API calls: server.py's Meta client is stubbed out
before import, and only the pure functions parse_copy() and
check_claims() are tested. Run: python3 test_guardrail.py
"""
import sys
import types
import unittest

# Stub the Meta API client so importing server.py needs no connection.
stub = types.ModuleType("meta_api")
stub.call = lambda *a, **k: (500, {})
stub.call_multipart = lambda *a, **k: (500, {})
sys.modules["meta_api"] = stub

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import server  # noqa: E402


class TestParseCopy(unittest.TestCase):
    def test_marker_present_splits_description_and_needs(self):
        text = ("Calbee snack, green bag, original flavor.\n"
                "NEEDS_CONFIRMATION:\n- Price\n- Net weight\n")
        desc, needs = server.parse_copy(text, "en")
        self.assertIn("Calbee", desc)
        self.assertNotIn("NEEDS_CONFIRMATION", desc)
        self.assertEqual(needs, ["Price", "Net weight"])

    def test_marker_absent_keeps_text_and_warns(self):
        text = "A tasty snack, 129 baht, sold everywhere."
        desc, needs = server.parse_copy(text, "th")
        self.assertEqual(desc, text)
        self.assertEqual(len(needs), 1)  # fallback warning, not silent

    def test_empty_description_gets_safe_minimum(self):
        text = "NEEDS_CONFIRMATION:\n- Price\n"
        desc, needs = server.parse_copy(text, "en")
        self.assertTrue(desc)
        self.assertEqual(needs, ["Price"])

    def test_thai_and_english_share_marker(self):
        text = ("ขนมถั่วลันเตา ถุงสีเขียว\nNEEDS_CONFIRMATION:\n- ราคา\n")
        desc, needs = server.parse_copy(text, "th")
        self.assertIn("ขนม", desc)
        self.assertEqual(needs, ["ราคา"])


class TestCheckClaims(unittest.TestCase):
    def test_price_without_seller_price_is_flagged(self):
        # Currency-marked price, no seller price supplied:
        desc = "Crispy snack, only \u0e3f129 per bag."
        needs = server.check_claims(desc, "", "en")
        self.assertEqual(len(needs), 1)

    def test_price_with_seller_price_is_not_flagged(self):
        desc = "Crispy snack, only \u0e3f129 per bag."
        needs = server.check_claims(desc, "ราคา 129 บาท", "th")
        self.assertEqual(needs, [])

    def test_seven_eleven_claim_without_support_is_flagged(self):
        desc = "Available at 7-Eleven nationwide."
        needs = server.check_claims(desc, "", "en")
        self.assertEqual(len(needs), 1)
        desc_th = "มีขายที่ 7-Eleven ทุกสาขา"
        needs = server.check_claims(desc_th, "", "th")
        self.assertEqual(len(needs), 1)

    def test_seven_eleven_claim_with_seller_fact_is_not_flagged(self):
        desc = "Available at 7-Eleven nationwide."
        needs = server.check_claims(desc, "sold at 7-Eleven", "en")
        self.assertEqual(needs, [])

    def test_generic_availability_phrase_without_seller_facts_is_flagged(self):
        desc = "Find it available at leading stores."
        needs = server.check_claims(desc, "", "en")
        self.assertEqual(len(needs), 1)

    def test_description_with_confirmed_facts_stays_nonempty(self):
        text = ("Calbee BunBun green pea snack, green bag shown in photo.\n"
                "NEEDS_CONFIRMATION:\n- Price\n")
        desc, needs = server.parse_copy(text, "en")
        self.assertTrue(desc)
        self.assertNotIn("Price", desc)
        self.assertEqual(needs, ["Price"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
