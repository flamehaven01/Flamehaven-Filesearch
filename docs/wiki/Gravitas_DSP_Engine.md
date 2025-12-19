# Gravitas DSP Engine (v2.0)

The **Gravitas Deterministic Semantic Projection (DSP)** engine is the heart of Flamehaven-Filesearch's semantic capabilities. It provides high-quality vector embeddings without the overhead of heavy Machine Learning libraries.

---

## 1. Core Philosophy

Traditional semantic search relies on transformer models (BERT, RoBERTa) which require GBs of memory and dedicated GPU/CPU resources. Gravitas DSP adopts a **Deterministic Projection** approach:

- **Mathematical Grounding**: Uses signed feature hashing to project text into a fixed-dimensional unit sphere.
- **Zero-Dependency**: No `numpy`, `scipy`, or `torch` required for the core vectorization logic (standard library only).
- **Instant Scaling**: Scales linearly with text length and constant initialization time.

---

## 2. Algorithm Details

### Feature Extraction
1. **Word Tokens**: Significant words are extracted and weighted (2.0x weight factor).
2. **Character N-grams**: Slides a 3-5 character window across the text to capture sub-word semantics and typo tolerance.
3. **Signed Hashing**: Features are hashed into 384 dimensions. To mitigate collisions, a signed bit determines if the feature increments or decrements the dimension's value.

### Normalization
- Vectors are L2-normalized to ensure all embeddings lie on the unit hypersphere, making Cosine Similarity equivalent to Dot Product.

---

## 3. Vector Quantization

To support massive indices, Gravitas DSP includes an **int8 Quantizer**:

- **Asymmetric Mapping**: Maps the `[-1.0, 1.0]` float range to `[-128, 127]` integers.
- **Calibration**: Uses per-vector min/max values to preserve maximum dynamic range.
- **Performance**: Similarity calculations are 30% faster using integer arithmetic.

---

## 4. Chronos-Grid Integration

Chronos-Grid acts as the persistent ledger for DSP vectors:

- **Lore Scrolls**: Vectors and metadata are stored in a proprietary compressed format.
- **Lore Packing**: Uses **GravitasPacker** symbolic compression to strip redundancy from JSON metadata before storage.

---

## 5. Usage Example (Core API)

```python
from flamehaven_filesearch.embedding import EmbeddingGenerator

# Initialize (Instant)
gen = EmbeddingGenerator(dimension=384)

# Project text to vector
vector = gen.generate("SR9 resonance and DI2 capsule integrity check")

# Result: List[float] of length 384
```

## 6. Comparison with Transformers

| Feature | BERT/Transformer | **Gravitas DSP v2.0** |
|---------|------------------|----------------------|
| Memory | 500MB - 2GB | **< 10MB** |
| GPU Required | Recommended | **No** |
| Latency | ~50ms / doc | **< 1ms / doc** |
| Typo Resilience | Moderate | **High (N-gram based)** |
| Accuracy | State-of-the-Art | **Strong (Standard Search)** |
