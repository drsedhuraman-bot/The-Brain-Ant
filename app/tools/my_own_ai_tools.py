async def personalize_response(text: str, style: str) -> str:
    """Format and adapt a response text based on the user's specific cognitive style preference."""
    try:
        style_lower = style.lower()
        if "concise" in style_lower or "brief" in style_lower:
            summary = text[:250] + "..." if len(text) > 250 else text
            return f"**Personalized Response (Style: Concise)**:\n{summary}"
        elif "tutorial" in style_lower or "detailed" in style_lower:
            return (
                f"**Personalized Response (Style: Tutorial/Step-by-Step)**:\n"
                f"Here is a comprehensive breakdown of the results adapted to your learning profile:\n\n"
                f"1. **Core Concept**:\n   {text}\n\n"
                f"2. **Key Takeaway**:\n   Keep this info handy for future reference."
            )
        elif "creative" in style_lower:
            return (
                f"**Personalized Response (Style: Creative/Empathetic)**:\n"
                f"🎨 *Here is a crafted, reader-friendly version of the response:*\n\n"
                f"\"{text}\""
            )
        else:
            return f"**Personalized Response (Style: {style})**:\n{text}"
    except Exception as exc:
        return f"Response personalization error: {exc}"
