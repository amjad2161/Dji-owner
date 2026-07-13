"""Ollama Client - Local LLM management"""

import requests
import json
import asyncio
from typing import List, Dict, Optional, Any

import logging

logger = logging.getLogger(__name__)


class LoggerMixin:
    """Simple logging mixin."""
    
    @property
    def log(self):
        return logger


class ModelConfig:
    """Model configuration for Ollama."""
    
    def __init__(self, name: str = "llama3", temperature: float = 0.7, 
                 max_tokens: int = 512, context_window: int = 4096):
        self.name = name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.context_window = context_window


class OllamaClient(LoggerMixin):
    """
    Ollama API client for local LLM inference.
    
    Features:
    - Chat completions
    - Text generation
    - Vision support (image analysis)
    - Streaming responses
    """
    
    def __init__(self, base_url: str = "http://localhost:11434", 
                 default_model: str = "llama3"):
        self.base_url = base_url.rstrip('/')
        self.default_model = default_model
        self.session = requests.Session()
        self._connected = False
    
    async def initialize(self):
        """Initialize connection to Ollama server."""
        try:
            response = await self._async_get("/api/tags")
            if response:
                self._connected = True
                logger.info(f"Ollama connected: {self.base_url}")
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            self._connected = False
    
    def is_available(self) -> bool:
        """Check if Ollama server is available."""
        return self._connected
    
    async def generate(self, prompt: str, model: Optional[str] = None, 
                       temperature: float = 0.7, stream: bool = False) -> str:
        """Generate text from prompt."""
        model = model or self.default_model
        
        payload = {
            "model": model,
            "prompt": prompt,
            "temperature": temperature,
            "stream": stream
        }
        
        try:
            response = await self._async_post("/api/generate", payload)
            if response and 'response' in response:
                return response['response']
        except Exception as e:
            logger.error(f"Generation error: {e}")
        
        return ""
    
    async def chat(self, messages: List[Dict], model: Optional[str] = None) -> str:
        """Chat completion with message history."""
        model = model or self.default_model
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": False
        }
        
        try:
            response = await self._async_post("/api/chat", payload)
            if response and 'message' in response:
                return response['message'].get('content', '')
        except Exception as e:
            logger.error(f"Chat error: {e}")
        
        return ""
    
    async def analyze_image(self, image_path: str, prompt: str, 
                           model: str = "llava") -> str:
        """Analyze image with vision-capable model."""
        import base64
        
        try:
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode()
            
            payload = {
                "model": model,
                "prompt": prompt,
                "images": [image_data],
                "stream": False
            }
            
            response = await self._async_post("/api/generate", payload)
            if response and 'response' in response:
                return response['response']
        except Exception as e:
            logger.error(f"Image analysis error: {e}")
        
        return ""
    
    async def list_models(self) -> List[str]:
        """List available models on server."""
        try:
            response = await self._async_get("/api/tags")
            if response and 'models' in response:
                return [m['name'] for m in response['models']]
        except Exception as e:
            logger.error(f"List models error: {e}")
        return []
    
    async def _async_get(self, endpoint: str) -> Optional[Dict]:
        """Async GET request."""
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: self.session.get(f"{self.base_url}{endpoint}", timeout=30)
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"GET {endpoint} error: {e}")
        return None
    
    async def _async_post(self, endpoint: str, payload: Dict) -> Optional[Dict]:
        """Async POST request."""
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: self.session.post(f"{self.base_url}{endpoint}", 
                                         json=payload, timeout=60)
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"POST {endpoint} error: {e}")
        return None
    
    def get_statistics(self) -> Dict:
        """Get client statistics."""
        return {
            'base_url': self.base_url,
            'default_model': self.default_model,
            'connected': self._connected
        }