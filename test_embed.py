import traceback
import sys
sys.path.insert(0, '.')

try:
    from src.embedder import EMBED_DIM
    print('EMBED_DIM:', EMBED_DIM)
    from src.embedder import embed_text
    vec = embed_text('测试文本')
    print('Vector length:', len(vec))
    print('SUCCESS')
except Exception as e:
    traceback.print_exc()
    print('FAILED:', e)
