"""Download BAAI/bge-reranker-base for offline use."""
from sentence_transformers import CrossEncoder
import os

model_name = "BAAI/bge-reranker-base"
save_path = os.path.join("models", "cross-encoder", "bge-reranker-base")

print(f"Downloading {model_name}...")
model = CrossEncoder(model_name)
model.save(save_path)
print(f"Saved to {save_path}")

# Verify
model2 = CrossEncoder(save_path)
scores = model2.predict([("What is AI?", "Artificial intelligence is a field of computer science.")])
print(f"Verification score: {scores}")
print("Done!")
