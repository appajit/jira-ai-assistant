from __future__ import annotations
import os

def get_llm():
    """Create a chat model based on environment variables.

    - GitHub Models: GITHUB_TOKEN (optional GITHUB_MODEL) - FREE
    - OpenAI: OPENAI_API_KEY (optional OPENAI_MODEL)
    - Anthropic: ANTHROPIC_API_KEY (optional ANTHROPIC_MODEL)
    """
    # GitHub Models (free) - uses OpenAI-compatible API
    if os.getenv("GITHUB_TOKEN") and not os.getenv("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=os.getenv("GITHUB_MODEL", "gpt-4o-mini"),
            temperature=0,
            api_key=os.getenv("GITHUB_TOKEN"),
            base_url="https://models.inference.ai.azure.com",
        )
    
    if os.getenv("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"), temperature=0)
    if os.getenv("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"), temperature=0)

    raise RuntimeError("No LLM configured. Set GITHUB_TOKEN (free), OPENAI_API_KEY, or ANTHROPIC_API_KEY.")
