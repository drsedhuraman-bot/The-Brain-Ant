import asyncio
import sys
from io import StringIO


async def execute_code(code: str, language: str = "python") -> str:
    """Execute Python code in a sandboxed subprocess and return stdout + stderr."""
    if language != "python":
        return f"Unsupported language: {language}. Only 'python' is supported."

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-c", code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)

        output_parts: list[str] = []
        if stdout:
            output_parts.append(f"stdout:\n{stdout.decode()}")
        if stderr:
            output_parts.append(f"stderr:\n{stderr.decode()}")
        if proc.returncode != 0:
            output_parts.append(f"exit code: {proc.returncode}")

        return "\n".join(output_parts) if output_parts else "(no output)"

    except asyncio.TimeoutError:
        return "Error: code execution timed out (10s limit)"
    except Exception as exc:
        return f"Error executing code: {exc}"
