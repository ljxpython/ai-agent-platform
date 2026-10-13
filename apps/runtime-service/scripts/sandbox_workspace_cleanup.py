"""Report one bound workspace; mark/apply require verified absent Thread and work."""

import argparse
import json

from runtime_service.workspace.cleanup import cleanup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("tenant", "project", "thread", "graph"):
        parser.add_argument("--" + key, required=True)
    parser.add_argument(
        "--action", choices=("report", "mark", "apply"), default="report"
    )
    parser.add_argument("--verified-by")
    parser.add_argument("--candidate-token")
    args = parser.parse_args()
    result = cleanup(
        (args.tenant, args.project, args.thread),
        args.graph,
        action=args.action,
        verified_by=args.verified_by,
        candidate_token=args.candidate_token,
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
