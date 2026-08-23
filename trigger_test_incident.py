import httpx
import json

def trigger_incident():
    url = "http://localhost:8000/api/v1/events"
    project_id = "proj_seed"
    
    headers = {
        "X-Project-ID": project_id,
        "X-User-ID": "usr_seed",
        "X-User-Email": "seed_user@example.com",
        "X-Organization-ID": "org_seed",
        "Content-Type": "application/json"
    }
    
    # Ensure project exists
    try:
        httpx.post("http://localhost:8000/api/v1/projects", json={
            "id": project_id,
            "name": "API Gateway & Core Services",
            "repository": "seed-org/seed-repo"
        }, headers=headers, timeout=5.0)
    except Exception:
        pass
    
    payload = {
        "project_id": project_id,
        "exception_type": "TypeError",
        "exception_message": "Cannot read properties of undefined (reading 'layer_data')",
        "stack_trace": """Traceback (most recent call last):
  File "src/components/LayerVisualizer.tsx", line 48, in render
    return layer_data.map(item => item.name)
TypeError: Cannot read properties of undefined (reading 'layer_data')""",
        "environment": "production",
        "context": {
            "module": "osi-tcp-simulator",
            "repository": "seed-org/seed-repo"
        }
    }
    
    print("Sending failure event to Autonomous Recovery PaaS...")
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=10.0)
        if response.status_code == 200:
            data = response.json()
            print("\nSUCCESS! Incident Ingested Successfully:")
            print(f"  Incident ID:  {data.get('id')}")
            print(f"  Status:        {data.get('status')}")
            print(f"  Exception:     {data.get('exception_type')}: {data.get('exception_message')}")
            print(f"  Project:       {data.get('affected_project')} ({data.get('affected_repository')})")
            print("\nView it now in your browser at http://localhost:3000 (under 'Incidents' tab)!")
        else:
            print(f"Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Failed to connect to API: {e}")


if __name__ == "__main__":
    trigger_incident()
