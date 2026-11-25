"""通过 OpenAI SDK 调用 MiniMax 的兼容接口。"""

from __future__ import annotations

import os

from openai import OpenAI

from client.LLMclientgeneric import LLMclientgeneric


MINIMAX_BASE_URL = "https://api.minimaxi.com/v1"
DEFAULT_MINIMAX_MODEL = "MiniMax-M3.1-Flash"
DEFAULT_MINIMAX_IMAGE_MODEL = "MiniMax-H3-Image"


def get_minimax_api_key() -> str:
    """从进程环境读取 MiniMax 密钥，兼容两种现有变量名。"""
    key = (os.getenv("api_key_minimax") or os.getenv("MINIMAX_API_KEY") or "").strip()
    if not key:
        raise ValueError("请在电脑环境变量中配置 api_key_minimax 或 MINIMAX_API_KEY")
    return key


class MiniMaxAPI(LLMclientgeneric):
    """MiniMax 文本对话客户端，复用通用 OpenAI SDK 流式调用逻辑。"""

    def __init__(self) -> None:
        super().__init__(
            api_key=get_minimax_api_key(),
            base_url=(os.getenv("MINIMAX_BASE_URL") or MINIMAX_BASE_URL).strip(),
            model_name=(os.getenv("MINIMAX_MODEL") or DEFAULT_MINIMAX_MODEL).strip(),
        )


def get_image_client() -> OpenAI:
    """创建 MiniMax 图片生成客户端，密钥始终来自进程环境。"""
    return OpenAI(
        api_key=get_minimax_api_key(),
        base_url=(os.getenv("MINIMAX_BASE_URL") or MINIMAX_BASE_URL).strip(),
        max_retries=0,
    )


def image_model() -> str:
    """返回可替换的图片模型配置。"""
    return (os.getenv("MINIMAX_IMAGE_MODEL") or DEFAULT_MINIMAX_IMAGE_MODEL).strip()
