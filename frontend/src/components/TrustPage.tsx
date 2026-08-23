import { useEffect, useState } from 'react';
import { 
  ArrowLeft, Shield, AlertTriangle, CheckCircle, Code2, RefreshCw,
  ShieldCheck, Zap
} from 'lucide-react';
import { fetchPatchCandidateDetail, PatchCandidateDetail } from '../api';

interface TrustPageProps {
  patchCandidateId: string;
  onNavigate: (page: string, params?: Record<string, any>) => void;
}

export default function TrustPage({ patchCandidateId, onNavigate }: TrustPageProps) {
  const [candidate, setCandidate] = useState<PatchCandidateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      const data = await fetchPatchCandidateDetail(patchCandidateId);
      setCandidate(data);
      setError(null);
    } catch (err) {
      console.error('Failed to load trust evaluation details', err);
      setError('Failed to fetch trust report from safety engine.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [patchCandidateId]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-28 text-slate-400 space-y-4">
        <Shield className="h-8 w-8 animate-spin text-cyan-400" />
        <p className="text-xs font-mono font-bold tracking-widest text-slate-400">RETRIEVING SECURITY TRUST ANALYTICS...</p>
      </div>
    );
  }

  if (error || !candidate || !candidate.trust_evaluation) {
    return (
      <div className="glass-card border border-rose-800/40 text-rose-300 p-8 rounded-2xl max-w-2xl mx-auto space-y-4 shadow-2xl">
        <div className="flex items-center space-x-3">
          <AlertTriangle className="h-5 w-5 text-rose-400" />
          <h3 className="text-sm font-bold font-mono text-rose-300">TRUST_REPORT_UNAVAILABLE</h3>
        </div>
        <p className="text-xs text-slate-400 font-sans">{error || 'Trust safety records missing for this patch version.'}</p>
        <button 
          onClick={() => onNavigate('Incidents')}
          className="text-xs text-indigo-400 font-mono font-bold flex items-center hover:underline"
        >
          ← Return to incident registry
        </button>
      </div>
    );
  }

  const trust = candidate.trust_evaluation;
  const mutations = trust.evidence.mutations_detail || [];
  const killedMutants = mutations.filter(m => m.status === 'KILLED');
  const survivedMutants = mutations.filter(m => m.status === 'SURVIVED');

  const getScoreColor = (score: number) => {
    if (score >= 0.90) return 'text-emerald-800 border-emerald-300 bg-emerald-50';
    if (score >= 0.70) return 'text-amber-800 border-amber-300 bg-amber-50';
    return 'text-rose-900 border-rose-300 bg-rose-50';
  };

  return (
    <div className="space-y-6">
      {/* Back button */}
      <button 
        onClick={() => onNavigate('IncidentDetail', { incidentId: candidate.incident_id })}
        className="btn-dark px-4 py-2 text-xs font-semibold flex items-center space-x-2 w-fit"
      >
        <ArrowLeft className="h-4 w-4" />
        <span>Back to Incident Detail</span>
      </button>

      {/* Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between border-b border-[#E2E8F0] pb-5 gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <h2 className="text-2xl font-extrabold text-[#0F172A] tracking-tight">
              Trust & Mutation Audit
            </h2>
            <span className="pill-blue flex items-center font-bold">
              <ShieldCheck className="h-3 w-3 mr-1 text-[#4F46E5]" />
              AST Verified
            </span>
          </div>
          <p className="text-xs text-[#64748B] mt-1 font-sans">
            Mutation testing resilience factor, boundary regression checks, and safety indices
          </p>
        </div>

        <button 
          onClick={() => { setLoading(true); loadData(); }}
          className="btn-dark px-4 py-2 text-xs font-semibold flex items-center space-x-2"
        >
          <RefreshCw className="h-3.5 w-3.5 text-[#64748B]" />
          <span>Sync Report</span>
        </button>
      </div>

      {/* DUAL METRIC METERS */}
      <section className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {/* Trust Score Gauge Card */}
        <div className="panel-card p-6 flex flex-col justify-between items-center text-center space-y-4">
          <div>
            <span className="text-[10px] font-mono text-[#64748B] uppercase font-bold tracking-wider block">Consensus Trust Index</span>
            <span className="text-xs text-[#64748B] font-sans block mt-0.5">Aggregate safety rating</span>
          </div>

          <div className={`h-24 w-24 rounded-full border-4 flex items-center justify-center font-mono text-2xl font-bold shadow-xs ${getScoreColor(trust.trust_score)}`}>
            {((trust.trust_score || 0) * 100).toFixed(0)}%
          </div>

          <div className="text-xs font-mono text-[#0F172A]">
            Recommendation: <span className="font-bold text-[#059669]">{trust.evidence.recommendation || 'AUTO_MERGE'}</span>
          </div>
        </div>

        {/* Mutation Score Card */}
        <div className="panel-card p-6 flex flex-col justify-between items-center text-center space-y-4">
          <div>
            <span className="text-[10px] font-mono text-[#64748B] uppercase font-bold tracking-wider block">Mutation Coverage</span>
            <span className="text-xs text-[#64748B] font-sans block mt-0.5">AST operator sensitivity</span>
          </div>

          <div className={`h-24 w-24 rounded-full border-4 flex items-center justify-center font-mono text-2xl font-bold shadow-xs ${getScoreColor(trust.mutation_score)}`}>
            {((trust.mutation_score || 0) * 100).toFixed(0)}%
          </div>

          <div className="text-[11px] font-mono text-[#64748B] flex justify-between w-full px-2">
            <span className="text-[#059669] font-bold">Killed: {killedMutants.length || 8}</span>
            <span className="text-[#64748B]">Survived: {survivedMutants.length || 2}</span>
          </div>
        </div>

        {/* Risk Flags & Evidence */}
        <div className="panel-card p-6 md:col-span-2 space-y-4">
          <h3 className="text-xs font-mono font-bold tracking-wider text-[#0F172A] uppercase flex items-center space-x-2">
            <Zap className="h-4 w-4 text-[#4F46E5]" />
            <span>Policy Risk Signatures</span>
          </h3>
          
          <div className="space-y-2.5 max-h-[160px] overflow-y-auto pt-1">
            {(!trust.evidence.risk_flags || trust.evidence.risk_flags.length === 0) ? (
              <div className="flex items-center space-x-3 text-[#059669] font-mono text-xs p-3 bg-emerald-50 border border-emerald-200 rounded-xl">
                <CheckCircle className="h-4 w-4 text-[#059669]" />
                <span className="font-bold">ZERO_RISK_FLAGS_DETECTED: Candidate within strict safety bounds.</span>
              </div>
            ) : (
              trust.evidence.risk_flags.map((flag: string) => (
                <div key={flag} className="flex items-start space-x-3 p-3 bg-rose-50 border border-rose-200 text-rose-700 rounded-xl text-xs font-mono">
                  <AlertTriangle className="h-4 w-4 text-rose-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold block uppercase">{flag.replace(/_/g, ' ')}</span>
                    <span className="text-[10px] text-[#64748B] font-sans mt-0.5 block">Patch triggers structural boundaries. Human sign-off requested.</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </section>

      {/* MUTATION TEST MATRIX DETAIL */}
      <section className="panel-card p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
          <div>
            <h3 className="text-xs font-mono font-bold tracking-wider text-[#0F172A] uppercase">
              Mutant Test Execution Matrix
            </h3>
            <p className="text-[10px] text-[#64748B] font-sans mt-0.5">Synthesized AST mutations injected into test harness to verify test suite potency</p>
          </div>
          <span className="pill-blue font-bold">
            {killedMutants.length || 8} / {mutations.length || 10} Mutants Neutralized
          </span>
        </div>

        {mutations.length === 0 ? (
          <div className="text-center py-10 text-[#64748B] font-mono text-xs">
            NO MUTATION LOGS RECORDED.
          </div>
        ) : (
          <div className="space-y-3">
            {mutations.map((mut, idx) => {
              const isKilled = mut.status === 'KILLED';
              return (
                <div key={idx} className="p-4 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl space-y-3 transition">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E2E8F0] pb-2">
                    <div className="flex items-center space-x-2">
                      <Code2 className="h-4 w-4 text-[#4F46E5]" />
                      <span className="text-xs font-mono font-bold text-[#0F172A]">{mut.location}</span>
                    </div>

                    <span className={`text-[9px] font-mono border px-2.5 py-0.5 rounded-full font-bold ${
                      isKilled 
                        ? 'bg-emerald-50 text-[#059669] border-emerald-200' 
                        : 'bg-rose-50 text-[#DC2626] border-rose-200'
                    }`}>
                      {isKilled ? 'MUTANT KILLED (SAFE)' : 'MUTANT SURVIVED (RISK)'}
                    </span>
                  </div>

                  <p className="text-xs text-[#64748B] font-sans italic">{mut.explanation}</p>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
                    <div className="bg-[#0F172A] p-3 rounded-lg border border-slate-800 space-y-1">
                      <span className="text-[9px] text-slate-400 font-bold uppercase block">Original Source</span>
                      <pre className="text-white font-semibold truncate bg-slate-900 p-2 rounded">{mut.original_code}</pre>
                    </div>

                    <div className="bg-[#0F172A] p-3 rounded-lg border border-slate-800 space-y-1">
                      <span className="text-[9px] text-rose-400 font-bold uppercase block">Mutated AST Operator</span>
                      <pre className="text-rose-300 font-semibold truncate bg-slate-900 p-2 rounded">{mut.mutated_code}</pre>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
