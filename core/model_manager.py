"""
Model Manager - Handles Ollama model installation and availability
Provides model checking, installation, and size information
"""

import requests
import subprocess
import threading
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass
from enum import Enum


class ModelType(Enum):
    """Type of model by purpose"""
    EMBEDDING = "embedding"
    GENERATION = "generation"


@dataclass
class ModelInfo:
    """Information about an Ollama model"""
    name: str
    size_gb: float
    description: str
    model_type: ModelType
    recommended_for: List[str]  # e.g., ["parsing", "grading", "polishing"]
    
    def size_display(self) -> str:
        """Human readable size"""
        if self.size_gb < 1:
            return f"{int(self.size_gb * 1024)} MB"
        return f"{self.size_gb:.1f} GB"


# Known models with metadata
KNOWN_MODELS: Dict[str, ModelInfo] = {
    # Embedding models
    "mxbai-embed-large": ModelInfo(
        name="mxbai-embed-large",
        size_gb=0.67,
        description="High quality embeddings (1024 dims)",
        model_type=ModelType.EMBEDDING,
        recommended_for=["embeddings"]
    ),
    "nomic-embed-text": ModelInfo(
        name="nomic-embed-text",
        size_gb=0.27,
        description="Fast, compact embeddings (768 dims)",
        model_type=ModelType.EMBEDDING,
        recommended_for=["embeddings"]
    ),
    "all-minilm": ModelInfo(
        name="all-minilm",
        size_gb=0.045,
        description="Tiny, fast embeddings (384 dims)",
        model_type=ModelType.EMBEDDING,
        recommended_for=["embeddings"]
    ),
    
    # Small generation models (for parsing)
    "phi3:mini": ModelInfo(
        name="phi3:mini",
        size_gb=2.2,
        description="Microsoft Phi-3 Mini - fast, efficient",
        model_type=ModelType.GENERATION,
        recommended_for=["parsing"]
    ),
    "llama3.2:1b": ModelInfo(
        name="llama3.2:1b",
        size_gb=1.3,
        description="Llama 3.2 1B - very fast, lightweight",
        model_type=ModelType.GENERATION,
        recommended_for=["parsing"]
    ),
    "qwen2.5:1.5b": ModelInfo(
        name="qwen2.5:1.5b",
        size_gb=0.99,
        description="Qwen 2.5 1.5B - fast, multilingual",
        model_type=ModelType.GENERATION,
        recommended_for=["parsing"]
    ),
    
    # Medium generation models (for grading)
    "llama3.1:8b": ModelInfo(
        name="llama3.1:8b",
        size_gb=4.7,
        description="Llama 3.1 8B - balanced quality/speed",
        model_type=ModelType.GENERATION,
        recommended_for=["grading", "polishing"]
    ),
    "llama3.2:3b": ModelInfo(
        name="llama3.2:3b",
        size_gb=2.0,
        description="Llama 3.2 3B - good balance",
        model_type=ModelType.GENERATION,
        recommended_for=["grading"]
    ),
    "mistral:7b": ModelInfo(
        name="mistral:7b",
        size_gb=4.1,
        description="Mistral 7B - excellent reasoning",
        model_type=ModelType.GENERATION,
        recommended_for=["grading", "polishing"]
    ),
    "qwen2.5:7b": ModelInfo(
        name="qwen2.5:7b",
        size_gb=4.7,
        description="Qwen 2.5 7B - strong multilingual",
        model_type=ModelType.GENERATION,
        recommended_for=["grading", "polishing"]
    ),
    
    # Large generation models (for polishing)
    "llama3.1:70b": ModelInfo(
        name="llama3.1:70b",
        size_gb=40.0,
        description="Llama 3.1 70B - highest quality",
        model_type=ModelType.GENERATION,
        recommended_for=["polishing"]
    ),
    "qwen2.5:32b": ModelInfo(
        name="qwen2.5:32b",
        size_gb=20.0,
        description="Qwen 2.5 32B - excellent quality",
        model_type=ModelType.GENERATION,
        recommended_for=["polishing"]
    ),
    "mixtral:8x7b": ModelInfo(
        name="mixtral:8x7b",
        size_gb=26.0,
        description="Mixtral 8x7B MoE - very capable",
        model_type=ModelType.GENERATION,
        recommended_for=["polishing"]
    ),
}


class ModelManager:
    """Manages Ollama model availability and installation"""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self._installed_cache: Optional[List[str]] = None
        self._cache_time = 0
    
    def is_ollama_running(self) -> bool:
        """Check if Ollama server is running"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def get_installed_models(self, force_refresh: bool = False) -> List[str]:
        """Get list of installed models"""
        import time
        
        # Use cache if recent (5 seconds)
        if not force_refresh and self._installed_cache is not None:
            if time.time() - self._cache_time < 5:
                return self._installed_cache
        
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                models = response.json().get('models', [])
                self._installed_cache = [m['name'] for m in models]
                self._cache_time = time.time()
                return self._installed_cache
        except:
            pass
        
        return []
    
    def is_model_installed(self, model_name: str) -> bool:
        """Check if a specific model is installed"""
        installed = self.get_installed_models()
        
        # Check exact match
        if model_name in installed:
            return True
        
        # Check base name (e.g., "llama3.1:8b" matches "llama3.1:8b-instruct-q4_0")
        base_name = model_name.split(':')[0]
        for m in installed:
            if m.startswith(base_name):
                return True
        
        return False
    
    def get_model_info(self, model_name: str) -> Optional[ModelInfo]:
        """Get info about a model"""
        # Check known models
        if model_name in KNOWN_MODELS:
            return KNOWN_MODELS[model_name]
        
        # Check base name
        base_name = model_name.split(':')[0]
        for name, info in KNOWN_MODELS.items():
            if name.startswith(base_name):
                return info
        
        return None
    
    def get_models_for_purpose(self, purpose: str) -> List[ModelInfo]:
        """Get models recommended for a specific purpose"""
        return [
            info for info in KNOWN_MODELS.values()
            if purpose in info.recommended_for
        ]
    
    def get_embedding_models(self) -> List[ModelInfo]:
        """Get all known embedding models"""
        return [
            info for info in KNOWN_MODELS.values()
            if info.model_type == ModelType.EMBEDDING
        ]
    
    def get_generation_models(self) -> List[ModelInfo]:
        """Get all known generation models"""
        return [
            info for info in KNOWN_MODELS.values()
            if info.model_type == ModelType.GENERATION
        ]
    
    def install_model(
        self, 
        model_name: str, 
        progress_callback: Optional[Callable[[str], None]] = None,
        completion_callback: Optional[Callable[[bool, str], None]] = None
    ) -> None:
        """
        Install a model using 'ollama pull' in background thread.
        
        Args:
            model_name: Name of model to install
            progress_callback: Called with progress messages
            completion_callback: Called with (success, message) when done
        """
        def _install():
            output_lines = []
            try:
                if progress_callback:
                    progress_callback(f"Starting download of {model_name}...")
                
                # Use subprocess to run ollama pull
                process = subprocess.Popen(
                    ['ollama', 'pull', model_name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                
                # Stream output
                for line in process.stdout:
                    line = line.strip()
                    if line:
                        output_lines.append(line)
                        if progress_callback:
                            progress_callback(line)
                
                process.wait()
                
                # Refresh cache
                self._installed_cache = None
                
                if process.returncode == 0:
                    # Verify model is actually installed
                    self.get_installed_models(force_refresh=True)
                    if self.is_model_installed(model_name):
                        if completion_callback:
                            completion_callback(True, f"Successfully installed {model_name}")
                    else:
                        if completion_callback:
                            completion_callback(False, f"Installation completed but model not found. Try: ollama pull {model_name}")
                else:
                    # Get the last few lines for error context
                    error_context = '\n'.join(output_lines[-5:]) if output_lines else "No output"
                    if completion_callback:
                        completion_callback(False, f"Installation failed (code {process.returncode}):\n{error_context}")
                        
            except FileNotFoundError:
                if completion_callback:
                    completion_callback(False, "Ollama not found. Please install Ollama first.")
            except Exception as e:
                if completion_callback:
                    completion_callback(False, f"Installation error: {str(e)}")
        
        # Run in background thread
        thread = threading.Thread(target=_install, daemon=True)
        thread.start()
    
    def install_model_sync(self, model_name: str) -> Tuple[bool, str]:
        """
        Install a model synchronously (blocking).
        
        Returns:
            Tuple of (success, message)
        """
        try:
            result = subprocess.run(
                ['ollama', 'pull', model_name],
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )
            
            # Refresh cache
            self._installed_cache = None
            
            if result.returncode == 0:
                return True, f"Successfully installed {model_name}"
            else:
                return False, f"Installation failed: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            return False, "Installation timed out"
        except FileNotFoundError:
            return False, "Ollama not found. Please install Ollama first."
        except Exception as e:
            return False, f"Installation error: {str(e)}"
    
    def ensure_model_available(
        self, 
        model_name: str,
        auto_install: bool = False,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Tuple[bool, str]:
        """
        Ensure a model is available, optionally installing if missing.
        
        Args:
            model_name: Model to check/install
            auto_install: If True, install if missing
            progress_callback: Called with progress messages during install
            
        Returns:
            Tuple of (available, message)
        """
        if not self.is_ollama_running():
            return False, "Ollama is not running. Start it with 'ollama serve'"
        
        if self.is_model_installed(model_name):
            return True, f"Model {model_name} is ready"
        
        if auto_install:
            if progress_callback:
                progress_callback(f"Model {model_name} not found. Installing...")
            return self.install_model_sync(model_name)
        
        return False, f"Model {model_name} is not installed"


# Singleton instance
_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """Get singleton ModelManager instance"""
    global _manager
    if _manager is None:
        _manager = ModelManager()
    return _manager
