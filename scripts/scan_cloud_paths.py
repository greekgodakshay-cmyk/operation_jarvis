import os, re

root_dir = r"C:\Users\Akshay aravind .rv\operation_jarvis"
ignore_dirs = {".venv", ".git", "__pycache__", "node_modules", "repo_eval", "data"}

cloud_patterns = [
    re.compile(r"\b(openai|litellm|openrouter|anthropic|google\.generativeai)\b", re.IGNORECASE),
    re.compile(r"api\.openrouter\.ai", re.IGNORECASE),
    re.compile(r"api\.openai\.com", re.IGNORECASE),
    re.compile(r"api\.anthropic\.com", re.IGNORECASE)
]

cloud_paths = []
for root, dirs, files in os.walk(root_dir):
    dirs[:] = [d for d in dirs if d not in ignore_dirs]
    for f in files:
        if f.endswith((".py", ".json", ".md")):
            p = os.path.join(root, f)
            rel = os.path.relpath(p, root_dir)
            try:
                text = open(p, encoding="utf-8", errors="ignore").read()
                for line_no, line in enumerate(text.splitlines(), 1):
                    for cp in cloud_patterns:
                        if cp.search(line):
                            cloud_paths.append((rel, line_no, line.strip()))
                            break
            except Exception:
                pass

print(f"Total cloud-capable references found: {len(cloud_paths)}")
for rel, line_no, line in cloud_paths[:25]:
    print(f"{rel}:{line_no} -> {line[:80]}")
