"""Provider execution moved to approved Runtime tools; see provenance.json."""
def generate_image(*args, **kwargs):
    raise RuntimeError("Use generate_image/edit_image tools with idempotency_key; shell provider calls are disabled.")


if __name__ == "__main__":
    raise SystemExit("Use the approved generate_image/edit_image tools, not this script.")
