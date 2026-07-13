"""
AI Brain Module - Local AI processing and decision making
Ollama integration, local LLM, edge AI
"""

from .ai_brain import AIBrain, ProcessingTask, ResponseMode, AIContext, AIDecision, DecisionType
from .ollama_client import OllamaClient, ModelConfig

# Placeholder for edge_inference (can be implemented later)
class EdgeAI:
    """Edge AI inference placeholder."""
    pass

class InferenceResult:
    """Inference result placeholder."""
    pass

__all__ = ['AIBrain', 'ProcessingTask', 'ResponseMode', 'AIContext', 'AIDecision', 'DecisionType',
           'OllamaClient', 'ModelConfig', 'EdgeAI', 'InferenceResult']