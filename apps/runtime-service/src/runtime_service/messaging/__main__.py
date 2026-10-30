"""Apply the additive inbox migration explicitly before starting queue consumers."""

import argparse
import json
import os

from runtime_service.messaging import MessageInbox

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument(
        "--stats",
        action="store_true",
        help="Read aggregate queue metrics without migrating",
    )
    parser.add_argument(
        "--apply", action="store_true", help="Apply the bounded deletion preview"
    )
    parser.add_argument("--limit", type=int, default=100)
    operation.add_argument(
        "--prune-deleted",
        action="store_true",
        help="Purge inbox records for deleted Threads after the 24h retry window",
    )
    args = parser.parse_args()
    inbox = MessageInbox(os.environ["DATABASE_URI"])
    if args.stats:
        print(json.dumps(inbox.stats(), sort_keys=True))
    elif args.prune_deleted:
        print(
            json.dumps(
                {
                    "candidates": inbox.prune_deleted_threads(
                        apply=args.apply, limit=args.limit
                    ),
                    "apply": args.apply,
                }
            )
        )
    else:
        inbox.initialize()
        print("Runtime inbox schema ready")
