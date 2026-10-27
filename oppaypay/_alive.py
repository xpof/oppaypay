import time
import random
import math
from ._sensors import update_header_device_state

class HumanPatternSimulator:
    def __init__(self, core):
        self.core = core
        self._flow_state = 1.0

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

def simulate_human_behavior(core):
    sim = HumanPatternSimulator(core)
    sim.run_full_session_simulation()
