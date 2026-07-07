"""
AI Service layer - the heart of the LangChain orchestration.

Responsibilities:
- Instantiate the correct chat model (Claude via langchain-anthropic, or
  ChatGPT via langchain-openai) based on the user's selected provider.
- Build a RAG-aware conversation chain: condense follow-up question ->
  retrieve relevant document chunks -> generate grounded answer.
- Manage per-conversation memory (chat history) so context is preserved
  across turns regardless of which provider is currently selected.
- Expose provider-agnostic helper functions (title generation, suggested
  follow-up questions) reused throughout the app.

Every chain built here runs through LangChain, so every invocation is
automatically traced in LangSmith when LANGCHAIN_TRACING_V2=true.
"""
import time
from typing import List, Tuple

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from config import config
from services import prompts
from services.rag_service import retrieve_context
from utils.logger import get_logger

logger = get_logger(__name__)

SUPPORTED_PROVIDERS = {"claude", "openai"}


class AIProviderError(Exception):
    """Raised when an AI provider call fails (bad key, rate limit, network, etc.)."""


def get_chat_model(provider: str, streaming: bool = False):
    """
    Factory that returns a configured LangChain chat model instance for the
    requested provider. Adding a new provider later only requires adding a
    branch here plus one new prompt-compatible model class.
    """
    provider = provider.lower()

    if provider == "claude":
        if not config.ANTHROPIC_API_KEY:
            raise AIProviderError("Anthropic API key is not configured.")
        return ChatAnthropic(
            model=config.ANTHROPIC_MODEL,
            anthropic_api_key=config.ANTHROPIC_API_KEY,
            temperature=0.3,
            max_tokens=1500,
            streaming=streaming,
        )

    if provider == "openai":
        if not config.OPENAI_API_KEY:
            raise AIProviderError("OpenAI API key is not configured.")
        return ChatOpenAI(
            model=config.OPENAI_MODEL,
            api_key=config.OPENAI_API_KEY,
            temperature=0.3,
            max_tokens=1500,
            streaming=streaming,
        )

    raise AIProviderError(f"Unsupported AI provider: {provider}")


def _to_lc_history(history: List[dict]) -> List:
    """Convert stored {role, content} dicts into LangChain message objects."""
    lc_messages = []
    for turn in history:
        if turn["role"] == "user":
            lc_messages.append(HumanMessage(content=turn["content"]))
        else:
            lc_messages.append(AIMessage(content=turn["content"]))
    return lc_messages


def condense_question(provider: str, question: str, history: List[dict]) -> str:
    """Rewrite a follow-up question into a standalone question using chat history."""
    if not history:
        return question
    try:
        model = get_chat_model(provider)
        chain = prompts.CONDENSE_QUESTION_PROMPT | model | StrOutputParser()
        return chain.invoke({
            "chat_history": _to_lc_history(history[-6:]),
            "question": question,
        }).strip()
    except Exception as exc:
        logger.warning("Question condensation failed, using original question: %s", exc)
        return question


def generate_response(
    provider: str,
    question: str,
    history: List[dict],
    user_role: str = "guest",
    use_rag: bool = True,
) -> dict:
    """
    Main entry point: generate an AI response for a user turn.

    Returns a dict: {
        "answer": str,
        "provider": str,
        "sources": list[dict],
        "latency_ms": int,
    }
    Raises AIProviderError on failure (caller should handle gracefully).
    """
    provider = provider.lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise AIProviderError(f"Unknown AI provider '{provider}'.")

    start = time.time()

    # Step 1: resolve follow-up references into a standalone query for retrieval
    standalone_question = condense_question(provider, question, history)

    # Step 2: retrieve relevant document chunks (RAG)
    context, sources = ("", [])
    if use_rag:
        context, sources = retrieve_context(standalone_question)

    # Step 3: build the generation chain with the right prompt (with or without context)
    try:
        model = get_chat_model(provider)
        chat_prompt = prompts.CHAT_PROMPT if context else prompts.NO_CONTEXT_CHAT_PROMPT
        chain = chat_prompt | model | StrOutputParser()

        invoke_args = {
            "college_name": config.COLLEGE_NAME,
            "user_role": user_role,
            "chat_history": _to_lc_history(history[-10:]),
            "question": question,
        }
        if context:
            invoke_args["context"] = context

        answer = chain.invoke(invoke_args)
    except Exception as exc:
        logger.error("AI generation failed for provider '%s': %s", provider, exc)
        raise AIProviderError(str(exc)) from exc

    latency_ms = int((time.time() - start) * 1000)

    return {
        "answer": answer.strip(),
        "provider": provider,
        "sources": sources,
        "latency_ms": latency_ms,
    }


def generate_title(provider: str, first_message: str) -> str:
    """Generate a short conversation title from the opening user message."""
    try:
        model = get_chat_model(provider)
        chain = prompts.TITLE_GENERATION_PROMPT | model | StrOutputParser()
        title = chain.invoke({"message": first_message}).strip().strip('"')
        return title[:80] if title else "New Conversation"
    except Exception as exc:
        logger.warning("Title generation failed: %s", exc)
        return first_message[:40] + ("..." if len(first_message) > 40 else "")


def generate_suggested_questions(provider: str, answer: str, user_role: str) -> List[str]:
    """Generate 3 suggested follow-up questions based on the last AI answer."""
    try:
        model = get_chat_model(provider)
        chain = prompts.SUGGESTED_QUESTIONS_PROMPT | model | StrOutputParser()
        raw = chain.invoke({"answer": answer, "user_role": user_role})
        lines = [ln.strip(" .") for ln in raw.split("\n") if ln.strip()]
        cleaned = []
        for ln in lines:
            # strip leading numbering like "1." or "1)"
            import re
            ln = re.sub(r"^\d+[\.\)]\s*", "", ln)
            if ln:
                cleaned.append(ln)
        return cleaned[:3]
    except Exception as exc:
        logger.warning("Suggested question generation failed: %s", exc)
        return []
