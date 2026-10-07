import argparse
from types import SimpleNamespace

from app.soar.playbooks.engine import execution_plan, load_playbook


def main():
    parser = argparse.ArgumentParser(description="Offline playbook graph simulation; grants no real approval")
    parser.add_argument("playbook")
    args = parser.parse_args()
    book = load_playbook(args.playbook)
    proposal = SimpleNamespace(action_type=book.action_type, target="fixture-target", parameters={"lab_only": True})
    plan = execution_plan(book, proposal)
    labels = {
        "validate_target": "VALIDATE        PASS (schema only)",
        "human_approval": "APPROVAL        SIMULATED",
        "windows_firewall_block": "EXECUTION       WOULD EXECUTE",
        "suspend_test_process": "EXECUTION       WOULD EXECUTE",
        "verify_block": "VERIFY          WOULD VERIFY",
        "verify_process": "VERIFY          WOULD VERIFY",
        "rollback_block": "ROLLBACK        AVAILABLE",
        "rollback_process": "ROLLBACK        AVAILABLE",
        "branch": "CONDITION       PASS",
    }
    for step in plan:
        print(labels[step["action"]] if step["status"] != "SKIPPED" else f"{step['id']} SKIPPED")


if __name__ == "__main__":
    main()
