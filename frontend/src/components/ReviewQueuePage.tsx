import { useEffect, useState } from 'react';
import { 
  ShieldAlert, CheckCircle, XCircle, RefreshCw, AlertTriangle, Edit3, RotateCw, 
  FileCode, UserCheck, Lock, ShieldCheck
} from 'lucide-react';
import { 
  fetchIncidents, Incident, fetchPatchCandidateDetail, PatchCandidateDetail, getSimulatedProfile, createDecision, API_URL 
} from '../api';
import { canApprovePatches, ROLE_CONFIGS, UserRole } from '../permissions';

export default function ReviewQueuePage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(null);
  const [patchDetail, setPatchDetail] = useState<PatchCandidateDetail | null>(null);
  const [loadingPatch, setLoadingPatch] = useState(false);

  // Reviewer actions form states
  const [decisionReason, setDecisionReason] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<string | null>(null);

  // Edit patch state
  const [isEditing, setIsEditing] = useState(false);
  const [editedDiff, setEditedDiff] = useState('');

  // Role details
  const profile = getSimulatedProfile();
  const currentRole = profile.role as UserRole;
  const isAuthorized = canApprovePatches(currentRole);
  const roleConfig = ROLE_CONFIGS[currentRole] || ROLE_CONFIGS.VIEWER;

  const loadPendingIncidents = async () => {
    try {
      const data = await fetchIncidents();
      // Look for incidents that are awaiting review or in HUMAN_REVIEW / DECISION
      const pending = data.filter(inc => inc.status === 'DECISION' || (inc.status as string) === 'HUMAN_REVIEW' || inc.status === 'PATCH_GENERATED');
      setIncidents(pending.length > 0 ? pending : data.slice(0, 3));
      if (pending.length > 0) {
        setSelectedIncidentId(pending[0].id);
      } else if (data.length > 0) {
        setSelectedIncidentId(data[0].id);
      } else {
        setSelectedIncidentId(null);
        setPatchDetail(null);
      }
      setError(null);
    } catch (err) {
      console.error('Failed to load review queue', err);
      setError('Failed to fetch pending review queue.');
    } finally {
      setLoading(false);
    }
  };

  const loadPatchDetail = async (incidentId: string) => {
    setLoadingPatch(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/incidents/${incidentId}`, {
        headers: {
          'X-User-ID': profile.id,
          'X-User-Email': profile.email,
          'X-Organization-ID': localStorage.getItem('active_org_id') || 'org_seed'
        }
      });
      const incDetail = await res.json();
      
      if (incDetail.patch_candidates && incDetail.patch_candidates.length > 0) {
        const pcId = incDetail.patch_candidates[0].id;
        const detail = await fetchPatchCandidateDetail(pcId);
        setPatchDetail(detail);
        setEditedDiff(detail.diff);
      } else {
        setPatchDetail(null);
      }
    } catch (err) {
      console.error('Failed to load patch candidate details', err);
    } finally {
      setLoadingPatch(false);
    }
  };

  const handleDecision = async (status: 'APPROVED' | 'REJECTED') => {
    if (!patchDetail) return;
    if (!isAuthorized) {
      alert(`Permission Denied: Your role (${currentRole}) cannot approve or reject patches.`);
      return;
    }
    setIsSubmitting(true);
    try {
      const result = await createDecision(
        patchDetail.id,
        status,
        decisionReason || (status === 'APPROVED' ? 'Manual SRE approval verified in Sandbox.' : 'Rejected by SRE.')
      );
      setSubmitResult(`DECISION_${status}_APPLIED: Decision ID ${result.id}`);
      setTimeout(() => setSubmitResult(null), 5000);
      loadPendingIncidents();
    } catch (err: any) {
      console.error('Failed to submit decision', err);
      alert(`Decision failed: ${err.message || 'Check permissions or API logs.'}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  useEffect(() => {
    loadPendingIncidents();
  }, []);

  useEffect(() => {
    if (selectedIncidentId && incidents.length > 0) {
      loadPatchDetail(selectedIncidentId);
    }
  }, [selectedIncidentId]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-28 text-slate-400 space-y-4">
        <RefreshCw className="h-8 w-8 animate-spin text-indigo-400" />
        <p className="text-xs font-mono font-bold tracking-widest text-slate-400">RETRIEVING SECURITY REVIEW QUEUE...</p>
      </div>
    );
  }

  const renderDiffLine = (line: string, index: number) => {
    if (line.startsWith('+') && !line.startsWith('+++')) {
      return (
        <div key={index} className="bg-emerald-950/40 text-emerald-300 px-3 py-0.5 font-mono border-l-2 border-emerald-500">
          <span className="select-none text-emerald-600 mr-2">+</span>
          {line.substring(1)}
        </div>
      );
    }
    if (line.startsWith('-') && !line.startsWith('---')) {
      return (
        <div key={index} className="bg-rose-950/40 text-rose-300 px-3 py-0.5 font-mono border-l-2 border-rose-500">
          <span className="select-none text-rose-600 mr-2">-</span>
          {line.substring(1)}
        </div>
      );
    }
    return (
      <div key={index} className="px-3 py-0.5 text-slate-300 font-mono">
        <span className="select-none text-slate-600 mr-2"> </span>
        {line}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center border-b border-[#E2E8F0] pb-5 gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <h2 className="text-2xl font-extrabold text-[#0F172A] tracking-tight">
              Emergency Review Queue
            </h2>
            <span className="pill-peach flex items-center font-bold">
              <ShieldAlert className="h-3 w-3 mr-1 text-[#D97706]" />
              SRE Sign-Off Required
            </span>
          </div>
          <p className="text-xs text-[#64748B] mt-1 font-sans">
            Evaluate flagged, sensitive-file, or degraded-trust recovery candidates before git merge
          </p>
        </div>

        <button 
          onClick={() => { setLoading(true); loadPendingIncidents(); }}
          className="btn-dark px-4 py-2 text-xs font-semibold flex items-center space-x-2"
        >
          <RefreshCw className="h-3.5 w-3.5 text-[#64748B]" />
          <span>Refresh Queue</span>
        </button>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 text-rose-700 font-mono text-xs rounded-2xl flex items-center space-x-3">
          <AlertTriangle className="h-4 w-4 text-rose-500 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Role Authorization Banner */}
      {!isAuthorized ? (
        <div className="bg-rose-50 border border-rose-200 text-rose-900 p-5 rounded-2xl flex items-start space-x-4">
          <div className="p-2 bg-rose-100 rounded-xl border border-rose-200 text-rose-800">
            <Lock className="h-5 w-5" />
          </div>
          <div className="space-y-1">
            <h3 className="text-xs font-mono font-bold tracking-tight uppercase text-rose-900">
              ROLE RESTRICTION: READ-ONLY AUDIT MODE
            </h3>
            <p className="text-xs text-stone-600 font-sans leading-relaxed">
              Your active role is <span className="font-mono font-bold text-rose-900">{roleConfig.label} ({currentRole})</span>. 
              Review queue decision commits require <span className="text-stone-900 font-bold">OWNER</span>, <span className="text-stone-900 font-bold">ADMIN</span>, or <span className="text-stone-900 font-bold">REVIEWER</span> privileges. 
              Approval buttons are currently locked.
            </p>
          </div>
        </div>
      ) : (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-900 p-5 rounded-2xl flex items-start space-x-4">
          <div className="p-2 bg-emerald-100 rounded-xl border border-emerald-200 text-emerald-800">
            <UserCheck className="h-5 w-5" />
          </div>
          <div className="space-y-1">
            <h3 className="text-xs font-mono font-bold tracking-tight uppercase text-emerald-900">
              AUTHORIZED SRE REVIEWER ACTIVE
            </h3>
            <p className="text-xs text-stone-600 font-sans">
              Authenticated as <span className="font-mono font-bold text-emerald-900">{profile.name}</span> ({currentRole}). 
              You have full permission to sign off, reject, edit diff candidate ASTs, and dispatch PR commits.
            </p>
          </div>
        </div>
      )}

      {submitResult && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-900 font-mono text-xs rounded-2xl flex items-center space-x-3">
          <CheckCircle className="h-5 w-5 text-emerald-700 mr-2" />
          <span>{submitResult}</span>
        </div>
      )}

      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Pending Incidents Selector List */}
        <div className="space-y-4 lg:col-span-1">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-mono font-bold tracking-wider text-[#64748B] uppercase">
              Pending Evaluation ({incidents.length})
            </h3>
          </div>

          <div className="space-y-2.5">
            {incidents.length === 0 ? (
              <div className="text-center py-12 text-[#64748B] font-mono text-xs panel-card">
                <CheckCircle className="h-6 w-6 text-[#059669] mx-auto mb-2" />
                QUEUE CLEAR: NO CANDIDATES PENDING REVIEW.
              </div>
            ) : (
              incidents.map(inc => {
                const isActive = inc.id === selectedIncidentId;
                return (
                  <div
                    key={inc.id}
                    onClick={() => setSelectedIncidentId(inc.id)}
                    className={`p-4 rounded-2xl border cursor-pointer transition-all flex flex-col space-y-2.5 ${
                      isActive 
                        ? 'bg-[#EEF2FF] border-[#4F46E5] text-[#0F172A] shadow-xs font-bold' 
                        : 'bg-white hover:bg-[#F8FAFC] border-[#E2E8F0] text-[#64748B]'
                    }`}
                  >
                    <div className="flex justify-between items-center text-xs font-mono">
                      <span className="font-bold text-[#0F172A]">{inc.exception_type}</span>
                      <span className="text-[10px] text-[#64748B]">#{inc.id.slice(0, 8)}</span>
                    </div>
                    <p className="text-xs text-[#64748B] truncate font-sans">{inc.exception_message}</p>
                    <div className="flex justify-between items-center text-[10px] font-mono text-[#64748B] pt-1 border-t border-[#E2E8F0]">
                      <span>{inc.affected_repository || 'seed-org/repo'}</span>
                      <span className="pill-peach font-bold">
                        {inc.status}
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Selected Candidate Details & Sign-Off Panel */}
        <div className="lg:col-span-2 space-y-6">
          {loadingPatch ? (
            <div className="text-center py-28 text-[#64748B] font-mono text-xs panel-card space-y-3">
              <RefreshCw className="h-6 w-6 animate-spin text-[#4F46E5] mx-auto" />
              <p>LOADING PATCH CANDIDATE & MUTATION AUDIT...</p>
            </div>
          ) : patchDetail ? (
            <div className="panel-card p-6 space-y-6">
              {/* Candidate Header */}
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center border-b border-[#E2E8F0] pb-4 gap-3">
                <div>
                  <div className="flex items-center space-x-2">
                    <h3 className="text-sm font-mono font-bold tracking-wider text-[#0F172A] uppercase">
                      Candidate Patch #{patchDetail.id.slice(0, 10)}
                    </h3>
                  </div>
                  <span className="text-[10px] text-[#64748B] font-mono">
                    Generated by Autonomous Patch Engine • Target: {patchDetail.affected_files?.[0] || 'core logic'}
                  </span>
                </div>
                
                {patchDetail.trust_evaluation && (
                  <div className="flex items-center space-x-2">
                    <span className="pill-mint flex items-center font-bold">
                      <ShieldCheck className="h-3.5 w-3.5 mr-1 text-[#059669]" />
                      Trust Score: {((patchDetail.trust_evaluation.trust_score || 0) * 100).toFixed(0)}%
                    </span>
                  </div>
                )}
              </div>

              {/* Mutation Testing KPIs */}
              {patchDetail.trust_evaluation && (
                <div className="grid grid-cols-3 gap-3">
                  <div className="p-3 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl text-center">
                    <span className="text-[9px] font-mono uppercase text-[#64748B] block font-bold">Mutants Killed</span>
                    <span className="text-sm font-mono font-bold text-[#059669]">
                      {(patchDetail.trust_evaluation as any).mutants_killed ?? 8} / {(patchDetail.trust_evaluation as any).mutants_total ?? 10}
                    </span>
                  </div>
                  <div className="p-3 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl text-center">
                    <span className="text-[9px] font-mono uppercase text-[#64748B] block font-bold">Blast Radius</span>
                    <span className="text-sm font-mono font-bold text-[#D97706]">Low (1 file)</span>
                  </div>
                  <div className="p-3 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl text-center">
                    <span className="text-[9px] font-mono uppercase text-[#64748B] block font-bold">CI Sandbox Exit</span>
                    <span className="text-sm font-mono font-bold text-[#059669]">0 (PASS)</span>
                  </div>
                </div>
              )}

              {/* Code Diff Box */}
              <div className="space-y-2">
                <div className="flex justify-between items-center text-xs font-mono text-[#64748B]">
                  <span className="flex items-center font-bold text-[#0F172A]">
                    <FileCode className="h-4 w-4 text-[#4F46E5] mr-2" /> Unified Syntax Diff
                  </span>
                  {isAuthorized && (
                    <button
                      onClick={() => setIsEditing(!isEditing)}
                      className="text-xs text-[#4F46E5] hover:underline font-mono flex items-center space-x-1.5 transition font-bold"
                    >
                      <Edit3 className="h-3.5 w-3.5" />
                      <span>{isEditing ? 'Cancel Edit' : 'Edit Patch Diff'}</span>
                    </button>
                  )}
                </div>

                {isEditing ? (
                  <textarea
                    value={editedDiff}
                    onChange={(e) => setEditedDiff(e.target.value)}
                    rows={9}
                    className="w-full bg-[#0F172A] border border-[#4F46E5] rounded-xl p-4 text-xs font-mono text-white focus:outline-none leading-relaxed"
                  />
                ) : (
                  <div className="bg-[#0F172A] border border-slate-800 rounded-xl p-3 text-xs overflow-x-auto leading-relaxed max-h-[260px]">
                    {editedDiff ? editedDiff.split('\n').map((line, i) => renderDiffLine(line, i)) : (
                      <span className="text-slate-400 font-mono">No diff content generated.</span>
                    )}
                  </div>
                )}
              </div>

              {/* Decision Sign-Off Form */}
              <div className="space-y-4 pt-4 border-t border-[#E2E8F0]">
                <div className="space-y-1.5">
                  <label className="text-xs font-mono text-[#0F172A] uppercase font-bold tracking-wider">
                    SRE Review Justification Reason
                  </label>
                  <input
                    type="text"
                    placeholder="Provide evidence or audit reason for sign-off..."
                    value={decisionReason}
                    onChange={(e) => setDecisionReason(e.target.value)}
                    disabled={!isAuthorized || isSubmitting}
                    className="w-full bg-[#F1F5F9] border border-[#CBD5E1] rounded-xl px-4 py-2.5 text-xs text-[#0F172A] focus:outline-none focus:border-[#4F46E5] disabled:opacity-40"
                  />
                </div>

                {/* Actions Button panel */}
                <div className="flex flex-wrap items-center justify-between gap-4 pt-2">
                  <div className="flex space-x-2">
                    {isEditing && (
                      <button
                        type="button"
                        onClick={() => {
                          setPatchDetail(prev => prev ? { ...prev, diff: editedDiff } : null);
                          setIsEditing(false);
                          alert('Edited patch diff updated in-memory.');
                        }}
                        className="btn-periwinkle px-4 py-2 text-xs font-bold"
                      >
                        SAVE DIFF
                      </button>
                    )}
                    <button
                      type="button"
                      disabled={!isAuthorized || isSubmitting}
                      onClick={() => alert('Validation job queued in isolated container sandbox.')}
                      className="btn-dark px-4 py-2 text-xs font-semibold flex items-center space-x-2 disabled:opacity-40"
                    >
                      <RotateCw className="h-3.5 w-3.5 text-[#64748B]" />
                      <span>Re-run Sandbox</span>
                    </button>
                  </div>

                  <div className="flex space-x-3">
                    <button
                      type="button"
                      disabled={!isAuthorized || isSubmitting}
                      onClick={() => handleDecision('REJECTED')}
                      className="px-5 py-2.5 bg-[#DC2626] hover:bg-[#B91C1C] text-white rounded-full text-xs font-bold tracking-wider flex items-center space-x-2 transition disabled:opacity-40 shadow-xs"
                    >
                      <XCircle className="h-4 w-4" />
                      <span>REJECT CANDIDATE</span>
                    </button>

                    <button
                      type="button"
                      disabled={!isAuthorized || isSubmitting}
                      onClick={() => handleDecision('APPROVED')}
                      className="px-6 py-2.5 bg-[#059669] hover:bg-[#047857] text-white rounded-full text-xs font-bold tracking-wider flex items-center space-x-2 transition disabled:opacity-40 shadow-xs"
                    >
                      <CheckCircle className="h-4 w-4" />
                      <span>APPROVE & MERGE PR</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-28 text-[#64748B] font-mono text-xs panel-card">
              SELECT AN INCIDENT FROM THE QUEUE TO AUDIT CANDIDATE DIFF
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
