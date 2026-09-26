from openai import APITimeoutError
from pydantic_ai.exceptions import UnexpectedModelBehavior

EMPTY_STREAM_MESSAGE = (
    "模型接口未返回有效的流式事件。请检查 Base URL 是否包含服务商要求的 API 前缀"
    "（例如 /v1），以及所选模型是否支持流式输出。"
)


def model_error_message(error: Exception) -> str:
    if isinstance(error, APITimeoutError):
        # SDK versions use either httpx or httpx2 as the underlying transport.
        phase = type(error.__cause__).__name__
        if phase == "ConnectTimeout":
            return "连接主模型服务超时，请检查模型服务地址、网络或代理后重试。"
        if phase == "ReadTimeout":
            return "主模型服务响应超时，可能正在排队或暂时繁忙，请稍后重试。"
        return "主模型请求超时，请检查模型服务状态和网络后重试。"
    if isinstance(error, UnexpectedModelBehavior) and (
        "Streamed response ended without content or tool calls" in str(error)
    ):
        return EMPTY_STREAM_MESSAGE
    return f"AI run failed: {error}"
