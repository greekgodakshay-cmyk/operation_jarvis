"""
Prompt Injection Defense and Content Sanitizer.
Ensures external tool outputs, fetched web pages, and file contents cannot hijack LLM system prompts.
"""
import html
import re

class InjectionGuard:
    INJECTION_INDICATORS = [
        re.compile(r"(?:ignore|disregard|override)\s+(?:all\s+|previous\s+|prior\s+|system\s+|security\s+)*(?:instructions|constraints|rules|policies|directives)", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+(?:an?\s+unrestricted|in\s+developer\s+mode|freed|jailbroken)", re.IGNORECASE),
        re.compile(r"system\s*:\s*you\s+must", re.IGNORECASE),
        re.compile(r"<\|im_start\|>", re.IGNORECASE),
        re.compile(r"(?:bypass|disable|circumvent)\s+(?:all\s+)*(?:security|policy|restrictions|filters|engine|guard)", re.IGNORECASE),
        re.compile(r"(?:admin|system|root|emergency|operational)\s+(?:directive|override|reset|command|instruction)", re.IGNORECASE),
        re.compile(r"execute\s+(?:shell\s+|powershell\s+|bash\s+)*command", re.IGNORECASE)
    ]

    def wrap_untrusted_content(self, content: str, source_identifier: str = "tool_output") -> str:
        """
        Wraps content in strict boundary delimiters with sanitized tags,
        preventing prompt injection escape sequences.
        """
        if not isinstance(content, str):
            content = str(content)

        # Flag any suspicious prompt injection patterns
        suspicious = any(pattern.search(content) for pattern in self.INJECTION_INDICATORS)
        warning_attr = ' warning="possible_prompt_injection_detected"' if suspicious else ''

        # Neutralize markdown system fake headers
        safe_content = content.replace("```system", "```escaped_system")
        safe_content = safe_content.replace("<|im_start|>", "[ESCAPED_TOKEN]")
        safe_content = safe_content.replace("<|im_end|>", "[ESCAPED_TOKEN]")

        return (
            f"<untrusted_external_content source=\"{source_identifier}\"{warning_attr}>\n"
            f"{safe_content}\n"
            f"</untrusted_external_content>"
        )

    def scan_for_injection(self, text: str) -> bool:
        if not isinstance(text, str):
            return False
        return any(pattern.search(text) for pattern in self.INJECTION_INDICATORS)

injection_guard = InjectionGuard()
