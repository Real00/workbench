from pydantic_ai.exceptions import UnexpectedModelBehavior

EMPTY_STREAM_MESSAGE = (
    "模型接口未返回有效的流式事件。请检查 Base URL 是否包含服务商要求的 API 前缀"
    "（例如 /v1），以及所选模型是否支持流式输出。"
)


def model_error_message(error: Exception) -> str:
    if isinstance(error, UnexpectedModelBehavior) and (
        "Streamed response ended without content or tool calls" in str(error)
    ):
        return EMPTY_STREAM_MESSAGE
    return f"AI run failed: {error}"
