"""python -m tools.m4web"""

from __future__ import annotations

import argparse
import os

from .m4_client import DEFAULT_HOST
from .server import DEFAULT_PORT, run


def main() -> None:
    p = argparse.ArgumentParser(description="Proxy local de la web M4 Board")
    p.add_argument("--host", default="127.0.0.1", help="Bind local")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument(
        "--m4",
        default=os.environ.get("M4_HOST", DEFAULT_HOST),
        help="URL base de la M4 (env M4_HOST)",
    )
    p.add_argument("--no-browser", action="store_true")
    args = p.parse_args()
    run(
        host=args.host,
        port=args.port,
        m4_host=args.m4,
        open_browser=not args.no_browser,
    )


if __name__ == "__main__":
    main()
