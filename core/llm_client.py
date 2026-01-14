"""
Local LLM Client - Shared Ollama API wrapper
Uses Ollama API to interact with local language models
"""

import requests
import json
import numpy as np
from typing import Optional, List, Dict, Any, Union
from pathlib import Path

# Import model manager for availability checks
try:
    from .model_manager import get_model_manager
except ImportError:
    # Fallback if imported directly
    from model_manager import get_model_manager


class LocalLLM:
    """Client for interacting with local LLM via Ollama API"""
    
    def __init__(self, model: str = "llama3.1:8b", base_url: str = "http://localhost:11434",
                 auto_install: bool = False):
        self.model = model
        self.base_url = base_url
        self.auto_install = auto_install
        self.conversation_history: List[Dict[str, str]] = []
        self._model_manager = get_model_manager()
        
        # Ensure model is available if auto_install is True
        if auto_install:
            self._ensure_model_available(model)
    
    def chat(self, message: str, stream: bool = True) -> str:
        """Send a message and get response with conversation history"""
        self.conversation_history.append({
            "role": "user",
            "content": message
        })
        
        url = f"{self.base_url}/api/chat"
        data = {
            "model": self.model,
            "messages": self.conversation_history,
            "stream": stream
        }
        
        try:
            if stream:
                response = requests.post(url, json=data, stream=True)
                full_response = ""
                
                for line in response.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        if 'message' in chunk:
                            content = chunk['message'].get('content', '')
                            print(content, end='', flush=True)
                            full_response += content
                
                print()  # New line after response
                
                self.conversation_history.append({
                    "role": "assistant",
                    "content": full_response
                })
                
                return full_response
            else:
                response = requests.post(url, json=data)
                result = response.json()
                content = result['message']['content']
                
                self.conversation_history.append({
                    "role": "assistant",
                    "content": content
                })
                
                return content
        
        except Exception as e:
            return f"Error: {e}"
    
    def generate(self, prompt: str, stream: bool = False, 
                 temperature: float = 0.7, timeout: int = 60) -> str:
        """Generate response without conversation history (stateless)"""
        url = f"{self.base_url}/api/generate"
        data = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": temperature
            }
        }
        
        try:
            if stream:
                response = requests.post(url, json=data, stream=True, timeout=timeout)
                full_response = ""
                
                for line in response.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        content = chunk.get('response', '')
                        print(content, end='', flush=True)
                        full_response += content
                
                print()
                return full_response
            else:
                response = requests.post(url, json=data, timeout=timeout)
                result = response.json()
                return result.get('response', '')
        
        except Exception as e:
            return f"LLM_ERROR: {str(e)}"
    
    def embed(self, texts: Union[str, List[str]], 
              model: str = "mxbai-embed-large",
              timeout: int = 60,
              auto_install: bool = False) -> np.ndarray:
        """
        Generate embeddings for text(s) using Ollama embeddings API.
        
        Args:
            texts: Single text string or list of texts to embed
            model: Embedding model to use (default: mxbai-embed-large, 1024 dims)
            timeout: Request timeout in seconds
            auto_install: If True, install model if not available
            
        Returns:
            numpy array of shape (n_texts, embedding_dim) or (embedding_dim,) for single text
        """
        # Check if model is installed
        if not self._model_manager.is_model_installed(model):
            if auto_install:
                print(f"[Embed] Model {model} not found. Installing...")
                success, msg = self._model_manager.install_model_sync(model)
                if not success:
                    raise RuntimeError(f"Failed to install embedding model {model}: {msg}")
            else:
                raise RuntimeError(
                    f"Embedding model '{model}' is not installed.\n"
                    f"Install it with: ollama pull {model}\n"
                    f"Or enable auto_install in settings."
                )
        
        url = f"{self.base_url}/api/embeddings"
        
        # Handle single text vs list
        single_input = isinstance(texts, str)
        if single_input:
            texts = [texts]
        
        embeddings = []
        
        try:
            for text in texts:
                data = {
                    "model": model,
                    "prompt": text
                }
                response = requests.post(url, json=data, timeout=timeout)
                response.raise_for_status()
                result = response.json()
                
                embedding = result.get('embedding', [])
                if not embedding:
                    raise ValueError(f"No embedding returned for text: {text[:50]}...")
                
                embeddings.append(embedding)
            
            # Convert to numpy array
            embeddings_array = np.array(embeddings, dtype=np.float32)
            
            # Return single vector if single input, else 2D array
            if single_input:
                return embeddings_array[0]
            return embeddings_array
            
        except requests.exceptions.RequestException as e:
            # More helpful error message
            if "404" in str(e):
                raise ConnectionError(
                    f"Embedding model '{model}' not found. Install with: ollama pull {model}"
                )
            raise ConnectionError(f"Failed to connect to Ollama for embeddings: {e}")
        except Exception as e:
            raise RuntimeError(f"Embedding error: {e}")
    
    def list_models(self) -> List[str]:
        """List available models"""
        url = f"{self.base_url}/api/tags"
        try:
            response = requests.get(url, timeout=10)
            models = response.json().get('models', [])
            return [m['name'] for m in models]
        except:
            return []
    
    def is_available(self) -> bool:
        """Check if LLM server is available"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def is_model_installed(self, model: str = None) -> bool:
        """Check if a specific model is installed"""
        model = model or self.model
        return self._model_manager.is_model_installed(model)
    
    def ensure_model(self, model: str = None) -> tuple:
        """
        Ensure a model is available, installing if needed.
        
        Returns:
            Tuple of (success, message)
        """
        model = model or self.model
        return self._model_manager.ensure_model_available(model, auto_install=True)
    
    def _ensure_model_available(self, model: str):
        """Internal method to ensure model is available on init"""
        if not self._model_manager.is_ollama_running():
            print(f"[LLM] Warning: Ollama is not running")
            return
        
        if not self._model_manager.is_model_installed(model):
            print(f"[LLM] Model {model} not found. Installing...")
            success, msg = self._model_manager.install_model_sync(model)
            if success:
                print(f"[LLM] {msg}")
            else:
                print(f"[LLM] Failed to install {model}: {msg}")
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []


# Convenience function for one-shot generation
def generate_once(prompt: str, model: str = "llama3.1:8b", 
                  temperature: float = 0.7, timeout: int = 60) -> str:
    """One-shot generation without creating LLM instance"""
    llm = LocalLLM(model=model)
    return llm.generate(prompt, stream=False, temperature=temperature, timeout=timeout)
