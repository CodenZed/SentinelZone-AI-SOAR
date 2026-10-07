# AI

AI providers implement `AIProvider.analyze(context)`. Supported configuration choices are `mock`, `openai`, `openai_compatible`/`local`, and `ollama`. Provider choice is configuration-driven; a missing or unavailable provider degrades an investigation without changing SOAR state.

The context builder selects a bounded severity/time/source-balanced evidence set, redacts credentials before truncation, marks all source text `UNTRUSTED EVENT DATA`, and preserves UNKNOWN for missing telemetry. Providers receive a schema-only request and no tools. Structured output is parsed, redacted, and validated before storage.

Citation validation checks event existence, tenant scope, incident membership, and selected-context membership. `trusted=true` means those checks passed; it does not mean the model's semantic conclusion is correct. Hidden reasoning and raw provider failures are never stored. Human review is always required.
