# Source provenance

The canonical editable application source lives at the project root (`app/`, `migrations/`, `tests/`, etc.). This directory records the uploaded baseline hashes and the release change patch; it does not contain a second copy of the application.

`input-provenance.json` identifies the four uploaded inputs and the baseline Git commit. The uploaded bundle's checked-out HEAD and TAR file tree were byte-for-byte equal. `changes-from-v0.29.0.patch` records the integration changes against that baseline; applying it is not required to install this complete release.
