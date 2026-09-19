"""Usage: python -m runtime_service.db upgrade."""
import argparse

from runtime_service.db import upgrade

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("command", choices=["upgrade"])
parser.parse_args()
upgrade()
