"""Single-instance AETHER live strategy worker. Disabled unless server flags are explicitly enabled."""
import os
import time
import logging
from app.main import run_auto_scan_once

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("aether.autotrader")

def main():
    if os.getenv("AETHER_AUTO_WORKER_ENABLED", "false").lower() != "true":
        raise SystemExit("Set AETHER_AUTO_WORKER_ENABLED=true only after broker/exchange approval and live-risk review.")
    interval = max(30, int(os.getenv("AETHER_AUTO_WORKER_INTERVAL_SECONDS", "60")))
    log.warning("AETHER live strategy worker started. It may submit real Groww orders if all live gates are enabled.")
    while True:
        try:
            result = run_auto_scan_once()
            log.info("scan result: %s", result)
        except KeyboardInterrupt:
            log.warning("worker stopped by operator")
            break
        except Exception:
            log.exception("worker scan failed; no assumption of order status should be made")
        time.sleep(interval)

if __name__ == "__main__":
    main()
