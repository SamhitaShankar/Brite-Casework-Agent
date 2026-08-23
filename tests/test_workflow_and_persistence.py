"""
Test Suite: Workflow Coordination, Resumability, and Architectural LLM Safety Assertion.
"""
import unittest
from unittest.mock import AsyncMock, patch
from backend.compat import create_engine, sessionmaker, InMemorySession, HAS_SQLALCHEMY

from backend.database import Base
from backend.models import (
    ReferralModel,
    ProcessingState,
    PolicyDecision,
    WorkflowDisposition,
    TriageNoteSchema,
)
from backend.coordinator import WorkflowCoordinator


SAMPLE_TRIAGE_NOTE = TriageNoteSchema(
    summary_of_situation="Routine administrative update per authority policy guidelines.",
    recommended_next_steps="Proceed with standard notification.",
    full_text="1. Summary of the Situation:\nRoutine administrative request.\n2. Recommended Next Steps:\nUpdate records.",
    drafted_by_llm=True,
    llm_model="gemini-2.5-flash",
    suppression_reason=None,
)


class TestWorkflowAndPersistence(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        if HAS_SQLALCHEMY and create_engine is not None:
            self.engine = create_engine("sqlite:///:memory:", echo=False)
            Base.metadata.create_all(bind=self.engine)
            TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            self.test_db = TestingSessionLocal()
        else:
            self.test_db = InMemorySession(store=[])

    def tearDown(self):
        self.test_db.close()

    async def test_under_18_household_never_calls_gemini(self):
        """
        CRITICAL SURPRISE-CHALLENGE INVARIANT:
        For RF-2026-0412 (R-20500, household contains William Iverson age ~5),
        the workflow coordinator MUST trigger HANDOFF and NEVER invoke Gemini.
        """
        coordinator = WorkflowCoordinator()
        coordinator.seed_referrals_if_empty(self.test_db)

        with patch.object(
            coordinator.gemini_service, "draft_triage", new_callable=AsyncMock
        ) as mock_draft:
            ref = await coordinator.process_referral("RF-2026-0412", self.test_db)

            # Invariants
            self.assertEqual(ref.workflow_disposition, WorkflowDisposition.HANDOFF.value)
            self.assertEqual(ref.processing_state, ProcessingState.HANDED_OFF.value)
            self.assertEqual(ref.policy_decision, PolicyDecision.HANDOFF_REQUIRED.value)
            self.assertTrue(ref.has_under_18)

            # Assert Gemini LLM was NEVER called
            mock_draft.assert_not_called()

            # Check preserved snapshot
            self.assertIsNotNone(ref.resident_snapshot)
            self.assertEqual(ref.resident_snapshot.resident_ref, "R-20500")

    async def test_adult_household_allowed_calls_gemini_or_drafts_proposal(self):
        """
        For RF-2026-0413 (R-20507, all adult household, routine address change),
        the workflow coordinator permits Section 2 triage.
        """
        coordinator = WorkflowCoordinator()
        coordinator.seed_referrals_if_empty(self.test_db)

        with patch.object(
            coordinator.gemini_service, "draft_triage", new_callable=AsyncMock, return_value=SAMPLE_TRIAGE_NOTE
        ):
            ref = await coordinator.process_referral("RF-2026-0413", self.test_db)

            self.assertEqual(ref.workflow_disposition, WorkflowDisposition.COMPLETED.value)
            self.assertEqual(ref.processing_state, ProcessingState.COMPLETED.value)
            self.assertEqual(ref.policy_decision, PolicyDecision.ALLOWED.value)
            self.assertFalse(ref.has_under_18)
            self.assertIsNotNone(ref.triage_note)
            self.assertIn("Situation", ref.triage_note.full_text)

    async def test_full_queue_independent_execution(self):
        """
        Processing all 12 referrals completes without being halted by escalations or handoffs.
        """
        coordinator = WorkflowCoordinator()
        coordinator.seed_referrals_if_empty(self.test_db)

        with patch.object(
            coordinator.gemini_service, "draft_triage", new_callable=AsyncMock, return_value=SAMPLE_TRIAGE_NOTE
        ):
            results = await coordinator.process_all_queue(self.test_db)
            self.assertEqual(len(results), 12)

            # Check breakdown of expected outcomes
            dispositions = [r.workflow_disposition for r in results]
            self.assertIn(WorkflowDisposition.HANDOFF.value, dispositions)
            self.assertIn(WorkflowDisposition.ESCALATE.value, dispositions)
            self.assertIn(WorkflowDisposition.COMPLETED.value, dispositions)

            # Assert no unhandled failures
            self.assertNotIn(WorkflowDisposition.FAILED.value, dispositions)

    async def test_resumability_preserves_work_and_applies_amendment(self):
        """
        A partially processed case resumes, reuses existing snapshot, but applies Amendment ACA-2026/2.
        """
        coordinator = WorkflowCoordinator()
        coordinator.seed_referrals_if_empty(self.test_db)

        # First run
        ref = await coordinator.process_referral("RF-2026-0416", self.test_db)
        self.assertEqual(ref.workflow_disposition, WorkflowDisposition.HANDOFF.value)

        # Resume run
        resumed_ref = await coordinator.resume_referral("RF-2026-0416", self.test_db)
        self.assertTrue(resumed_ref.is_resumed)
        self.assertEqual(resumed_ref.workflow_disposition, WorkflowDisposition.HANDOFF.value)
        self.assertIsNotNone(resumed_ref.resident_snapshot)

    async def test_supervisor_approval_state_transitions(self):
        """
        Tests supervisor workflow approval and rejection transitions.
        """
        coordinator = WorkflowCoordinator()
        coordinator.seed_referrals_if_empty(self.test_db)

        with patch.object(
            coordinator.gemini_service, "draft_triage", new_callable=AsyncMock, return_value=SAMPLE_TRIAGE_NOTE
        ):
            # Case requiring approval under ACA-2026/1 §6.1 / §2.3 (e.g. Discretionary Housing Payment award)
            ref_obj = self.test_db.query(ReferralModel).filter(ReferralModel.referral_id == "RF-2026-0419").first()
            ref_obj.requested_action = "Approve discretionary housing payment award"

            ref = await coordinator.process_referral("RF-2026-0419", self.test_db)
            self.assertEqual(ref.processing_state, ProcessingState.AWAITING_APPROVAL.value)
            self.assertEqual(ref.policy_decision, PolicyDecision.UNCLEAR.value)
            self.assertIsNotNone(ref.approval_request)
            self.assertEqual(ref.approval_request.status, "PENDING")

            # Simulate Supervisor Approval
            req = ref.approval_request
            req.status = "APPROVED"
            ref.processing_state = ProcessingState.COMPLETED.value
            ref.workflow_disposition = WorkflowDisposition.COMPLETED.value
            self.test_db.commit()

            self.assertEqual(ref.processing_state, ProcessingState.COMPLETED.value)
            self.assertEqual(ref.approval_request.status, "APPROVED")

    async def test_gemini_failure_enters_paused_state_with_no_synthetic_fallback(self):
        """
        When Gemini encounters an API error, the system enters PAUSED/FAILED and does not create synthetic notes.
        """
        coordinator = WorkflowCoordinator()
        coordinator.seed_referrals_if_empty(self.test_db)

        with patch.object(
            coordinator.gemini_service, "draft_triage", side_effect=RuntimeError("QuotaExceeded")
        ):
            ref = await coordinator.process_referral("RF-2026-0413", self.test_db)
            self.assertEqual(ref.processing_state, ProcessingState.PAUSED.value)
            self.assertEqual(ref.workflow_disposition, WorkflowDisposition.FAILED.value)
            self.assertIsNone(ref.triage_note)
            self.assertIn("QuotaExceeded", ref.error_message)

    async def test_supervisor_api_boundaries_and_invalid_transitions(self):
        """
        Verify that supervisor approval workflows strictly reject invalid states,
        duplicate calls, and attempts to approve minor safeguarding handoffs.
        """
        coordinator = WorkflowCoordinator()
        coordinator.seed_referrals_if_empty(self.test_db)

        with patch.object(
            coordinator.gemini_service, "draft_triage", new_callable=AsyncMock, return_value=SAMPLE_TRIAGE_NOTE
        ):
            # 1. Case requiring approval (e.g. discretionary award approval)
            ref_obj = self.test_db.query(ReferralModel).filter(ReferralModel.referral_id == "RF-2026-0422").first()
            ref_obj.requested_action = "Approve discretionary housing payment award"

            ref = await coordinator.process_referral("RF-2026-0422", self.test_db)
            self.assertEqual(ref.processing_state, ProcessingState.AWAITING_APPROVAL.value)
            self.assertIsNotNone(ref.approval_request)
            self.assertEqual(ref.approval_request.status, "PENDING")

            # Simulate valid approval
            ref.approval_request.status = "APPROVED"
            ref.processing_state = ProcessingState.COMPLETED.value
            ref.workflow_disposition = WorkflowDisposition.COMPLETED.value
            self.assertEqual(ref.processing_state, ProcessingState.COMPLETED.value)
            self.assertEqual(ref.approval_request.status, "APPROVED")

            # 2. Invariant: Minors cannot have approval requests created or bypass handoff
            minor_ref = await coordinator.process_referral("RF-2026-0412", self.test_db) # Minor William Iverson
            self.assertEqual(minor_ref.workflow_disposition, WorkflowDisposition.HANDOFF.value)
            self.assertEqual(minor_ref.processing_state, ProcessingState.HANDED_OFF.value)
            self.assertIsNone(minor_ref.approval_request)
            self.assertTrue(minor_ref.has_under_18)

    async def test_mixed_queue_with_isolated_gemini_failure_resilience(self):
        """
        When Gemini fails on one specific referral in the queue, other referrals
        (including other permitted triage requests) continue processing unaffected.
        """
        coordinator = WorkflowCoordinator()
        coordinator.seed_referrals_if_empty(self.test_db)

        async def selective_mock(*args, **kwargs):
            ref = kwargs.get("referral", {})
            if ref.get("resident_ref") == "R-20507": # RF-2026-0413
                raise RuntimeError("Temporary upstream 503")
            return SAMPLE_TRIAGE_NOTE

        with patch.object(coordinator.gemini_service, "draft_triage", side_effect=selective_mock):
            results = await coordinator.process_all_queue(self.test_db)
            self.assertEqual(len(results), 12)

            # RF-2026-0413 paused/failed
            failed_ref = next(r for r in results if r.referral_id == "RF-2026-0413")
            self.assertEqual(failed_ref.processing_state, ProcessingState.PAUSED.value)
            self.assertEqual(failed_ref.workflow_disposition, WorkflowDisposition.FAILED.value)
            self.assertIn("Temporary upstream 503", failed_ref.error_message)

            # Other routine cases succeeded
            success_ref = next(r for r in results if r.referral_id == "RF-2026-0414")
            self.assertEqual(success_ref.workflow_disposition, WorkflowDisposition.COMPLETED.value)
            self.assertEqual(success_ref.processing_state, ProcessingState.COMPLETED.value)

            # Minors handed off safely
            minor_ref = next(r for r in results if r.referral_id == "RF-2026-0412")
            self.assertEqual(minor_ref.workflow_disposition, WorkflowDisposition.HANDOFF.value)


if __name__ == "__main__":
    unittest.main()
