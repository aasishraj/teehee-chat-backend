import httpx
import json
from typing import AsyncGenerator, Dict, Any, Optional
from abc import ABC, abstractmethod
from app.core.config import settings


class BaseProvider(ABC):
    """Base class for LLM providers."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient()
    
    @abstractmethod
    async def stream_chat(
        self, 
        messages: list[Dict[str, str]], 
        model: str, 
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion tokens."""
        pass
    
    @abstractmethod
    def get_models(self) -> list[str]:
        """Get available models for this provider."""
        pass
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class OpenAIProvider(BaseProvider):
    """OpenAI API provider."""
    
    BASE_URL = "https://api.openai.com/v1"
    
    def get_models(self) -> list[str]:
        return [
            "gpt-4-turbo-preview",
            "gpt-4",
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k"
        ]
    
    async def stream_chat(
        self, 
        messages: list[Dict[str, str]], 
        model: str = "gpt-3.5-turbo",
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion from OpenAI."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "messages": messages,
            "stream": True,
            "max_tokens": kwargs.get("max_tokens", settings.max_tokens),
            "temperature": kwargs.get("temperature", 0.7)
        }
        
        async with self.client.stream(
            "POST",
            f"{self.BASE_URL}/chat/completions",
            headers=headers,
            json=data,
            timeout=settings.stream_timeout
        ) as response:
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    
                    try:
                        data = json.loads(data_str)
                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                    except json.JSONDecodeError:
                        continue


class AnthropicProvider(BaseProvider):
    """Anthropic Claude API provider."""
    
    BASE_URL = "https://api.anthropic.com/v1"
    
    def get_models(self) -> list[str]:
        return [
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            "claude-2.1",
            "claude-2.0"
        ]
    
    async def stream_chat(
        self, 
        messages: list[Dict[str, str]], 
        model: str = "claude-3-sonnet-20240229",
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion from Anthropic."""
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        # Convert messages to Anthropic format
        system_message = ""
        formatted_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                formatted_messages.append(msg)
        
        data = {
            "model": model,
            "messages": formatted_messages,
            "max_tokens": kwargs.get("max_tokens", settings.max_tokens),
            "stream": True,
            "temperature": kwargs.get("temperature", 0.7)
        }
        
        if system_message:
            data["system"] = system_message
        
        async with self.client.stream(
            "POST",
            f"{self.BASE_URL}/messages",
            headers=headers,
            json=data,
            timeout=settings.stream_timeout
        ) as response:
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    
                    try:
                        data = json.loads(data_str)
                        if data.get("type") == "content_block_delta":
                            delta = data.get("delta", {})
                            if "text" in delta:
                                yield delta["text"]
                    except json.JSONDecodeError:
                        continue


class MistralProvider(BaseProvider):
    """Mistral AI API provider."""
    
    BASE_URL = "https://api.mistral.ai/v1"
    
    def get_models(self) -> list[str]:
        return [
            "mistral-large-latest",
            "mistral-medium-latest",
            "mistral-small-latest",
            "open-mixtral-8x7b",
            "open-mistral-7b"
        ]
    
    async def stream_chat(
        self, 
        messages: list[Dict[str, str]], 
        model: str = "mistral-medium-latest",
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion from Mistral."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "messages": messages,
            "stream": True,
            "max_tokens": kwargs.get("max_tokens", settings.max_tokens),
            "temperature": kwargs.get("temperature", 0.7)
        }
        
        async with self.client.stream(
            "POST",
            f"{self.BASE_URL}/chat/completions",
            headers=headers,
            json=data,
            timeout=settings.stream_timeout
        ) as response:
            response.raise_for_status()
            
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    
                    try:
                        data = json.loads(data_str)
                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                    except json.JSONDecodeError:
                        continue


def get_provider(provider_name: str, api_key: str) -> BaseProvider:
    """Factory function to get provider instance."""
    providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "mistral": MistralProvider
    }
    
    if provider_name not in providers:
        raise ValueError(f"Unsupported provider: {provider_name}")
    
    return providers[provider_name](api_key)


def get_all_providers_info() -> list[Dict[str, Any]]:
    """Get information about all supported providers."""
    return [
        {
            "name": "openai",
            "models": OpenAIProvider("").get_models(),
            "description": "OpenAI GPT models"
        },
        {
            "name": "anthropic", 
            "models": AnthropicProvider("").get_models(),
            "description": "Anthropic Claude models"
        },
        {
            "name": "mistral",
            "models": MistralProvider("").get_models(), 
            "description": "Mistral AI models"
        }
    ] 