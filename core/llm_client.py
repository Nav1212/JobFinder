"""
Local LLM Client - Shared Ollama API wrapper
Uses Ollama API to interact with local language models
"""

import requests
import json
from typing import Optional, List, Dict, Any


class LocalLLM:
    """Client for interacting with local LLM via Ollama API"""
    
    def __init__(self, model: str = "llama3.1:8b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self.conversation_history: List[Dict[str, str]] = []
    
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
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []


# Convenience function for one-shot generation
def generate_once(prompt: str, model: str = "llama3.1:8b", 
                  temperature: float = 0.7, timeout: int = 60) -> str:
    """One-shot generation without creating LLM instance"""
    llm = LocalLLM(model=model)
    return llm.generate(prompt, stream=False, temperature=temperature, timeout=timeout)
