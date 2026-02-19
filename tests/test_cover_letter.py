"""tests/test_cover_letter.py — Unit tests for cover letter generation."""

import sys
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch
import cover_letter


SAMPLE_JOB = {
    "Job_ID": "001",
    "Company": "Acme Corp",
    "Position": "Software Engineer",
    "Status": "Not Applied",
    "Job_URL": "https://www.linkedin.com/jobs/view/123456",
    "_row_index": 2,
}


def test_generates_without_error():
    letter = cover_letter.generate(SAMPLE_JOB)
    assert isinstance(letter, str)
    assert len(letter) > 50


def test_placeholders_replaced():
    letter = cover_letter.generate(SAMPLE_JOB)
    assert "Acme Corp" in letter
    assert "Software Engineer" in letter
    # No un-rendered Jinja tags left
    assert "{{" not in letter
    assert "}}" not in letter


def test_custom_context():
    letter = cover_letter.generate(SAMPLE_JOB, extra_context={"applicant_name": "Jane Doe", "skills": "machine learning"})
    assert "Jane Doe" in letter
    assert "machine learning" in letter


def test_preview_does_not_raise():
    cover_letter.preview(SAMPLE_JOB)  # just shouldn't throw
