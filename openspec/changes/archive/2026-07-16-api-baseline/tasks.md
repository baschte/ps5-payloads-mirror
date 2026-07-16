## 1. Validate specs against current code

- [x] 1.1 Run `openspec validate --change api-baseline --strict` and fix any
      formatting issues (scenario header levels, missing scenarios).
      Confirmed passing: `openspec validate api-baseline --strict` → "Change
      'api-baseline' is valid".
- [x] 1.2 Cross-check every scenario in `specs/mirror-management-api/spec.md`
      against the current behavior of `/api/payloads*` and `/payloads.json`
      in [server/main.py](server/main.py) and [mirror_core.py](mirror_core.py).
      Done via full read-through of both files; reflected in the detailed
      API reference in `proposal.md`.
- [x] 1.3 Cross-check `specs/collection-title/spec.md` against `/api/title`
      in [server/main.py](server/main.py). Done — matches.
- [x] 1.4 Cross-check `specs/api-authentication/spec.md` against the Basic
      Auth middleware in [server/main.py](server/main.py). Done — matches.
- [x] 1.5 Cross-check `specs/update-scheduler/spec.md` against
      [server/scheduler.py](server/scheduler.py). Done — matches.
- [x] 1.6 Cross-check `specs/git-publish/spec.md` against
      [server/git_ops.py](server/git_ops.py) and
      [server/auto_publish.py](server/auto_publish.py). Done — matches.

## 2. Reconcile discrepancies

- [x] 2.1 For any scenario that doesn't match current code, either correct
      the spec (preferred, since this change documents existing behavior)
      or flag it to the user as a possible latent bug rather than silently
      "fixing" the spec to hide it. No discrepancies found during the
      cross-check in section 1 — all five spec files match current code
      behavior as documented in `proposal.md`'s API reference.

## 3. Archive

- [ ] 3.1 Run `openspec archive api-baseline` (or the project's archive
      flow) once all specs are validated, so the five new spec files land
      under `openspec/specs/`.
