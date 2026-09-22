"""Import a historical range through the same validated collector used by the worker."""
import sys
from app.market_data.worker import main

if __name__ == "__main__":
    raise SystemExit(main(["--once", *sys.argv[1:]]))
