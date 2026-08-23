import React, { useState } from 'react';
import { 
  Activity, CheckCircle2, Lock, Cpu, ShieldCheck, Check, X
} from 'lucide-react';
import { getSimulatedProfile } from '../api';
import { canManageSettings, UserRole, PERMISSION_MATRIX } from '../permissions';

export default function SettingsPage() {
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [activeTab, setActiveTab] = useState<'config' | 'rbac'>('config');

  // Form states
  const [monitoringThreshold, setMonitoringThreshold] = useState(10);
  const [dedupWindow, setDedupWindow] = useState(600);
  const [candidateCount, setCandidateCount] = useState(3);
  const [maxPatchSize, setMaxPatchSize] = useState(1000);
  const [networkPolicy, setNetworkPolicy] = useState('none');
  const [cpuLimit, setCpuLimit] = useState(0.5);
  const [memoryLimit, setMemoryLimit] = useState('512m');

  const profile = getSimulatedProfile();
  const currentRole = profile.role as UserRole;
  const userCanEdit = canManageSettings(currentRole);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!userCanEdit) {
      alert(`Permission Denied: Your role (${currentRole}) cannot edit global system parameters.`);
      return;
    }
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 4000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center border-b border-[#E2E8F0] pb-5 gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <h2 className="text-3xl font-extrabold tracking-tight text-[#0F172A]">
              System Settings & Controls
            </h2>
            <span className="pill-blue">
              Production Active
            </span>
          </div>
          <p className="text-sm text-[#64748B] mt-1 font-sans">
            Configure global telemetry thresholds, sandbox container security boundaries, and RBAC governance
          </p>
        </div>

        <div className="flex bg-[#F1F5F9] border border-[#CBD5E1] p-1 rounded-full">
          <button
            onClick={() => setActiveTab('config')}
            className={`px-4 py-1.5 rounded-full text-xs font-bold transition ${activeTab === 'config' ? 'bg-[#4F46E5] text-white shadow-sm' : 'text-[#64748B] hover:text-[#0F172A]'}`}
          >
            System Parameters
          </button>
          <button
            onClick={() => setActiveTab('rbac')}
            className={`px-4 py-1.5 rounded-full text-xs font-bold transition ${activeTab === 'rbac' ? 'bg-[#4F46E5] text-white shadow-sm' : 'text-[#64748B] hover:text-[#0F172A]'}`}
          >
            RBAC Matrix
          </button>
        </div>
      </div>

      {activeTab === 'config' && (
        <form onSubmit={handleSave} className="space-y-6 max-w-4xl mx-auto panel-card p-8">
          {saveSuccess && (
            <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 font-mono text-sm rounded-xl flex items-center justify-between font-bold">
              <span className="flex items-center"><CheckCircle2 className="h-5 w-5 mr-2 text-emerald-600" /> GLOBAL_CONFIG_SAVED_AND_APPLIED</span>
            </div>
          )}

          {!userCanEdit && (
            <div className="p-4 bg-rose-50 border border-rose-200 text-rose-700 font-mono text-sm rounded-xl flex items-center space-x-3">
              <Lock className="h-5 w-5 text-rose-500 flex-shrink-0" />
              <span>Read-Only Mode: Role {currentRole} cannot commit platform configuration changes. Requires OWNER or ADMIN.</span>
            </div>
          )}

          {/* TELEMETRY MONITORING CONFIG */}
          <section className="space-y-4">
            <div className="flex items-center space-x-2.5 border-b border-[#E2E8F0] pb-2.5">
              <Activity className="h-5 w-5 text-[#4F46E5]" />
              <h3 className="text-sm font-bold text-[#0F172A] uppercase">Telemetry Monitoring Rules</h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div className="space-y-2 p-5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-2xl">
                <label className="text-xs font-bold text-[#0F172A] uppercase tracking-wider block">Error Rate Alert Threshold (%)</label>
                <input 
                  type="number" 
                  value={monitoringThreshold} 
                  disabled={!userCanEdit}
                  onChange={(e) => setMonitoringThreshold(Number(e.target.value))}
                  className="w-full bg-white border border-[#CBD5E1] rounded-xl px-4 py-2.5 text-sm font-semibold text-[#0F172A] focus:outline-none focus:border-[#4F46E5] disabled:opacity-50"
                />
                <span className="text-xs text-[#64748B] block font-sans">Triggers self-healing pipeline if error spike crosses percentage in production.</span>
              </div>

              <div className="space-y-2 p-5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-2xl">
                <label className="text-xs font-bold text-[#0F172A] uppercase tracking-wider block">Deduplication Window (Seconds)</label>
                <input 
                  type="number" 
                  value={dedupWindow} 
                  disabled={!userCanEdit}
                  onChange={(e) => setDedupWindow(Number(e.target.value))}
                  className="w-full bg-white border border-[#CBD5E1] rounded-xl px-4 py-2.5 text-sm font-semibold text-[#0F172A] focus:outline-none focus:border-[#4F46E5] disabled:opacity-50"
                />
                <span className="text-xs text-[#64748B] block font-sans">Exceptions sharing identical fingerprints are aggregated during this sliding window.</span>
              </div>
            </div>
          </section>

          {/* RECOVERY ENGINE CONFIG */}
          <section className="space-y-4">
            <div className="flex items-center space-x-2.5 border-b border-[#E2E8F0] pb-2.5">
              <Cpu className="h-5 w-5 text-[#059669]" />
              <h3 className="text-sm font-bold text-[#0F172A] uppercase">AI Recovery Engine Policies</h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div className="space-y-2 p-5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-2xl">
                <label className="text-xs font-bold text-[#0F172A] uppercase tracking-wider block">Maximum Candidate Diffs Count</label>
                <input 
                  type="number" 
                  value={candidateCount} 
                  disabled={!userCanEdit}
                  onChange={(e) => setCandidateCount(Number(e.target.value))}
                  className="w-full bg-white border border-[#CBD5E1] rounded-xl px-4 py-2.5 text-sm font-semibold text-[#0F172A] focus:outline-none focus:border-[#4F46E5] disabled:opacity-50"
                />
                <span className="text-xs text-[#64748B] block font-sans">Limit of alternative code fixes generated per diagnosed failure event.</span>
              </div>

              <div className="space-y-2 p-5 bg-[#F8FAFC] border border-[#E2E8F0] rounded-2xl">
                <label className="text-xs font-bold text-[#0F172A] uppercase tracking-wider block">Maximum Patch Size (Bytes)</label>
                <input 
                  type="number" 
                  value={maxPatchSize} 
                  disabled={!userCanEdit}
                  onChange={(e) => setMaxPatchSize(Number(e.target.value))}
                  className="w-full bg-white border border-[#CBD5E1] rounded-xl px-4 py-2.5 text-sm font-semibold text-[#0F172A] focus:outline-none focus:border-[#4F46E5] disabled:opacity-50"
                />
                <span className="text-xs text-[#64748B] block font-sans">Safety boundary to reject overly large patches. Max is 10,000 bytes.</span>
              </div>
            </div>
          </section>

          {/* SANDBOX CONTAINER CONFIG */}
          <section className="space-y-4">
            <div className="flex items-center space-x-2.5 border-b border-[#E2E8F0] pb-2.5">
              <Lock className="h-5 w-5 text-[#2563EB]" />
              <h3 className="text-sm font-bold text-[#0F172A] uppercase">Sandbox Container Security Boundaries</h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2 p-4 bg-[#F8FAFC] border border-[#E2E8F0] rounded-2xl">
                <label className="text-xs font-bold text-[#0F172A] uppercase tracking-wider block">Container CPU Limits</label>
                <input 
                  type="number" 
                  step="0.1" 
                  value={cpuLimit} 
                  disabled={!userCanEdit}
                  onChange={(e) => setCpuLimit(Number(e.target.value))}
                  className="w-full bg-white border border-[#CBD5E1] rounded-xl px-4 py-2 text-sm font-semibold text-[#0F172A] focus:outline-none focus:border-[#4F46E5] disabled:opacity-50"
                />
              </div>

              <div className="space-y-2 p-4 bg-[#F8FAFC] border border-[#E2E8F0] rounded-2xl">
                <label className="text-xs font-bold text-[#0F172A] uppercase tracking-wider block">Container RAM Limits</label>
                <select 
                  value={memoryLimit} 
                  disabled={!userCanEdit}
                  onChange={(e) => setMemoryLimit(e.target.value)}
                  className="w-full bg-white border border-[#CBD5E1] rounded-xl px-4 py-2 text-sm font-semibold text-[#0F172A] focus:outline-none focus:border-[#4F46E5] disabled:opacity-50 cursor-pointer"
                >
                  <option value="128m">128 MB</option>
                  <option value="256m">256 MB</option>
                  <option value="512m">512 MB</option>
                  <option value="1024m">1024 MB</option>
                </select>
              </div>

              <div className="space-y-2 p-4 bg-[#F8FAFC] border border-[#E2E8F0] rounded-2xl">
                <label className="text-xs font-bold text-[#0F172A] uppercase tracking-wider block">Network Policy</label>
                <select 
                  value={networkPolicy} 
                  disabled={!userCanEdit}
                  onChange={(e) => setNetworkPolicy(e.target.value)}
                  className="w-full bg-white border border-[#CBD5E1] rounded-xl px-4 py-2 text-sm font-semibold text-[#0F172A] focus:outline-none focus:border-[#4F46E5] disabled:opacity-50 cursor-pointer"
                >
                  <option value="none">Isolated (network: none)</option>
                  <option value="bridge">Local (network: bridge)</option>
                </select>
              </div>
            </div>
            <span className="text-xs text-[#64748B] block font-sans">Docker container resources allocated for validation test suites. Network isolation is strictly enforced.</span>
          </section>

          {/* GITHUB APP INTEGRATION */}
          <section className="space-y-4 pt-4 border-t border-[#E2E8F0]">
            <div className="flex items-center space-x-2.5 border-b border-[#E2E8F0] pb-2.5">
              <ShieldCheck className="h-5 w-5 text-[#0284C7]" />
              <h3 className="text-sm font-bold text-[#0F172A] uppercase">GitHub App & Repository Connection</h3>
            </div>

            <div className="p-6 bg-[#EEF2FF] border border-[#C7D2FE] rounded-2xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
              <div className="space-y-2">
                <div className="flex items-center space-x-3">
                  <span className="text-base font-bold text-[#0F172A]">Autonomous Software Recovery App</span>
                  <span className="pill-mint">ACTIVE</span>
                </div>
                <p className="text-sm text-[#475569] max-w-xl font-sans">
                  Connect your GitHub organization or user account. Our bot listens to exception webhooks, opens automated PRs, and auto-merges verified patches.
                </p>
                <div className="flex items-center space-x-5 pt-1 text-xs font-mono text-[#64748B]">
                  <span className="flex items-center space-x-1.5">
                    <span className="h-2 w-2 rounded-full bg-[#059669] inline-block"></span>
                    <span className="font-semibold">Webhook HMAC: Verified</span>
                  </span>
                  <span className="flex items-center space-x-1.5">
                    <span className="h-2 w-2 rounded-full bg-[#4F46E5] inline-block"></span>
                    <span className="font-semibold">App ID: 104829</span>
                  </span>
                </div>
              </div>

              <div className="flex flex-col sm:flex-row gap-3 w-full md:w-auto">
                <a
                  href="https://github.com/apps/autonomous-recovery-paas/installations/new"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-periwinkle px-6 py-3 text-xs font-bold flex items-center justify-center space-x-2 shadow-sm"
                >
                  <svg className="h-4 w-4 fill-current" viewBox="0 0 24 24">
                    <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
                  </svg>
                  <span>INSTALL_GITHUB_APP</span>
                </a>
              </div>
            </div>
          </section>

          {/* Form Submission */}
          <div className="flex justify-end pt-4 border-t border-[#E2E8F0]">
            {userCanEdit ? (
              <button
                type="submit"
                className="btn-periwinkle px-8 py-3 text-sm font-bold tracking-wide shadow-sm"
              >
                SAVE SYSTEM SETTINGS
              </button>
            ) : (
              <button
                type="button"
                disabled
                className="px-6 py-3 bg-[#F1F5F9] border border-[#CBD5E1] text-[#94A3B8] rounded-full text-xs font-bold cursor-not-allowed"
              >
                LOCKED (ADMIN ONLY)
              </button>
            )}
          </div>
        </form>
      )}

      {activeTab === 'rbac' && (
        <section className="panel-card p-8 space-y-6 max-w-4xl mx-auto">
          <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-4">
            <div>
              <h3 className="text-base font-bold text-[#0F172A] uppercase flex items-center space-x-2">
                <ShieldCheck className="h-5 w-5 text-[#4F46E5]" />
                <span>Role-Based Access Control (RBAC) Matrix</span>
              </h3>
              <p className="text-sm text-[#64748B] font-sans mt-1">Authorization constraints and permission boundaries per role</p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="border-b border-[#E2E8F0] text-[#64748B] text-xs uppercase bg-[#F8FAFC]">
                  <th className="text-left py-3 px-4 font-bold">Action / Privilege</th>
                  <th className="text-center py-3 px-2">Owner</th>
                  <th className="text-center py-3 px-2">Admin</th>
                  <th className="text-center py-3 px-2">Reviewer</th>
                  <th className="text-center py-3 px-2">Engineer</th>
                  <th className="text-center py-3 px-2">Viewer</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2E8F0]">
                {PERMISSION_MATRIX.map((perm, idx) => (
                  <tr key={idx} className="hover:bg-[#F8FAFC] transition">
                    <td className="py-3 px-4">
                      <span className="font-bold text-[#0F172A] text-sm block">{perm.action}</span>
                      <span className="text-xs text-[#64748B] block font-sans mt-0.5">{perm.description}</span>
                    </td>
                    {(['OWNER', 'ADMIN', 'REVIEWER', 'ENGINEER', 'VIEWER'] as UserRole[]).map(r => {
                      const allowed = perm.allowedRoles.includes(r);
                      const isCurrent = currentRole === r;
                      return (
                        <td key={r} className={`text-center py-3 px-2 ${isCurrent ? 'bg-[#EEF2FF]' : ''}`}>
                          {allowed ? (
                            <span className="inline-flex items-center justify-center h-5 w-5 rounded-full bg-emerald-100 text-emerald-700 border border-emerald-300">
                              <Check className="h-3.5 w-3.5" />
                            </span>
                          ) : (
                            <span className="inline-flex items-center justify-center h-5 w-5 rounded-full bg-[#F1F5F9] text-[#94A3B8]">
                              <X className="h-3.5 w-3.5" />
                            </span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
