"""
Test Suite: Deterministic Policy Engine & Under-18 Safeguarding Invariants.
"""
import unittest
from datetime import date
from backend.policy_engine import PolicyEngine, SafeguardingGate, calculate_age
from backend.models import PolicyDecision


class TestPolicyAndSafety(unittest.TestCase):
    def test_calculate_age(self):
        as_of = date(2026, 3, 17)
        self.assertEqual(calculate_age("2021-02-26", as_of), 5)
        self.assertEqual(calculate_age("2002-11-12", as_of), 23)
        self.assertEqual(calculate_age("2008-03-18", as_of), 17)  # Turns 18 tomorrow -> Still 17!
        self.assertEqual(calculate_age("2008-03-17", as_of), 18)  # Exactly 18 today

    def test_safeguarding_gate_detects_minor(self):
        """Critical Invariant: Minor in household -> HANDOFF_REQUIRED, triage not permitted."""
        household_with_child = [
            {"name": "Elizabeth Whitlock", "date_of_birth": "1964-05-25", "relationship": "Applicant"},
            {"name": "William Iverson", "date_of_birth": "2021-02-26", "relationship": "Son/daughter"},
        ]
        eval_result, enriched = PolicyEngine.evaluate(
            requested_action="Review award",
            summary="Resident reports rent arrears",
            household_data=household_with_child,
        )

        self.assertEqual(eval_result.decision, PolicyDecision.HANDOFF_REQUIRED)
        self.assertEqual(eval_result.applicable_section, "ACA-2026/2 §3.9")
        self.assertFalse(eval_result.triage_permitted)
        self.assertTrue(any(m.is_minor for m in enriched))
        self.assertIn("William Iverson", eval_result.rationale)

    def test_safeguarding_gate_adults_only_allows_triage(self):
        """Adults only -> Passes safeguarding gate and allows routine Section 2 triage."""
        adult_household = [
            {"name": "Susan Marsh", "date_of_birth": "1971-03-15", "relationship": "Applicant"},
            {"name": "Sarah Hollis", "date_of_birth": "2002-11-12", "relationship": "Son/daughter"},
            {"name": "Rosa Crowley", "date_of_birth": "2000-01-10", "relationship": "Other relative"},
        ]
        eval_result, enriched = PolicyEngine.evaluate(
            requested_action="Record change of address",
            summary="New address notified",
            household_data=adult_household,
        )

        self.assertEqual(eval_result.decision, PolicyDecision.ALLOWED)
        self.assertEqual(eval_result.applicable_section, "ACA-2026/1 §2.4")
        self.assertTrue(eval_result.triage_permitted)
        self.assertTrue(all(not m.is_minor for m in enriched))

    def test_safeguarding_gate_unresolvable_household_invokes_section_6_1(self):
        """Missing or unresolvable household -> Invokes Section 6.1 / Section 5.2 fail-safe."""
        eval_result, enriched = PolicyEngine.evaluate(
            requested_action="Review award",
            summary="Unclear household",
            household_data=None,
        )

        self.assertEqual(eval_result.decision, PolicyDecision.UNCLEAR)
        self.assertIn("§6.1", eval_result.applicable_section)
        self.assertFalse(eval_result.triage_permitted)

    def test_policy_section_3_2_suspension_prohibited(self):
        """Section 3.2: Suspension requested -> PROHIBITED / ESCALATE."""
        adult_household = [
            {"name": "Jessica Delgado", "date_of_birth": "1993-07-02", "relationship": "Applicant"}
        ]
        eval_result, _ = PolicyEngine.evaluate(
            requested_action="Suspend assistance pending investigation",
            summary="Anonymous fraud allegation",
            household_data=adult_household,
        )

        self.assertEqual(eval_result.decision, PolicyDecision.PROHIBITED)
        self.assertEqual(eval_result.applicable_section, "ACA-2026/1 §3.2")
        self.assertFalse(eval_result.triage_permitted)

    def test_policy_section_3_4_payment_details_prohibited(self):
        """Section 3.4: Payment details change -> PROHIBITED / ESCALATE."""
        adult_household = [
            {"name": "Sarah Thorne", "date_of_birth": "1993-08-28", "relationship": "Applicant"}
        ]
        eval_result, _ = PolicyEngine.evaluate(
            requested_action="Update payment details",
            summary="Resident asks to change account details",
            household_data=adult_household,
        )

        self.assertEqual(eval_result.decision, PolicyDecision.PROHIBITED)
        self.assertEqual(eval_result.applicable_section, "ACA-2026/1 §3.4")
        self.assertFalse(eval_result.triage_permitted)


    def test_policy_section_3_1_entitlement_alteration_prohibited(self):
        """Section 3.1: Entitlement change -> PROHIBITED."""
        adult_household = [{"name": "Jane Doe", "date_of_birth": "1990-01-01", "relationship": "Applicant"}]
        eval_result, _ = PolicyEngine.evaluate("Alter entitlement", "Increase grant", adult_household)
        self.assertEqual(eval_result.decision, PolicyDecision.PROHIBITED)
        self.assertEqual(eval_result.applicable_section, "ACA-2026/1 §3.1")
        self.assertFalse(eval_result.triage_permitted)

    def test_policy_section_3_3_payment_initiation_prohibited(self):
        """Section 3.3: Issue/cancel payment -> PROHIBITED."""
        adult_household = [{"name": "Jane Doe", "date_of_birth": "1990-01-01", "relationship": "Applicant"}]
        eval_result, _ = PolicyEngine.evaluate("Issue payment", "Emergency cash transfer", adult_household)
        self.assertEqual(eval_result.decision, PolicyDecision.PROHIBITED)
        self.assertEqual(eval_result.applicable_section, "ACA-2026/1 §3.3")
        self.assertFalse(eval_result.triage_permitted)

    def test_policy_section_3_5_communication_prohibited(self):
        """Section 3.5: Send direct communication -> PROHIBITED."""
        adult_household = [{"name": "Jane Doe", "date_of_birth": "1990-01-01", "relationship": "Applicant"}]
        eval_result, _ = PolicyEngine.evaluate("Send letter to resident", "Notice of rent change", adult_household)
        self.assertEqual(eval_result.decision, PolicyDecision.PROHIBITED)
        self.assertEqual(eval_result.applicable_section, "ACA-2026/1 §3.5")
        self.assertFalse(eval_result.triage_permitted)

    def test_policy_section_3_6_disclosure_prohibited(self):
        """Section 3.6: Disclosure outside department -> PROHIBITED."""
        adult_household = [{"name": "Jane Doe", "date_of_birth": "1990-01-01", "relationship": "Applicant"}]
        eval_result, _ = PolicyEngine.evaluate("Disclose resident data to police", "Information request", adult_household)
        self.assertEqual(eval_result.decision, PolicyDecision.PROHIBITED)
        self.assertEqual(eval_result.applicable_section, "ACA-2026/1 §3.6")
        self.assertFalse(eval_result.triage_permitted)

    def test_policy_section_3_8_irreversible_prohibited(self):
        """Section 3.8: Irreversible action -> PROHIBITED."""
        adult_household = [{"name": "Jane Doe", "date_of_birth": "1990-01-01", "relationship": "Applicant"}]
        eval_result, _ = PolicyEngine.evaluate("Permanently delete resident records", "Resident request", adult_household)
        self.assertEqual(eval_result.decision, PolicyDecision.PROHIBITED)
        self.assertEqual(eval_result.applicable_section, "ACA-2026/1 §3.8")
        self.assertFalse(eval_result.triage_permitted)


if __name__ == "__main__":
    unittest.main()
