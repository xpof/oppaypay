import time
import random
import math
import logging
from datetime import datetime, timedelta
from .exceptions import OpPayPayError

log = logging.getLogger(__name__)

class AliveSimulator:

    def __init__(self, core):
        self.core = core
        
        self.URL_CHAT_ROOMS = "https://app4.paypay.ne.jp/p2p/v1/getP2PChatRoomListLite"
        self.URL_CHAT_MESSAGES = "https://app4.paypay.ne.jp/bff/v1/getP2PMessageList"
        self.URL_HISTORY = "https://app4.paypay.ne.jp/bff/v4/getPaymentHistory"

    def _get_focus_level(self) -> float:
        now = datetime.now()
        hour = now.hour
        
        if 9 <= hour < 22:
            base_focus = 0.8 + 0.2 * math.sin((hour - 9) / 13 * math.pi)
        elif 22 <= hour < 24 or 5 <= hour < 9:
            base_focus = 0.6
        else:
            base_focus = 0.1
            
        # 微小なランダムノイズを加える
        noise = random.uniform(-0.1, 0.1)
        return max(0.0, min(1.0, base_focus + noise))

    def _random_wait(self):

        focus = self._get_focus_level()
        
        if focus < 0.2:
            wait_time = random.uniform(60.0, 300.0)
            log.debug(f"[Alive] 深夜モード: {wait_time:.1f}秒休憩します...")
        else:
            mean_wait = 15.0 * (2.0 - focus) 
            wait_time = random.expovariate(1.0 / mean_wait)
            wait_time = max(3.0, min(wait_time, 120.0)) 
            
        time.sleep(wait_time)

    def _view_balance(self):
        log.info("[Alive] 💰 残高を確認しています...")
        try:
            balance = self.core.get_balance()
            log.debug(f"[Alive] 残高: {balance.money} 円")
            
            focus = self._get_focus_level()
            if focus < 0.3:
                view_time = random.uniform(5.0, 15.0) 
            else:
                view_time = random.uniform(1.0, 5.0)  
                
            log.debug(f"[Alive] 残高画面を {view_time:.1f}秒 見つめます...")
            time.sleep(view_time)
            
        except OpPayPayError as e:
            log.warning(f"[Alive] 残高確認エラー: {e}")

    def _view_chat(self):
        log.info("[Alive] 💬 チャットルームを眺めています...")
        try:
            params = {
                "pageSize": "20",
                "customTypes": "P2P_CHAT,P2P_CHAT_INACTIVE,P2P_PUBLIC_GROUP_CHAT,P2P_LINK,P2P_OLD",
                "requiresLastMessage": "true",
                "socketConnection": "P2P",
                "payPayLang": "ja"
            }
            res = self.core._api_request("get", self.URL_CHAT_ROOMS, params=params)
            
            rooms = res.get("payload", {}).get("chatRooms", [])
            if rooms:
                room = random.choice(rooms)
                room_id = room.get("chatRoomId")
                log.debug(f"[Alive] チャットルーム '{room_id}' のメッセージを読み込み中...")
                
                msg_params = {
                    "chatRoomId": room_id,
                    "include": "false",
                    "prev": "15",
                    "next": "0",
                    "payPayLang": "ja"
                }
                msg_res = self.core._api_request("get", self.URL_CHAT_MESSAGES, params=msg_params)
                
                focus = self._get_focus_level()
                
                msgs = msg_res.get("payload", {}).get("messages", [])
                msg_count = len(msgs) if msgs else 5
                effective_msg_count = min(msg_count, 15)
                
                if focus < 0.3:
                    base_read_time_per_msg = random.uniform(3.0, 8.0)
                elif focus > 0.7:
                    base_read_time_per_msg = random.uniform(0.5, 2.0)
                else:
                    base_read_time_per_msg = random.uniform(1.0, 4.0)
                
                total_read_time = base_read_time_per_msg * effective_msg_count
                
                if random.random() < 0.07: 
                    extra_time = random.uniform(5.0, 20.0)
                    log.debug(f"[Alive] メッセージに見入ってしまいました... (+{extra_time:.1f}秒)")
                    total_read_time += extra_time
                
                total_read_time = max(2.5, total_read_time)
                
                log.debug(f"[Alive] チャットを {total_read_time:.1f}秒 眺めます...")
                time.sleep(total_read_time)
            else:
                log.debug("[Alive] チャットルームがありませんでした。")
                
        except OpPayPayError as e:
            log.warning(f"[Alive] チャット閲覧エラー: {e}")

    def _view_history(self):
        log.info("[Alive] 📜 支払い履歴を遡っています...")
        try:
            params = {
                "pageSize": "20",
                "orderTypes": "",
                "paymentMethodTypes": "",
                "signUpCompletedAt": "2021-01-02T10:16:24Z",
                "isOverdraftOnly": "false",
                "payPayLang": "ja"
            }
            self.core._api_request("get", self.URL_HISTORY, params=params)
            
            focus = self._get_focus_level()
            if focus < 0.3:
                view_time = random.uniform(3.0, 10.0)
            else:
                view_time = random.uniform(1.0, 3.0)
                
            log.debug(f"[Alive] 履歴画面を {view_time:.1f}秒 見つめます...")
            time.sleep(view_time)
            
        except OpPayPayError as e:
            log.warning(f"[Alive] 履歴確認エラー: {e}")

    def _do_random_action(self):
        focus = self._get_focus_level()
        
        if focus < 0.3:
            log.info("[Alive] 🌙 眠たいので、アプリを開いてすぐ閉じます...")
            self.core.alive() 
            return

        actions = [
            (self.core.alive, 40),    
            (self._view_balance, 30), 
            (self._view_chat, 20),    
            (self._view_history, 10) 
        ]
        
        funcs, weights = zip(*actions)
        chosen_action = random.choices(funcs, weights=weights, k=1)[0]
        
        chosen_action()

    def simulate_session(self, duration_minutes: int = 5):

        end_time = datetime.now() + timedelta(minutes=duration_minutes)
        log.info(f"{duration_minutes}分間の人間シミュレーションを開始します")
        
        while datetime.now() < end_time:
            self._do_random_action()
            self._random_wait()
            
        log.info("人間シミュレーションを終了します")
