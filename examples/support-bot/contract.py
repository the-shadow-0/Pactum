"""
Support Bot example — customer support reply contract.
"""

from pactum import contract, MemorySchema


@contract(
    name="customer_support_reply:v1",
    inputs={"query": str, "customer_id": str},
    outputs={"reply": str, "intent": str},
    memory=MemorySchema(keys={"customer_profile": {"type": "json", "version": 1}}),
    allowed_tools=["kb_retriever", "crm_get"],
    nondet_budget={"tokens": 256},
)
def support_reply(ctx, inputs):
    """
    Generate a customer support reply with intent classification.
    """
    # Retrieve relevant knowledge base snippets
    try:
        snippets = ctx.tools.kb_retriever(inputs["query"], top_k=3)
    except AttributeError:
        snippets = ["No knowledge base available."]

    # Build prompt
    prompt = (
        f"You are a helpful customer support agent.\n"
        f"Customer ID: {inputs['customer_id']}\n"
        f"Query: {inputs['query']}\n"
        f"Context: {snippets}\n"
        f"Provide a concise, helpful reply and classify the intent "
        f"(e.g., 'order_status', 'refund', 'general').\n"
        f"Reply in JSON format: {{\"reply\": \"...\", \"intent\": \"...\"}}"
    )

    result = ctx.llm.complete(prompt, temperature=0.7, max_tokens=256)

    # Parse response (in production, you'd parse JSON properly)
    ctx.trace("llm_raw_response", result.text)

    return {"reply": result.text, "intent": "general"}
