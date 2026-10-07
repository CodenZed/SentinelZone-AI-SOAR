from pathlib import Path

import yaml

from app.contracts import Playbook
from app.errors import ServiceError

MUTATIONS = {"windows_firewall_block", "suspend_test_process"}
ROLLBACKS = {"rollback_block", "rollback_process"}
VERIFIERS = {"verify_block", "verify_process"}


def validate_playbook(value):
    book = Playbook.model_validate(value)
    steps = {s.id: s for s in book.steps}
    if len(steps) != len(book.steps):
        raise ValueError("duplicate step id")
    order, visiting, done = [], set(), set()

    def visit(key):
        if key not in steps or key in visiting:
            raise ValueError("unknown dependency or cycle")
        if key in done:
            return
        visiting.add(key)
        for dep in steps[key].depends_on:
            visit(dep)
        visiting.remove(key)
        done.add(key)
        order.append(steps[key])

    for key in steps:
        visit(key)

    def ancestors(step):
        result = set(step.depends_on)
        for key in step.depends_on:
            result |= ancestors(steps[key])
        return result

    expected = {
        "BLOCK_IP": ("windows_firewall_block", "verify_block", "rollback_block"),
        "SUSPEND_TEST_PROCESS": ("suspend_test_process", "verify_process", "rollback_process"),
    }[book.action_type]
    mandatory = ["validate_target", "human_approval", *expected]
    selected = {}
    for action in mandatory:
        found = [s for s in order if s.action == action]
        if len(found) != 1:
            raise ValueError("exactly one of each mandatory step is required")
        selected[action] = found[0]
    if any(s.action in MUTATIONS | VERIFIERS | ROLLBACKS and s.action not in expected for s in order):
        raise ValueError("action/playbook mismatch")
    chain = [selected[a] for a in mandatory]
    for before, after in zip(chain, chain[1:]):
        if before.id not in ancestors(after):
            raise ValueError("required safety dependency missing")
    if not selected[expected[0]].requires_approval:
        raise ValueError("execution requires approval")
    if any(s.condition for s in chain if s.action not in MUTATIONS):
        raise ValueError("safety steps cannot be conditional")
    book.steps = order
    return book


def load_playbook(path):
    path = Path(path)
    if path.stat().st_size > 64000:
        raise ValueError("playbook too large")
    return validate_playbook(yaml.safe_load(path.read_text(encoding="utf-8")))


def catalog(directory):
    result = {}
    for path in sorted(Path(directory).glob("*.yml")):
        book = load_playbook(path)
        if book.id in result:
            raise ValueError("duplicate playbook id")
        result[book.id] = book
    return result


def condition_passes(condition, proposal):
    if condition is None:
        return True
    if condition.field == "parameters.lab_only":
        actual = proposal.parameters.get("lab_only")
    else:
        actual = getattr(proposal, condition.field)
    return actual == condition.equals


def execution_plan(book, proposal):
    states, result = {}, []
    for step in book.steps:
        if step.action in ROLLBACKS:
            state = "AVAILABLE"
        elif any(states[d] == "SKIPPED" for d in step.depends_on) or not condition_passes(step.condition, proposal):
            state = "SKIPPED"
        else:
            state = "READY"
        states[step.id] = state
        result.append({"id": step.id, "action": step.action, "status": state})
    mutation = next(s for s in result if s["action"] in MUTATIONS)
    if mutation["status"] == "SKIPPED":
        raise ServiceError("playbook_condition_not_met", 409)
    return result
