"""Real isolated ACL persistence for gateway transport contract tests."""
import tempfile
from pathlib import Path

from platform_api.core.db import build_engine, build_session_factory, create_core_tables
from platform_api.modules.runtime_gateway.application.thread_access import register


def thread_acl_factory(test, *, actor, project_id, thread_id="thread-1"):
    directory = tempfile.TemporaryDirectory()
    test.addCleanup(directory.cleanup)
    engine = build_engine(f"sqlite:///{Path(directory.name) / 'threads.db'}")
    test.addCleanup(engine.dispose)
    factory = build_session_factory(engine)
    create_core_tables(engine)
    register(factory, actor=actor, project_id=project_id, thread_id=thread_id)
    return factory
