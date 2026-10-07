def select_evidence(evidence, limit):
    """Stable severity/time selection with at least one event per available source."""
    ranks = {"critical": 3, "high": 2, "medium": 1, "low": 0}
    ordered = sorted(evidence, key=lambda e: (-ranks.get(e.priority, -1), -e.event_time.timestamp(), e.event_uid))
    selected, sources = [], set()
    for item in ordered:
        if item.source not in sources and len(selected) < limit:
            selected.append(item)
            sources.add(item.source)
    selected_ids = {e.event_uid for e in selected}
    for item in ordered:
        if item.event_uid not in selected_ids and len(selected) < limit:
            selected.append(item)
            selected_ids.add(item.event_uid)
    return selected
