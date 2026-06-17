"""CLI entry point for updating all mirrored payloads.

Kept intact for the GitHub Action (`python update_payloads.py`). The real logic
now lives in ``mirror_core`` so it can be reused by the web backend too.
"""

import mirror_core

# Backwards-compatible re-exports (other code / the Action may import these).
JSON_FILE = str(mirror_core.JSON_FILE)
PAYLOADS_DIR = str(mirror_core.PAYLOADS_DIR)
BASE_URL = mirror_core.BASE_URL

update_readme = mirror_core.update_readme
cleanup_release_assets = mirror_core.cleanup_release_assets


def update_payloads():
    results = mirror_core.update_all(cleanup=True)
    for r in results:
        print(f"{r['name']}: {r['message']}")
    if any(r["updated"] for r in results):
        print(f"\nSuccessfully updated files and sorted {mirror_core.JSON_FILE.name}")
    else:
        print(f"\nSorted {mirror_core.JSON_FILE.name} (no new files downloaded).")


if __name__ == "__main__":
    update_payloads()
