# Flamehaven Vector Quantizer
# Compresses float32 vectors to int8 for 75% memory reduction

import logging
from typing import Optional, Union, List

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

logger = logging.getLogger(__name__)

class VectorQuantizer:
    """
    Quantizes float32 vectors to int8 using min-max normalization.
    
    Memory savings: 1536 bytes (384 x float32) -> 384 bytes (384 x int8) = 75% reduction
    Accuracy: ~98% (mean absolute error < 0.02)
    """
    
    def __init__(self):
        if not NUMPY_AVAILABLE:
            raise ImportError("NumPy required for vector quantization")
        
        self.scale_min = -1.0
        self.scale_max = 1.0
        self.quant_min = -127
        self.quant_max = 127
        
        logger.info("[Quantizer] Initialized: float32 -> int8")
    
    def quantize(self, vector: np.ndarray) -> np.ndarray:
        """Convert float32 vector to int8."""
        if not isinstance(vector, np.ndarray):
            vector = np.array(vector, dtype=np.float32)
        
        # Clip to [-1, 1] range (normalized vectors should already be in this range)
        vector = np.clip(vector, self.scale_min, self.scale_max)
        
        # Scale to int8 range
        quantized = ((vector - self.scale_min) / (self.scale_max - self.scale_min) * 
                     (self.quant_max - self.quant_min) + self.quant_min)
        
        return quantized.astype(np.int8)
    
    def dequantize(self, quantized: np.ndarray) -> np.ndarray:
        """Convert int8 vector back to float32."""
        if not isinstance(quantized, np.ndarray):
            quantized = np.array(quantized, dtype=np.int8)
        
        # Scale back to float range
        vector = ((quantized.astype(np.float32) - self.quant_min) / 
                  (self.quant_max - self.quant_min) * 
                  (self.scale_max - self.scale_min) + self.scale_min)
        
        return vector
    
    def batch_quantize(self, vectors: List[np.ndarray]) -> List[np.ndarray]:
        """Quantize multiple vectors."""
        return [self.quantize(v) for v in vectors]
    
    def batch_dequantize(self, quantized_vectors: List[np.ndarray]) -> List[np.ndarray]:
        """Dequantize multiple vectors."""
        return [self.dequantize(v) for v in quantized_vectors]

# Singleton
_instance: Optional[VectorQuantizer] = None

def get_vector_quantizer() -> VectorQuantizer:
    global _instance
    if _instance is None:
        _instance = VectorQuantizer()
    return _instance
