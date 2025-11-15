"""LLM client utility for unified access to OpenAI and Anthropic APIs."""
import logging
from typing import Optional, List, Dict, Any
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from matrix.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Unified LLM client supporting OpenAI and Anthropic."""

    def __init__(self):
        """Initialize LLM clients based on configuration."""
        self.provider = settings.llm_provider.lower()

        # Initialize OpenAI client
        if settings.openai_api_key:
            self.openai_client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                timeout=settings.openai_timeout
            )
        else:
            self.openai_client = None

        # Initialize Anthropic client
        if settings.anthropic_api_key:
            self.anthropic_client = AsyncAnthropic(
                api_key=settings.anthropic_api_key,
                timeout=settings.anthropic_timeout
            )
        else:
            self.anthropic_client = None

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        json_mode: bool = False
    ) -> str:
        """
        Generate a chat completion using the configured LLM provider.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            system_prompt: Optional system prompt (overrides messages system if provided)
            temperature: Sampling temperature (uses config default if None)
            max_tokens: Maximum tokens to generate (uses config default if None)
            provider: Override default provider ('openai' or 'anthropic')
            model: Override default model
            json_mode: Enable JSON response mode (OpenAI only)

        Returns:
            Generated text response

        Raises:
            ValueError: If provider is not configured or invalid
            Exception: If API call fails
        """
        provider = provider or self.provider

        try:
            if provider == "openai":
                return await self._openai_completion(
                    messages, system_prompt, temperature, max_tokens, model, json_mode
                )
            elif provider == "anthropic":
                return await self._anthropic_completion(
                    messages, system_prompt, temperature, max_tokens, model
                )
            else:
                raise ValueError(f"Invalid LLM provider: {provider}")

        except Exception as e:
            logger.error(f"LLM completion failed: {str(e)}", exc_info=True)
            raise

    async def _openai_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        temperature: Optional[float],
        max_tokens: Optional[int],
        model: Optional[str],
        json_mode: bool
    ) -> str:
        """Generate completion using OpenAI API."""
        if not self.openai_client:
            raise ValueError("OpenAI client not configured. Set OPENAI_API_KEY in environment.")

        # Prepare messages
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        formatted_messages.extend(messages)

        # Prepare parameters
        params = {
            "model": model or settings.openai_model,
            "messages": formatted_messages,
            "temperature": temperature if temperature is not None else settings.openai_temperature,
            "max_tokens": max_tokens or settings.openai_max_tokens
        }

        if json_mode:
            params["response_format"] = {"type": "json_object"}

        logger.info(f"Calling OpenAI API with model {params['model']}")

        response = await self.openai_client.chat.completions.create(**params)
        content = response.choices[0].message.content

        logger.info(f"OpenAI API call successful. Tokens used: {response.usage.total_tokens}")

        return content

    async def _anthropic_completion(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        temperature: Optional[float],
        max_tokens: Optional[int],
        model: Optional[str]
    ) -> str:
        """Generate completion using Anthropic Claude API."""
        if not self.anthropic_client:
            raise ValueError("Anthropic client not configured. Set ANTHROPIC_API_KEY in environment.")

        # Extract system prompt from messages if not provided
        if not system_prompt and messages and messages[0].get("role") == "system":
            system_prompt = messages[0]["content"]
            messages = messages[1:]

        # Prepare parameters
        params = {
            "model": model or settings.anthropic_model,
            "messages": messages,
            "temperature": temperature if temperature is not None else settings.anthropic_temperature,
            "max_tokens": max_tokens or settings.anthropic_max_tokens
        }

        if system_prompt:
            params["system"] = system_prompt

        logger.info(f"Calling Anthropic API with model {params['model']}")

        response = await self.anthropic_client.messages.create(**params)
        content = response.content[0].text

        logger.info(f"Anthropic API call successful. Tokens used: {response.usage.input_tokens + response.usage.output_tokens}")

        return content

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        provider: Optional[str] = None
    ) -> str:
        """
        Generate JSON output from a prompt.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            provider: Override default provider

        Returns:
            JSON string response
        """
        messages = [{"role": "user", "content": prompt}]

        # For OpenAI, use JSON mode; for Anthropic, rely on system prompt
        if (provider or self.provider) == "openai":
            return await self.chat_completion(
                messages=messages,
                system_prompt=system_prompt,
                json_mode=True,
                provider=provider
            )
        else:
            # For Anthropic, add JSON instruction to system prompt
            json_system = (system_prompt or "") + "\n\nYou must respond with valid JSON only. Do not include any text outside the JSON structure."
            return await self.chat_completion(
                messages=messages,
                system_prompt=json_system,
                provider=provider
            )


# Global LLM client instance
llm_client = LLMClient()
