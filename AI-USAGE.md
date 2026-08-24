# AI Usage Declaration

This project was developed with the assistance of an AI coding assistant (Antigravity), used strictly to accelerate repetitive tasks and scaffold boilerplate, allowing the primary focus to remain on the core hackathon requirements.

## Project Architecture & Engineering
- **System Architecture & Fallback Design:** The overall application architecture was explicitly designed to include a zero-dependency Python fallback mechanism (`compat.py`). This allows the system to run purely on the standard library without requiring external SQL databases or heavy SDKs.
- **Domain Logic & Deterministic Gates:** The core business logic and interpretation of the casework policies (ACA-2026/1 and ACA-2026/2) were manually engineered. It was a critical design requirement that the LLM be entirely stripped of decision-making authority, which was achieved by building hard deterministic safeguard gates (e.g., the Under-18 check) that forcefully short-circuit the generative AI when policy dictates.
- **Integration & Control Flow:** The critical pathway in `coordinator.py` was authored to enforce a strict separation of concerns, ensuring that the AI can never override a hardcoded policy or perform irreversible actions on a case.

## AI Assistant Usage
- **UI Prototyping & Scaffolding:** The AI was utilized to rapidly generate React components, Tailwind CSS layouts, and basic state management scaffolding based on specific UI mockups and design requirements for the dashboard.
- **Debugging & Troubleshooting:** The AI provided assistance in troubleshooting tricky frontend layout issues (such as resolving CSS flexbox collapsing on the timeline view) and backend data issues (such as resolving timezone offset discrepancies between SQLite and Javascript).
- **Boilerplate Code:** The AI was leveraged to write repetitive boilerplate code, including standard FastAPI routing, database model schemas, and initial project structure setup.
