#!/usr/bin/env python
"""Phase 3: Real-world compression performance test"""

from flamehaven_filesearch.cache import FileMetadataCache
import json

cache = FileMetadataCache(maxsize=100)

# Simulate realistic file metadata
test_files = [
    {
        'file_path': 'D:\\Sanctum\\Flamehaven-Filesearch\\flamehaven_filesearch\\engine\\embedding_generator.py',
        'file_name': 'embedding_generator.py',
        'file_type': '.py',
        'size_bytes': 15840,
        'created_at': '2025-12-15T09:30:00Z',
        'modified_at': '2025-12-15T10:45:00Z',
        'accessed_at': '2025-12-15T10:55:00Z',
        'lines_of_code': 384,
        'encoding': 'utf-8',
        'is_binary': False,
        'content_hash': 'sha256:abc123def456789',
        'tags': ['python', 'embedding', 'vectorizer', 'dsp']
    },
    {
        'file_path': 'D:\\Sanctum\\Flamehaven-Filesearch\\tests\\test_gravitas_cache_integration.py',
        'file_name': 'test_gravitas_cache_integration.py',
        'file_type': '.py',
        'size_bytes': 6446,
        'created_at': '2025-12-15T10:55:00Z',
        'modified_at': '2025-12-15T10:55:00Z',
        'lines_of_code': 150,
        'encoding': 'utf-8',
        'is_binary': False,
        'tags': ['python', 'test', 'integration']
    },
    {
        'file_path': 'D:\\Sanctum\\Flamehaven-Filesearch\\README.md',
        'file_name': 'README.md',
        'file_type': '.md',
        'size_bytes': 25600,
        'created_at': '2025-11-01T00:00:00Z',
        'modified_at': '2025-12-15T09:50:00Z',
        'encoding': 'utf-8',
        'is_binary': False,
        'tags': ['documentation', 'markdown']
    }
]

print('[*] Phase 3: Gravitas-Pack Cache Integration Performance Test')
print('='*70)

# Store files
for i, meta in enumerate(test_files):
    cache.set(f'file_{i}', meta)

# Retrieve and verify
print('\nData Integrity Check:')
all_passed = True
for i, original_meta in enumerate(test_files):
    retrieved = cache.get(f'file_{i}')
    passed = retrieved == original_meta
    all_passed = all_passed and passed
    status = 'PASS' if passed else 'FAIL'
    filename = original_meta['file_name'][:30]
    print(f'  [{status}] file_{i}: {filename}')

print(f'\nIntegrity: {"ALL PASS" if all_passed else "FAILED"}')

# Get compression stats
stats = cache.get_stats()

print('\n' + '='*70)
print('COMPRESSION STATISTICS')
print('='*70)
print(f'Total files cached:       {stats["current_size"]}')
print(f'Compression enabled:      {stats["compression_enabled"]}')
print(f'Total compressed:         {stats["total_compressed"]}')
print(f'Total decompressed:       {stats["total_decompressed"]}')
print(f'Bytes saved:              {stats["bytes_saved"]} bytes')
print(f'Average compression:      {stats["average_compression_ratio"]*100:.1f}%')
print('='*70)

# Calculate memory efficiency
total_original = sum(len(json.dumps(m)) for m in test_files)
print(f'\nMemory Efficiency:')
print(f'  Original size (uncompressed): {total_original} bytes')
print(f'  Savings achieved:             {stats["bytes_saved"]} bytes')
print(f'  Effective reduction:          {(stats["bytes_saved"]/total_original)*100:.1f}%')

print('\n[+] Phase 3 Integration: COMPLETE')
