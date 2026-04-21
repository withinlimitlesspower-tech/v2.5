"""
API Handler for BotManager V3.0 - DEEPSEEK V3.2 ONLY
Single Provider, Ultra-Fast, No Fallbacks
Zero Bloat, Maximum Performance
"""

import os
import json
import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class APIResponse:
    """Standardized API response"""
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    tokens: int = 0
    latency: float = 0.0
    provider: str = "deepseek"
    model: str = "deepseek-chat"  # V3.2


class APIHandler:
    """
    DeepSeek V3.2 ONLY API Handler
    - Model: deepseek-chat (V3.2)
    - Single provider: DeepSeek
    - No fallbacks
    - Ultra-fast timeouts
    - Connection pooling
    - Smart retry logic
    """
    
    # Timeout constants
    CONNECT_TIMEOUT = 8       # 8 seconds to connect
    READ_TIMEOUT_MIN = 30     # Minimum 30s for reading
    MAX_RETRIES = 3           # Maximum retry attempts
    RETRY_DELAY = 1.5         # Delay between retries
    
    # Connection pool settings
    POOL_CONNECTIONS = 20
    POOL_MAXSIZE = 30
    
    def __init__(self):
        """Initialize DeepSeek V3.2 API handler"""
        self.api_key = os.getenv('DEEPSEEK_API_KEY')
        if not self.api_key:
            raise ValueError("❌ DEEPSEEK_API_KEY not found in environment variables")
        
        # ⭐ DeepSeek V3.2 Configuration
        self.api_url = "https://api.deepseek.com/v1/chat/completions"
        self.model = "deepseek-chat"  # V3.2 Model
        
        # Alternative V3.2 model names if needed
        self.model_aliases = ["deepseek-chat", "deepseek-v3", "deepseek-chat-v3"]
        
        # Create optimized session
        self.session = self._create_session()
        
        # Statistics
        self.stats = {
            "total_requests": 0,
            "successful": 0,
            "failed": 0,
            "total_tokens": 0,
            "total_latency": 0.0
        }
        
        logger.info("✅ DeepSeek V3.2 API Handler initialized (NO FALLBACKS)")
        logger.info(f"   Model: {self.model} (V3.2)")
        logger.info(f"   Timeouts: Connect={self.CONNECT_TIMEOUT}s, Read=Dynamic")
        logger.info(f"   Max Tokens: 8192 (output)")
    
    def _create_session(self) -> requests.Session:
        """Create optimized session with connection pooling"""
        session = requests.Session()
        
        # Connection pool settings
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=self.POOL_CONNECTIONS,
            pool_maxsize=self.POOL_MAXSIZE,
            pool_block=False
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        # Keep-alive headers
        session.headers.update({
            'Connection': 'keep-alive',
            'Accept-Encoding': 'gzip, deflate',
            'Accept': 'application/json',
        })
        
        return session
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        top_p: float = 0.95
    ) -> Dict[str, Any]:
        """
        Direct DeepSeek V3.2 chat - NO FALLBACKS
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate (up to 8192)
            stream: Whether to stream response
            top_p: Nucleus sampling parameter
            
        Returns:
            Dict with success status and content/error
        """
        self.stats["total_requests"] += 1
        start_time = time.time()
        
        # Validate API key
        if not self.api_key:
            return {
                "success": False,
                "error": "DeepSeek V3.2 API key not configured",
                "provider": "deepseek",
                "model": self.model
            }
        
        # Cap max_tokens at 8192 (V3.2 limit)
        max_tokens = min(max_tokens, 8192)
        
        # Prepare request
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Connection": "keep-alive"
        }
        
        payload = {
            "model": self.model,  # deepseek-chat (V3.2)
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
            "top_p": top_p
        }
        
        # Calculate timeouts based on token count
        if max_tokens > 4000:
            read_timeout = 600  # 10 minutes for large generations
        elif max_tokens > 2000:
            read_timeout = 300  # 5 minutes for medium
        else:
            read_timeout = 120  # 2 minutes for small
            
        timeout_tuple = (self.CONNECT_TIMEOUT, read_timeout)
        
        # Retry logic
        last_error = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.debug(f"DeepSeek V3.2 request (attempt {attempt + 1}/{self.MAX_RETRIES}): {max_tokens} tokens")
                
                response = self.session.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=timeout_tuple
                )
                
                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    tokens = data.get("usage", {}).get("total_tokens", 0)
                    latency = time.time() - start_time
                    
                    # Update stats
                    self.stats["successful"] += 1
                    self.stats["total_tokens"] += tokens
                    self.stats["total_latency"] += latency
                    
                    logger.info(f"✅ DeepSeek V3.2 success: {tokens} tokens, {latency:.2f}s")
                    
                    return {
                        "success": True,
                        "content": content,
                        "tokens": tokens,
                        "latency": latency,
                        "provider": "deepseek",
                        "model": self.model,
                        "version": "3.2"
                    }
                    
                elif response.status_code == 429:
                    # Rate limit - wait and retry
                    wait_time = self.RETRY_DELAY * (attempt + 1)
                    logger.warning(f"Rate limited (attempt {attempt + 1}), waiting {wait_time}s")
                    time.sleep(wait_time)
                    
                elif response.status_code == 402:
                    # Payment required
                    self.stats["failed"] += 1
                    return {
                        "success": False,
                        "error": "DeepSeek V3.2 credit/quota exceeded",
                        "provider": "deepseek",
                        "model": self.model
                    }
                    
                else:
                    error_msg = f"API Error {response.status_code}"
                    try:
                        error_data = response.json()
                        error_msg = error_data.get('error', {}).get('message', error_msg)
                    except:
                        pass
                    
                    logger.error(f"DeepSeek V3.2 error: {error_msg}")
                    last_error = error_msg
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout (attempt {attempt + 1})")
                last_error = "Request timeout"
                
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Connection error (attempt {attempt + 1}): {e}")
                last_error = f"Connection error: {e}"
                
            except Exception as e:
                logger.error(f"Unexpected error (attempt {attempt + 1}): {e}")
                last_error = str(e)
            
            # Wait before retry
            if attempt < self.MAX_RETRIES - 1:
                time.sleep(self.RETRY_DELAY)
        
        # All retries failed
        self.stats["failed"] += 1
        logger.error(f"❌ DeepSeek V3.2 failed after {self.MAX_RETRIES} attempts: {last_error}")
        
        return {
            "success": False,
            "error": last_error or "Unknown error",
            "latency": time.time() - start_time,
            "provider": "deepseek",
            "model": self.model
        }
    
    def generate_code(
        self,
        filename: str,
        project_description: str,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        Generate code using DeepSeek V3.2
        
        Args:
            filename: Name of file to generate
            project_description: Description of the project
            max_tokens: Maximum tokens (up to 8192)
            
        Returns:
            Dict with success status and code/error
        """
        system_prompt = f"""You are an expert programmer. Generate complete, production-ready code for {filename}.
        
        Project description: {project_description}
        
        Important:
        - Provide ONLY the code without markdown formatting
        - Include all necessary imports and dependencies
        - Add helpful comments explaining key parts
        - Ensure the code is functional and follows best practices"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Generate the complete code for {filename}"}
        ]
        
        return self.chat(messages, temperature=0.3, max_tokens=max_tokens)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get API usage statistics"""
        avg_latency = 0
        if self.stats["successful"] > 0:
            avg_latency = self.stats["total_latency"] / self.stats["successful"]
        
        success_rate = 0
        if self.stats["total_requests"] > 0:
            success_rate = (self.stats["successful"] / self.stats["total_requests"]) * 100
        
        return {
            "total_requests": self.stats["total_requests"],
            "successful": self.stats["successful"],
            "failed": self.stats["failed"],
            "success_rate": f"{success_rate:.1f}%",
            "total_tokens": self.stats["total_tokens"],
            "avg_latency": f"{avg_latency:.2f}s",
            "provider": "deepseek",
            "model": self.model,
            "version": "3.2",
            "max_output_tokens": 8192,
            "fallbacks": "NONE"
        }
    
    def health_check(self) -> bool:
        """Test DeepSeek V3.2 connection"""
        test_messages = [{"role": "user", "content": "Hi"}]
        response = self.chat(test_messages, max_tokens=10)
        return response.get("success", False)
    
    def reset_stats(self):
        """Reset statistics"""
        self.stats = {
            "total_requests": 0,
            "successful": 0,
            "failed": 0,
            "total_tokens": 0,
            "total_latency": 0.0
        }
        logger.info("Statistics reset")


# Singleton instance
_api_handler = None

def get_api_handler() -> APIHandler:
    """Get or create singleton API handler"""
    global _api_handler
    if _api_handler is None:
        _api_handler = APIHandler()
    return _api_handler


# Example usage
if __name__ == "__main__":
    handler = APIHandler()
    
    print("=" * 50)
    print("DeepSeek V3.2 API Test")
    print(f"Model: {handler.model}")
    print(f"Max Output Tokens: 8192")
    print("=" * 50)
    
    # Test chat
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, what model are you?"}
    ]
    
    response = handler.chat(messages, max_tokens=50)
    
    if response["success"]:
        print(f"\n✅ Response: {response['content']}")
        print(f"📊 Tokens: {response['tokens']}")
        print(f"⏱️ Latency: {response['latency']:.2f}s")
        print(f"🤖 Model: {response['model']}")
    else:
        print(f"\n❌ Error: {response['error']}")
    
    print(f"\n📈 Stats: {json.dumps(handler.get_stats(), indent=2)}")
