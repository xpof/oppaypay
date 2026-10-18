import logging
from ._waf_solver import solve_aws_waf_challenge

log = logging.getLogger("oppaypay.waf")

class WAFSolver:
    def __init__(self, session):
        self.session = session

    def solve(self, url: str) -> bool:
        try:
            resp = self.session.get(url, timeout=15)
            if "aws-waf-token" in self.session.cookies:
                return True
            if "challenge.js" in resp.text or "aws-waf-token" in resp.headers.get("Set-Cookie", ""):
                log.info("WAF challenge detected, attempting to solve...")
                token = solve_aws_waf_challenge(resp.text, self.session.headers.get("User-Agent", ""))
                self.session.cookies.set("aws-waf-token", token, domain=".paypay.ne.jp")
                return True
            return True
        except Exception as e:
            log.error(f"WAF solve error: {e}")
            return False