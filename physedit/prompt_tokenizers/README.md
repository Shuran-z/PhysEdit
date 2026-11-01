# Tokenizer vocabularies for exact prompt budgets

These are tokenizer vocabularies, not model weights. `sources.json` records the
official Hugging Face model repositories and immutable revisions used.

- `t5.model`: Lightricks/LTX-Video tokenizer/spiece.model; byte-identical to
  zai-org/CogVideoX1.5-5B-I2V at the recorded revisions.
- `umt5.model`: Wan-AI/Wan2.2-TI2V-5B-Diffusers tokenizer/spiece.model.

Counts use the original SentencePiece encoding with one EOS token and no text
truncation. They are cross-checked against AutoTokenizer for every fixed100 task.
The same compact English text is used for all compared models. Other tokenizer
versions must be counted separately at inference; file names and metadata are
not concatenated into the prompt.
