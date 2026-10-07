# Phase 28 AI contract

The AI provider's output has **exactly five mandatory sections**, with extra properties forbidden:

1. `observed_facts`: text and nonempty `evidence_event_ids`.
2. `hypotheses`: text and explicit limitations.
3. `missing_evidence`: selected missing/unknown information.
4. `recommended_investigation`: advisory investigation steps.
5. `containment_options`: advisory options, with no action authority.

`contracts/ai-output.schema.json` is generated from the Python model. The dashboard's outer AIRunView envelope adds metadata, citations and compatibility `analysis`; those metadata fields are not additional AI output sections.

## Evidence and trust

Real mode retrieves incident metadata, timeline event links, selected summaries and asset inventory exclusively through authenticated read-only Core REST. Optional identity/host/sensor context is allowlisted; absent data remains UNKNOWN. The mapper accepts explicit REAL/TEST/REPLAY/UNKNOWN labels and never fabricates enrichment. Fixtures exist only in development/test Core mode and are marked TEST.

Selection is deterministic by severity/time with source diversity. A character budget and event cap bound input. Redaction runs **before truncation and before provider access**, including the persisted context snapshot. It covers password/token/API key assignments, authorization, JWT, cookies/session IDs, PEM keys, SMTP credentials, Cowrie password data, URL userinfo and credential query parameters, including encoded query names. Arbitrary encoded/unlabeled secrets cannot be guaranteed detectable; do not use summary fields to smuggle raw logs. Full raw logs, environment dumps and process command lines are not part of the input mapping.

A static trusted system instruction is separate from a JSON user/data object labeled `UNTRUSTED EVENT DATA`. No untrusted event text is concatenated into the system prompt. Providers get no tools, function calls, action API credentials or executors. Apparent commands in logs remain data. Prompt-boundary tests verify message structure and no action creation; they are not proof that a live LLM cannot be persuaded by malicious text. Local schema/citation gates and human review remain essential.

Every cited event is checked against current Core existence, current incident membership, tenant scope and the selected context for that run. A hallucinated, foreign-incident, wrong-tenant or omitted-context citation cannot yield `trusted=true`. Citations are revalidated after inference; Core errors mean unavailable validation, not assumed validity. Validation proves identifiers/scope, **not semantic entailment of every sentence**. `trusted=true` does not mean 100% correct and does not authorize a proposal or execution. `human_review_required=true` is permanent.

Malformed/duplicate-key JSON, missing/extra sections, refusal, incomplete response and excessive output fail safely. Raw provider errors/output are not persisted; redacted validated objects are stored, invalid citation results are quarantined and hidden from normal analysis fields. Missing telemetry is preserved even if a provider omits it. Provider/core unavailability records a failed run; other service routes remain available when the dedicated DB is ready.

## Providers

- `AI_PROVIDER=mock`: deterministic fixture-free inference logic over the supplied context. Can consume real Core evidence, but makes no live-model diagnosis. Always labeled provider `mock`.
- `AI_PROVIDER=openai`: configurable `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_API_URL`; Responses JSON Schema request, `store=false`, no tools. No model is hardcoded.
- `AI_PROVIDER=local`: configurable OpenAI-compatible `/v1/chat/completions` and `/v1/models`, schema output support, model/token/internal CA. Include `/v1` in `LOCAL_AI_URL`.

Provider URLs are administrator configuration; TLS verification stays enabled, redirects are rejected. Bad provider URL/CA/missing model/key degrades provider health without preventing service startup. Health checks model availability, not successful inference. Live OpenAI/local inference was NOT RUN in this release; provider HTTP request/response contracts were mocked.
