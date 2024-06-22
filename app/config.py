import os
import logging
import random
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 获取环境变量值，支持大小写不敏感，空值返回默认值。
def get_env_value(key, default=None):
    value = os.getenv(key) or os.getenv(key.lower()) or os.getenv(key.upper())
    return default if value in [None, ''] else value

IGNORED_MODEL_NAMES = ["gpt-4", "gpt-3.5", "websearch", "dall-e-3", "gpt-4o"]
IMAGE_MODEL_NAMES = ["dalle3", "dalle-3", "dall-e-3"]
AUTH_TOKEN = get_env_value("AUTHORIZATION")
G_TOKEN = get_env_value("G_TOKEN")
HISTORY_MSG_LIMIT = get_env_value("HISTORY_MSG_LIMIT", 0)
RECAPTCHA_SECRET = get_env_value("RECAPTCHA_SECRET")
POPAI_BASE_URL = "https://www.popai.pro/"
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()

def configure_logging():
    extended_log_format = (
        '%(asctime)s | %(levelname)s | %(name)s | '
        '%(process)d | %(filename)s:%(lineno)d | %(funcName)s | %(message)s'
    )
    logging.basicConfig(level=log_level, format=extended_log_format)


def _get_proxies_from_env(env_var):
    proxies = get_env_value(env_var, '')
    return [proxy.strip() for proxy in proxies.split(',') if proxy.strip()]


class ProxyPool:
    def __init__(self):
        self.http_proxies = _get_proxies_from_env('HTTP_PROXY')
        self.https_proxies = _get_proxies_from_env('HTTPS_PROXY')

    def get_random_proxy(self):
        proxy = {}
        if self.http_proxies:
            proxy['http'] = random.choice(self.http_proxies)
        if self.https_proxies:
            proxy['https'] = random.choice(self.https_proxies)
        
        # 若只存在一个键，使用其值填充另一个
        if 'http' in proxy or 'https' in proxy:
            proxy.setdefault('http', proxy.get('https'))
            proxy.setdefault('https', proxy.get('http'))
    
        # logging.info("proxy URL %s", proxy)

        return proxy if proxy else None
