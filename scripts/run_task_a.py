import sys, os, shutil
from pathlib import Path
sys.path.insert(0, r"C:\Users\Akshay aravind .rv\operation_jarvis")
from core.code_engine import code_engine

calc_dir = Path(r"C:\Users\Akshay aravind .rv\operation_jarvis\data\sacrificial_calc")
calc_dir.mkdir(parents=True, exist_ok=True)

calc_py = calc_dir / "calc.py"
test_py = calc_dir / "test_calc.py"

# 1. Intentional bug: division performs addition
calc_py.write_text("def divide(a, b):\n    return a + b\n", encoding="utf-8")
test_py.write_text("from calc import divide\ndef test_divide():\n    assert divide(10, 2) == 5\n", encoding="utf-8")

# 2. Run initial test - must fail (assert 10 + 2 == 5 fails)
init_res = code_engine.run_test_suite("pytest test_calc.py -q", working_dir=str(calc_dir))
print("Initial test run passed:", init_res["passed"], "| exit_code:", init_res.get("exit_code"))
assert init_res["passed"] is False and init_res.get("exit_code") == 1

# 3. Patch bug using multi_file_patch with 'path' key
patch_res = code_engine.multi_file_patch([
    {
        "path": str(calc_py),
        "action": "replace",
        "target": "return a + b",
        "replacement": "if b == 0:\n        raise ValueError('Zero division')\n    return a / b"
    }
])
print("Patch applied successfully:", patch_res["ok"], "| count:", patch_res.get("count"))
assert patch_res["ok"] is True

# 4. Re-run test - must pass (assert 10 / 2 == 5 passes)
final_res = code_engine.run_test_suite("pytest test_calc.py -q", working_dir=str(calc_dir))
print("Final test run passed:", final_res["passed"], "| exit_code:", final_res.get("exit_code"))
assert final_res["passed"] is True and final_res.get("exit_code") == 0

# 5. Cleanup
shutil.rmtree(calc_dir, ignore_errors=True)
print("TASK (A) BUG FIX & TEST TO GREEN: VERIFIED!")
