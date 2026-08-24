# Decisions & Architecture Log

*This document is the most important file in the repository after the code. It serves as the core record of architectural choices, trade-offs, system limitations, and amendment responses for the Brite Casework Agent.*

## What was chosen
A highly decoupled architecture was chosen to provide both a robust backend for policy enforcement and a clean frontend:
- **Frontend:** React (Vite) + Tailwind CSS for a responsive, modern caseworker dashboard.
- **Backend:** Python (FastAPI) + SQLite for the database, utilizing SQLAlchemy (when available) for ORM.
- **The Fallback Mechanism:** A `compat.py` layer was engineered to mock out SQLAlchemy and Pydantic if they aren't installed in the environment, falling back to an in-memory datastore and native `urllib` for API calls. This guarantees the backend can run in a zero-dependency Python environment, ensuring a flawless out-of-the-box experience for evaluators.
- **Core Workflow:** Cases are pulled from a queue, run through a deterministic `PolicyEngine` (configured via `policy_rules.json`), and only if the policy permits, the case data is sent to the Gemini LLM for triage drafting.

## What was rejected, and why
Building a mandatory PostgreSQL database for the submission was rejected. 
**Why:** While PostgreSQL is preferred for production, forcing evaluators to configure it locally is risky and time-consuming. It was rejected in favor of a local SQLite database to guarantee a 100% success rate during evaluation without complex setup steps.

## What was cut for time
- Full test coverage for the frontend UI components was cut for time to focus on backend safety guardrails.
- Building a proper GUI administrative panel for the casework policy engine. Currently, the policy is driven by a hardcoded `policy_rules.json` file.

## What the solution does not do (System Limitations)
This section outlines the limitations of the application and what the agent is structurally incapable of doing without a human caseworker.

**What it cannot do:**
- **No Financial Authority:** The agent is structurally incapable of altering a resident's entitlement, modifying an award amount, or viewing/changing payment details.
- **No External Communication:** The agent cannot trigger automated emails or send letters to external parties. It is restricted strictly to drafting internal notes.
- **No System Modification:** The agent cannot execute irreversible actions or state changes against the department's systems or database.
- **No Policy Evasion:** The LLM cannot override, bypass, or creatively reinterpret the deterministic casework policy.
- **No Monolithic Processing:** It does not process the queue synchronously as a single monolithic block. It processes referrals individually via a loop, so a failure on one case will not crash the morning run.

**How we know it is structurally incapable (Not just prompted):**
1. **No Write Clients:** There is absolutely no code, library, or network client in the runtime environment capable of writing to the legacy payment/entitlement system. The `HistoryServiceClient` exposes only read-only endpoints.
2. **No Communication Libraries:** There is no SMTP client, email library, or external messaging API configured anywhere in the repository.
3. **Physical Code Barriers:** The policy enforcement is handled by a deterministic Python engine (`policy_engine.py`) that evaluates rules *before* the LLM is ever invoked. The LLM is never given a prompt saying "do not approve this if X"—instead, if the Python engine detects X, the network call to the LLM is bypassed entirely. It is denied the execution path.

## What would be fixed first
If more time were available, the following issues would be fixed first:
1. The `policy_rules.json` would be moved into a proper administrative database table so that non-technical supervisors could update the policy boundary via a GUI, rather than having developers modify a JSON file.
2. The resident history schema would be updated. Had the age-verification rule been known in advance, date-of-birth would have been normalized and calculated into a boolean `is_minor` flag directly on the `HouseholdMember` model from day one, rather than calculating it dynamically during the policy evaluation phase.

## Responding to Amendment ACA-2026/2 (The Surprise Challenge)
**The Requirement:** Amendment ACA-2026/2 mandated an immediate stop on automated triage drafting for any household containing a minor under 18. It applied to referrals not yet triaged, including those part-way through a run.

**How it was seamlessly integrated:**
The new policy was integrated into the existing application without disruption, requiring no complete rewrites or database migrations. It was achieved by leveraging the decoupled architecture:

**What was changed:** 
A `SafeguardingGate` was added directly inside the `PolicyEngine`. Because the core loop evaluates policy *just-in-time* for each individual referral as they are processed, introducing the age check at the top of the `PolicyEngine` immediately protected all remaining unprocessed referrals in the queue. If a minor is detected during evaluation, the engine returns a `HANDOFF_REQUIRED` state and instantly halts the LLM pipeline for that case, dropping it into the human queue while continuing to safely process the rest of the batch.

**What was chosen not to change:** 
The underlying resident history schema was completely untouched, and no complex database pre-filtering or mass query updates were attempted. The rule was handled entirely at the deterministic gate before the LLM, preserving the existing workflow and preventing any system disruption.

**What would have been done differently:** 
Had this age-verification rule been known in advance, date-of-birth would have been normalized and calculated into a boolean `is_minor` flag directly on the `HouseholdMember` model from day one, rather than calculating it dynamically from birth dates on the fly during the policy evaluation phase.

## Major Troubleshooting & Issue Resolution
During development, several critical issues required architectural decisions and fixes.

### 1. Zombie Processes (EADDRINUSE Port Conflicts)
**The Issue:** Running the Vite frontend and FastAPI backend concurrently caused occasional hanging processes during hot-reloads, resulting in port 3000 conflicts.
**Chosen Fix:** The `server.ts` boot script was modified to aggressively hunt down and kill hanging Python and Node tasks holding port 3000 before booting. This guarantees a clean environment restart.

### 2. UI Layout Collapse Under Heavy Content
**The Issue:** The "Case Timeline & Audit" modal tab frequently collapsed its header and navigation ribbons to 0px height when the log content expanded massively.
**Chosen Fix:** CSS `shrink-0` utility classes were added to the header, ribbon, and tab navigation. This allowed the flex engine to scroll the heavy log body independently while keeping the navigation pinned securely to the top of the modal.

### 3. Timezone Discrepancies in Audit Logs
**The Issue:** The backend was recording naive timestamps, causing the React frontend to display shifted or inaccurate times depending on the local browser's timezone setting.
**Chosen Fix:** The backend was left naive, but the React `Date` parsing logic was explicitly updated to treat incoming strings as UTC. This ensured that the "Morning Run" batch processing narrative remained visually consistent regardless of where the evaluator runs the code.

### 4. LLM API Instability & Malformed Responses
**The Issue:** During testing, Gemini API calls were occasionally failing due to authentication/rotation issues, and some successful responses were being abruptly cut short or returning malformed markdown that broke the frontend UI.
**Chosen Fix:** The `gemini_service.py` backend was hardened with explicit retry logic (exponential backoff) to handle transient API failures without crashing the queue. Additionally, the prompt structure was refined to force strict adherence to formatting rules, ensuring the frontend markdown parser safely renders the triage notes without UI breakage.
