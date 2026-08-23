import subprocess
import time
import httpx
import os
import sys

def main():
    print("--- STARTING END-TO-END ACCEPTANCE TEST ---")
    
    # 1. Clean up old test db if exists
    db_file = f"recovery_test_{int(time.time())}.db"
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
            print(f"Removed existing test db: {db_file}")
        except Exception as e:
            print(f"Could not remove {db_file}: {e}")

    # Set up environment variables to force SQLite database and add PYTHONPATH
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_file}"
    env["BYPASS_CELERY"] = "true"
    # Ensure correct python paths
    env["PYTHONPATH"] = os.path.abspath("apps/api") + os.pathsep + os.path.abspath("demo-repo") + os.pathsep + os.path.abspath("packages/recovery-sdk")
    
    # 2. Start FastAPI Backend API on port 8000
    print("Starting backend API on port 8000...")
    api_cmd = [
        sys.executable, "-m", "uvicorn", "main:app",
        "--host", "127.0.0.1", "--port", "8000"
    ]
    api_log = open("backend_api.log", "w")
    api_process = subprocess.Popen(
        api_cmd,
        cwd="apps/api",
        env=env,
        stdout=api_log,
        stderr=api_log
    )
    
    # Give uvicorn a moment to boot
    time.sleep(3.0)
    
    # 3. Create the project proj_123
    print("Creating project 'proj_123' on the API backend...")
    try:
        with httpx.Client() as client:
            resp = client.post(
                "http://127.0.0.1:8000/api/v1/projects",
                json={
                    "id": "proj_123",
                    "name": "Demo Repo",
                    "repository": "demo/repo"
                },
                timeout=5.0
            )
            print(f"Project creation status: {resp.status_code}, response: {resp.text}")
            resp.raise_for_status()
    except Exception as e:
        print(f"Failed to create project: {e}")
        sys.exit(1)

    # 4. Start Demo App on port 8001
    print("Starting Demo App on port 8001...")
    demo_cmd = [
        sys.executable, "-m", "uvicorn", "app:app",
        "--host", "127.0.0.1", "--port", "8001"
    ]
    demo_log = open("demo_app.log", "w")
    demo_process = subprocess.Popen(
        demo_cmd,
        cwd="demo-repo",
        env=env,
        stdout=demo_log,
        stderr=demo_log
    )
    
    # Give uvicorn a moment to boot
    time.sleep(3.0)
    
    # 5. Cause the unhandled exception by requesting /users/1 on Demo App
    print("Triggering exception on Demo App (GET /users/1)...")
    try:
        with httpx.Client() as client:
            # This request should result in 500 Internal Server Error due to NameError bug
            resp = client.get("http://127.0.0.1:8001/users/1", timeout=5.0)
            print(f"Demo App request status: {resp.status_code} (Expected: 500)")
    except Exception as e:
        print(f"Request to Demo App failed: {e}")

    # 6. Wait for telemetry delivery (the SDK sends telemetry asynchronously in a background thread)
    print("Waiting for telemetry delivery...")
    time.sleep(3.0)
    
    # 7. Verify persisted incident on the API backend
    print("Querying API backend to verify persisted event...")
    success = False
    try:
        with httpx.Client() as client:
            resp = client.get("http://127.0.0.1:8000/api/v1/incidents", timeout=5.0)
            print(f"Query status: {resp.status_code}")
            incidents = resp.json()
            print(f"Incidents retrieved: {len(incidents)}")
            
            if len(incidents) > 0:
                incident = incidents[0]
                print("\n=== PERSISTED INCIDENT FOUND ===")
                print(f"ID: {incident['id']}")
                print(f"Project ID: {incident['project_id']}")
                print(f"Exception Type: {incident['exception_type']}")
                print(f"Exception Message: {incident['exception_message']}")
                print(f"Status: {incident['status']}")
                
                context = incident.get("context", {})
                print("\n=== TELEMETRY METADATA (CONTEXT) ===")
                print(f"File: {context.get('file')}")
                print(f"Line: {context.get('line')}")
                print(f"Function: {context.get('function')}")
                print(f"Git Commit Hash: {context.get('git_commit')}")
                print(f"Environment: {context.get('environment')}")
                print(f"Runtime Metadata: {context.get('runtime_metadata')}")
                print(f"SDK Version: {context.get('sdk_version')}")
                print(f"Request Metadata: {context.get('request_metadata')}")
                
                # Assertions
                assert incident["project_id"] == "proj_123"
                assert incident["exception_type"] == "NameError"
                assert "profile_db" in incident["exception_message"]
                assert context.get("file") is not None
                assert "users.py" in context.get("file")
                assert context.get("function") == "get_user_profile"
                assert context.get("environment") == "production"
                assert context.get("git_commit") is not None
                
                # Check safe request metadata
                req_meta = context.get("request_metadata")
                assert req_meta is not None
                assert req_meta.get("method") == "GET"
                assert "/users/1" in req_meta.get("url")
                
                print("\n--- ALL ASSERTIONS PASSED! END-TO-END TELEMETRY VERIFIED! ---")
                success = True
            else:
                print("Error: No incidents were persisted in the database.")
    except Exception as e:
        print(f"Verification failed: {e}")
        import traceback
        traceback.print_exc()

    # 8. Clean up
    print("Terminating server processes...")
    demo_process.terminate()
    api_process.terminate()
    
    # Wait for processes to exit
    demo_process.wait()
    api_process.wait()
    
    api_log.close()
    demo_log.close()
    
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
            print("Cleaned up database file.")
        except Exception:
            pass
            
    if not success:
        sys.exit(1)
    else:
        print("E2E Acceptance Test Finished successfully!")
        
if __name__ == "__main__":
    main()
