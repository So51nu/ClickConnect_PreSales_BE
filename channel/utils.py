# channel/utils.py
import secrets
from .models import ChannelPartnerProfile

def generate_unique_referral_code(prefix: str = "CP") -> str:
    """
    Generates a unique referral code like 'CP-4F8A2C'.
    """
    while True:
        code = f"{prefix}-{secrets.token_hex(3).upper()}"  # 6 hex chars
        if not ChannelPartnerProfile.objects.filter(referral_code=code).exists():
            return code
