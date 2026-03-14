"""Optional LangChain-based RAG helper.

This module provides a small wrapper to run a RetrievalQA chain using LangChain + Chroma.
It is optional: if `langchain` or `chromadb` are not installed the functions raise ImportError.

Usage:
- Populate a Chroma collection (use `store_and_query_chroma.py` to persist into a directory).
- Call `run_langchain_rag(persist_dir, collection_name, query, k, llm_model)` to get an LLM answer.

Note: This helper assumes OpenAI API key is set for the LLM call.
"""
from __future__ import annotations
from typing import Any, Dict


def run_langchain_rag(persist_dir: str, collection_name: str, query: str, k: int = 3, llm_model: str = 'gpt-4o-mini') -> Dict[str, Any]:
    try:
        import chromadb
        from chromadb.config import Settings
    except Exception as e:
        raise ImportError('chromadb is required for LangChain RAG: ' + str(e))

    try:
        from langchain.chains import RetrievalQA
        from langchain.llms import OpenAI
        from langchain.vectorstores import Chroma
    except Exception as e:
        raise ImportError('langchain and its Chroma integration are required: ' + str(e))

    # create a chroma client backed vectorstore via LangChain wrapper
    # LangChain's Chroma wrapper can be constructed using persist_directory
    try:
        vect = Chroma(collection_name=collection_name, persist_directory=persist_dir)
    except Exception as e:
        # fallback: try connecting directly with chromadb and then wrap
        client = chromadb.Client(Settings(chroma_db_impl='duckdb+parquet', persist_directory=persist_dir))
        try:
            collection = client.get_collection(collection_name)
        except Exception as e2:
            raise RuntimeError(f'Failed to access Chroma collection: {e2}')
        # LangChain's Chroma wrapper requires a chroma client, but to keep this helper
        # lightweight we raise here. The primary path is Chroma(persist_directory=...)
        raise RuntimeError('Failed to construct LangChain Chroma wrapper; ensure langchain-chroma is available')

    try:
        llm = OpenAI(model_name=llm_model)
    except Exception as e:
        raise RuntimeError('Failed to create OpenAI LLM via LangChain: ' + str(e))

    # Build a RetrievalQA chain
    qa = RetrievalQA.from_chain_type(llm=llm, chain_type='stuff', retriever=vect.as_retriever(search_kwargs={'k': k}))
    answer = qa.run(query)
    return {'answer': answer}

