import asyncio
from time import perf_counter

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.ai.context.builder import build_context
from app.ai.context.redactor import redact
from app.ai.investigation.ledger import step
from app.ai.validation.evidence import validate_evidence
from app.ai.validation.output import parse_output
from app.db.models import AIAnalysis, AIRun, Audit, uid, utcnow
from app.errors import DependencyUnavailable, ServiceError


async def investigate(session, principal, incident_id, core, provider, settings):
    run = AIRun(
        run_id=uid("AIR"),
        tenant_id=principal.tenant_id,
        incident_id=incident_id,
        requested_by=principal.id,
        provider=provider.name,
        model=provider.model,
    )
    session.add(run)
    session.commit()
    seq, start = 0, perf_counter()

    def record(stage, **kwargs):
        nonlocal seq, start
        seq += 1
        step(session, run, stage, seq, duration_ms=int((perf_counter() - start) * 1000), **kwargs)
        start = perf_counter()

    try:
        original = await core.get_incident_context(incident_id, principal.tenant_id)
        record("CONTEXT_BUILT")
        context = build_context(original, settings)
        run.context_snapshot = context
        record("REDACTED", evidence_ids=[e["event_uid"] for e in context["data"]["evidence"]])
        record("PROVIDER_CALLED")
        raw = await asyncio.wait_for(provider.analyze(context), settings.provider_timeout_seconds)
        output = parse_output(raw)
        # Never persist raw provider output or exception messages.
        safe = redact(output.model_dump(mode="json"))
        output = parse_output(safe)
        output.missing_evidence = list(dict.fromkeys(context["data"]["missing_telemetry"] + output.missing_evidence))[
            :100
        ]
        record("OUTPUT_RECEIVED")
        validation = await validate_evidence(output, context, core)
        run.validation_status = validation["validation_status"]
        record("EVIDENCE_VALIDATED", status=run.validation_status)
        session.add(
            AIAnalysis(
                run_id=run.run_id,
                output=output.model_dump(mode="json"),
                trusted=run.validation_status == "valid",
                validation=validation,
            )
        )
        run.status = "completed" if run.validation_status == "valid" else "invalid"
        run.completed_at = utcnow()
        record("STORED")
    except (ValidationError, ValueError, TypeError, KeyError):
        run.status, run.validation_status, run.error_code = "rejected", "invalid", "malformed_ai_or_core_contract"
    except (DependencyUnavailable, asyncio.TimeoutError):
        run.status, run.validation_status, run.error_code = "failed", "unavailable", "dependency_unavailable"
    except ServiceError as exc:
        run.status, run.validation_status, run.error_code = "failed", "unavailable", exc.code
    except SQLAlchemyError:
        raise
    except Exception:
        run.status, run.validation_status, run.error_code = "failed", "unavailable", "analysis_internal_error"
    if run.status in {"failed", "rejected"}:
        run.completed_at = utcnow()
        record("FAILED", status=run.status)
    session.add(Audit(id=uid("AUD"), tenant_id=principal.tenant_id, actor=principal.id,
                      action="AI_INVESTIGATION", detail={"run_id": run.run_id, "status": run.status,
                                                       "validation_status": run.validation_status}))
    session.commit()
    return run
