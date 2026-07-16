## Context

`mirror_core.py` currently persists a single list in `payloads.json`, and
`_write_data` re-sorts that list by `last_update` on every write — so the
displayed/stored order is an accidental side effect of update recency, not a
deliberate choice. There is no ordering field, and no way to keep a mirror's
record around while excluding it from the published feed/README other than
deleting it (`remove_payload`, which discards the record entirely).

The prior `add-mirror-editing` change (archived) introduced `edit_payload`,
which replaces an item's fields "in place" in the in-memory list at a given
index, then calls `save_payloads` — which re-sorts the whole list on write.
That prior design explicitly accepted "in-place replacement, but the actual
on-disk order is whatever `_write_data`'s sort produces" as the status quo.
This change replaces that sort with an explicit `sort_order` field, which
means `edit_payload`'s in-place replacement now has a concrete value it must
carry over (or it silently resets).

## Goals / Non-Goals

**Goals:**
- Let a user drag-and-drop reorder the mirrors table, with the order
  persisted and stable across any subsequent save (add, edit, update,
  scheduled run) — not just until the next write re-sorts it away.
- Let a user hide a mirror (exclude it from the published `payloads.json`/
  README/API-visible-as-active) without losing its record, and reactivate it
  later with one action.
- Keep hidden mirrors' data fresh: the scheduler/"update all" must keep
  checking and downloading updates for hidden mirrors exactly as for visible
  ones.
- Keep `hidden_payloads.json` entirely out of git — never staged, committed,
  or pushed by the existing auto-publish/manual-publish mechanism.

**Non-Goals:**
- No new frontend drag-and-drop library — native HTML5 Drag and Drop API
  only, accepting its weaker touch/keyboard accessibility as a trade-off.
- No "trash"/undo history beyond the hidden state itself — a hidden mirror
  is either visible or hidden; there's no multi-level archive.
- No change to how `remove_payload` (permanent delete) works — hiding and
  deleting remain two distinct, independent actions.
- No user-facing distinction between "hidden because I chose to" vs. any
  other state — a single boolean is sufficient; no additional hidden
  sub-states (e.g. "hidden until date X").

## Decisions

### 1. `sort_order` replaces sort-by-`last_update` as the single ordering key

Every payload item gains an integer `sort_order`. `_write_data` no longer
sorts by `last_update`; instead, both `payloads.json` and
`hidden_payloads.json` are written with items ordered by `sort_order`
ascending (this ordering is also what callers see from `load_payloads()`/
the merged list — see Decision 3).

`add_payload` assigns a new item `sort_order = max(existing sort_order,
default -1) + 1`, so new mirrors always land at the end.

**Backfill for pre-existing entries**: on the first `load_data()` call after
this change ships, any item without a `sort_order` is assigned one based on
its *current* position in the file (the position produced by the old
last-updated sort), so the existing visual order is preserved as the
starting point rather than being scrambled. This assignment is persisted on
the next write (whichever write happens first — it does not require a
dedicated migration script).

**Alternative considered**: keep sorting by `last_update` and add
`sort_order` only as a tiebreaker or a purely client-side concept (e.g.
store custom order in `localStorage`). Rejected — the user explicitly wants
this to be _the_ order, persisted server-side, not a per-browser client
preference; the proposal's Q&A already settled this.

### 2. `hidden_payloads.json`: separate, git-ignored file; single logical list

A new constant `HIDDEN_JSON_FILE = BASE_DIR / "hidden_payloads.json"` holds
the same shape as `payloads.json` (`{"name": ..., "payloads": [...]}` — note:
its own `"name"` field is unused/ignored; only `"payloads"` matters). It is
added to `.gitignore` and is *not* added to `server/git_ops.py`'s
`COMMIT_FILES` (which already only lists `payloads.json` and `README.md`, so
no code change is needed there — this design explicitly calls out that it
must **stay** that way; a follow-up author must not "helpfully" add it).

`load_data()` reads both files, tags each item from `hidden_payloads.json`
with `hidden = True` (and each item from `payloads.json` with `hidden =
False` if not already present), concatenates them into one list, backfills
missing `sort_order` (Decision 1), and sorts by `sort_order`. Every existing
consumer (`load_payloads()`, `update_all`, `update_one`, `add_payload`,
`edit_payload`, `remove_payload`, the `/api/payloads` endpoint) keeps
operating on this one merged list — none of their internal logic needs to
know which file an item came from.

`_write_data`/`save_payloads` partitions the incoming list by `item["hidden"]`
before writing: hidden items go to `hidden_payloads.json`, everything else to
`payloads.json`. Both files are written atomically (same temp-file + replace
pattern already used today), under the same `DATA_LOCK`. README generation
continues to read only the *visible* subset (hidden items are excluded from
the README table and from the public `/payloads.json` feed — see Decision 4).

**Alternative considered**: two fully separate load/save pipelines (as
sketched during exploration). Rejected in favor of the shared-pipeline
approach precisely to avoid duplicating `add_payload`/`edit_payload`/
`update_one`/`update_all` logic across two parallel code paths — the whole
point of `hidden` being "just a field" is that existing operations don't
need to change.

### 3. `GET /api/payloads` returns the full merged, sort_order-ordered list

The management API (`/api/payloads`, used by the authenticated UI) returns
*all* items — visible and hidden — each carrying `hidden: bool`, in
`sort_order` order. This lets the frontend render one continuous list where
hidden rows are simply styled differently, exactly as decided during
exploration. It is a different contract from the *public* feed (Decision 4).

### 4. The public `/payloads.json` feed and README stay visible-only

`GET /payloads.json` (the raw file response) is unaffected in shape — it
already serves `payloads.json` directly from disk, which after this change
contains only *visible* items by construction (hidden items physically live
in the other file). No filtering logic is needed there; it falls out of
Decision 2's file split. `update_readme()` similarly continues to read
`payloads.json`'s visible items only, so hidden mirrors never appear in the
generated README table — matching "hidden means excluded from what's
published," independent of whether the git-publish button is even
configured.

### 5. Bulk reorder endpoint: `PUT /api/payloads/reorder`

Accepts the complete list of mirror names in the desired new order (across
both visible and hidden items — the frontend always has the full merged
list in memory, so it always sends all names, not just the visible ones).
The handler:
- Validates that the provided name set matches exactly the current set of
  known names (no silent drops/adds — mismatch is a 400).
- Assigns `sort_order` values in step increments (e.g. 10, 20, 30, ...) in
  the given order, rather than 0, 1, 2, ... — leaving room is not required
  for correctness today (every reorder rewrites all values anyway) but costs
  nothing and matches common practice.
- Persists via the existing merged-list write path (Decision 2) — some of
  the renumbered items may be hidden, some visible; the split-on-write logic
  handles that transparently.

**Alternative considered**: an endpoint that takes only `{name, new_index}`
and shifts intermediate items' `sort_order` server-side. Rejected per the
user's explicit choice of the simpler bulk-send-full-order approach —
robust regardless of how far an item moved, and the payload size (a dozen
names) is trivial.

### 6. `edit_payload` must preserve `sort_order` and `hidden` across a URL change

The existing `mirror-editing` capability's in-place-replacement behavior
(URL-changing edit rebuilds the item and replaces it "at its current
position") predates `sort_order`/`hidden`. Without an explicit fix, the
rebuilt item (built by `_download_and_build_item`, which has no concept of
`sort_order`/`hidden`) would silently drop both fields, moving the mirror to
the end of the order (whatever backfill/default applies) and/or flipping it
back to visible. The fix: `edit_payload`'s URL-changed branch copies
`sort_order` and `hidden` from the item being replaced onto the rebuilt item
before writing. The metadata-only (source-unchanged) branch already
preserves these implicitly since it patches the existing dict in place
(`dict(item)` copy) rather than rebuilding from scratch — no change needed
there. This is called out as a **Modified Capability** delta on
`mirror-editing` in the proposal, not a new requirement, since it clarifies
existing in-place-replacement behavior rather than adding a new one.

### 7. Frontend: derive render order from props, optimistic reorder, local drag-visual state

Per the vercel-react-best-practices guidance the user asked to apply:
- `PayloadTable` renders rows directly in the order of the `payloads` prop
  (already `sort_order`-ordered from the API) — no separate client-side
  "shadow" ordering state computed in a `useEffect` that could drift from
  the server's order (`rerender-derived-state-no-effect`).
- On drop, `App.tsx` optimistically reorders its local `payloads` state
  immediately (via a functional `setState` update, `rerender-functional-
  setstate`), then fires the bulk reorder request in the background; on
  failure, it reverts to the last known-good order and surfaces an error
  toast — the same optimistic-then-reconcile pattern already used elsewhere
  in this codebase is extended here, not invented fresh.
- Each `PayloadRow`'s transient "am I being dragged" / "is this the drop
  target" visual state is local `useState` inside the row component, not
  lifted into `App.tsx` or any shared store — it's purely cosmetic and never
  needs to be read by a sibling.

## Risks / Trade-offs

- **[Risk]** Native HTML5 DnD has materially weaker touch-device and
  keyboard support than a dedicated library. → **Mitigation**: accepted
  trade-off per explicit user choice (no new dependency); this is an
  internal admin UI, not a public-facing product, which lowers the bar for
  acceptable a11y gaps versus a consumer product, though it's still a real
  limitation worth documenting for a future revisit.
- **[Risk]** `hidden_payloads.json` living only on local disk (never in git)
  means it is NOT backed up by the existing git-publish mechanism — a lost
  container/volume loses all hidden mirrors' records permanently, with no
  recovery path other than re-adding them. → **Mitigation**: this is the
  explicit, deliberate design the user asked for (git must never see this
  file); the existing `docker-compose.yml` bind-mount of the whole repo
  directory already gives it the same on-host durability as `payloads/`
  (the downloaded binaries), which is already git-ignored today for the
  same reason — this is consistent with existing risk acceptance in this
  codebase, not a new category of risk.
- **[Risk]** The reorder endpoint's "exact name-set match or reject" validation
  means a stale frontend (open in one tab while a mirror is added/removed
  from another) could have its reorder rejected. → **Mitigation**: surfaced
  as a normal error toast; the user retries after refreshing, same pattern
  as any other conflicting-edit scenario in this app.
- **[Trade-off]** Every reorder rewrites `sort_order` for the entire list
  (not just the moved item and its immediate neighbors), which is simpler
  but means every drag-and-drop operation touches every item's `sort_order`.
  Accepted — the list is small (a dozen items today) and a full rewrite was
  the user's explicit choice over an index-shift endpoint.

## Migration Plan

No manual migration step is required before deploy. On first load after
this ships:
1. Items lacking `sort_order` are assigned one based on their current file
   position (Decision 1), preserving today's visual order as the baseline.
2. Items lacking `hidden` are treated as `hidden = False` (visible) — the
   existing single `payloads.json` file becomes, unambiguously, "the
   visible file."
3. `hidden_payloads.json` does not need to exist yet; it is created on first
   write that includes a hidden item (or can be pre-created empty).
4. `docker-compose.yml`'s existing whole-repo bind mount (`.:/app`) already
   covers any new file created in `BASE_DIR`, so no volume changes are
   strictly required — but `.gitignore` must be updated so the new file is
   never accidentally staged by a future `git add -A` or similar.

Rollback is a plain code revert; the `sort_order`/`hidden` fields left in
`payloads.json` by a rolled-back-from version are simply ignored by the
prior code (which re-sorts by `last_update` and knows nothing about
`hidden`), so no data cleanup is required for a rollback either — though any
mirrors hidden while the new code was live would suddenly reappear in
`payloads.json` after a rollback, since the old code has no hidden concept.

## Open Questions

- Should there be a lightweight "N hidden mirrors" indicator/count visible
  even when the hidden rows are scrolled out of view, or is the inline
  dimmed styling in the same list sufficient on its own? Leaning toward
  "not needed initially" given the list is small, but worth a UX gut-check
  during implementation.
- Should the bulk reorder endpoint reject a request that only reorders a
  strict subset (e.g. because the frontend miscounted), or should it be
  lenient and just ignore missing names? Design leans toward strict
  rejection (Decision 5) for safety; flagged here in case that's overly
  strict for real usage patterns once built.
