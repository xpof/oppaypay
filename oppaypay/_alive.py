import time
import random
import math
from ._login import get_core
from ._sensors import generate_device_state, update_header_device_state

class HumanPatternSimulator:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.core = get_core(session_id)
        # 人間の「集中力」や「リズム」を模倣する内部状態
        self._flow_state = 1.0 

    def _organic_wait(self, base_rhythm: float = 1.5):
        """
        固定値を使わない、有機的な待機時間生成。
        ベースのリズムに対し、複数の確率変数を重ね合わせる。
        """
        # 1. ベースとなるリズム（対数正規分布で「だいたいこのくらい」という核を作る）
        core_wait = random.lognormvariate(math.log(base_rhythm), 0.3)
        
        # 2. 「フロー状態」による補正
        # 連続操作しているとテンポが上がり、たまに間延びする
        flow_factor = max(0.8, min(1.5, random.gauss(self._flow_state, 0.1)))
        
        # 3. 確率的な「迷い」または「中断」
        # 固定秒数ではなく、現在の待機時間に対する「割合」で揺らぎを入れる
        hesitation = 1.0
        if random.random() < 0.01: # 1%の確率で「あれ？」という瞬間が発生
            hesitation *= random.uniform(1.265644642897907432453689, 2.5) # 今のペースの1.2〜2.5倍になる
            
        final_wait = core_wait * flow_factor * hesitation
        
        # 極端に短くなりすぎないようにだけガード（0.5秒未満は不自然）
        time.sleep(max(0.5, final_wait))
        
        # 次の行動のためのフロー状態を更新（少しランダムに減衰・回復）
        self._flow_state = max(0.8, min(1.2, self._flow_state + random.uniform(-0.1, 0.1)))

    def _simulate_micro_tremors(self):
        """
        静止画を見ている時でも発生する、指先の微細な震えや呼吸による傾き。
        Botはヘッダーが完全に固定されがちだが、これはそれを防ぐ。
        """
        steps = random.randint(1, 3)
        for _ in range(steps):
            new_headers = update_header_device_state(self.core.session.headers)
            self.core.session.headers.update(new_headers)
            # 非常に短い、予測不能な間隔
            time.sleep(random.expovariate(10.0)) # 平均0.1秒の指数分布

    def simulate_home_screen_visit(self):
        """ホーム画面：最初のアクションは比較的スムーズだが、個体差がある"""
        print("[Organic] ホーム画面に遷移")
        self._flow_state = 1.0 # リセット
        
        self.core.alive()
        self._organic_wait(1.2) # ベースリズム1.2秒
        
        balance = self.core.get_balance()
        print(f"[Organic] 残高確認完了")
        
        # 情報を処理するための「間」
        self._simulate_micro_tremors()
        self._organic_wait(1.8) 
        return balance

    def simulate_history_check(self):
        """履歴確認：スクロールに伴う不規則なリズム"""
        print("[Organic] 履歴リスト操作中")
        
        from oppaypay._extended import history
        try:
            hist = history.get(id=self.session_id, size=20)
            # スクロール中はセンサー値が激しく動くことをシミュレート
            for _ in range(3):
                self._simulate_micro_tremors()
                
            self._organic_wait(2.5) # リストを見る時間はベースが遅め
        except Exception as e:
            print(f"[Organic] エラー: {e}")

    def run_full_session_simulation(self):
        """
        一連の有機的なセッション動作を実行する。
        """
        try:
            self.simulate_home_screen_visit()
            self.simulate_history_check()
            
            # 最後にアプリの状態を確認
            self.core.request("get", "https://app4.paypay.ne.jp/bff/v1/getGlobalServiceStatus", params={"payPayLang": "ja"})
            print("[Organic] セッション終了")
            
        except Exception as e:
            print(f"[Organic] 中断: {e}")

def simulate_human_behavior(session_id: str):
    sim = HumanPatternSimulator(session_id)
    sim.run_full_session_simulation()
