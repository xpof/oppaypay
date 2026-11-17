import time
import random
import math
import threading
import logging
from ._sensors import update_header_device_state

log = logging.getLogger("oppaypay.alive")

class HumanPatternSimulator:

    def __init__(self, core, interval_range=(30, 180)):
        self.core = core
        self._flow_state = 1.0
        self.interval_range = interval_range

    def _organic_wait(self, base_rhythm: float = 1.5):
        core_wait = random.lognormvariate(math.log(base_rhythm), 0.3)
        flow_factor = max(0.8, min(1.5, random.gauss(self._flow_state, 0.1)))
        hesitation = 1.0
        if random.random() < 0.01:
            hesitation *= random.uniform(1.2, 2.5)
        final_wait = core_wait * flow_factor * hesitation
        time.sleep(max(0.5, final_wait))
        self._flow_state = max(0.8, min(1.2, self._flow_state + random.uniform(-0.1, 0.1)))

    def _simulate_micro_tremors(self):
        steps = random.randint(1, 3)
        for _ in range(steps):
            new_headers = update_header_device_state(self.core.session.headers)
            self.core.session.headers.update(new_headers)
            time.sleep(random.expovariate(10.0))

    def simulate_home_screen_visit(self):
        print("[Organic] ホーム画面に遷移")
        self._flow_state = 1.0
        self.core.alive()
        self._organic_wait(1.2)
        balance = self.core.get_balance()
        print(f"[Organic] 残高確認完了")
        self._simulate_micro_tremors()
        self._organic_wait(1.8)
        return balance

    def simulate_history_check(self):
        print("[Organic] 履歴リスト操作中")
        for _ in range(3):
            self._simulate_micro_tremors()
        self._organic_wait(2.5)

    def run_full_session_simulation(self):
        try:
            self.simulate_home_screen_visit()
            self.simulate_history_check()
            self.core._api_request("get", "https://app4.paypay.ne.jp/bff/v1/getGlobalServiceStatus", params={"payPayLang": "ja"})
            print("[Organic] セッション終了")
        except Exception as e:
            print(f"[Organic] 中断: {e}")

    def start(self):
        if hasattr(self, '_thread') and self._thread.is_alive():
            log.warning("HumanPatternSimulator はすでに起動しています。")
            return
            
        self._stop_event = threading.Event()
        def _run():
            while not self._stop_event.is_set():
                try:
                    self.run_full_session_simulation()
                except Exception as e:
                    log.error(f"HumanPatternSimulator error: {e}")
                
                wait_time = random.uniform(self.interval_range[0], self.interval_range[1])
                log.info(f"[Organic] 次のセッションまで {wait_time:.1f} 秒待機...")
                self._stop_event.wait(wait_time)
                
        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        log.info("🌱 HumanPatternSimulator をバックグラウンドで開始しました。")

    def stop(self):
        if hasattr(self, '_stop_event'):
            self._stop_event.set()
        if hasattr(self, '_thread'):
            self._thread.join(timeout=10)
        log.info("🌿 HumanPatternSimulator を停止しました。")


class AliveSimulator:

    def __init__(self, core):
        self.core = core
        self.human_simulator = HumanPatternSimulator(core)

    def simulate_session(self, duration_minutes: int = 60):

        self.human_simulator.run_full_session_simulation()


def simulate_human_behavior(core):

    sim = HumanPatternSimulator(core)
    sim.run_full_session_simulation()
