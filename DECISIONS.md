# Decisions & Architecture Log

This document serves as the core record of architectural choices, structural guardrails, trade-offs, and amendment responses for the Brite Casework Agent.

## Day 1: Stack Choice & Initial Architecture
**What I chose:** 
I chose a highly decoupled architecture: React (Vite) + Tailwind for the frontend, and Python (FastAPI) + SQLite/SQLAlchemy for the backend. 

**Why:** 
I needed a stack that could run effortlessly out-of-the-box for evaluators while providing a robust backend to handle policy enforcement. I intentionally built a fallback `compat.py` layer that mocks out SQLAlchemy and Pydantic if they aren't installed, and uses `urllib` natively for Gemini API calls. This guarantees the backend can run in a zero-dependency Python environment if necessary.

## Structural Guardrails: What the Agent is Incapable of Doing
Per the evaluation rubric, this section explicitly outlines what the agent is structurally incapable of doing without a human.

**What it cannot do:** 
The agent is structurally incapable of altering a resident's entitlement, award amount, or payment details, and executing irreversible actions against the department's systems.

**How I know:**
1. **No Execution API Clients:** The runtime environment does not contain any code, libraries, or network clients capable of writing to the legacy payment/entitlement system. The `HistoryServiceClient` is strictly read-only.
2. **Policy as Data (Decoupled Logic):** The LLM is **never** asked "is this action alloId?". The deterministic Python engine evaluates the action based on a strict `policy_rules.json` file *before* the LLM is invoked.
3. **Hard Short-Circuiting (The Gate):** If the deterministic `PolicyEngine` flags a referral as `PROHIBITED` or `APPROVAL_REQUIRED`, the code path physically short-circuits. The network call to the LLM is bypassed entirely. The agent isn't "instructed to ask nicely"—it is denied the execution path.

## Trade-offs: What I cut for time & What the solution does not do
**What I rejected:** 
I rejected building a mandatory PostgreSQL database for the submission. 

**Why (What I cut for time):** 
While PostgreSQL is our preferred production target, forcing evaluators to configure it locally is risky and time-consuming. I cut it in favor of a local SQLite database to guarantee a 100% success rate when evaluators clone and run the repository.

**What the solution does not do:** 
- It does not attempt to automatically draft emails to external parties, even as a prompt instruction. 
- It does not process the queue synchronously as a single monolithic block. It processes referrals individually via `process_all_queue`, so a failure on one case will not crash the morning run.
- It does not evaluate the policy using the LLM. The policy boundaries are strictly enforced via the JSON rules engine.

**What I would fix first:**
If I had more time, I would move the `policy_rules.json` into a proper administrative database table so that non-technical supervisors could update the policy boundary via a GUI, rather than having developers modify the JSON file.

## Day 2: Responding to Amendment ACA-2026/2
**The Requirement:** 
Amendment ACA-2026/2 mandated an immediate stop on automated triage drafting for any household containing a minor under 18. It applied to referrals not yet triaged, including those part-way through a run.

**How I handled it:**
1. **What I changed:** I implemented a `SafeguardingGate` inside the `PolicyEngine`. Because our processing loop (`process_all_queue`) evaluates policy *just-in-time* for each individual referral, introducing the check at the top of the `PolicyEngine` immediately applied it to all unprocessed referrals in the queue. If a minor is detected, it returns a `HANDOFF_REQUIRED` state and immediately halts the LLM pipeline for that case.
2. **What I chose not to change:** I didn't change the underlying resident history schema or attempt complex database pre-filtering. I enforced the rule at the deterministic gate before the LLM.
3. **What I would have done differently:** Had I known this age-verification rule was coming, I would have normalized date-of-birth and calculated age into a boolean `is_minor` flag directly on the `HouseholdMember` model from day one, rather than calculating it on the fly during the policy evaluation phase.
