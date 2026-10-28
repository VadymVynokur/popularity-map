import pytest

from scripts.validate_commits import validate_header


@pytest.mark.parametrize(
    "header",
    [
        "chore: initialize project",
        "feat(accounts): add email login",
        "test(reviews): cover duplicate active review",
        "ops(ci): configure postgres and redis services",
        "fix: prevent duplicate view events",
        "docs: document api requirements",
    ],
)
def test_valid_conventional_headers(header):
    assert validate_header(header) == []


@pytest.mark.parametrize(
    "header",
    [
        "Add a feature",
        "feature: add a feature",
        "feat(accounts): Add email login",
        "feat(accounts): add email login.",
        "feat(Accounts): add email login",
        "feat(accounts): ",
        "feat: " + "a" * 100,
    ],
)
def test_invalid_conventional_headers(header):
    assert validate_header(header)


def test_merge_and_revert_headers_are_allowed():
    assert validate_header("Merge branch 'dev'") == []
    assert validate_header('Revert "feat: add email login"') == []
