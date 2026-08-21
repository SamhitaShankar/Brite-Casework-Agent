"""
Deterministic Policy Engine for Calder County Department of Household Services.
Enforces:
  1. Policy ACA-2026/1 (Permitted vs Supervisor-required actions, Escalation, Section 6.1 fail-safe)
  2. Amendment ACA-2026/2 (Under-18 Safeguarding Gate §3.9, Handoff vs Escalation §3.3)

NO LLM logic or heuristic guessing is used here. Decisions are 100% deterministic code.
"""
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple
from .models import PolicyDecision, PolicyEvaluationSchema, HouseholdMemberSchema


# Reference date for the overnight queue intake (17 March 2026)
REFERENCE_DATE = date(2026, 3, 17)


def calculate_age(dob_str: str, as_of: date = REFERENCE_DATE) -> int:
    """Calculate age from ISO DOB string (YYYY-MM-DD)."""
    try:
        dob = datetime.strptime(dob_str.strip(), "%Y-%m-%d").date()
        return (
            as_of.year
            - dob.year
            - ((as_of.month, as_of.day) < (dob.month, dob.day))
        )
    except Exception:
        return 0


class SafeguardingGate:
    """
    Evaluates household composition under Amendment ACA-2026/2 §3.9.
    Must be executed before triage generation is reachable.
    """

    @classmethod
    def evaluate_household(
        cls,
        household_data: Optional[List[Dict[str, Any]]],
        as_of: date = REFERENCE_DATE,
    ) -> Tuple[bool, List[HouseholdMemberSchema], Optional[PolicyEvaluationSchema]]:
        """
        Returns:
          (has_minor: bool, enriched_members: List, evaluation: Optional[PolicyEvaluationSchema])
        """
        # Section 5.2: Where household composition cannot be established,
        # 3.9 is treated as applying via Section 6.1 fail-safe.
        if household_data is None or len(household_data) == 0:
            eval_result = PolicyEvaluationSchema(
                decision=PolicyDecision.UNCLEAR,
                applicable_section="ACA-2026/1 §6.1 / ACA-2026/2 §5.2",
                rule_title="Uncertainty Fail-Safe: Household Composition Unresolvable",
                rationale="Household composition could not be established from official Department records. Under Section 6.1 and Section 5.2, this is treated as engaging Section 3 safeguarding restrictions.",
                triage_permitted=False,
                human_action_required="Manually verify resident household composition and conduct casework.",
                evaluated_at=datetime.utcnow(),
            )
            return True, [], eval_result

        enriched_members: List[HouseholdMemberSchema] = []
        minors: List[str] = []

        for member in household_data:
            dob_str = member.get("date_of_birth", "")
            age = calculate_age(dob_str, as_of)
            is_minor = age < 18
            if is_minor:
                minors.append(f"{member.get('name')} (Age {age}, DOB {dob_str})")

            enriched_members.append(
                HouseholdMemberSchema(
                    name=member.get("name", "Unknown"),
                    date_of_birth=dob_str,
                    relationship=member.get("relationship", "Unknown"),
                    calculated_age=age,
                    is_minor=is_minor,
                )
            )

        if len(minors) > 0:
            eval_result = PolicyEvaluationSchema(
                decision=PolicyDecision.HANDOFF_REQUIRED,
                applicable_section="ACA-2026/2 §3.9",
                rule_title="Drafting triage note for household with minor under 18",
                rationale=(
                    f"Household composition contains {len(minors)} person(s) under age 18: "
                    + ", ".join(minors)
                    + ". Under Amendment ACA-2026/2 §3.9, drafting a triage note for a household with a child requires caseworker judgement from the outset. Automated triage drafting is prohibited."
                ),
                triage_permitted=False,
                human_action_required="Hand off referral and retrieved resident history to caseworker for manual triage.",
                evaluated_at=datetime.utcnow(),
            )
            return True, enriched_members, eval_result

        return False, enriched_members, None


import os
import json

HERE = os.path.dirname(os.path.abspath(__file__))
POLICY_DATA_PATH = os.path.join(HERE, "..", "data", "policy_rules.json")

class PolicyEngine:
    """
    Deterministic Authority Policy ACA-2026/1 & ACA-2026/2 engine.
    Policy rules are loaded from data/policy_rules.json.
    """
    _policy_rules = None

    @classmethod
    def load_policy(cls):
        if cls._policy_rules is None:
            with open(POLICY_DATA_PATH, "r", encoding="utf-8") as f:
                cls._policy_rules = json.load(f)
        return cls._policy_rules

    @classmethod
    def evaluate(
        cls,
        requested_action: str,
        summary: str,
        household_data: Optional[List[Dict[str, Any]]],
        as_of: date = REFERENCE_DATE,
    ) -> Tuple[PolicyEvaluationSchema, List[HouseholdMemberSchema]]:
        """
        Step 1: Check Safeguarding Gate (Amendment ACA-2026/2 §3.9)
        Step 2: Check Policy ACA-2026/1 from JSON rules
        """
        # Step 1: Safeguarding Gate
        has_minor, enriched_members, safeguard_eval = SafeguardingGate.evaluate_household(
            household_data, as_of=as_of
        )
        if safeguard_eval is not None:
            return safeguard_eval, enriched_members

        # Step 2: Policy ACA-2026/1 Authority Checks
        action_norm = requested_action.strip().lower()
        summary_norm = summary.strip().lower()

        policy_data = cls.load_policy()

        for rule in policy_data["rules"]:
            match = False
            if "match_any" in rule:
                if any(kw in action_norm for kw in rule["match_action"]) and any(kw in action_norm or kw in summary_norm for kw in rule["match_any"]):
                    match = True
            elif "match_summary" in rule:
                if any(kw in action_norm for kw in rule["match_action"]) and all(kw in summary_norm for kw in rule["match_summary"]):
                    match = True
            else:
                if any(kw in action_norm for kw in rule["match_action"]):
                    match = True

            if match:
                decision_enum = getattr(PolicyDecision, rule["decision"])
                return (
                    PolicyEvaluationSchema(
                        decision=decision_enum,
                        applicable_section=rule["section"],
                        rule_title=rule["title"],
                        rationale=rule["rationale_template"],
                        triage_permitted=rule["triage_permitted"],
                        human_action_required=rule["human_action"],
                        evaluated_at=datetime.utcnow(),
                    ),
                    enriched_members,
                )

        # Default fallback rule (Section 6.1)
        default_rule = policy_data["default_rule"]
        return (
            PolicyEvaluationSchema(
                decision=getattr(PolicyDecision, default_rule["decision"]),
                applicable_section=default_rule["section"],
                rule_title=default_rule["title"],
                rationale=default_rule["rationale_template"],
                triage_permitted=default_rule["triage_permitted"],
                human_action_required=default_rule["human_action"],
                evaluated_at=datetime.utcnow(),
            ),
            enriched_members,
        )
