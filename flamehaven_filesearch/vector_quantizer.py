# Flamehaven Vector Quantizer v1.0
# ARCHITECTURE: Scalar Quantization for Memory Efficiency
# DEPENDENCIES: numpy (optional but recommended)

import logging
from typing import List, Tuple, Any, Optional

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

logger = logging.getLogger(__name__)

class VectorQuantizer:
    """
    Flamehaven Vector Quantizer
    
    Compresses float32 vectors into int8 using Scalar Quantization.
    Achieves 75% memory reduction with minimal accuracy loss.
    
    Method: Min-Max Normalization + Scale/Offset tracking
    - Original: 384 dims × 4 bytes = 1536 bytes
    - Quantized: 384 dims × 1 byte + 8 bytes metadata = 392 bytes
    - Compression: 74.5%
    """
    
    def __init__(self):
        """Initialize quantizer."""
        self.stats = {
            'quantized': 0,
            'dequantized': 0,
            'total_original_bytes': 0,
            'total_compressed_bytes': 0
        }
        logger.info("[Flamehaven] Vector Quantizer initialized")
    
    def quantize(self, vector: Any) -> Tuple[bytes, float, float]:
        """
        Quantize float32 vector to int8.
        
        Args:
            vector: Input vector (numpy array or list of floats)
        
        Returns:
            Tuple of (quantized_bytes, scale, offset)
        """
        if NUMPY_AVAILABLE:
            if not isinstance(vector, np.ndarray):
                vector = np.array(vector, dtype=np.float32)
        else:
            if not isinstance(vector, list):
                vector = list(vector)
        
        # Calculate min/max for normalization
        if NUMPY_AVAILABLE:
            v_min = float(np.min(vector))
            v_max = float(np.max(vector))
        else:
            v_min = min(vector)
            v_max = max(vector)
        
        # Avoid division by zero
        if abs(v_max - v_min) < 1e-10:
            v_min = -1.0
            v_max = 1.0
        
        # Calculate scale and offset
        scale = (v_max - v_min) / 255.0
        offset = v_min
        
        # Quantize: map [v_min, v_max] -> [0, 255]
        if NUMPY_AVAILABLE:
            quantized = ((vector - offset) / scale).astype(np.uint8)
            quantized_bytes = quantized.tobytes()
        else:
            quantized = [int((v - offset) / scale) for v in vector]
            # Clamp to [0, 255]
            quantized = [max(0, min(255, q)) for q in quantized]
            quantized_bytes = bytes(quantized)
        
        # Update stats
        self.stats['quantized'] += 1
        self.stats['total_original_bytes'] += len(vector) * 4
        self.stats['total_compressed_bytes'] += len(quantized_bytes) + 8
        
        return quantized_bytes, scale, offset
    
    def dequantize(self, quantized_bytes: bytes, scale: float, offset: float) -> Any:
        """
        Dequantize int8 back to float32.
        
        Args:
            quantized_bytes: Quantized vector as bytes
            scale: Scale factor from quantization
            offset: Offset factor from quantization
        
        Returns:
            Reconstructed vector (numpy array or list)
        """
        # Decode bytes to integers
        if NUMPY_AVAILABLE:
            quantized = np.frombuffer(quantized_bytes, dtype=np.uint8)
            # Dequantize: map [0, 255] -> [v_min, v_max]
            vector = quantized.astype(np.float32) * scale + offset
        else:
            quantized = list(quantized_bytes)
            vector = [q * scale + offset for q in quantized]
        
        # Update stats
        self.stats['dequantized'] += 1
        
        return vector
    
    def get_stats(self) -> dict:
        """Return compression statistics."""
        total_orig = self.stats['total_original_bytes']
        total_comp = self.stats['total_compressed_bytes']
        
        compression_ratio = 0.0
        if total_orig > 0:
            compression_ratio = (1 - total_comp / total_orig) * 100
        
        return {
            'quantized_count': self.stats['quantized'],
            'dequantized_count': self.stats['dequantized'],
            'original_bytes': total_orig,
            'compressed_bytes': total_comp,
            'compression_ratio': round(compression_ratio, 2),
            'backend': 'numpy' if NUMPY_AVAILABLE else 'pure_python'
        }

# Singleton instance
_quantizer: Optional[VectorQuantizer] = None

def get_quantizer() -> VectorQuantizer:
    """Get singleton quantizer instance."""
    global _quantizer
    if _quantizer is None:
        _quantizer = VectorQuantizer()
    return _quantizer
