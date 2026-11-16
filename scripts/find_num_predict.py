import os, re
root_dir = r"C:\Users\Akshay aravind .rv\operation_jarvis"
for root, dirs, files in os.walk(root_dir):
    if any(k in root for k in [".venv", ".git", "repo_eval", "data"]): continue
    for f in files:
        if f.endswith(".py"):
            p = os.path.join(root, f)
            text = open(p, encoding="utf-8", errors="ignore").read()
            for line_no, l in enumerate(text.splitlines(), 1):
                if "num_predict" in l:
                    rel = os.path.relpath(p, root_dir)
                    print(f"{rel}:{line_no} -> {l.strip()}")
