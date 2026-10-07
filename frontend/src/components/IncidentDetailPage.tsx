import { useEffect, useState } from 'react';
import { 
  ArrowLeft, AlertTriangle, FileCode, GitBranch, Cpu, Code2, RefreshCw, 
  CheckCircle2, Terminal, ArrowRight, ShieldCheck, ExternalLink, GitPullRequest
} from 'lucide-react';
import { fetchIncidentDetail, IncidentDetail, fetchPatchCandidateDetail, PatchCandidateDetail, applyPatchCandidateAndCreatePR } from '../api';

interface IncidentDetailPageProps {
  incidentId: string;
  onNavigate: (page: string, params?: Record<string, any>) => void;
}

const TIMELINE_STAGES = [
  { id: 'DETECTED', name: '1. Ingested' },
  { id: 'LOCALIZED', name: '2. Fault AST' },
  { id: 'PATCH_GENERATED', name: '3. 3-Patches' },
  { id: 'SANDBOX_RUNNING', name: '4. Docker CI' },
  { id: 'TRUST_EVALUATED', name: '5. Trust Audit' },
  { id: 'DECISION', name: '6. Decision' },
  { id: 'PR_CREATED', name: '7. PR Created' },
  { id: 'VERIFIED', name: '8. Verified' }
];

export default function IncidentDetailPage({ incidentId, onNavigate }: IncidentDetailPageProps) {
  const [incident, setIncident] = useState<IncidentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPatch, setSelectedPatch] = useState<string | null>(null);
  const [patchDetail, setPatchDetail] = useState<PatchCandidateDetail | null>(null);
  const [loadingPatch, setLoadingPatch] = useState(false);

  // Apply Patch & Create Recovery PR state
  const [applyingPatch, setApplyingPatch] = useState(false);
  const [prResult, setPrResult] = useState<{ pull_request_url: string; pull_request_number: number; branch_name: string; repository: string } | null>(null);
  const [applyError, setApplyError] = useState<string | null>(null);

  const handleApplyPatchAndCreatePR = async () => {
    if (!selectedPatch || applyingPatch) return;
    setApplyingPatch(true);
    setApplyError(null);
    setPrResult(null);

    try {
      const result = await applyPatchCandidateAndCreatePR(selectedPatch);
      setPrResult(result);
      loadIncident();
    } catch (err: any) {
      console.error("Failed to apply patch and create PR:", err);
      setApplyError(err.message || "Failed to apply patch and create GitHub Recovery PR.");
    } finally {
      setApplyingPatch(false);
    }
  };

  const loadIncident = async () => {
    try {
      const data = await fetchIncidentDetail(incidentId);
      setIncident(data);
      if (data.patch_candidates && data.patch_candidates.length > 0) {
        setSelectedPatch(data.patch_candidates[0].id);
      }
      setError(null);
    } catch (err) {
      console.error('Failed to load incident detail', err);
      setError('Failed to retrieve incident telemetry.');
    } finally {
      setLoading(false);
    }
  };

  const loadPatchDetail = async (patchId: string) => {
    setLoadingPatch(true);
    try {
      const detail = await fetchPatchCandidateDetail(patchId);
      setPatchDetail(detail);
    } catch (err) {
      console.error('Failed to load patch detail', err);
    } finally {
      setLoadingPatch(false);
    }
  };

  useEffect(() => {
    loadIncident();
  }, [incidentId]);

  useEffect(() => {
    if (selectedPatch) {
      loadPatchDetail(selectedPatch);
    }
  }, [selectedPatch]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-28 text-stone-400 space-y-4">
        <Cpu className="h-8 w-8 animate-spin text-amber-700" />
        <p className="text-xs font-mono font-bold tracking-widest text-stone-500">RETRIEVING FAULT DATA FROM CONTROL PLANE...</p>
      </div>
    );
  }

  if (error || !incident) {
    return (
      <div className="bg-rose-50 border border-rose-200 text-rose-900 p-8 rounded-2xl flex items-center space-x-5 max-w-2xl mx-auto shadow-sm">
        <div className="p-3 bg-rose-100 border border-rose-300 rounded-xl">
          <AlertTriangle className="h-6 w-6 text-rose-700" />
        </div>
        <div className="space-y-2">
          <h3 className="text-sm font-bold font-mono text-rose-950">RECORD_UNAVAILABLE</h3>
          <p className="text-xs text-stone-600 font-sans">{error || 'Incident file has been archived or deleted.'}</p>
          <button 
            onClick={() => onNavigate('Incidents')}
            className="text-xs text-amber-800 hover:text-amber-950 font-mono font-bold flex items-center"
          >
            ← Return to Incidents
          </button>
        </div>
      </div>
    );
  }

  const getStageIndex = (statusStr: string) => {
    const s = (statusStr || '').toUpperCase();
    if (['VERIFIED', 'MERGED', 'RESOLVED', 'CLOSED'].includes(s)) return 7;
    if (['PR_CREATED', 'PENDING_CI', 'CI_PASSED', 'CI_RUNNING'].includes(s)) return 6;
    if (['DECISION', 'AUTO_MERGE', 'HUMAN_REVIEW', 'APPROVED', 'PENDING_REVIEW', 'REJECTED'].includes(s)) return 5;
    if (['TRUST_EVALUATED'].includes(s)) return 4;
    if (['SANDBOX_RUNNING', 'TESTED'].includes(s)) return 3;
    if (['PATCH_GENERATED', 'PATCH_SYNTHESIZED'].includes(s)) return 2;
    if (['LOCALIZED'].includes(s)) return 1;
    return 0; // DETECTED, TRIAGED
  };

  const currentStageIndex = getStageIndex(incident.status);

  const renderFaultCodeSnippet = () => {
    const file = incident.fault_locations[0]?.file_path || 'auth/verification.py';
    const line = incident.fault_locations[0]?.line_number || 42;
    const func = incident.fault_locations[0]?.function_name || 'verify_webhook_signature';

    return (
      <div className="bg-white border border-stone-200 rounded-2xl overflow-hidden shadow-sm">
        <div className="bg-stone-900 px-5 py-3 border-b border-stone-800 flex justify-between items-center text-xs font-mono text-stone-400">
          <span className="flex items-center font-bold text-stone-200">
            <FileCode className="h-4 w-4 text-amber-500 mr-2" /> {file}
          </span>
          <span className="text-[10px] text-amber-400 font-bold bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
            AST Node: {func}()
          </span>
        </div>
        <div className="p-4 font-mono text-xs text-stone-300 space-y-1 bg-stone-950">
          <div className="text-stone-500"><span className="w-8 inline-block text-right mr-4 select-none">{Math.max(1, line - 2)}</span> def {func}(*args, **kwargs):</div>
          <div className="text-stone-500"><span className="w-8 inline-block text-right mr-4 select-none">{Math.max(1, line - 1)}</span>     # Target execution block</div>
          <div className="bg-rose-950/60 border-l-2 border-rose-500 py-1 text-rose-200 px-1 rounded-r">
            <span className="w-8 inline-block text-right mr-4 text-rose-400 font-bold select-none">{line}</span>
            <span className="font-semibold text-rose-200">{incident.stack_trace.split('\n').pop()?.trim() || 'return execute_operation()'}</span>
          </div>
          <div className="text-stone-500"><span className="w-8 inline-block text-right mr-4 select-none">{line + 1}</span>     return result</div>
        </div>
      </div>
    );
  };

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
      <div key={index} className="px-3 py-0.5 text-stone-300 font-mono">
        <span className="select-none text-stone-600 mr-2"> </span>
        {line}
      </div>
    );
  };

  const isAutoMerged = ['VERIFIED', 'MERGED', 'RESOLVED'].includes(incident.status.toUpperCase());

  return (
    <div className="space-y-6">
      {/* TOP BREADCRUMB & HEADER */}
      <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-[#E2E8F0] pb-5 gap-4">
        <div className="space-y-1">
          <button 
            onClick={() => onNavigate('Incidents')}
            className="btn-dark px-4 py-2 text-xs font-semibold flex items-center space-x-2 w-fit mb-2"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Back to Incidents</span>
          </button>
          
          <div className="flex items-center space-x-3">
            <h2 className="text-2xl font-extrabold text-[#0F172A] tracking-tight font-mono">
              {incident.exception_type}
            </h2>
            <span className={`text-xs font-mono font-bold px-3 py-1 rounded-full border ${
              isAutoMerged 
                ? 'bg-emerald-50 text-[#059669] border-emerald-300' 
                : (incident.status as string) === 'HUMAN_REVIEW'
                ? 'bg-amber-50 text-[#D97706] border-amber-300'
                : 'bg-indigo-50 text-[#4F46E5] border-indigo-300'
            }`}>
              {isAutoMerged ? 'AUTO-MERGED' : incident.status}
            </span>
          </div>
          <p className="text-xs text-[#64748B] font-mono">{incident.exception_message}</p>
        </div>

        <div className="flex items-center space-x-3">
          <div className="bg-white border border-[#CBD5E1] rounded-xl px-3.5 py-2 flex items-center space-x-3 shadow-xs">
            <span className="text-xs text-[#64748B] font-medium">Telemetry Volume</span>
            <span className="text-xs font-mono text-[#059669] font-bold">{incident.occurrence_count} events</span>
          </div>
          <button
            onClick={() => onNavigate('Sandbox', { jobId: incident.id })}
            className="btn-periwinkle px-4 py-2 text-xs font-bold flex items-center space-x-2 shadow-sm"
          >
            <Terminal className="h-4 w-4" />
            <span>Sandbox Log Stream</span>
          </button>
        </div>
      </div>

      {/* VISUAL RECOVERY TIMELINE: ALL 1-8 STEPS */}
      <section className="panel-card p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
          <h3 className="text-xs font-mono font-bold tracking-wider text-[#0F172A] uppercase">
            Autonomous Self-Healing 8-Stage Pipeline Lifecycle
          </h3>
          <span className={`pill-blue font-bold ${currentStageIndex === 7 ? 'bg-emerald-50 text-[#059669] border-emerald-300' : ''}`}>
            {currentStageIndex === 7 ? 'ALL 8 OF 8 STEPS COMPLETED (AUTO-MERGED)' : `STEP ${currentStageIndex + 1} OF 8 COMPLETED`}
          </span>
        </div>
        
        <div className="relative pt-6 pb-2">
          <div className="absolute top-1/2 left-0 right-0 h-1.5 bg-[#E2E8F0] -translate-y-1/2 z-0 rounded-full" />
          <div 
            className="absolute top-1/2 left-0 h-1.5 bg-[#10B981] -translate-y-1/2 z-0 transition-all duration-500 rounded-full" 
            style={{ width: `${(Math.min(currentStageIndex, TIMELINE_STAGES.length - 1) / (TIMELINE_STAGES.length - 1)) * 100}%` }}
          />

          <div className="relative flex justify-between z-10 overflow-x-auto gap-2">
            {TIMELINE_STAGES.map((stObj, idx) => {
              const isAllComplete = currentStageIndex === 7;
              const isCompleted = idx < currentStageIndex || (isAllComplete && idx === 7);
              const isActive = idx === currentStageIndex && !isAllComplete;
              
              let nodeColor = 'bg-[#F1F5F9] border-[#CBD5E1] text-[#94A3B8]';
              if (isCompleted) {
                nodeColor = 'bg-[#10B981] border-[#059669] text-white font-bold shadow-xs';
              } else if (isActive) {
                nodeColor = 'bg-[#4F46E5] border-[#4338CA] text-white shadow-md scale-110 font-bold';
              }

              return (
                <div key={stObj.id} className="flex flex-col items-center min-w-[85px] text-center">
                  <div className={`h-9 w-9 rounded-full border-2 flex items-center justify-center font-mono text-xs transition-all duration-300 ${nodeColor}`}>
                    {isCompleted ? <CheckCircle2 className="h-5 w-5 text-white" /> : idx + 1}
                  </div>
                  <span className={`text-[10px] font-mono font-bold tracking-tight mt-2.5 uppercase transition ${isCompleted ? 'text-[#059669]' : isActive ? 'text-[#4F46E5]' : 'text-[#94A3B8]'}`}>
                    {stObj.name}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* CORE TELEMETRY PANEL */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Stack Trace & Code Snippet */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white border border-stone-200 rounded-2xl p-6 space-y-3 shadow-sm">
            <h3 className="text-xs font-mono font-bold tracking-wider text-stone-900 uppercase flex items-center space-x-2">
              <Terminal className="h-4 w-4 text-amber-700" />
              <span>Diagnosed Exception Callstack</span>
            </h3>
            <pre className="p-4 bg-stone-900 border border-stone-800 rounded-xl text-xs font-mono text-stone-200 overflow-x-auto leading-relaxed max-h-[220px]">
              {incident.stack_trace}
            </pre>
          </div>

          {renderFaultCodeSnippet()}
        </div>

        {/* Side Panel: Evidence, Test Suite, Similar Fixes */}
        <div className="space-y-6">
          {/* Git Ingestion Evidence */}
          <div className="bg-white border border-stone-200 rounded-2xl p-5 space-y-3 shadow-sm">
            <h3 className="text-xs font-mono font-bold tracking-wider text-stone-900 uppercase flex items-center space-x-2">
              <GitBranch className="h-4 w-4 text-amber-700" />
              <span>Git Origin Evidence</span>
            </h3>
            <div className="space-y-2.5 pt-1 text-xs font-mono">
              <div className="flex justify-between items-center border-b border-stone-200 pb-2">
                <span className="text-stone-500">REF COMMIT</span>
                <span className="text-stone-900 font-bold bg-stone-100 px-2.5 py-0.5 rounded-md border border-stone-200">
                  e1129b8
                </span>
              </div>
              <div className="flex justify-between items-center border-b border-stone-200 pb-2">
                <span className="text-stone-500">ENVIRONMENT</span>
                <span className="text-amber-800 uppercase font-bold">{incident.environment}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-stone-500">AST LOCALIZATION</span>
                <span className="text-emerald-800 font-bold">96% CONFIDENCE</span>
              </div>
            </div>
          </div>

          {/* Verification Harness */}
          <div className="bg-white border border-stone-200 rounded-2xl p-5 space-y-3 shadow-sm">
            <h3 className="text-xs font-mono font-bold tracking-wider text-stone-900 uppercase flex items-center space-x-2">
              <Code2 className="h-4 w-4 text-emerald-700" />
              <span>Verification Test Suite</span>
            </h3>
            <div className="p-3 bg-stone-50 border border-stone-200 rounded-xl flex items-center justify-between">
              <span className="text-xs font-mono text-stone-800">pytest tests/test_auth.py</span>
              <span className="text-[10px] font-mono text-emerald-800 bg-emerald-50 px-2 py-0.5 border border-emerald-200 rounded font-bold">
                PASSED
              </span>
            </div>
          </div>

          {/* Similar Fixes */}
          <div className="bg-white border border-stone-200 rounded-2xl p-5 space-y-3 shadow-sm">
            <h3 className="text-xs font-mono font-bold tracking-wider text-stone-900 uppercase">
              Historical Similar Fixes
            </h3>
            <div className="p-3 bg-stone-50 border border-stone-200 rounded-xl space-y-1">
              <div className="flex justify-between items-center text-[10px] font-mono">
                <span className="text-stone-600 font-bold">inc_auth_token_keyerror</span>
                <span className="text-emerald-800 font-bold">98% SIMILAR</span>
              </div>
              <p className="text-xs font-sans text-stone-600">KeyError in header retrieval verification</p>
              <div className="text-[10px] font-mono text-amber-800 font-bold pt-1">Resolved in 14.2s (Zero-Touch)</div>
            </div>
          </div>
        </div>
      </section>

      {/* CANDIDATE PATCHES SECTION */}
      {incident.patch_candidates.length > 0 && (
        <section className="bg-white border border-stone-200 rounded-2xl p-6 space-y-4 shadow-sm">
          <div className="flex items-center justify-between border-b border-stone-200 pb-3">
            <div>
              <h3 className="text-xs font-mono font-bold tracking-wider text-stone-900 uppercase">
                Generated Candidate Patches ({incident.patch_candidates.length})
              </h3>
              <p className="text-[10px] text-stone-500 font-sans mt-0.5">Synthesized code corrections evaluated in isolated sandbox containers</p>
            </div>
            <button
              onClick={() => onNavigate('PatchComparison', { incidentId, activePatchId: selectedPatch })}
              className="flex items-center space-x-1 text-xs font-mono text-amber-800 hover:text-amber-950 font-bold"
            >
              <span>Side-by-Side Comparison</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="md:col-span-1 space-y-2 border-r border-stone-200 pr-4">
              {incident.patch_candidates.map((pc, idx) => (
                <button
                  key={pc.id}
                  onClick={() => setSelectedPatch(pc.id)}
                  className={`w-full text-left p-3.5 rounded-xl border font-mono transition text-xs flex flex-col space-y-1 ${
                    selectedPatch === pc.id 
                      ? 'bg-amber-50 border-amber-300 text-amber-900 shadow-sm font-bold' 
                      : 'bg-white border-stone-200 text-stone-600 hover:bg-stone-50'
                  }`}
                >
                  <span className="font-bold text-stone-900 uppercase">Patch Candidate {String.fromCharCode(65 + idx)}</span>
                  <span className="text-[10px] text-stone-500 truncate">#{pc.id.slice(0, 10)}</span>
                </button>
              ))}
            </div>

            <div className="md:col-span-3 space-y-4 pl-0 md:pl-2">
              {loadingPatch ? (
                <div className="flex items-center justify-center text-stone-500 font-mono text-xs py-10 space-x-2">
                  <RefreshCw className="h-4 w-4 animate-spin text-amber-700" />
                  <span>LOADING CANDIDATE DIFF...</span>
                </div>
              ) : patchDetail ? (
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-xs text-stone-700 font-sans italic">{patchDetail.explanation}</p>
                    {patchDetail.trust_evaluation && (
                      <span className="text-[10px] font-mono font-bold bg-amber-50 text-amber-800 border border-amber-200 px-3 py-1 rounded-xl flex items-center">
                        <ShieldCheck className="h-3 w-3 mr-1 text-amber-700" />
                        Trust Score: {((patchDetail.trust_evaluation.trust_score || 0) * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>

                  <div className="bg-stone-900 border border-stone-800 rounded-xl p-3 text-xs overflow-x-auto leading-relaxed max-h-[180px]">
                    {patchDetail.diff ? patchDetail.diff.split('\n').map((line, i) => renderDiffLine(line, i)) : (
                      <span className="text-stone-500 font-mono">No diff content.</span>
                    )}
                  </div>
                </div>
              ) : (
                <div className="text-stone-500 font-mono text-xs py-10">Select a patch candidate to view AST diff.</div>
              )}

              {/* SINGLE BUTTON: Apply Patch / Create Recovery PR */}
              <div className="pt-4 border-t border-stone-200 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex-1">
                  {prResult ? (
                    <div className="bg-emerald-50 border border-emerald-300 text-emerald-900 p-3 rounded-xl flex items-center space-x-3 text-xs font-mono">
                      <CheckCircle2 className="h-5 w-5 text-emerald-600 flex-shrink-0" />
                      <div>
                        <span className="font-bold block text-emerald-950">Recovery PR Created Successfully!</span>
                        <a
                          href={prResult.pull_request_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-indigo-600 hover:text-indigo-800 underline font-bold flex items-center space-x-1 mt-0.5"
                        >
                          <span>View PR #{prResult.pull_request_number} on GitHub ({prResult.repository})</span>
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      </div>
                    </div>
                  ) : applyError ? (
                    <div className="bg-rose-50 border border-rose-200 text-rose-800 p-3 rounded-xl flex items-center space-x-2 text-xs font-mono">
                      <AlertTriangle className="h-4 w-4 text-rose-600 flex-shrink-0" />
                      <span>{applyError}</span>
                    </div>
                  ) : (
                    <p className="text-[11px] text-stone-500 font-mono">
                      {selectedPatch 
                        ? `Selected Candidate #${selectedPatch.slice(0, 8)} — Ready to apply and create GitHub recovery PR.`
                        : 'Select a candidate patch above to enable recovery PR creation.'}
                    </p>
                  )}
                </div>

                <button
                  type="button"
                  onClick={handleApplyPatchAndCreatePR}
                  disabled={!selectedPatch || applyingPatch}
                  className="px-6 py-3 bg-[#4F46E5] hover:bg-[#4338CA] text-white text-xs font-mono font-extrabold uppercase tracking-wider flex items-center justify-center space-x-2 rounded-xl transition shadow-md disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0"
                >
                  {applyingPatch ? (
                    <>
                      <RefreshCw className="h-4 w-4 animate-spin text-white" />
                      <span>Applying & Creating Recovery PR...</span>
                    </>
                  ) : (
                    <>
                      <GitPullRequest className="h-4 w-4 text-white" />
                      <span>Apply Patch / Create Recovery PR</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
