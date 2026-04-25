try:
    from lightrag.mcp.server import main
except ImportError:  # pragma: no cover - package execution fallback
    from .server import main


if __name__ == "__main__":
    raise SystemExit(main())
