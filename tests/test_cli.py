import sys
from setup_cost_alerts import main

def test_dry_run(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [
        "script",
        "--budget", "100",
        "--email", "test@email.com",
        "--slack-webhook", "https://hooks.slack.com/test",
        "--dry-run"
    ])

    try:
        main()
    except SystemExit:
        pass

    captured = capsys.readouterr()
    assert "DRY RUN" in captured.out 