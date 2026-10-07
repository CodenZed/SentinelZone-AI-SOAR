async def validate_evidence(output, context, core):
    data = context["data"]
    selected = {e["event_uid"] for e in data["evidence"]}
    ids = sorted({uid for fact in output.observed_facts for uid in fact.evidence_event_ids})
    reason = await core.validate_event_ids(ids, data["incident_id"], data["tenant_id"])
    if reason:
        return {"validation_status": "invalid", "reason": reason}
    if any(uid not in selected for uid in ids):
        return {"validation_status": "invalid", "reason": "evidence_not_in_selected_context"}
    return {
        "validation_status": "valid",
        "reason": None,
        "scope": "citation existence, incident membership, tenant binding and selected-context membership; not semantic proof",
    }
