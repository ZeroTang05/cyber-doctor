from env import get_env_value


def get_client(api_key_variable):
    from zhipuai import ZhipuAI

    api_key = (get_env_value(api_key_variable) or "").strip()
    if not api_key:
        raise ValueError(f"请在 .env 中配置 {api_key_variable}（官方智谱 API Key）")
    return ZhipuAI(api_key=api_key, max_retries=0)

