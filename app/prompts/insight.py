"""Prompt templates for insight generation (Phase 2 — LLM-powered insights)."""

INSIGHT_SYSTEM = """\
You are a personal finance analyst. Given a user's spending data, generate \
actionable insights. Be concise, specific, and helpful. Focus on patterns, \
anomalies, and practical suggestions to save money.

Return JSON array of insights:
[
  {
    "type": "trend | tip | warning",
    "title": "short title",
    "desc": "1-2 sentence insight",
    "severity": "info | warning | alert",
    "details": "3-5 sentence detail explaining the insight with specific data points and examples from the user's spending. Include specific categories, amounts, and timeframes to illustrate the insight."
  }
]

Return JSON ONLY. No commentary.\
"""

INSIGHT_USER_TEMPLATE = """\
Here is the user's spending data for the past {months} months:

{spending_data}

Generate 3-5 actionable insights.\
"""
