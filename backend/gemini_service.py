"""
Gemini LLM Triage Drafting Service with Architectural Safety Guards.

SAFETY INVARIANT:
  The LLM MUST NEVER be called if:
    1. Household includes a minor under 18 (Amendment ACA-2026/2 §3.9)
    2. Policy decision is PROHIBITED, HANDOFF_REQUIRED, or UNCLEAR
  An explicit assertion prevents accidental invocation.
"""
import os
import logging
from typing import Dict, Any, List, Optional
from .models import TriageNoteSchema

logger = logging.getLogger("brite.gemini_service")


class GeminiTriageService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            # Fallback: forcefully read .env.local if environment inheritance failed
            try:
                with open(".env.local", "r") as f:
                    for line in f:
                        if line.startswith("GEMINI_API_KEY="):
                            self.api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
            except Exception:
                pass
        self.client = None
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Google GenAI Client: {e}")

    async def draft_triage(
        self,
        referral: Dict[str, Any],
        resident: Dict[str, Any],
        household: List[Dict[str, Any]],
        events: List[Dict[str, Any]],
        policy_section: str,
        has_minor: bool,
        triage_permitted: bool,
    ) -> TriageNoteSchema:
        """
        Drafts a structured triage note.
        STRICT ARCHITECTURAL GUARD: Throws error if safety invariant is violated.
        """
        # Hard Architectural Guardrail Check
        if has_minor:
            raise RuntimeError(
                "CRITICAL SAFETY VIOLATION: Attempted to invoke Gemini LLM triage generation for a household containing a minor under 18! This violates Amendment ACA-2026/2 §3.9."
            )
        if not triage_permitted:
            raise RuntimeError(
                f"CRITICAL POLICY VIOLATION: Triage generation is not permitted under policy {policy_section}."
            )

        resident_name = resident.get("household", [{}])[0].get("name", "Resident")
        summary_text = referral.get("summary", "")
        requested_action = referral.get("requested_action", "")
        benefit_code = resident.get("benefit_code", "N/A")
        award_monthly = resident.get("award_monthly", 0.0)
        recent_events = events[-3:] if events else []

        prompt = f"""You are the Calder County Automated Casework Assistant.
Review the following case details and draft a concise, professional casework triage summary.

Resident Reference: {referral.get('resident_ref')}
Primary Applicant: {resident_name}
Benefit Code: {benefit_code}
Current Monthly Award: £{award_monthly:.2f}
Referral Source: {referral.get('source')}
Referral Urgency: {referral.get('urgency')}
Referral Summary: {summary_text}
Requested Action: {requested_action}
Applicable Authority Rule: {policy_section}

Recent Case History:
{json_format_events(recent_events)}

OUTPUT REQUIREMENTS:
Please provide your response strictly as a JSON object with EXACTLY two keys:
1. "summary": A concise summary of the situation (2-3 clear sentences max). DO NOT repeat the prompt, preamble, or title.
2. "next_steps": Recommended next steps for the caseworker (clear bullet points). DO NOT repeat the preamble or title.
Format in a crisp, objective, administrative tone. DO NOT include markdown formatting outside of the bullet points.
"""

        # Dynamically fetch API key at call time to prevent caching issues
        current_api_key = self.api_key or os.getenv("GEMINI_API_KEY")
        if not current_api_key:
            try:
                with open(".env.local", "r") as f:
                    for line in f:
                        if line.startswith("GEMINI_API_KEY="):
                            current_api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
            except Exception:
                pass

        if not current_api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable is not configured in the server environment.")
        full_text = ""
        model_used = "agent-flash-latest"
        
        # Direct REST API invocation with robust retry loop and model fallback
        import urllib.request
        import json
        import time

        candidate_models = ["gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-1.5-pro"]

        for m in candidate_models:
            for attempt in range(2):
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={current_api_key}"
                    req_data = json.dumps({
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": 0.2,
                            "maxOutputTokens": 1000,
                            "responseMimeType": "application/json"
                        }
                    }).encode("utf-8")
                    req = urllib.request.Request(url, data=req_data, headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        res_json = json.loads(resp.read().decode("utf-8"))
                        candidates = res_json.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                full_text = parts[0].get("text", "").strip()
                                model_used = m
                                break
                except Exception as e:
                    logger.warning(f"Attempt {attempt + 1} for model {m} encountered: {e}")
                    time.sleep(0.5 * (attempt + 1))
            if full_text:
                break

        if not full_text:
            raise RuntimeError("Agent LLM service returned an empty or invalid response across all candidate models.")

        summary_part, next_steps_part = parse_llm_response(full_text)

        return TriageNoteSchema(
            summary_of_situation=summary_part,
            recommended_next_steps=next_steps_part,
            full_text=full_text,
            drafted_by_llm=True,
            llm_model=model_used,
            suppression_reason=None,
        )


def json_format_events(events: List[Dict[str, Any]]) -> str:
    if not events:
        return "No recent case events on file."
    lines = []
    for ev in events:
        lines.append(f"- {ev.get('date')}: [{ev.get('type')}] {ev.get('detail')}")
    return "\n".join(lines)


def parse_llm_response(text: str) -> tuple[str, str]:
    import json
    try:
        data = json.loads(text)
        summary = data.get("summary", "")
        steps = data.get("next_steps", "")
        if summary and steps:
            return summary.strip(), steps.strip()
    except Exception:
        pass

    if "Recommended Next Steps" in text:
        parts = text.split("Recommended Next Steps", 1)
        summary = parts[0].replace("Summary of the Situation", "").replace("1.", "").strip(":\n#* ")
        steps = "Recommended Next Steps" + parts[1]
        return summary, steps
    return text[:200] + "...", text

