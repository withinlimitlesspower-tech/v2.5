"""
API Handler for BotManager V2.5 - Enhanced AI Project Generator with Multi-Bot Support

This module provides a centralized API handler for interacting with various AI services
including OpenAI, Anthropic, and other LLM providers. It handles API key management,
rate limiting, error handling, and response parsing.
"""

import os
import json
import time
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError
import openai
from openai import OpenAI, AsyncOpenAI
import anthropic
import backoff

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class APIProvider(Enum):
    """Enumeration of supported API providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    COHERE = "cohere"
    HUGGINGFACE = "huggingface"
    REPLICATE = "replicate"
    TOGETHER = "together"


@dataclass
class APIResponse:
    """Standardized API response structure"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    latency: Optional[float] = None


@dataclass
class APIConfig:
    """Configuration for API connections"""
    provider: APIProvider
    api_key: str
    base_url: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3
    rate_limit_delay: float = 1.0


class APIHandler:
    """
    Main API handler class for managing connections to various AI services.
    
    Features:
    - Multi-provider support (OpenAI, Anthropic, Google, etc.)
    - Automatic retry with exponential backoff
    - Rate limiting and quota management
    - Response standardization
    - Error handling and logging
    - Token usage tracking
    """
    
    def __init__(self, configs: Optional[Dict[APIProvider, APIConfig]] = None):
        """
        Initialize the API handler with configurations.
        
        Args:
            configs: Dictionary mapping APIProvider to APIConfig objects
        """
        self.configs = configs or {}
        self.clients = {}
        self.rate_limiters = {}
        self._initialize_from_secrets()
        self._setup_clients()
        
        # Statistics tracking
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_tokens": 0,
            "provider_stats": {}
        }
    
    def _initialize_from_secrets(self):
        """Initialize API configurations from environment variables/Replit Secrets"""
        # OpenAI
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            self.configs[APIProvider.OPENAI] = APIConfig(
                provider=APIProvider.OPENAI,
                api_key=openai_key,
                base_url=os.getenv("OPENAI_BASE_URL"),
                timeout=int(os.getenv("OPENAI_TIMEOUT", "30")),
                max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "3"))
            )
        
        # Anthropic
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            self.configs[APIProvider.ANTHROPIC] = APIConfig(
                provider=APIProvider.ANTHROPIC,
                api_key=anthropic_key,
                timeout=int(os.getenv("ANTHROPIC_TIMEOUT", "30")),
                max_retries=int(os.getenv("ANTHROPIC_MAX_RETRIES", "3"))
            )
        
        # Google
        google_key = os.getenv("GOOGLE_API_KEY")
        if google_key:
            self.configs[APIProvider.GOOGLE] = APIConfig(
                provider=APIProvider.GOOGLE,
                api_key=google_key,
                base_url=os.getenv("GOOGLE_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"),
                timeout=int(os.getenv("GOOGLE_TIMEOUT", "30")),
                max_retries=int(os.getenv("GOOGLE_MAX_RETRIES", "3"))
            )
        
        # Cohere
        cohere_key = os.getenv("COHERE_API_KEY")
        if cohere_key:
            self.configs[APIProvider.COHERE] = APIConfig(
                provider=APIProvider.COHERE,
                api_key=cohere_key,
                base_url=os.getenv("COHERE_BASE_URL", "https://api.cohere.ai/v1"),
                timeout=int(os.getenv("COHERE_TIMEOUT", "30")),
                max_retries=int(os.getenv("COHERE_MAX_RETRIES", "3"))
            )
        
        # HuggingFace
        hf_key = os.getenv("HUGGINGFACE_API_KEY")
        if hf_key:
            self.configs[APIProvider.HUGGINGFACE] = APIConfig(
                provider=APIProvider.HUGGINGFACE,
                api_key=hf_key,
                base_url=os.getenv("HUGGINGFACE_BASE_URL", "https://api-inference.huggingface.co"),
                timeout=int(os.getenv("HUGGINGFACE_TIMEOUT", "60")),
                max_retries=int(os.getenv("HUGGINGFACE_MAX_RETRIES", "3"))
            )
        
        # Replicate
        replicate_key = os.getenv("REPLICATE_API_KEY")
        if replicate_key:
            self.configs[APIProvider.REPLICATE] = APIConfig(
                provider=APIProvider.REPLICATE,
                api_key=replicate_key,
                timeout=int(os.getenv("REPLICATE_TIMEOUT", "60")),
                max_retries=int(os.getenv("REPLICATE_MAX_RETRIES", "3"))
            )
        
        # Together AI
        together_key = os.getenv("TOGETHER_API_KEY")
        if together_key:
            self.configs[APIProvider.TOGETHER] = APIConfig(
                provider=APIProvider.TOGETHER,
                api_key=together_key,
                base_url=os.getenv("TOGETHER_BASE_URL", "https://api.together.xyz/v1"),
                timeout=int(os.getenv("TOGETHER_TIMEOUT", "30")),
                max_retries=int(os.getenv("TOGETHER_MAX_RETRIES", "3"))
            )
    
    def _setup_clients(self):
        """Initialize client objects for each configured provider"""
        for provider, config in self.configs.items():
            try:
                if provider == APIProvider.OPENAI:
                    self.clients[provider] = OpenAI(
                        api_key=config.api_key,
                        base_url=config.base_url,
                        timeout=config.timeout
                    )
                elif provider == APIProvider.ANTHROPIC:
                    self.clients[provider] = anthropic.Anthropic(
                        api_key=config.api_key,
                        timeout=config.timeout
                    )
                # Other providers would be initialized here as needed
                
                logger.info(f"Initialized client for {provider.value}")
                
            except Exception as e:
                logger.error(f"Failed to initialize client for {provider.value}: {e}")
    
    def _rate_limit(self, provider: APIProvider):
        """Implement rate limiting for API calls"""
        if provider not in self.rate_limiters:
            self.rate_limiters[provider] = {"last_call": 0}
        
        last_call = self.rate_limiters[provider]["last_call"]
        current_time = time.time()
        time_since_last_call = current_time - last_call
        
        config = self.configs.get(provider)
        if config and time_since_last_call < config.rate_limit_delay:
            sleep_time = config.rate_limit_delay - time_since_last_call
            time.sleep(sleep_time)
        
        self.rate_limiters[provider]["last_call"] = time.time()
    
    @backoff.on_exception(
        backoff.expo,
        (RequestException, Timeout, ConnectionError),
        max_tries=3
    )
    def _make_request_with_retry(self, func: Callable, *args, **kwargs) -> APIResponse:
        """Make API request with exponential backoff retry logic"""
        start_time = time.time()
        
        try:
            response = func(*args, **kwargs)
            latency = time.time() - start_time
            
            return APIResponse(
                success=True,
                data=response,
                latency=latency
            )
            
        except Exception as e:
            latency = time.time() - start_time
            logger.error(f"API request failed: {e}")
            
            return APIResponse(
                success=False,
                error=str(e),
                latency=latency
            )
    
    def call_openai(
        self,
        model: str = "gpt-4",
        messages: List[Dict[str, str]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> APIResponse:
        """
        Call OpenAI API with the given parameters.
        
        Args:
            model: The model to use (e.g., "gpt-4", "gpt-3.5-turbo")
            messages: List of message dictionaries with "role" and "content"
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters for OpenAI API
            
        Returns:
            APIResponse object with success status and data/error
        """
        self._rate_limit(APIProvider.OPENAI)
        
        if APIProvider.OPENAI not in self.clients:
            return APIResponse(
                success=False,
                error="OpenAI client not configured",
                provider="openai"
            )
        
        try:
            client = self.clients[APIProvider.OPENAI]
            
            # Prepare request parameters
            params = {
                "model": model,
                "messages": messages or [],
                "temperature": temperature,
                **kwargs
            }
            
            if max_tokens:
                params["max_tokens"] = max_tokens
            
            # Make the API call
            response = client.chat.completions.create(**params)
            
            # Extract content and token usage
            content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if response.usage else None
            
            # Update statistics
            self._update_stats(APIProvider.OPENAI, True, tokens_used)
            
            return APIResponse(
                success=True,
                data=content,
                provider="openai",
                model=model,
                tokens_used=tokens_used
            )
            
        except Exception as e:
            self._update_stats(APIProvider.OPENAI, False)
            logger.error(f"OpenAI API call failed: {e}")
            
            return APIResponse(
                success=False,
                error=str(e),
                provider="openai",
                model=model
            )
    
    def call_anthropic(
        self,
        model: str = "claude-3-opus-20240229",
        messages: List[Dict[str, str]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> APIResponse:
        """
        Call Anthropic Claude API with the given parameters.
        
        Args:
            model: The model to use (e.g., "claude-3-opus-20240229")
            messages: List of message dictionaries with "role" and "content"
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters for Anthropic API
            
        Returns:
            APIResponse object with success status and data/error
        """
        self._rate_limit(APIProvider.ANTHROPIC)
        
        if APIProvider.ANTHROPIC not in self.clients:
            return APIResponse(
                success=False,
                error="Anthropic client not configured",
                provider="anthropic"
            )
        
        try:
            client = self.clients[APIProvider.ANTHROPIC]
            
            # Prepare messages for Anthropic format
            system_message = None
            anthropic_messages = []
            
            for msg in messages or []:
                if msg["role"] == "system":
                    system_message = msg["content"]
                else:
                    anthropic_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            
            # Make the API call
            response = client.messages.create(
                model=model,
                messages=anthropic_messages,
                system=system_message,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            # Extract content
            content = response.content[0].text
            tokens_used = response.usage.input_tokens + response.usage.output_tokens
            
            # Update statistics
            self._update_stats(APIProvider.ANTHROPIC, True, tokens_used)
            
            return APIResponse(
                success=True,
                data=content,
                provider="anthropic",
                model=model,
                tokens_used=tokens_used
            )
            
        except Exception as e:
            self._update_stats(APIProvider.ANTHROPIC, False)
            logger.error(f"Anthropic API call failed: {e}")
            
            return APIResponse(
                success=False,
                error=str(e),
                provider="anthropic",
                model=model
            )
    
    def call_google(
        self,
        model: str = "gemini-pro",
        prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> APIResponse:
        """
        Call Google Gemini API with the given parameters.
        
        Args:
            model: The model to use (e.g., "gemini-pro")
            prompt: The input prompt
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters for Google API
            
        Returns:
            APIResponse object with success status and data/error
        """
        self._rate_limit(APIProvider.GOOGLE)
        
        config = self.configs.get(APIProvider.GOOGLE)
        if not config:
            return APIResponse(
                success=False,
                error="Google API not configured",
                provider="google"
            )
        
        try:
            # Prepare request
            url = f"{config.base_url}/models/{model}:generateContent"
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": config.api_key
            }
            
            payload = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                    **kwargs.get("generation_config", {})
                }
            }
            
            # Make the API call
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=config.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract content
            if "candidates" in data and len(data["candidates"]) > 0:
                content = data["candidates"][0]["content"]["parts"][0]["text"]
            else:
                content = ""
            
            # Update statistics
            self._update_stats(APIProvider.GOOGLE, True)
            
            return APIResponse(
                success=True,
                data=content,
                provider="google",
                model=model
            )
            
        except Exception as e:
            self._update_stats(APIProvider.GOOGLE, False)
            logger.error(f"Google API call failed: {e}")
            
            return APIResponse(
                success=False,
                error=str(e),
                provider="google",
                model=model
            )
    
    def call_cohere(
        self,
        model: str = "command",
        prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> APIResponse:
        """
        Call Cohere API with the given parameters.
        
        Args:
            model: The model to use (e.g., "command", "command-r")
            prompt: The input prompt
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters for Cohere API
            
        Returns:
            APIResponse object with success status and data/error
        """
        self._rate_limit(APIProvider.COHERE)
        
        config = self.configs.get(APIProvider.COHERE)
        if not config:
            return APIResponse(
                success=False,
                error="Cohere API not configured",
                provider="cohere"
            )
        
        try:
            # Prepare request
            url = f"{config.base_url}/generate"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.api_key}"
            }
            
            payload = {
                "model": model,
                "prompt": prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
                **kwargs
            }
            
            # Make the API call
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=config.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract content
            if "generations" in data and len(data["generations"]) > 0:
                content = data["generations"][0]["text"]
            else:
                content = ""
            
            # Update statistics
            self._update_stats(APIProvider.COHERE, True)
            
            return APIResponse(
                success=True,
                data=content,
                provider="cohere",
                model=model
            )
            
        except Exception as e:
            self._update_stats(APIProvider.COHERE, False)
            logger.error(f"Cohere API call failed: {e}")
            
            return APIResponse(
                success=False,
                error=str(e),
                provider="cohere",
                model=model
            )
    
    def call_huggingface(
        self,
        model: str = "gpt2",
        inputs: str = "",
        parameters: Optional[Dict] = None,
        **kwargs
    ) -> APIResponse:
        """
        Call HuggingFace Inference API with the given parameters.
        
        Args:
            model: The model to use (e.g., "gpt2", "mistralai/Mistral-7B-Instruct-v0.1")
            inputs: The input text
            parameters: Generation parameters
            **kwargs: Additional parameters
            
        Returns:
            APIResponse object with success status and data/error
        """
        self._rate_limit(APIProvider.HUGGINGFACE)
        
        config = self.configs.get(APIProvider.HUGGINGFACE)
        if not config:
            return APIResponse(
                success=False,
                error="HuggingFace API not configured",
                provider="huggingface"
            )
        
        try:
            # Prepare request
            url = f"{config.base_url}/models/{model}"
            headers = {
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "inputs": inputs,
                "parameters": parameters or {},
                **kwargs
            }
            
            # Make the API call
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=config.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Update statistics
            self._update_stats(APIProvider.HUGGINGFACE, True)
            
            return APIResponse(
                success=True,
                data=data,
                provider="huggingface",
                model=model
            )
            
        except Exception as e:
            self._update_stats(APIProvider.HUGGINGFACE, False)
            logger.error(f"HuggingFace API call failed: {e}")
            
            return APIResponse(
                success=False,
                error=str(e),
                provider="huggingface",
                model=model
            )
    
    def call_together(
        self,
        model: str = "mistralai/Mixtral-8x7B-Instruct-v0.1",
        messages: List[Dict[str, str]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs
    ) -> APIResponse:
        """
        Call Together AI API with the given parameters.
        
        Args:
            model: The model to use
            messages: List of message dictionaries
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Returns:
            APIResponse object with success status and data/error
        """
        self._rate_limit(APIProvider.TOGETHER)
        
        config = self.configs.get(APIProvider.TOGETHER)
        if not config:
            return APIResponse(
                success=False,
                error="Together AI API not configured",
                provider="together"
            )
        
        try:
            # Prepare request
            url = f"{config.base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model,
                "messages": messages or [],
                "temperature": temperature,
                "max_tokens": max_tokens,
                **kwargs
            }
            
            # Make the API call
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=config.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract content
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"]
                tokens_used = data.get("usage", {}).get("total_tokens")
            else:
                content = ""
                tokens_used = None
            
            # Update statistics
            self._update_stats(APIProvider.TOGETHER, True, tokens_used)
            
            return APIResponse(
                success=True,
                data=content,
                provider="together",
                model=model,
                tokens_used=tokens_used
            )
            
        except Exception as e:
            self._update_stats(APIProvider.TOGETHER, False)
            logger.error(f"Together AI API call failed: {e}")
            
            return APIResponse(
                success=False,
                error=str(e),
                provider="together",
                model=model
            )
    
    def call_api(
        self,
        provider: Union[str, APIProvider],
        **kwargs
    ) -> APIResponse:
        """
        Generic API call method that routes to the appropriate provider.
        
        Args:
            provider: The API provider (string or APIProvider enum)
            **kwargs: Parameters specific to the provider
            
        Returns:
            APIResponse object with success status and data/error
        """
        # Convert string to APIProvider enum if needed
        if isinstance(provider, str):
            try:
                provider = APIProvider(provider.lower())
            except ValueError:
                return APIResponse(
                    success=False,
                    error=f"Unknown provider: {provider}"
                )
        
        # Route to the appropriate method
        if provider == APIProvider.OPENAI:
            return self.call_openai(**kwargs)
        elif provider == APIProvider.ANTHROPIC:
            return self.call_anthropic(**kwargs)
        elif provider == APIProvider.GOOGLE:
            return self.call_google(**kwargs)
        elif provider == APIProvider.COHERE:
            return self.call_cohere(**kwargs)
        elif provider == APIProvider.HUGGINGFACE:
            return self.call_huggingface(**kwargs)
        elif provider == APIProvider.TOGETHER:
            return self.call_together(**kwargs)
        else:
            return APIResponse(
                success=False,
                error=f"Provider {provider.value} not implemented"
            )
    
    def _update_stats(self, provider: APIProvider, success: bool, tokens_used: Optional[int] = None):
        """Update statistics for API calls"""
        self.stats["total_requests"] += 1
        
        if success:
            self.stats["successful_requests"] += 1
        else:
            self.stats["failed_requests"] += 1
        
        if tokens_used:
            self.stats["total_tokens"] += tokens_used
        
        # Update provider-specific stats
        provider_name = provider.value
        if provider_name not in self.stats["provider_stats"]:
            self.stats["provider_stats"][provider_name] = {
                "requests": 0,
                "successful": 0,
                "failed": 0,
                "tokens": 0
            }
        
        provider_stats = self.stats["provider_stats"][provider_name]
        provider_stats["requests"] += 1
        
        if success:
            provider_stats["successful"] += 1
        else:
            provider_stats["failed"] += 1
        
        if tokens_used:
            provider_stats["tokens"] += tokens_used
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current API usage statistics"""
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset all statistics"""
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_tokens": 0,
            "provider_stats": {}
        }
    
    def get_available_providers(self) -> List[str]:
        """Get list of configured API providers"""
        return [provider.value for provider in self.configs.keys()]
    
    def is_provider_available(self, provider: Union[str, APIProvider]) -> bool:
        """Check if a provider is configured and available"""
        if isinstance(provider, str):
            try:
                provider = APIProvider(provider.lower())
            except ValueError:
                return False
        
        return provider in self.configs and provider in self.clients
    
    def add_config(self, config: APIConfig):
        """Add or update an API configuration"""
        self.configs[config.provider] = config
        self._setup_clients()  # Reinitialize clients
    
    def remove_config(self, provider: APIProvider):
        """Remove an API configuration"""
        if provider in self.configs:
            del self.configs[provider]
        if provider in self.clients:
            del self.clients[provider]
    
    def get_config(self, provider: APIProvider) -> Optional[APIConfig]:
        """Get configuration for a specific provider"""
        return self.configs.get(provider)
    
    def health_check(self) -> Dict[str, bool]:
        """Check health/availability of all configured providers"""
        health_status = {}
        
        for provider in self.configs.keys():
            try:
                # Simple test call or client check
                if provider == APIProvider.OPENAI:
                    # Test with a minimal request
                    test_response = self.call_openai(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": "Hello"}],
                        max_tokens=5
                    )
                    health_status[provider.value] = test_response.success
                elif provider == APIProvider.ANTHROPIC:
                    # Just check if client is initialized
                    health_status[provider.value] = provider in self.clients
                else:
                    # For other providers, just check if configured
                    health_status[provider.value] = True
                    
            except Exception as e:
                logger.error(f"Health check failed for {provider.value}: {e}")
                health_status[provider.value] = False
        
        return health_status


# Singleton instance for easy access
_api_handler_instance = None

def get_api_handler(configs: Optional[Dict[APIProvider, APIConfig]] = None) -> APIHandler:
    """
    Get or create the singleton API handler instance.
    
    Args:
        configs: Optional configurations to initialize with
        
    Returns:
        APIHandler instance
    """
    global _api_handler_instance
    
    if _api_handler_instance is None:
        _api_handler_instance = APIHandler(configs)
    
    return _api_handler_instance


# Example usage
if __name__ == "__main__":
    # Example: Initialize and use the API handler
    handler = get_api_handler()
    
    # Check available providers
    print("Available providers:", handler.get_available_providers())
    
    # Example OpenAI call
    if handler.is_provider_available("openai"):
        response = handler.call_openai(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello, how are you?"}
            ],
            temperature=0.7,
            max_tokens=50
        )
        
        if response.success:
            print("OpenAI Response:", response.data)
        else:
            print("OpenAI Error:", response.error)
    
    # Get statistics
    stats = handler.get_stats()
    print("Statistics:", json.dumps(stats, indent=2))