'''edge-tts调用接口'''
import os
import asyncio

from env import get_app_root
import hashlib

_OUTPUT_DIR = os.path.join(get_app_root(), "data/cache/audio")

def get_file_path(text):
    file_name = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return os.path.join(_OUTPUT_DIR, f"{file_name}.mp3")


def audio_generate(text: str, model_name : str) -> str:
    import edge_tts

    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    _output_file = get_file_path(text)

    # 异步调用_generating函数，使得I/O时可以进行其他操作
    async def _generating() -> None:
        communicate = edge_tts.Communicate(text, model_name)
        await communicate.save(_output_file)

    asyncio.run(_generating())

    return _output_file
