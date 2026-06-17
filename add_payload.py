"""Interactive CLI for adding a new mirrored payload.

Thin wrapper around ``mirror_core`` so the CLI and the web backend share one
implementation. Run with ``python add_payload.py``.
"""

import mirror_core
from mirror_core import DuplicateError, MirrorError, ZipExtractNeeded


def add_payload():
    print("Add New PS5 Payload (Auto-download)")
    print("-" * 20)

    url = input("GitHub Download URL: ").strip()
    description = input("Description (optional): ").strip()

    extract_file = None
    while True:
        try:
            item = mirror_core.add_payload(url, description, extract_file)
            print(f"\nSuccessfully added and downloaded {item['name']} to {mirror_core.JSON_FILE.name}")
            return
        except ZipExtractNeeded as e:
            print(f"  Multiple .elf files in zip: {', '.join(e.candidates)}")
            extract_file = input("  Path inside zip to extract: ").strip()
            if not extract_file:
                print("Aborted: no extract path given.")
                return
        except (DuplicateError, MirrorError) as e:
            print(f"Error: {e}")
            return


if __name__ == "__main__":
    add_payload()
