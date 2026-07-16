## 1. Verify Spec Accuracy Against Current Code

- [ ] 1.1 Re-read `web/src/App.tsx`, `web/src/useTheme.ts`, and `web/src/api.ts` and confirm every requirement in `specs/frontend-base/spec.md` matches current behavior
- [ ] 1.2 Re-read each component in `web/src/components/` (`AddMirrorForm.tsx`, `PayloadTable.tsx`, `PayloadRow.tsx`, `CandidatePicker.tsx`, `EditMirrorDialog.tsx`, `SchedulerPanel.tsx`, `Toast.tsx`, `icons.tsx`) and confirm the corresponding scenarios match current behavior
- [ ] 1.3 Note any discovered behavior not yet covered by a requirement, and add a scenario for it (or file it as a follow-up if out of scope for this baseline)

## 2. Publish the Baseline

- [ ] 2.1 Confirm no files under `web/` were modified by this change (documentation-only)
- [ ] 2.2 Run `openspec validate --change frontend-base` (or equivalent) and fix any structural issues in the spec
- [ ] 2.3 Archive the change so `specs/frontend-base/spec.md` is merged into `openspec/specs/frontend-base/spec.md` as the permanent baseline
