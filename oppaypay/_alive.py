import time
import random
import threading
import logging

log = logging.getLogger("oppaypay.alive")


class HumanPatternSimulator:
    ENDPOINTS = [
        "/bff/v1/getGlobalServiceStatus",
        "/bff/v4/getHomeDisplayInfo",
        "/bff/v1/getFeatureFlagInfo",
        "/bff/v1/getBalanceInfo",
    ]

    def __init__(self, core, interval_range=(30, 180)):
        self.core = core
        self.interval_range = interval_range
        self._stop = threading.Event()
        self._thread = None

    def _run(self):
        log.info("alive simulator started")
        while not self._stop.is_set():
            wait = random.uniform(*self.interval_range)
            if self._stop.wait(wait):
                break
            try:
                self.core.alive()
                log.debug("alive: sent")
            except Exception as e:
                log.debug(f"alive failed: {e}")
            time.sleep(random.uniform(0.5, 3.0))

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        log.info("alive simulator stopped")


__all__ = ["HumanPatternSimulator"]