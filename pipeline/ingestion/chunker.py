"""Chunker placeholder
Splits text into chunks for embedding.
Provides token-aware chunking using tiktoken when available.

Public functions:
- chunk_text(text, chunk_size): simple character-based chunking
- chunk_text_by_tokens(text, max_tokens, overlap_tokens, model): token-aware chunking using tiktoken
"""

# Simple character-based chunking. Useful when tokenizers are not available.
def chunk_text(text: str, chunk_size: int = 500):
    """Split `text` into fixed-size character chunks.

    Args:
        text: input text string
        chunk_size: maximum characters per chunk

    Returns:
        list of text chunks (strings)
    """
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]


def chunk_text_by_tokens(text: str, max_tokens: int = 200, overlap_tokens: int = 20, model: str = "text-embedding-3-small"):
    """Chunk text by tokens using tiktoken when available.

    This function attempts to use `tiktoken` to encode the input text into tokens, then
    creates overlapping windows of `max_tokens` tokens with `overlap_tokens` overlap.
    Each window is decoded back to a string and returned as a chunk.

    If `tiktoken` is not installed or encoding cannot be determined for the model,
    the function falls back to character-based chunking with a heuristic length (approx 4 chars/token).

    Args:
        text: the input text to chunk
        max_tokens: the maximum number of tokens per chunk
        overlap_tokens: how many tokens each chunk should overlap with the previous one
        model: model name used to select tiktoken encoding (best-effort)

    Returns:
        list of text chunk strings
    """
    try:
        import tiktoken
    except Exception:
        # fallback to char-based if tiktoken not installed
        # approximate tokens as characters
        approx_size = max_tokens * 4  # heuristic: 4 chars per token
        return chunk_text(text, chunk_size=approx_size)

    # try to get encoding for the model, otherwise default to cl100k_base
    try:
        encoding = tiktoken.encoding_for_model(model)
    except Exception:
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            # fallback to char-based
            approx_size = max_tokens * 4
            return chunk_text(text, chunk_size=approx_size)

    # encode entire text
    tokens = encoding.encode(text)
    chunks = []
    start = 0
    text_token_len = len(tokens)
    while start < text_token_len:
        end = start + max_tokens
        window = tokens[start:end]
        try:
            chunk_text_str = encoding.decode(window)
        except Exception:
            # if decode fails, convert tokens back to pieces using join on whitespace - fallback
            chunk_text_str = text
        chunks.append(chunk_text_str)
        if end >= text_token_len:
            break
        start = end - overlap_tokens if end - overlap_tokens > start else end
    return chunks


if __name__ == "__main__":
    print(chunk_text("a"*1200, 500))
    print(chunk_text_by_tokens("This is a test. " * 100, max_tokens=50, overlap_tokens=5))
