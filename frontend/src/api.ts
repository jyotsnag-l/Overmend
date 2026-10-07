const envApiUrl = import.meta.env.VITE_API_URL;

function getApiUrl(): string {
  if (envApiUrl && envApiUrl.trim()) {
    return envApiUrl.trim();
  }
  if (typeof window !== 'undefined') {
    const { hostname, port, origin } = window.location;
    // When running locally on Vite dev server (e.g. port 3000, 5173)
    if ((hostname === 'localhost' || hostname === '127.0.0.1') && port !== '8000') {
      return 'http://localhost:8000';
    }
    // When deployed in production or served directly by FastAPI
    if (origin && origin !== 'null') {
      return origin;
    }
  }
  return 'http://localhost:8000';
}

export const API_URL = getApiUrl();



// Available simulated profiles for testing authorization policies
export interface Profile {
  id: string;
  email: string;
  name: string;
  role: 'OWNER' | 'ADMIN' | 'REVIEWER' | 'ENGINEER' | 'VIEWER';
}

export const SIMULATED_PROFILES: Profile[] = [
  { id: 'usr_jyotsna', email: 'jyotsnag.amcec@gmail.com', name: 'Jyotsna G L', role: 'OWNER' },
  { id: 'usr_admin', email: 'admin_user@example.com', name: 'Admin User', role: 'ADMIN' },
  { id: 'usr_reviewer', email: 'reviewer_user@example.com', name: 'Security Reviewer', role: 'REVIEWER' },
  { id: 'usr_engineer', email: 'engineer_user@example.com', name: 'Software Engineer', role: 'ENGINEER' },
  { id: 'usr_viewer', email: 'viewer_user@example.com', name: 'ReadOnly Viewer', role: 'VIEWER' }
];

// Cleanse legacy seed-org from browser localStorage
if (typeof window !== 'undefined') {
  if (localStorage.getItem('active_org_id') === 'org_seed') {
    localStorage.setItem('active_org_id', 'org_overmend');
  }
  if (localStorage.getItem('active_user_email') === 'seed_user@example.com') {
    localStorage.setItem('active_user_email', 'jyotsnag.amcec@gmail.com');
    localStorage.setItem('active_user_id', 'usr_jyotsna');
    localStorage.setItem('active_user_name', 'Jyotsna G L');
  }
}

export function getSimulatedProfile(): Profile {
  const email = localStorage.getItem('active_user_email') || 'jyotsnag.amcec@gmail.com';
  const profile = SIMULATED_PROFILES.find(p => p.email === email);
  return profile || SIMULATED_PROFILES[0];
}

export function setSimulatedProfile(email: string) {
  const profile = SIMULATED_PROFILES.find(p => p.email === email);
  if (profile) {
    localStorage.setItem('active_user_id', profile.id);
    localStorage.setItem('active_user_email', profile.email);
    localStorage.setItem('active_user_name', profile.name);
    localStorage.setItem('active_user_role', profile.role);
  }
}

// Set up default values on first load
if (typeof window !== 'undefined' && !localStorage.getItem('active_user_email')) {
  setSimulatedProfile('jyotsnag.amcec@gmail.com');
  localStorage.setItem('active_org_id', 'org_overmend');
}

export function getHeaders(): Record<string, string> {
  const email = (typeof window !== 'undefined' && localStorage.getItem('active_user_email')) || 'jyotsnag.amcec@gmail.com';
  const role = (typeof window !== 'undefined' && localStorage.getItem('active_user_role')) || 'OWNER';
  const orgId = (typeof window !== 'undefined' && localStorage.getItem('active_org_id')) || 'org_overmend';
  const userId = (typeof window !== 'undefined' && localStorage.getItem('active_user_id')) || 'usr_jyotsna';
  const name = (typeof window !== 'undefined' && localStorage.getItem('active_user_name')) || 'Jyotsna G L';

  return {
    'Content-Type': 'application/json',
    'X-User-ID': userId,
    'X-User-Email': email,
    'X-User-Name': name,
    'X-Organization-ID': orgId,
    'X-User-Role': role
  };
}

// ----------------- Type Declarations -----------------

export interface HealthStatus {
  status: 'healthy' | 'unhealthy';
  database: 'healthy' | 'unhealthy';
  redis: 'healthy' | 'unhealthy';
  celery: 'healthy' | 'unhealthy' | 'no_workers';
}

export interface Incident {
  id: string;
  project_id: string;
  organization_id: string;
  exception_type: string;
  exception_message: string;
  stack_trace: string;
  status: 'DETECTED' | 'TRIAGED' | 'LOCALIZED' | 'PATCH_GENERATED' | 'SANDBOX_RUNNING' | 'TESTED' | 'TRUST_EVALUATED' | 'DECISION' | 'PR' | 'VERIFIED' | 'REJECTED' | 'REVERTED' | 'INVESTIGATING';
  fingerprint: string;
  context: Record<string, any>;
  created_at: string;
  occurrence_count: number;
  first_seen: string;
  last_seen: string;
  error_rate: number;
  environment: string;
  affected_repository: string | null;
  affected_project: string | null;
  stack_frames: Record<string, any> | null;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  is_anomaly: boolean;
}

export interface FaultLocation {
  id: string;
  file_path: string;
  line_number: number;
  function_name: string;
  confidence: number;
}

export interface PatchCandidate {
  id: string;
  incident_id?: string;
  diff: string;
  explanation: string;
  patch_id: string | null;
  affected_files: string[] | null;
  estimated_change_scope: string | null;
  reasoning_summary: string | null;
  is_valid: boolean | null;
  created_at: string;
}

export interface SandboxExecution {
  id: string;
  stdout: string | null;
  stderr: string | null;
  exit_code: number | null;
  duration: number | null;
  resource_usage: {
    cpu_usage_pct?: number[];
    memory_mb?: number[];
    network_kb?: number[];
  };
  created_at: string;
}

export interface SandboxJobDetail {
  id: string;
  status: string;
  config: Record<string, any>;
  created_at: string;
  execution: SandboxExecution | null;
}

export interface MutationDetail {
  original_code: string;
  mutated_code: string;
  location: string;
  status: 'KILLED' | 'SURVIVED';
  test_result: string;
  explanation: string;
}

export interface TrustEvaluation {
  id: string;
  trust_score: number;
  mutation_score: number;
  evidence: {
    risk_flags?: string[];
    recommendation?: string;
    mutations_detail?: MutationDetail[];
  };
  created_at: string;
}

export interface Decision {
  id: string;
  status: 'APPROVED' | 'REJECTED' | 'PENDING_REVIEW';
  action: 'AUTO_MERGE' | 'HUMAN_REVIEW' | 'REJECT';
  reason: string;
  decided_by: string | null;
  created_at: string;
  policy_version: string | null;
  policy_checks: Record<string, any>[] | null;
  risk_flags: string[] | null;
}

export interface IncidentDetail extends Incident {
  fault_locations: FaultLocation[];
  patch_candidates: PatchCandidate[];
}

export interface PatchCandidateDetail extends PatchCandidate {
  trust_evaluation: TrustEvaluation | null;
  decision: Decision | null;
  sandbox_jobs: SandboxJobDetail[];
}

export interface ProjectPolicy {
  project_id: string;
  organization_id: string;
  auto_merge_threshold: number;
  mandatory_review_threshold: number;
  restricted_files: string[];
  anomaly_frequency_threshold: number;
  anomaly_zscore_threshold: number;
  anomaly_ewma_threshold: number;
  severity_rules: Record<string, any>;
}

export interface Repository {
  id: string;
  organization_id: string;
  project_id: string;
  name: string;
  url: string;
  created_at: string;
  last_synced_commit?: string;
  health_percentage?: number;
  active_incidents?: number;
  total_incidents?: number;
  status?: 'HEALTHY' | 'DEGRADED' | 'CRITICAL';
}

export interface AuditLog {
  id: string;
  organization_id: string;
  user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string;
  details: Record<string, any>;
  created_at: string;
}

export interface OrgAnalytics {
  active_incidents_count: number;
  resolved_incidents_count: number;
  recovery_success_rate: number;
  average_recovery_duration: number;
  average_trust_score: number;
  human_review_rate: number;
  auto_merge_rate: number;
  reverted_patch_count: number;
  mttr: number;
  mttd: number;
  incidents_over_time: { date: string; incidents: number; recovered: number }[];
  hourly_decisions_24h?: { time: string; approved: number; human_review: number; rejected: number }[];
  decisions_24h?: { approved: number; human_review: number; rejected: number; total: number };
  trust_distribution: { range: string; count: number }[];
  severity_distribution: Record<string, number>;
}

// ----------------- API Methods -----------------

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_URL}/health`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch health');
  return res.json();
}

export async function fetchIncidents(): Promise<Incident[]> {
  const res = await fetch(`${API_URL}/api/v1/incidents`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch incidents');
  return res.json();
}

export async function fetchIncidentDetail(id: string): Promise<IncidentDetail> {
  const res = await fetch(`${API_URL}/api/v1/incidents/${id}`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch incident details');
  return res.json();
}

export async function fetchPatchCandidateDetail(id: string): Promise<PatchCandidateDetail> {
  const res = await fetch(`${API_URL}/api/v1/patch-candidates/${id}`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch patch candidate details');
  return res.json();
}

export async function fetchOrgAnalytics(orgId: string): Promise<OrgAnalytics> {
  const res = await fetch(`${API_URL}/api/v1/organizations/${orgId}/analytics`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch organization analytics');
  return res.json();
}

export async function fetchRepositories(): Promise<Repository[]> {
  const res = await fetch(`${API_URL}/api/v1/repositories`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch repositories');
  return res.json();
}

export async function syncRepositories(): Promise<Repository[]> {
  const res = await fetch(`${API_URL}/api/v1/repositories/sync`, {
    method: 'POST',
    headers: getHeaders()
  });
  if (!res.ok) throw new Error('Failed to sync repositories from GitHub');
  return res.json();
}


export async function fetchProjectPolicy(projectId: string): Promise<ProjectPolicy> {
  const res = await fetch(`${API_URL}/api/v1/projects/${projectId}/policy`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch project policy');
  return res.json();
}

export async function saveProjectPolicy(projectId: string, policy: Partial<ProjectPolicy>): Promise<ProjectPolicy> {
  const res = await fetch(`${API_URL}/api/v1/projects/${projectId}/policy`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(policy)
  });
  if (!res.ok) throw new Error('Failed to save project policy');
  return res.json();
}

export async function createDecision(patchCandidateId: string, status: 'APPROVED' | 'REJECTED', reason: string): Promise<Decision> {
  const res = await fetch(`${API_URL}/api/v1/decisions`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({
      patch_candidate_id: patchCandidateId,
      status,
      reason
    })
  });
  if (!res.ok) throw new Error('Failed to submit decision');
  return res.json();
}

export async function applyPatchCandidateAndCreatePR(candidateId: string): Promise<{
  status: string;
  incident_id: string;
  patch_candidate_id: string;
  repository: string;
  branch_name: string;
  pull_request_number: number;
  pull_request_url: string;
}> {
  const res = await fetch(`${API_URL}/api/v1/patch-candidates/${candidateId}/apply-pr`, {
    method: 'POST',
    headers: getHeaders()
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to apply patch and create recovery PR');
  }
  return res.json();
}


export async function evaluateDecision(payload: {
  patch_candidate_id: string;
  trust_score: number;
  mutation_score: number;
  test_result: boolean;
  patch_size: number;
  files_changed: string[];
  sensitive_file_flags: any;
  blast_radius: number;
  repository_policy?: any;
  ci_status?: string;
}): Promise<Decision> {
  const res = await fetch(`${API_URL}/api/v1/decisions/evaluate`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error('Failed to evaluate policy');
  return res.json();
}

export async function listAuditLogs(): Promise<AuditLog[]> {
  const res = await fetch(`${API_URL}/api/v1/audit-logs`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch audit logs');
  return res.json();
}

// Trigger live incident to exercise autonomous recovery pipeline in real time
export async function triggerDemoIncident(
  type?: string,
  msg?: string,
  file?: string,
  line?: number,
  stackTrace?: string,
  commitSha?: string
): Promise<Incident> {
  const projectId = 'proj_04102d07';
  const repoName = 'jyotsnag-l/recovery-test-repo';
  const targetCommit = commitSha || undefined;

  // 1. Ensure project exists
  await fetch(`${API_URL}/api/v1/projects`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({
      id: projectId,
      name: 'recovery-test-repo',
      repository: repoName
    })
  }).catch(() => { });

  const excType = type || 'AssertionError';
  const excMsg = msg || 'assert 201 == 400 - Order exceeding stock quantity accepted with status 201 Created instead of 400 Bad Request';
  const targetFile = file || 'app/services/inventory_service.py';
  const targetLine = line || 46;
  const realStackTrace = stackTrace ||
`Traceback (most recent call last):
  File "app/services/inventory_service.py", line ${targetLine}, in validate_stock_availability
    if item.stock_quantity <= 0:
  File "tests/test_orders.py", line 44, in test_create_order_exceeding_stock_should_fail
    assert response.status_code == 400
AssertionError: assert 201 == 400
+ where 201 = <Response [201 Created]>.status_code`;

  const eventPayload: Record<string, any> = {
    project_id: projectId,
    exception_type: excType,
    exception_message: excMsg,
    stack_trace: realStackTrace,
    environment: 'production',
    file: targetFile,
    line: targetLine,
    function: 'validate_stock_availability'
  };

  if (targetCommit) {
    eventPayload.git_commit = targetCommit;
    eventPayload.commit_sha = targetCommit;
  }

  // 2. Post SDK Ingestion event
  const res = await fetch(`${API_URL}/api/v1/events`, {
    method: 'POST',
    headers: {
      ...getHeaders(),
      'X-Project-ID': projectId
    },
    body: JSON.stringify(eventPayload)
  });
  if (!res.ok) throw new Error('Failed to trigger demo incident');
  return res.json();
}

/**
 * Parses UTC ISO timestamp strings from backend SQLite/PostgreSQL accurately,
 * ensuring naive UTC strings (without 'Z' or offset) are correctly treated as UTC
 * and converted to the user's local timezone.
 */
export function parseUtcDate(dateStr: string | Date): Date {
  if (!dateStr) return new Date();
  if (dateStr instanceof Date) return dateStr;
  let str = String(dateStr).trim();
  if (!str.endsWith('Z') && !str.includes('+') && !str.includes('Z')) {
    str = str.replace(' ', 'T') + 'Z';
  }
  return new Date(str);
}

export function formatDateTime(dateStr: string | Date): string {
  const d = parseUtcDate(dateStr);
  return d.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

