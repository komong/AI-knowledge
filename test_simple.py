import sys
import os

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

print("START", flush=True)

try:
    print("importing sentence_transformers...", flush=True)
    from sentence_transformers import SentenceTransformer
    print("SentenceTransformer imported", flush=True)
    
    print("loading model...", flush=True)
    m = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    print("model loaded", flush=True)
    
    print("encoding...", flush=True)
    v = m.encode('test')
    print("RESULT: embed dim =", len(v), flush=True)
    
except Exception as e:
    print("ERROR:", e, flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)
