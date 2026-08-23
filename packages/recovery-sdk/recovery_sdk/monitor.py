import asyncio
import queue
import threading
import httpx
import traceback
import sys
import platform
import logging
import os
import subprocess
from typing import Any, Dict, Optional

logger = logging.getLogger("recovery_sdk")

SDK_VERSION = "0.1.0"
SDK_NAME = "recovery-sdk"

def get_git_commit() -> Optional[str]:
    # Check env vars
    commit = os.getenv("GIT_COMMIT") or os.getenv("COMMIT_SHA") or os.getenv("GITHUB_SHA")
    if commit:
        return commit
    
    # Try git command
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except Exception:
        pass
        
    # Try reading .git/HEAD
    try:
        git_dir = ".git"
        if os.path.exists(git_dir):
            head_file = os.path.join(git_dir, "HEAD")
            if os.path.exists(head_file):
                with open(head_file, "r") as f:
                    head = f.read().strip()
                if head.startswith("ref:"):
                    ref_path = os.path.join(git_dir, head.split(" ")[1])
                    if os.path.exists(ref_path):
                        with open(ref_path, "r") as f:
                            return f.read().strip()
                else:
                    return head
    except Exception:
        pass
        
    return "unknown"


def extract_safe_request_metadata(request) -> dict:
    headers = {}
    for k, v in request.headers.items():
        k_lower = k.lower()
        # Exclude secrets
        if any(term in k_lower for term in ["authorization", "cookie", "password", "key", "secret", "token"]):
            continue
        headers[k] = v
        
    query_params = {}
    for k, v in request.query_params.items():
        k_lower = k.lower()
        if any(term in k_lower for term in ["password", "key", "secret", "token", "auth"]):
            query_params[k] = "[MASKED]"
        else:
            query_params[k] = str(v)

    return {
        "url": str(request.url),
        "method": request.method,
        "headers": headers,
        "query_params": query_params,
        "client_ip": request.client.host if request.client else None
    }


class ExceptionMonitor:
    def __init__(self) -> None:
        self.project_id: Optional[str] = None
        self.environment: str = "production"
        self.api_url: str = "http://localhost:8000"
        self.queue: queue.Queue = queue.Queue(maxsize=100)  # bounded queue
        self.worker_thread: Optional[threading.Thread] = None
        self.running: bool = False
        self._old_excepthook: Optional[Any] = None
        self._old_thread_excepthook: Optional[Any] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self, project_id: str, environment: str = "production", api_url: str = "http://localhost:8000") -> None:
        if self.running:
            return
        
        self.project_id = project_id
        self.environment = environment
        self.api_url = api_url.rstrip("/")
        self.running = True
        
        # Install sys hooks
        self._install_hooks()
        
        # Start worker thread
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="recovery-sdk-worker")
        self.worker_thread.start()
        logger.info(f"Recovery SDK initialized for project: {project_id}")

    def stop(self) -> None:
        if not self.running:
            return
        self.running = False
        self._uninstall_hooks()
        if self.worker_thread:
            # We join the thread to allow clean shutdown
            self.worker_thread.join(timeout=2.0)
            self.worker_thread = None

    def _install_hooks(self) -> None:
        self._old_excepthook = sys.excepthook
        sys.excepthook = self._excepthook
        
        if hasattr(threading, "excepthook"):
            self._old_thread_excepthook = threading.excepthook
            threading.excepthook = self._thread_excepthook

    def _uninstall_hooks(self) -> None:
        if sys.excepthook == self._excepthook:
            sys.excepthook = self._old_excepthook or sys.__excepthook__
        if hasattr(threading, "excepthook") and threading.excepthook == self._thread_excepthook:
            threading.excepthook = self._old_thread_excepthook or threading.__excepthook__

    def _excepthook(self, exc_type, exc_value, exc_traceback) -> None:
        self.capture_exception(exc_value)
        if self._old_excepthook:
            self._old_excepthook(exc_type, exc_value, exc_traceback)

    def _thread_excepthook(self, args) -> None:
        self.capture_exception(args.exc_value)
        if self._old_thread_excepthook:
            self._old_thread_excepthook(args)

    def capture_exception(self, exc: Exception, context: Optional[Dict[str, Any]] = None, request: Optional[Any] = None) -> None:
        if not self.running:
            return
        
        # Traverse traceback to final frame
        tb = exc.__traceback__
        while tb and tb.tb_next:
            tb = tb.tb_next
            
        file_name = None
        line_no = None
        func_name = None
        if tb:
            file_name = tb.tb_frame.f_code.co_filename
            line_no = tb.tb_lineno
            func_name = tb.tb_frame.f_code.co_name
            
        tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        git_commit = get_git_commit()
        
        runtime_meta = {
            "os": platform.system(),
            "os_release": platform.release(),
            "python_version": platform.python_version(),
            "hostname": platform.node()
        }
        
        req_meta = None
        if request:
            try:
                req_meta = extract_safe_request_metadata(request)
            except Exception as e:
                logger.error(f"Error extracting request metadata: {e}")
                
        payload = {
            "project_id": self.project_id,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "stack_trace": tb_str,
            "file": file_name,
            "line": line_no,
            "function": func_name,
            "git_commit": git_commit,
            "runtime_metadata": runtime_meta,
            "environment": self.environment,
            "request_metadata": req_meta,
            "sdk_version": {
                "name": SDK_NAME,
                "version": SDK_VERSION
            }
        }
        
        if context:
            # Merge additional manual context
            if "context" not in payload:
                payload["context"] = {}
            payload["context"].update(context)

        # Push to bounded queue non-blockingly
        try:
            self.queue.put_nowait(payload)
        except queue.Full:
            logger.warning("Recovery SDK local queue buffer is full. Dropping exception event.")

    def _worker_loop(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._async_worker_loop())
        self.loop.close()

    async def _async_worker_loop(self) -> None:
        async with httpx.AsyncClient() as client:
            while self.running or not self.queue.empty():
                try:
                    try:
                        # Fetch from thread-safe queue with a timeout
                        payload = self.queue.get(timeout=0.2)
                    except queue.Empty:
                        continue
                        
                    success = await self._send_with_retry(client, payload)
                    if not success:
                        logger.error("Failed to send exception event to backend API after retries.")
                    self.queue.task_done()
                except Exception as e:
                    logger.error(f"Error in SDK background event queue processor: {e}")
                    
    async def _send_with_retry(self, client: httpx.AsyncClient, payload: dict) -> bool:
        max_retries = 3
        backoff = 0.5
        
        headers = {
            "Content-Type": "application/json",
            "X-Project-ID": str(self.project_id)
        }
        
        url = f"{self.api_url}/api/v1/events"
        
        for attempt in range(max_retries):
            try:
                response = await client.post(url, json=payload, headers=headers, timeout=5.0)
                if response.status_code in (200, 201):
                    return True
                logger.warning(f"Recovery API returned status {response.status_code}: {response.text}")
            except Exception as e:
                logger.warning(f"Error sending telemetry payload (attempt {attempt+1}/{max_retries}): {e}")
                
            if attempt < max_retries - 1:
                await asyncio.sleep(backoff)
                backoff *= 2.0
                
        return False
