from env import get_env_value
from abc import abstractmethod

from openai import OpenAI
from openai import Stream
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from typing import List, Dict


# 抽象类，用于构造client
class LLMclientbase(object):
    def __init__(
        self,
        *,
        api_key_variable: str = "LLM_API_KEY",
        base_url_variable: str = "LLM_BASE_URL",
        model_variable: str = "MODEL_NAME",
        api_key: str | None = None,
        base_url: str | None = None,
        model_name: str | None = None,
    ):
        """
        初始化LLM客户端基类
        """
        api_key = (api_key or get_env_value(api_key_variable) or "").strip()
        base_url = (base_url or get_env_value(base_url_variable) or "").strip()
        model_name = (model_name or get_env_value(model_variable) or "").strip()
        if not api_key:
            raise ValueError(f"请配置环境变量 {api_key_variable}")
        if not base_url:
            raise ValueError(f"请配置环境变量 {base_url_variable}")
        if not model_name:
            raise ValueError(f"请配置环境变量 {model_variable}")
        self.__client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.__model_name = model_name

    @property
    def client(self):
        return self.__client

    @property
    def model_name(self):
        return self.__model_name

    # 以下全都是抽象函数
    @abstractmethod
    def chat_with_ai(self, prompt: str) -> str | None:
        """
        与AI进行聊天，返回AI的回复
        :param prompt: 用户输入的提示信息
        :return: AI的回复，可能为None
        """
        raise NotImplementedError()

    @abstractmethod
    def chat_with_ai_stream(
        self, prompt: str, history: List[List[str]] | None = None
    ) -> ChatCompletion | Stream[ChatCompletionChunk]:
        """
        与AI进行流式聊天，返回流式回复
        :param prompt: 用户输入的提示信息
        :param history: 聊天历史记录，默认为None
        :return: 流式聊天完成或流式聊天块
        """
        raise NotImplementedError()

    @abstractmethod
    def construct_message(
        self, prompt: str, history: List[List[str]] | None = None
    ) -> List[Dict[str, str]] | str | None:
        """
        构造消息，用于与AI进行聊天
        :param prompt: 用户输入的提示信息
        :param history: 聊天历史记录，默认为None
        :return: 构造的消息列表或字符串，可能为None
        """
        raise NotImplementedError()

    @abstractmethod
    def chat_using_messages(self, messages: List[Dict]) -> str | None:
        """
        使用消息列表与AI进行聊天，返回AI的回复
        :param messages: 消息列表
        :return: AI的回复，可能为None
        """
        raise NotImplementedError()
