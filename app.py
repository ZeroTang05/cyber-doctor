import base64
from pathlib import Path
from qa.answer import get_answer
from qa.question_parser import parse_question
from qa.purpose_type import userPurposeType
from audio.audio_generate import audio_generate

import base64
import mimetypes
import gradio as gr
from icecream import ic
import os
from time import monotonic
from openai import APIError
from httpx import TransportError


AVATAR = ("resource/user.png", "resource/bot.jpg")
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# pip install whisper
# pip install openai-whisper
# pip install soundfile
# pip install pydub
# pip install opencc-python-reimplemented


def convert_to_simplified(text):
    from opencc import OpenCC

    converter = OpenCC("t2s")
    return converter.convert(text)


def convert_audio_to_wav(audio_file_path):
    from pydub import AudioSegment

    audio = AudioSegment.from_file(audio_file_path)  # 自动识别格式
    wav_file_path = audio_file_path.rsplit(".", 1)[0] + ".wav"  # 生成 WAV 文件路径
    audio.export(wav_file_path, format="wav")  # 将音频文件导出为 WAV 格式
    return wav_file_path


def audio_to_text(audio_file_path):
    from speech_recognition import AudioFile, Recognizer

    # 创建识别器对象
    # 如果不是 WAV 格式，先转换为 WAV
    if not audio_file_path.endswith(".wav"):
        audio_file_path = convert_audio_to_wav(audio_file_path)

    recognizer = Recognizer()
    with AudioFile(audio_file_path) as source:
        audio_data = recognizer.record(source)
        # 使用 Google Web Speech API 进行语音识别，不用下载模型但对网络要求高
        # text = recognizer.recognize_google(audio_data, language="zh-CN")
        # 使用 whisper 进行语音识别，自动下载模型到本地
        text = recognizer.recognize_whisper(audio_data, language="zh")
        text_simplified = convert_to_simplified(text)
    return text_simplified


# pip install PyPDF2
def pdf_to_str(pdf_file):
    from PyPDF2 import PdfReader

    reader = PdfReader(pdf_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text


def docx_to_str(file_path):
    from docx import Document

    doc = Document(file_path)
    text = []
    for paragraph in doc.paragraphs:
        text.append(paragraph.text)
    return "\n".join(text)


# pip install chardet
def text_file_to_str(text_file):
    import chardet

    with open(text_file, "rb") as file:
        raw_data = file.read()
        result = chardet.detect(raw_data)
        encoding = result["encoding"]

    # 使用检测到的编码来读取文件
    with open(text_file, "r", encoding=encoding) as file:
        return file.read()


def image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
        return encoded_string


# 核心函数
def grodio_view(chatbot, chat_input):
    user_message = chat_input["text"] or ""
    if not user_message.strip() and not chat_input["files"]:
        return
    bot_response = "正在处理…"
    chatbot.append([user_message, bot_response])
    yield chatbot, {"text": "", "files": []}

    # 处理用户上传的文件
    files = chat_input["files"]
    audios = []
    images = []
    pdfs = []
    docxs = []
    texts = []

    for file in files:
        file_type = mimetypes.guess_type(file)[0] or ""
        if file_type.startswith("audio/"):
            audios.append(file)
        elif file_type.startswith("image/"):
            images.append(file)
        elif file_type.startswith("application/pdf"):
            pdfs.append(file)
        elif file_type.startswith(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ):
            docxs.append(file)
        elif file_type.startswith("text/"):
            texts.append(file)
        else:
            user_message += "请你将下面的句子修饰后输出，不要包含额外的文字，句子:'该文件为不支持的文件类型'"
            print(f"Unknown file type: {file_type}")

    # 图片文件解析
    if images != []:
        image_url = images
        image_base64 = [image_to_base64(image) for image in image_url]

        for i, image in enumerate(image_base64):
            chatbot[-1][
                0
            ] += f"""
                <div>
                    <img src="data:image/png;base64,{image}" alt="Generated Image" style="max-width: 100%; height: auto; cursor: pointer;" />
                </div>
                """
            yield chatbot, gr.skip()
    else:
        image_url = None

    try:
        question_type = parse_question(user_message, image_url)
    except (APIError, ValueError) as error:
        chatbot[-1][1] = model_error_message(error)
        yield chatbot, gr.skip()
        return
    ic(question_type)

    # 音频文件解析
    if audios != []:
        for i, audio in enumerate(audios):
            audio_message = audio_to_text(audio)
            if audio_message == "":
                user_message += "请你将下面的句子修饰后输出，不要包含额外的文字，句子:'音频识别失败，请稍后再试'"
            elif "作曲" in audio_message:
                user_message += "请你将下面的句子修饰后输出，不要包含额外的文字，句子:'不好意思，我无法理解音乐'"
            else:
                user_message += f"音频{i+1}内容：{audio_message}"

    if pdfs != []:
        for i, pdf in enumerate(pdfs):
            pdf_text = pdf_to_str(pdf)
            user_message += f"PDF{i+1}内容：{pdf_text}"

    if docxs != []:
        for i, docx in enumerate(docxs):
            docx_text = docx_to_str(docx)
            user_message += f"DOCX{i+1}内容：{docx_text}"

    if texts != []:
        for i, text in enumerate(texts):
            text_string = text_file_to_str(text)
            user_message += f"文本{i+1}内容：{text_string}"

    if user_message == "":
        user_message = "请你将下面的句子修饰后输出，不要包含额外的文字，句子:'请问您有什么想了解的，我将尽力为您服务'"
    try:
        answer = get_answer(user_message, chatbot[:-1], question_type, image_url)
    except (APIError, ValueError) as error:
        chatbot[-1][1] = model_error_message(error)
        yield chatbot, gr.skip()
        return
    bot_response = ""

    # 处理文本生成/其他/文档检索/知识图谱检索
    if (
        answer[1] == userPurposeType.text
        or answer[1] == userPurposeType.RAG
        or answer[1] == userPurposeType.KnowledgeGraph
        or answer[1] == userPurposeType.DeepResearch
    ):
        # 合并高频 token，首段立即显示，结束时补齐最后一段。
        last_refresh = 0.0
        emitted_response = ""
        stream_started = monotonic()
        previous_chunk = stream_started
        max_chunk_gap = 0.0
        chunk_count = 0
        refresh_count = 0
        finish_reason = None
        stream_error = None
        try:
            for chunk in answer[0]:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                if choice.finish_reason is not None:
                    finish_reason = choice.finish_reason
                content = choice.delta.content
                if not content:
                    continue
                now = monotonic()
                gap = now - previous_chunk
                max_chunk_gap = max(max_chunk_gap, gap)
                if gap >= 2:
                    print(f"Text stream: upstream_gap={gap:.2f}s, content_chunks={chunk_count}", flush=True)
                previous_chunk = now
                chunk_count += 1
                bot_response += content
                if last_refresh and now - last_refresh < 0.1:
                    continue
                chatbot[-1][1] = bot_response
                emitted_response = bot_response
                last_refresh = now
                refresh_count += 1
                yield chatbot, gr.skip()
        except (APIError, TransportError) as error:
            stream_error = type(error).__name__
        finally:
            answer[0].close()
        if stream_error:
            bot_response += f"\n\n> 模型连接中断或等待超时（{stream_error}），以上为已收到的内容。"
        elif finish_reason == "length":
            bot_response += "\n\n> 模型达到输出长度上限，回答尚未完成。"
        elif finish_reason != "stop":
            bot_response += f"\n\n> 模型未正常完成回答（结束原因：{finish_reason or '未收到结束标记'}）。"
        # 无论最后一个 chunk 是否触发节流，都提交最终累积文本。
        chatbot[-1][1] = bot_response
        refresh_count += 1
        yield chatbot, gr.skip()
        print(
            f"Text stream: chunks={chunk_count}, refreshes={refresh_count}, "
            f"duration={monotonic() - stream_started:.2f}s, max_chunk_gap={max_chunk_gap:.2f}s, "
            f"finish_reason={finish_reason}, error={stream_error}, chars={len(bot_response)}",
            flush=True,
        )

    # 处理图片生成
    if answer[1] == userPurposeType.ImageGeneration:
        image_url = answer[0]
        combined_message = f"""
            **生成的图片:**
            ![Generated Image]({image_url})
            """
        chatbot[-1][1] = combined_message
        yield chatbot, gr.skip()

    # 处理图片描述
    if answer[1] == userPurposeType.ImageDescribe:
        for i in range(0, len(answer[0]), 1):
            bot_response += answer[0][i : i + 1]  # 累加当前chunk到combined_message
            chatbot[-1][1] = bot_response  # 更新chatbot对话中的最后一条消息
            yield chatbot, gr.skip()  # 实时输出当前累积的对话内容

    # 处理视频
    if answer[1] == userPurposeType.Video:
        if answer[0] is not None:
            chatbot[-1][1] = answer[0]
        else:
            chatbot[-1][1] = "抱歉，视频生成失败，请稍后再试"
        yield chatbot, gr.skip()

    # 处理PPT
    if answer[1] == userPurposeType.PPT:
        if answer[0] is not None:
            chatbot[-1][1] = answer[0]
        else:
            chatbot[-1][1] = "抱歉，PPT生成失败，请稍后再试"
        yield chatbot, gr.skip()

    # 处理Docx
    if answer[1] == userPurposeType.Docx:
        if answer[0] is not None:
            chatbot[-1][1] = answer[0]
        else:
            chatbot[-1][1] = "抱歉，文档生成失败，请稍后再试"
        yield chatbot, gr.skip()

    # 处理音频生成
    if answer[1] == userPurposeType.Audio:
        if answer[0] is not None:
            chatbot[-1][1] = answer[0]
        else:
            chatbot[-1][1] = "抱歉，音频生成失败，请稍后再试"
        yield chatbot, gr.skip()

    # 处理联网搜索
    if answer[1] == userPurposeType.InternetSearch:
        if answer[3] == False:
            output_message = (
                "联网搜索未获得可用资料，本次未生成联网回答。请检查网络或搜索配置。"
            )
        else:
            # 将字典中的内容转换为 Markdown 格式的链接
            links = "\n".join(f"[{title}]({link})" for link, title in answer[2].items())
            links += "\n"
            output_message = f"参考资料：{links}"
        for i in range(0, len(output_message)):
            bot_response = output_message[: i + 1]
            chatbot[-1][1] = bot_response
            yield chatbot, gr.skip()
        for chunk in answer[0]:
            bot_response = bot_response + (chunk.choices[0].delta.content or "")
            chatbot[-1][1] = bot_response
            yield chatbot, gr.skip()


def gradio_audio_view(chatbot, audio_input):
    if audio_input is None:
        raise gr.Error("请先录音或上传音频。")

    # 先显示已提交的录音，再将识别结果交给模型。
    chatbot.append([(audio_input, "audio"), "正在处理…"])
    yield chatbot

    user_message = audio_to_text(audio_input).strip()
    if not user_message or "作曲 作曲" in user_message:
        chatbot[-1][1] = "没有识别到语音，请重新录音或上传音频。"
        yield chatbot
        return
    chatbot[-1][0] = user_message
    try:
        question_type = parse_question(user_message)
        ic(question_type)
        answer = get_answer(user_message, chatbot[:-1], question_type)
    except (APIError, ValueError) as error:
        chatbot[-1][1] = model_error_message(error)
        yield chatbot
        return
    bot_response = ""

    # 处理文本生成/其他/文档检索/知识图谱检索
    if (
        answer[1] == userPurposeType.text
        or answer[1] == userPurposeType.RAG
        or answer[1] == userPurposeType.KnowledgeGraph
        or answer[1] == userPurposeType.DeepResearch
    ):
        # 语音输出
        for chunk in answer[0]:
            # 获取每个块的数据
            chunk_content = chunk.choices[0].delta.content or ""
            bot_response += chunk_content

        try:
            chatbot[-1][1] = (
                audio_generate(
                    text=bot_response,
                    model_name="zh-CN-YunxiNeural",
                ),
                "audio",
            )
        except Exception as e:
            print(f"音频生成失败，直接返回文本: {str(e)}")
            chatbot[-1][1] = bot_response 
            
        yield chatbot

    # 处理图片生成
    if answer[1] == userPurposeType.ImageGeneration:
        image_url = answer[0]
        combined_message = f"""
            **生成的图片:**
            ![Generated Image]({image_url})
            """
        chatbot[-1][1] = combined_message
        yield chatbot

    # 处理视频
    if answer[1] == userPurposeType.Video:
        if answer[0] is not None:
            chatbot[-1][1] = answer[0]
        else:
            try:
                chatbot[-1][1] = (
                    audio_generate(
                        text="抱歉，视频生成失败，请稍后再试",
                        model_name="zh-CN-YunxiNeural",
                    ),
                    "audio",
                )
            except Exception as e:
                chatbot[-1][1] = "抱歉，视频生成失败，请稍后再试"
        yield chatbot

    # 处理PPT
    if answer[1] == userPurposeType.PPT:
        if answer[0] is not None:
            chatbot[-1][1] = answer[0]
        else:
            try:
                chatbot[-1][1] = (
                    audio_generate(
                        text="抱歉，PPT生成失败，请稍后再试",
                        model_name="zh-CN-YunxiNeural",
                    ),
                    "audio",
                )
            except Exception as e:
                chatbot[-1][1] = "抱歉，PPT生成失败，请稍后再试"
        yield chatbot

    # 处理Docx
    if answer[1] == userPurposeType.Docx:
        if answer[0] is not None:
            chatbot[-1][1] = answer[0]
        else:
            try:
                chatbot[-1][1] = (
                    audio_generate(
                        text="抱歉，文档生成失败，请稍后再试",
                        model_name="zh-CN-YunxiNeural",
                    ),
                    "audio",
                )
            except Exception as e:
                chatbot[-1][1] = "抱歉，文档生成失败，请稍后再试"
        yield chatbot

    # 处理音频生成
    if answer[1] == userPurposeType.Audio:
        if answer[0] is not None:
            chatbot[-1][1] = answer[0]
        else:
            try:
                chatbot[-1][1] = (
                    audio_generate(
                        text="抱歉，音频生成失败，请稍后再试",
                        model_name="zh-CN-YunxiNeural",
                    ),
                    "audio",
                )
            except Exception as e:
                chatbot[-1][1] = "抱歉，音频生成失败，请稍后再试"
        yield chatbot

    # 处理联网搜索
    if answer[1] == userPurposeType.InternetSearch:
        if answer[3] == False:
            bot_response = (
                "由于网络问题，访问互联网失败，下面由我根据现有知识给出回答："
            )
        # 语音输出
        for chunk in answer[0]:
            # 获取每个块的数据
            chunk_content = chunk.choices[0].delta.content or ""
            bot_response += chunk_content

        try:
            chatbot[-1][1] = (
                audio_generate(
                    text=bot_response,
                    model_name="zh-CN-YunxiNeural",
                ),
                "audio",
            )
        except Exception as e:
            print(f"音频生成失败，直接返回文本: {str(e)}")
            chatbot[-1][1] = bot_response
        yield chatbot


def model_error_message(error):
    """将模型请求失败呈现在当前回答中。"""
    if isinstance(error, APIError) and getattr(error, "status_code", None) == 402:
        return "模型服务返回 402，当前账户额度不足。"
    return f"模型请求失败（{type(error).__name__}），请检查模型配置后重试。"


def chat_turns(messages):
    """将 Gradio 消息还原为模型调用使用的问答对。"""
    turns = []
    for message in messages:
        item = message["content"][0]
        content = item["text"] if item["type"] == "text" else (
            item["file"]["path"], item.get("alt_text")
        )
        if message["role"] == "user":
            turns.append([content, None])
        elif message["role"] == "assistant":
            turns[-1][1] = content
    return turns


def chat_messages(turns):
    """将问答对转换为 Gradio 6 的文本或文件消息。"""
    messages = []
    for turn in turns:
        for role, content in zip(("user", "assistant"), turn):
            if content is None:
                continue
            if isinstance(content, tuple):
                path, alt_text = content
                content = {"path": path, "alt_text": alt_text}
            messages.append({"role": role, "content": content})
    return messages


def submit_text_chat(messages, chat_input):
    """提交文字或附件，并逐次更新聊天记录。"""
    for turns, composer in grodio_view(chat_turns(messages), chat_input):
        yield chat_messages(turns), composer


def submit_voice_chat(messages, audio_input):
    """提交录音，并逐次更新聊天记录。"""
    for turns in gradio_audio_view(chat_turns(messages), audio_input):
        yield chat_messages(turns)


# 切换到语音模式的函数
def toggle_voice_mode():
    return (
        gr.update(visible=False),
        gr.update(visible=True),
        gr.update(variant="primary"),
        gr.update(variant="secondary"),
        gr.update(visible=True),
    )


# 切换回文本模式的函数
def toggle_text_mode():
    return (
        gr.update(visible=True),
        gr.update(visible=False),
        gr.update(variant="secondary"),
        gr.update(variant="primary"),
        gr.update(visible=False),
    )


examples = [
    {"text": "您好", "files": []},
    {"text": "糖尿病的常见症状有哪些？", "files": []},
    {"text": "用语音重新回答我一次", "files": []},
    {"text": "帮我搜索一下养生知识", "files": []},
    {"text": "请深度研究糖尿病治疗的最新进展", "files": []},
        {"text": "帮我生成一张老人练太极图片", "files": []},
    {
        "text": "帮我生成一份用于科普糖尿病发病原因，症状，治疗药物，预防措施的PPT",
        "files": [],
    },
    {"text": "请根据我给的参考资料，给我一个合理的饮食建议", "files": []},
    {"text": "请根据我给的参考资料，生成一个用于科普合理膳食的word", "files": []},
    {"text": "我最近想打太极养生，帮我生成一段老人打太极的视频吧", "files": []},
    {"text": "根据我的病历，给我一个合理的治疗方案", "files": []},
    {"text": "根据知识库介绍一下常见疾病", "files": []},
    {"text": "根据知识图谱告诉我糖尿病人适合吃的食物有哪些？", "files": []},
]


ASSISTANT_MARK = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M12 7.5C9.5 5.5 6.5 5 3 6v12c3.5-1 6.5-.5 9 1.5 2.5-2 5.5-2.5 9-1.5V6c-3.5-1-6.5-.5-9 1.5v12"/>'
    '<path d="M6 12h3m-1.5-1.5v3m7.5-.5h3"/></svg>'
)
QUICK_PROMPTS = (
    ("常见疾病", "高血压有哪些常见危险因素？", "pulse"),
    ("体检指标", "如何理解体检报告中的异常指标？", "report"),
    ("健康生活", "怎样改善日常睡眠质量？", "moon"),
    ("用药常识", "初次阅读药品说明书时应留意哪些信息？", "pill"),
    ("常见疾病", "普通感冒和流感有什么区别？", "pulse"),
)
SIDEBAR_ICON = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
    'stroke-linejoin="round" aria-hidden="true">'
    '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M9 5v14"/></svg>'
)


# 构建 Gradio 界面
with gr.Blocks(
    title="赛博华佗",
    fill_width=True,
    theme=gr.themes.Default(font=["sans-serif"], font_mono=["monospace"]),
    css=Path(__file__).with_name("interface.css").read_text(encoding="utf-8"),
    js="""
    () => {
        document.documentElement.lang = "zh-CN";
        const viewport = document.querySelector('meta[name="viewport"]');
        viewport.content += ", interactive-widget=resizes-content";

        const app = document.getElementById("cd-app");
        const modes = document.getElementById("cd-modes");
        const composer = document.getElementById("cd-composer");
        const sidebar = document.getElementById("cd-sidebar");
        const sidebarToggle = document.getElementById("cd-sidebar-toggle");
        const compact = matchMedia("(max-width: 640px)");
        let pendingPrompt;

        const labelControls = () => {
            for (const button of modes.querySelectorAll(".cd-mode")) {
                button.setAttribute("aria-pressed", button.classList.contains("primary"));
            }
            for (const [selector, label] of [
                ["textarea", "消息"],
                [".upload-button", "上传文件"],
                [".submit-button", "发送消息"],
            ]) {
                const control = composer.querySelector("#cd-message-input " + selector);
                control?.setAttribute("aria-label", label);
            }
            const field = composer.querySelector("#cd-message-input textarea");
            if (pendingPrompt && field?.getClientRects().length) {
                field.value = pendingPrompt;
                pendingPrompt = undefined;
                field.dispatchEvent(new Event("input", {bubbles: true}));
                field.focus();
            }
        };

        const setSidebar = (open, moveFocus = true) => {
            app.toggleAttribute("data-sidebar-open", open);
            sidebarToggle.setAttribute("aria-expanded", open);
            sidebarToggle.setAttribute("aria-label", open ? "收起侧栏" : "展开侧栏");
            if (moveFocus) {
                (open ? document.getElementById("cd-new") : sidebarToggle).focus();
            }
        };
        compact.addEventListener("change", () => setSidebar(false, false));
        sidebarToggle.addEventListener("click", () => setSidebar(!app.hasAttribute("data-sidebar-open")));
        app.addEventListener("click", (event) => {
            const prompt = event.target.closest("button[data-prompt]");
            if (prompt) {
                pendingPrompt = prompt.dataset.prompt;
                setSidebar(false, false);
                if (document.getElementById("cd-mode-voice").classList.contains("primary")) {
                    document.getElementById("cd-mode-text").click();
                }
                labelControls();
                return;
            }
            if (app.hasAttribute("data-sidebar-open") && !sidebarToggle.contains(event.target)) {
                if (event.target.closest("#cd-new, .cd-mode") || !sidebar.contains(event.target)) {
                    setSidebar(false, sidebar.contains(event.target));
                }
            }
        });
        app.addEventListener("keydown", (event) => {
            if (event.key === "Escape" && app.hasAttribute("data-sidebar-open")) {
                setSidebar(false);
            }
        });

        labelControls();
        const observer = new MutationObserver(labelControls);
        observer.observe(modes, {subtree: true, attributes: true, attributeFilter: ["class"]});
        observer.observe(composer, {subtree: true, childList: true, attributes: true, attributeFilter: ["class"]});
    }
    """,
) as demo:
    with gr.Row(elem_id="cd-app"):
        with gr.Column(elem_id="cd-sidebar", min_width=0):
            gr.HTML(
                f'<div class="cd-brand"><span class="cd-brand-mark">{ASSISTANT_MARK}</span>'
                '<div><h1>赛博华佗</h1><p>AI 健康知识助手</p></div></div>',
                elem_id="cd-brand",
            )
            new_chat = gr.ClearButton(value="新对话", elem_id="cd-new", min_width=0)
            with gr.Column(elem_id="cd-modes", min_width=0, scale=0):
                gr.HTML('<h2>对话模式</h2>', elem_id="cd-mode-label")
                toggle_text_button = gr.Button(
                    "文本对话", variant="primary", elem_id="cd-mode-text",
                    elem_classes=["cd-mode"], min_width=0,
                )
                toggle_voice_button = gr.Button(
                    "语音对话", elem_id="cd-mode-voice", elem_classes=["cd-mode"], min_width=0,
                )
            gr.HTML(
                '<section><h2>快捷提问</h2>'
                + "".join(
                    f'<button type="button" class="cd-prompt" data-icon="{icon}" data-prompt="{question}">'
                    f'{category}</button>'
                    for category, question, icon in QUICK_PROMPTS[:4]
                )
                + '</section>',
                elem_id="cd-shortcuts",
            )
            sidebar_examples = gr.Accordion("更多示例", open=False, elem_id="cd-examples")
            gr.HTML(
                '<a href="https://github.com/ZeroTang05/cyber-doctor" target="_blank" '
                'rel="noopener noreferrer">项目源码<span aria-hidden="true">↗</span></a>',
                elem_id="cd-source",
            )

        with gr.Column(elem_id="cd-workspace", min_width=0):
            with gr.Row(elem_id="cd-toolbar"):
                gr.HTML(
                    '<div class="cd-toolbar-title">'
                    '<button id="cd-sidebar-toggle" type="button" aria-label="展开侧栏" '
                    f'aria-controls="cd-sidebar" aria-expanded="false">{SIDEBAR_ICON}</button>'
                    '<div><h2>健康问答</h2><span class="cd-compact-brand">赛博华佗</span></div></div>',
                    elem_id="cd-title",
                )
                clear = gr.ClearButton(value="清除记录", elem_id="cd-clear", min_width=0)

            with gr.Column(elem_id="cd-conversation", min_width=0):
                chatbot = gr.Chatbot(
                    height="100%",
                    elem_id="cd-chat",
                    show_label=False,
                    container=False,
                    buttons=["share", "copy_all"],
                    avatar_images=AVATAR,
                    latex_delimiters=[
                        {"left": "\\(", "right": "\\)", "display": True},
                        {"left": "\\[", "right": "\\]", "display": True},
                        {"left": "$$", "right": "$$", "display": True},
                        {"left": "$", "right": "$", "display": True},
                    ],
                )
                gr.HTML(
                    f'<section class="cd-welcome-inner"><span class="cd-welcome-mark">{ASSISTANT_MARK}</span>'
                    '<h2>今天想了解什么？</h2>'
                    '<p>从健康知识到医学资料解读，开启一次清晰、简单的交流。</p>'
                    '<div class="cd-welcome-prompts" role="group" aria-label="快捷提问">'
                    + "".join(
                        f'<button type="button" class="cd-prompt" data-icon="{icon}" data-prompt="{question}">'
                        f'<span>{question}</span></button>'
                        for _, question, icon in (*QUICK_PROMPTS[:3], QUICK_PROMPTS[4])
                    )
                    + '</div></section>',
                    elem_id="cd-welcome",
                )

            with gr.Column(elem_id="cd-composer", min_width=0, scale=0):
                chat_input = gr.MultimodalTextbox(
                    interactive=True,
                    file_count="multiple",
                    placeholder="输入消息或上传文件…",
                    show_label=False,
                    max_lines=6,
                    min_width=0,
                    elem_id="cd-message-input",
                )
                audio_input = gr.Audio(
                    sources=["microphone", "upload"],
                    label="录音输入",
                    visible=False,
                    type="filepath",
                    elem_id="cd-audio-input",
                )
                submit_audio_button = gr.Button(
                    "发送", visible=False, interactive=False, variant="primary", elem_id="cd-audio-send",
                )
    with sidebar_examples:
        gr.Examples(
            examples=examples, inputs=chat_input, label="", elem_id="cd-example-list",
            examples_per_page=15,
        )

    new_chat.add([chatbot, chat_input, audio_input])
    clear.add([chatbot, chat_input, audio_input])

    chat_input.submit(
        fn=submit_text_chat, inputs=[chatbot, chat_input], outputs=[chatbot, chat_input],
        api_name="grodio_view",
    )
    # 切换按钮点击事件
    toggle_voice_button.click(
        fn=toggle_voice_mode,
        inputs=None,
        outputs=[
            chat_input,
            audio_input,
            toggle_voice_button,
            toggle_text_button,
            submit_audio_button,
        ],
    )

    toggle_text_button.click(
        fn=toggle_text_mode,
        inputs=None,
        outputs=[
            chat_input,
            audio_input,
            toggle_voice_button,
            toggle_text_button,
            submit_audio_button,
        ],
    )

    audio_input.change(
        fn=lambda audio: gr.update(interactive=audio is not None),
        inputs=audio_input,
        outputs=submit_audio_button,
        queue=False,
        api_visibility="private",
    )
    submit_audio_button.click(
        fn=submit_voice_chat, inputs=[chatbot, audio_input], outputs=[chatbot],
        api_name="gradio_audio_view",
    )


# 启动应用
def start_gradio():
    demo.launch(server_name="127.0.0.1", server_port=10032, share=False)


if __name__ == "__main__":
    start_gradio()
