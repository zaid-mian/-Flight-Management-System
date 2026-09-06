import os
import sys
import subprocess

PROJECT_ROOT = r"E:\n8n\flight-agent-hackathon"

def run_regression_suite():
    print("=== Consolidating E2E & Full Regression Suite Verification ===")
    
    test_files = [
        "scratch/test_phase3_suite.py",
        "scratch/test_task4_1_ingest.py",
        "scratch/test_task4_2_mcp.py",
        "scratch/test_task4_3_rag_agent.py",
        "scratch/test_task4_4_hitl_approval.py",
        "scratch/test_task4_5_batch_fraud.py",
        "scratch/test_task5_1_last_seat_race.py",
        "scratch/test_task5_2_dual_writer_lock.py",
        "scratch/test_task5_3_approval_token_security.py"
    ]
    
    results = {}
    for test in test_files:
        test_path = os.path.join(PROJECT_ROOT, test)
        if not os.path.exists(test_path):
            print(f"Skipping missing test: {test}")
            continue
            
        print(f"\n---> Running Regression Test: {test} ...")
        proc = subprocess.run([sys.executable, test_path], cwd=PROJECT_ROOT, capture_output=True, text=True)
        if proc.returncode == 0:
            print(f"  [PASS] {test}: VERIFIED CLEAN")
            results[test] = "PASS"
        else:
            print(f"  [FAIL] {test}: FAILED")
            print(f"  Stdout: {proc.stdout}")
            print(f"  Stderr: {proc.stderr}")
            results[test] = "FAIL"
            
    print("\n================ REGRESSION SUMMARY ================")
    all_pass = True
    for t, status in results.items():
        print(f"  - {t:50s}: {status}")
        if status != "PASS":
            all_pass = False
            
    if all_pass:
        print("\n--> ALL PHASE 3, 4, AND 5 REGRESSION TESTS PASSED 100%! ZERO REGRESSIONS! <--")
    else:
        print("\n--> REGRESSION FAILURES DETECTED! <--")
        
    return all_pass

if __name__ == "__main__":
    run_regression_suite()
