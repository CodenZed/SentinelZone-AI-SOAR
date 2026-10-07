# License attributions and provenance

This patch release modifies the uploaded v0.29.0 service. Its inherited provenance states that service code, fixtures, schemas, playbooks and tests were independently written. No upstream application source, frontend, runner or telemetry stack was copied or bundled. The references below informed the architecture described in the user's specification.

| Project | Use | License / attribution |
| --- | --- | --- |
| [beenuar/AiSOC](https://github.com/beenuar/AiSOC) | Investigation runs, ordered ledger, evidence citations, provider abstraction and deterministic offline evaluation as design references | MIT. Copyright (c) 2024-present AiSOC contributors. Upstream notice preserved in `licenses/aisoc-MIT.txt`; no source code imported. |
| [ClockworkZMP/soar-playbook-templates](https://github.com/ClockworkZMP/soar-playbook-templates) | YAML steps, depends_on, requires_approval, conditions and offline simulation concepts | The upstream README declares MIT. Attribution: ClockworkZMP and its contributors. Our restricted schema, runner and two YAML files are independent implementations. No separate upstream copyright notice was supplied by the inspected README; none is invented here. |
| [gapilongo/SOC](https://github.com/gapilongo/SOC) | Reference only: human review, approval state, audit and rollback ideas | No code or assets bundled; no dependency on its application or license. |
| [Shuffle/Shuffle](https://github.com/Shuffle/Shuffle) | Future external REST adapter seam only | Shuffle core is AGPLv3; none of its core source is bundled. `shuffle` selection currently fails closed. The separate workflows/App SDK license must be checked before any future reuse. |
| [ZahraAlizada5/SIEM-Backend](https://github.com/ZahraAlizada5/SIEM-Backend) | Existing REST endpoint shapes inspected for interoperability | No backend code, database schema or dashboard assets copied. Commit recorded in docs/INTEGRATION.md. |

The newly written service is distributed under the MIT license in LICENSE. Referenced licenses do not imply those projects endorse this implementation. Python packages are installed from requirements.lock.txt rather than vendored; their distributions retain their own notices. See `docs/DEPENDENCIES.json` for the resolved package names, versions and license metadata. Docker's Python base image and PostgreSQL image retain their upstream licenses and notices.

Historical source checks recorded by the uploaded v0.29.0 package (not newly re-verified in this release): [AiSOC license](https://github.com/beenuar/AiSOC/blob/main/LICENSE), [Clockwork README](https://github.com/ClockworkZMP/soar-playbook-templates#license), [Shuffle license](https://github.com/Shuffle/Shuffle/blob/main/LICENSE). OpenAI API contract reference: [official Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).


The current pinned dependency inventory is `SBOM.cdx.json`; copied distribution license/notice files and metadata are in `licenses/dependencies/` and indexed by `THIRD_PARTY_NOTICES.md`. These are provenance records, not a legal compliance certification.
