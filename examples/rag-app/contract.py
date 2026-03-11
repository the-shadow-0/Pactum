"""
RAG App example — retrieval-augmented generation contract.
"""

from pactum import contract, MemorySchema


@contract(
    name="rag_answer:v1",
    inputs={"question": str},
    outputs={"answer": str, "sources": list},
    allowed_tools=["document_retriever"],
    nondet_budget={"tokens": 512},
)
def rag_answer(ctx, inputs):
    """
    Answer a question using retrieved documents (RAG pattern).
    """
    # Retrieve relevant documents
    try:
        docs = ctx.tools.document_retriever(inputs["question"], top_k=5)
    except AttributeError:
        docs = ["No documents available."]

    # Build prompt with context
    context = "\n".join(str(d) for d in docs) if isinstance(docs, list) else str(docs)
    prompt = (
        f"Answer the following question based on the provided context.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {inputs['question']}\n\n"
        f"Provide a clear, concise answer. If the context doesn't contain "
        f"enough information, say so."
    )

    result = ctx.llm.complete(prompt, temperature=0.3, max_tokens=512)
    ctx.trace("rag_response", {"answer_length": len(result.text)})

    return {
        "answer": result.text,
        "sources": docs if isinstance(docs, list) else [docs],
    }
