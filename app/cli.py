import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.config import Settings
from app.db.models import Audit, Execution, Proposal, User, uid, utcnow
from app.db.session import database
from app.security.auth import create_user, hash_token
from app.soar.executors.dry_run import DryRunExecutor


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    users = sub.add_parser("create-user")
    users.add_argument("name")
    users.add_argument("role", choices=["viewer", "analyst", "operator", "admin"])
    users.add_argument("--tenant", required=True)
    rotate = sub.add_parser("rotate-token")
    rotate.add_argument("name")
    rotate.add_argument("--tenant", required=True)
    export = sub.add_parser("export-contracts")
    export.add_argument("--directory", default=".")
    reconcile = sub.add_parser("reconcile")
    reconcile.add_argument("proposal_id")
    reconcile.add_argument("--workers-stopped", action="store_true", required=True)
    password = sub.add_parser("set-password", help="Local recovery: interactively set an existing user password")
    password.add_argument("name")
    password.add_argument("--tenant", required=True)
    imp = sub.add_parser("import-sentinelzone", help="Explicit optional read-only import into product storage")
    imp.add_argument("incident_id")
    imp.add_argument("--source", required=True)
    imp.add_argument("--user", required=True, help="Existing analyst name")
    args = parser.parse_args()
    if args.command == "export-contracts":
        from app.contracts import ActionProposal, AIOutput, IncidentContext, Playbook
        from app.ingestion.contracts import EventBatch, IncidentBatch, AssetIn
        from app.connectors.base import ConnectorConfig
        from app.main import create_app
        from app.api.responses import AIRunView, ActionView, ErrorResponse
        from app.soar.executors.contracts import ExecutionReceipt, VerificationReport
        from app.soar.executors.factory import ExternalExecutorConfig

        root = Path(args.directory)
        for filename, model in [
            ("incident-context", IncidentContext),
            ("ai-output", AIOutput),
            ("action-proposal", ActionProposal),
            ("playbook", Playbook),
            ("ai-run", AIRunView),
            ("action-view", ActionView),
            ("api-error", ErrorResponse),
            ("execution-receipt", ExecutionReceipt),
            ("verification-report", VerificationReport),
            ("executor-config", ExternalExecutorConfig),
            ("ingest-events", EventBatch), ("ingest-incidents", IncidentBatch),
            ("asset-input", AssetIn), ("connector-config", ConnectorConfig),
        ]:
            target = root / "contracts" / f"{filename}.schema.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8")
        target = root / "docs" / "openapi.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                create_app(
                    Settings(
                        _env_file=None, app_env="test", core_mode="mock", ai_provider="mock", soar_executor="dry_run"
                    )
                ).openapi(),
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return
    settings = Settings()
    engine, sessions = database(settings.database_url)
    with sessions() as session:
        if args.command == "set-password":
            from getpass import getpass
            from sqlalchemy import delete
            from app.security.passwords import hash_password
            from app.db.models import BrowserSession
            user = session.scalar(select(User).where(User.name == args.name, User.tenant_id == args.tenant))
            if not user:
                raise SystemExit("user not found")
            value = getpass("New password (14+ characters): ")
            if value != getpass("Confirm password: "):
                raise SystemExit("passwords do not match")
            user.password_hash = hash_password(value)
            session.execute(delete(BrowserSession).where(BrowserSession.user_id == user.id))
            session.add(Audit(id=uid("AUD"), tenant_id=user.tenant_id, actor="local-admin",
                              action="PASSWORD_RESET", detail={"user_id": user.id}))
            session.commit()
            print("Password updated; browser sessions revoked.")
        elif args.command == "import-sentinelzone":
            from app.connectors.sentinelzone.client import RealCoreBackendClient
            from app.connectors.sentinelzone.importer import import_incident
            from app.security.auth import Principal
            user = session.scalar(select(User).where(User.name == args.user, User.tenant_id == settings.core_tenant_id,
                                                     User.active.is_(True), User.role == "analyst"))
            if not user:
                raise SystemExit("An active analyst in the configured connector tenant is required")
            async def run_import():
                client = RealCoreBackendClient(settings)
                try:
                    return await import_incident(session, Principal(user.id, user.name, user.role, user.tenant_id),
                                                 client, args.incident_id, args.source)
                finally:
                    await client.close()
            print(json.dumps(asyncio.run(run_import())))
        elif args.command == "create-user":
            print(create_user(session, args.name, args.role, args.tenant))
        elif args.command == "rotate-token":
            import secrets

            user = session.scalar(select(User).where(User.name == args.name, User.tenant_id == args.tenant))
            if not user:
                raise SystemExit("user not found")
            token = secrets.token_urlsafe(32)
            user.token_hash = hash_token(token)
            session.commit()
            print(token)
        elif args.command == "reconcile":
            if settings.soar_executor != "dry_run":
                raise SystemExit("Only the dry-run state can currently be reconciled")
            proposal = session.get(Proposal, args.proposal_id)
            if not proposal or proposal.status not in {"EXECUTING", "ROLLING_BACK", "UNKNOWN", "ROLLBACK_UNKNOWN"}:
                raise SystemExit("No uncertain operation to reconcile")
            restored = proposal.status in {"ROLLING_BACK", "ROLLBACK_UNKNOWN"}
            operation = session.scalar(
                select(Execution).where(
                    Execution.proposal_id == proposal.proposal_id,
                    Execution.operation == ("rollback" if restored else "execute"),
                )
            )
            if not operation or operation.executor != "dry_run":
                raise SystemExit("Operation is not a dry-run claim")
            verified = asyncio.run(DryRunExecutor(sessions).verify(proposal, restored=restored))
            status = (
                ("RESTORED" if restored else "SUCCESS") if verified else ("ROLLBACK_UNKNOWN" if restored else "UNKNOWN")
            )
            operation.status, proposal.status, operation.completed_at = status, status, utcnow()
            operation.result = {
                **(operation.result or {}),
                "dry_run": True,
                "reconciled": True,
                ("verified_removed" if restored else "verified"): True if verified else None,
            }
            session.add(
                Audit(
                    id=uid("AUD"),
                    tenant_id=proposal.tenant_id,
                    proposal_id=proposal.proposal_id,
                    actor="local-admin",
                    action="RECONCILED",
                    detail={"status": status, "verified": verified, "dry_run": True},
                )
            )
            session.commit()
            print(status)
    engine.dispose()


if __name__ == "__main__":
    main()
