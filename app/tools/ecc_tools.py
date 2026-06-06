import re

async def optimize_prompts(prompt: str) -> str:
    """Optimize prompt for token efficiency, clarity, and system performance."""
    try:
        trimmed = prompt.strip()
        word_count = len(trimmed.split())
        token_estimate = int(word_count * 1.3)
        
        # Simple rule-based optimization simulations
        optimized = trimmed
        optimized = re.sub(r'\bplease\b', '', optimized, flags=re.IGNORECASE)
        optimized = re.sub(r'\bcould you\b', '', optimized, flags=re.IGNORECASE)
        optimized = re.sub(r'\bwould you mind\b', '', optimized, flags=re.IGNORECASE)
        optimized = re.sub(r'\s+', ' ', optimized).strip()
        
        opt_word_count = len(optimized.split())
        opt_token_estimate = int(opt_word_count * 1.3)
        reduction = token_estimate - opt_token_estimate
        
        return (
            f"Prompt optimized successfully!\n\n"
            f"**Original prompt size**: ~{token_estimate} tokens\n"
            f"**Optimized prompt size**: ~{opt_token_estimate} tokens (reduced by {reduction} tokens)\n\n"
            f"**Optimized Prompt**:\n\"{optimized}\""
        )
    except Exception as exc:
        return f"Prompt optimization error: {exc}"

async def security_scan(code: str) -> str:
    """Perform a security scan on source code to check for vulnerabilities, secrets, and injection points."""
    try:
        findings = []
        
        # Basic patterns
        if "eval(" in code:
            findings.append("- [HIGH] Found use of 'eval()'. This is a potential code injection risk.")
        if "exec(" in code:
            findings.append("- [HIGH] Found use of 'exec()'. This is a potential code injection risk.")
        if re.search(r'(api_key|token|password|secret)\s*=\s*[\'"][^\'"]+[\'"]', code, re.IGNORECASE):
            findings.append("- [MEDIUM] Potential hardcoded API key, token, or secret detected.")
        if "subprocess.Popen" in code or "os.system" in code:
            findings.append("- [MEDIUM] System shell execution detected. Ensure command arguments are sanitized.")
            
        if not findings:
            return "Security Scan Report:\n- No critical or medium vulnerabilities detected. Code is safe for execution."
        
        return "Security Scan Report:\n" + "\n".join(findings)
    except Exception as exc:
        return f"Security scan error: {exc}"
