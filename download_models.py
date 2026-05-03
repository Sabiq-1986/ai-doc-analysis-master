"""
Download HuggingFace DPR models for offline use.
Run this on a machine WITH internet.

Usage:
    python download_models.py

Creates:
    models/
    ├── dpr-question-encoder/   (~420MB)
    └── dpr-context-encoder/    (~420MB)
"""
from pathlib import Path

MODELS_DIR = Path("models")
MODELS_DIR.mkdir(exist_ok=True)

print("=" * 60)
print("  Downloading HuggingFace DPR Models for Offline Use")
print("=" * 60)

try:
    from transformers import (
        DPRQuestionEncoder, DPRQuestionEncoderTokenizer,
        DPRContextEncoder, DPRContextEncoderTokenizer
    )
    
    # DPR Question Encoder
    print("\n[1/2] Downloading DPR Question Encoder...")
    model_name = "facebook/dpr-question_encoder-single-nq-base"
    save_path = MODELS_DIR / "dpr-question-encoder"
    
    print(f"      From: {model_name}")
    print(f"      To:   {save_path}")
    
    tokenizer = DPRQuestionEncoderTokenizer.from_pretrained(model_name)
    model = DPRQuestionEncoder.from_pretrained(model_name)
    tokenizer.save_pretrained(save_path)
    model.save_pretrained(save_path)
    print("      ✓ Done!")
    
    # DPR Context Encoder  
    print("\n[2/2] Downloading DPR Context Encoder...")
    model_name = "facebook/dpr-ctx_encoder-single-nq-base"
    save_path = MODELS_DIR / "dpr-context-encoder"
    
    print(f"      From: {model_name}")
    print(f"      To:   {save_path}")
    
    tokenizer = DPRContextEncoderTokenizer.from_pretrained(model_name)
    model = DPRContextEncoder.from_pretrained(model_name)
    tokenizer.save_pretrained(save_path)
    model.save_pretrained(save_path)
    print("      ✓ Done!")
    
    print("\n" + "=" * 60)
    print("  SUCCESS!")
    print("=" * 60)
    print(f"\nModels saved to: {MODELS_DIR.absolute()}")
    print("\nFolder structure:")
    print("  models/")
    print("  ├── dpr-question-encoder/")
    print("  └── dpr-context-encoder/")
    print("\nNext: Copy 'models' folder to offline machine.")
    
except ImportError as e:
    print(f"\nERROR: Missing package - {e}")
    print("Install with: pip install transformers torch")
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
