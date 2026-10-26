import re
import base64
import json
from ._awswaf import solve_challenge

def solve_aws_waf_challenge(html_content: str, user_agent: str) -> str:
    match = re.search(r'window\.awsWafChallenge\s*=\s*"([^"]+)"', html_content)
    if not match:
        # Fallback or different extraction method might be needed depending on PayPay's updates
        raise ValueError("AWS WAF challenge data not found in HTML")
        
    challenge_data = match.group(1)
    
    token = solve_challenge(challenge_data, user_agent)
    return token