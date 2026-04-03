"""RAG-Agent Pattern Example -- Knowledge Base Q&A.

Demonstrates an agent that decides when to retrieve documents from a
knowledge base and synthesizes information to answer user queries.

Usage:
    1. Copy ``.env.example`` to ``.env`` and add your OpenAI API key.
    2. Run::

        python -m patterns.rag_agent.example
"""

from dotenv import load_dotenv

load_dotenv()

from patterns.rag_agent.pattern import RAGAgentPattern


def main() -> None:
    # Default: uses built-in mock documents for demonstration.
    pattern = RAGAgentPattern(max_retrievals=3)

    # To use your own retriever, pass a callable with signature:
    #   Callable[[list[str]], list[dict]]
    # def my_retriever(doc_ids: list[str]) -> list[dict]:
    #     # e.g., query your vector DB (Pinecone, Weaviate, Chroma, etc.)
    #     return [{"doc_id": id, "content": "...", "score": 0.9} for id in doc_ids]
    # pattern = RAGAgentPattern(max_retrievals=3, retriever=my_retriever)

    queries = [
        "What is Python and when was it created?",
        "How does LangGraph enable agentic workflows?",
        "What is the capital of France?",
    ]

    for query in queries:
        result = pattern.run(query=query)

        print("=" * 60)
        print(f"QUERY: {query}")
        print("=" * 60)
        print(f"Retrievals: {result['retrieval_count']}")
        print(f"Documents Retrieved: {len(result['retrieved_docs'])}")
        if result["retrieved_docs"]:
            print("Retrieved:")
            for doc in result["retrieved_docs"]:
                print(f"  - [{doc['doc_id']}]")
        print(f"\nResponse: {result['response']}")
        print()


if __name__ == "__main__":
    main()
