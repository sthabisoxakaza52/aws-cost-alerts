"""Tests for README.md structure and required project invariants."""

from pathlib import Path


def test_readme_preserves_cleanup_instructions():
    readme = (Path(__file__).parent.parent / "README.md").read_text(
        encoding="utf-8"
    )

    assert "WTC-JJNPY2UD" in readme
    cleanup_section = readme.split("## Uninstall / Cleanup", 1)
    assert len(cleanup_section) == 2
    assert readme.rstrip().endswith("Delete `aws-cost-alert-lambda-role`")
    assert "Delete `MonthlyAWSBudget`" in cleanup_section[1]
    assert "Delete `aws-cost-alert-topic`" in cleanup_section[1]
    assert "Delete `aws-cost-alert-slack-forwarder`" in cleanup_section[1]
    assert "Delete `aws-cost-alert-lambda-role`" in cleanup_section[1]
