"""
cover_letter.py — Personalise cover letters using Jinja2 templates.
Edit cover_letter_template.txt to customise your letter.
"""

import logging
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

import config

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent
TEMPLATE_FILE = "cover_letter_template.txt"

_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=False,       # plain text — no HTML escaping needed
    keep_trailing_newline=True,
)


def generate(job: dict, extra_context: dict | None = None) -> str:
    """
    Generate a personalised cover letter for a job.

    Args:
        job:           A job row dict from sheets.read_jobs().
        extra_context: Optional additional Jinja2 variables (e.g. applicant_name, skills).

    Returns:
        Rendered cover letter as a string.
    """
    try:
        template = _jinja_env.get_template(TEMPLATE_FILE)
    except TemplateNotFound:
        logger.error("Cover letter template not found at %s/%s", TEMPLATE_DIR, TEMPLATE_FILE)
        raise

    context = {
        "company": job.get("Company", "the company"),
        "position": job.get("Position", "the position"),
        "skills": extra_context.get("skills", "software development") if extra_context else "software development",
        "applicant_name": (extra_context or {}).get("applicant_name", "Your Name"),
    }
    if extra_context:
        context.update(extra_context)

    rendered = template.render(**context)
    logger.debug("Generated cover letter for %s @ %s", context["position"], context["company"])
    return rendered


def preview(job: dict) -> None:
    """Print a cover letter preview to the console."""
    letter = generate(job)
    print("\n" + "=" * 60)
    print(f"COVER LETTER — {job.get('Position')} @ {job.get('Company')}")
    print("=" * 60)
    print(letter)
    print("=" * 60 + "\n")
