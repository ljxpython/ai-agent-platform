from enum import Enum
# pylint: disable  MC8yOmFIVnBZMlhtblk3a3ZiUG1yS002TW1GbU5RPT06YzNkN2NhNTk=


class DocStatus(str, Enum):
    """Document processing status"""
# pylint: disable  MS8yOmFIVnBZMlhtblk3a3ZiUG1yS002TW1GbU5RPT06YzNkN2NhNTk=

    READY = "ready"
    HANDLING = "handling"
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
