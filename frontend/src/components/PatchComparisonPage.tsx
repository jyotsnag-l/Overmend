import { useEffect, useState } from 'react';
import { 
  ArrowLeft, AlertTriangle, Columns, Eye, ShieldCheck, Terminal
} from 'lucide-react';
import { fetchIncidentDetail, IncidentDetail, fetchPatchCandidateDetail, PatchCandidateDetail } from '../api';

interface PatchComparisonPageProps {
  incidentId: string;
  activePatchId?: string;
  onNavigate: (page: string, params?: Record<string, any>) => void;
}

export default function PatchComparisonPage({ incidentId, activePatchId, onNavigate }: PatchComparisonPageProps) {
  const [incident, setIncident] = useState<IncidentDetail | null>(null);
  const [patches, setPatches] = useState<PatchCandidateDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [layoutMode, setLayoutMode] = useState<'SIDE_BY_SIDE' | 'TABBED'>('SIDE_BY_SIDE');
  const [activeTabIdx, setActiveTabIdx] = useState(0);

  const loadData = async () => {
    try {
      const incData = await fetchIncidentDetail(incidentId);
      setIncident(incData);

      if (incData.patch_candidates && incData.patch_candidates.length > 0) {
        const patchDetails = await Promise.all(
          incData.patch_candidates.map(pc => fetchPatchCandidateDetail(pc.id))
        );
        setPatches(patchDetails);
        
        if (activePatchId) {
          const idx = incData.patch_candidates.findIndex(pc => pc.id === activePatchId);
          if (idx !== -1) setActiveTabIdx(idx);
        }
      }
      setError(null);
    } catch (err) {
      console.error('Failed to load comparison data', err);
      setError('Failed to load candidate patches comparison matrix.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [incidentId]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-28 text-slate-400 space-y-4">
        <Columns className="h-8 w-8 animate-spin text-indigo-400" />
        <p className="text-xs font-mono font-bold tracking-widest text-slate-400">LOADING COMPARISON MATRIX LAYOUTS...</p>
      </div>
    );
  }

  if (error || !incident || patches.length === 0) {
    return (
      <div className="glass-card border border-rose-800/40 text-rose-300 p-8 rounded-2xl max-w-2xl mx-auto space-y-4 shadow-2xl">
        <div className="flex items-center space-x-3">
          <AlertTriangle className="h-5 w-5 text-rose-400" />
          <h3 className="text-sm font-bold font-mono text-rose-300">PATCH_MATRIX_UNAVAILABLE</h3>
        </div>
        <p className="text-xs text-slate-400 font-sans">{error || 'No patches available for this incident.'}</p>
        <button 
          onClick={() => onNavigate('IncidentDetail', { incidentId })}
          className="text-xs text-indigo-400 font-mono font-bold flex items-center hover:underline"
        >
          ← Return to incident detail
        </button>
      </div>
    );
  }

  const renderDiff = (diffText: string) => {
    const lines = diffText.split('\n');
    return (
      <div className="p-3 bg-slate-950/90 border border-slate-800 rounded-xl overflow-x-auto text-xs font-mono leading-relaxed max-h-[300px] overflow-y-auto">
        {lines.map((line, idx) => {
          let lineClass = 'text-slate-400';
          if (line.startsWith('+') && !line.startsWith('+++')) {
            lineClass = 'bg-emerald-950/40 text-emerald-300 font-bold border-l-2 border-emerald-500';
          } else if (line.startsWith('-') && !line.startsWith('---')) {
            lineClass = 'bg-rose-950/40 text-rose-300 font-bold border-l-2 border-rose-500';
          } else if (line.startsWith('@@')) {
            lineClass = 'text-indigo-400 font-bold';
          }
          return (
            <div key={idx} className={`${lineClass} px-2 py-0.5 rounded`}>
              {line}
            </div>
          );
        })}
      </div>
    );
  };

  const getSandboxBadge = (job: any) => {
    if (!job) return <span className="text-stone-500 font-mono font-bold">NO_JOB</span>;
    if (job.status === 'COMPLETED') {
      const exitCode = job.execution?.exit_code;
      return exitCode === 0 
        ? <span className="text-emerald-800 font-bold">PASSED (Exit 0)</span>
        : <span className="text-rose-900 font-bold">FAILED ({exitCode})</span>;
    }
    return <span className="text-amber-800 animate-pulse font-bold">{job.status}</span>;
  };

  const renderPatchCard = (pc: PatchCandidateDetail, letter: string) => {
    const sandboxJob = pc.sandbox_jobs?.[0];
    const trust = pc.trust_evaluation;
    
    return (
      <div key={pc.id} className="bg-white border border-stone-200 rounded-2xl p-6 flex flex-col justify-between space-y-4 shadow-sm">
        <div className="space-y-3">
          <div className="flex justify-between items-start border-b border-stone-200 pb-3">
            <div>
              <span className="text-[10px] font-mono text-stone-500 uppercase font-bold block">Candidate Alternative</span>
              <h4 className="text-sm font-mono font-bold text-stone-900 uppercase">Candidate Patch {letter}</h4>
              <span className="text-[10px] text-stone-500 font-mono">#{pc.id.slice(0, 10)}</span>
            </div>

            <div className="flex flex-col items-end space-y-1">
              {trust && (
                <span className={`text-[10px] font-mono px-2.5 py-0.5 rounded-full font-bold border ${
                  trust.trust_score >= 0.85 
                    ? 'bg-emerald-50 text-emerald-800 border-emerald-300' 
                    : 'bg-amber-50 text-amber-800 border-amber-300'
                }`}>
                  Trust: {((trust.trust_score || 0) * 100).toFixed(0)}%
                </span>
              )}
              
              <span className="text-[10px] font-mono text-stone-500">
                CI: {getSandboxBadge(sandboxJob)}
              </span>
            </div>
          </div>

          <p className="text-xs text-stone-600 font-sans italic">{pc.explanation}</p>

          {renderDiff(pc.diff)}
        </div>

        <div className="space-y-3 pt-2 border-t border-stone-200">
          <div className="grid grid-cols-2 gap-2 text-xs font-mono">
            <div className="bg-stone-50 p-2.5 rounded-xl border border-stone-200 text-center">
              <span className="text-[9px] text-stone-500 block uppercase font-bold">Scope</span>
              <span className="text-amber-800 font-bold">{pc.estimated_change_scope || '+2 lines, -1 line'}</span>
            </div>
            <div className="bg-stone-50 p-2.5 rounded-xl border border-stone-200 text-center">
              <span className="text-[9px] text-stone-500 block uppercase font-bold">Target File</span>
              <span className="text-stone-900 font-bold truncate block">{pc.affected_files?.[0] || 'verification.py'}</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            {sandboxJob && (
              <button 
                onClick={() => onNavigate('Sandbox', { jobId: sandboxJob.id })}
                className="w-full text-center py-2 bg-white hover:bg-stone-50 border border-stone-200 hover:border-amber-300 rounded-xl text-xs font-mono font-bold text-stone-700 transition flex items-center justify-center space-x-1.5 shadow-sm"
              >
                <Terminal className="h-3.5 w-3.5 text-amber-700" />
                <span>Sandbox Log</span>
              </button>
            )}

            {trust && (
              <button 
                onClick={() => onNavigate('Trust', { patchCandidateId: pc.id })}
                className="w-full text-center py-2 bg-white hover:bg-stone-50 border border-stone-200 hover:border-amber-300 rounded-xl text-xs font-mono font-bold text-amber-800 transition flex items-center justify-center space-x-1.5 shadow-sm"
              >
                <ShieldCheck className="h-3.5 w-3.5 text-amber-700" />
                <span>Trust Audit</span>
              </button>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Back button */}
      <button 
        onClick={() => onNavigate('IncidentDetail', { incidentId })}
        className="btn-dark px-4 py-2 text-xs font-semibold flex items-center space-x-2 w-fit"
      >
        <ArrowLeft className="h-4 w-4" />
        <span>Back to Incident Detail</span>
      </button>

      {/* Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between border-b border-[#E2E8F0] pb-5 gap-4">
        <div>
          <h2 className="text-2xl font-extrabold text-[#0F172A] tracking-tight">
            Patch Comparison Matrix
          </h2>
          <p className="text-xs text-[#64748B] mt-1 font-sans">
            Compare candidate diffs, AST mutant scores, and test sandbox results side-by-side
          </p>
        </div>

        {/* Layout Mode Toggles */}
        <div className="flex items-center space-x-1 bg-[#F1F5F9] border border-[#CBD5E1] p-1 rounded-full">
          <button
            onClick={() => setLayoutMode('SIDE_BY_SIDE')}
            className={`px-4 py-1.5 text-xs font-bold rounded-full transition flex items-center space-x-1.5 ${
              layoutMode === 'SIDE_BY_SIDE' 
                ? 'bg-[#4F46E5] text-white shadow-xs' 
                : 'text-[#64748B] hover:text-[#0F172A]'
            }`}
          >
            <Columns className="h-3.5 w-3.5" />
            <span>Side-by-side</span>
          </button>
          <button
            onClick={() => setLayoutMode('TABBED')}
            className={`px-4 py-1.5 text-xs font-bold rounded-full transition flex items-center space-x-1.5 ${
              layoutMode === 'TABBED' 
                ? 'bg-[#4F46E5] text-white shadow-xs' 
                : 'text-[#64748B] hover:text-[#0F172A]'
            }`}
          >
            <Eye className="h-3.5 w-3.5" />
            <span>Tabbed view</span>
          </button>
        </div>
      </div>

      {layoutMode === 'SIDE_BY_SIDE' ? (
        <section className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          {patches.map((pc, idx) => renderPatchCard(pc, String.fromCharCode(65 + idx)))}
        </section>
      ) : (
        <section className="space-y-4">
          <div className="flex border-b border-[#E2E8F0] space-x-2">
            {patches.map((pc, idx) => (
              <button
                key={pc.id}
                onClick={() => setActiveTabIdx(idx)}
                className={`px-4 py-2 border-b-2 font-mono text-xs font-bold transition ${
                  activeTabIdx === idx 
                    ? 'border-[#4F46E5] text-[#4F46E5]' 
                    : 'border-transparent text-[#64748B] hover:text-[#0F172A]'
                }`}
              >
                CANDIDATE PATCH {String.fromCharCode(65 + idx)}
              </button>
            ))}
          </div>

          <div className="max-w-3xl mx-auto">
            {patches[activeTabIdx] && renderPatchCard(patches[activeTabIdx], String.fromCharCode(65 + activeTabIdx))}
          </div>
        </section>
      )}
    </div>
  );
}
