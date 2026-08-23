import { useEffect, useState } from 'react';
import { 
  Search, ChevronRight, Archive, RefreshCw, AlertTriangle
} from 'lucide-react';
import { fetchIncidents, Incident } from '../api';

interface IncidentsPageProps {
  onNavigate: (page: string, params?: Record<string, any>) => void;
}

export default function IncidentsPage({ onNavigate }: IncidentsPageProps) {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [envFilter, setEnvFilter] = useState('ALL');

  const loadIncidents = async () => {
    try {
      const data = await fetchIncidents();
      setIncidents(data);
      setError(null);
    } catch (err) {
      console.error('Failed to load incidents', err);
      setError('Failed to fetch incident log.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadIncidents();
  }, []);

  const filteredIncidents = incidents.filter(inc => {
    const matchesSearch = 
      inc.id.toLowerCase().includes(search.toLowerCase()) ||
      inc.exception_type.toLowerCase().includes(search.toLowerCase()) ||
      inc.exception_message.toLowerCase().includes(search.toLowerCase()) ||
      (inc.affected_repository && inc.affected_repository.toLowerCase().includes(search.toLowerCase()));
      
    const matchesStatus = statusFilter === 'ALL' || inc.status === statusFilter;
    const matchesSeverity = severityFilter === 'ALL' || inc.severity === severityFilter;
    const matchesEnv = envFilter === 'ALL' || inc.environment === envFilter;

    return matchesSearch && matchesStatus && matchesSeverity && matchesEnv;
  });

  const getSeverityBadge = (sev: string) => {
    const styles: Record<string, string> = {
      CRITICAL: 'bg-rose-50 text-rose-900 border-rose-300',
      HIGH: 'bg-rose-50 text-rose-900 border-rose-300',
      MEDIUM: 'bg-amber-50 text-amber-800 border-amber-300',
      LOW: 'bg-stone-100 text-stone-700 border-stone-200'
    };
    return (
      <span className={`text-[10px] font-mono border px-2.5 py-0.5 rounded-full font-bold ${styles[sev] || styles.LOW}`}>
        {sev.charAt(0) + sev.slice(1).toLowerCase()}
      </span>
    );
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      VERIFIED: 'bg-emerald-50 text-emerald-800 border-emerald-300 font-semibold',
      MERGED: 'bg-emerald-50 text-emerald-800 border-emerald-300 font-semibold',
      REJECTED: 'bg-rose-50 text-rose-900 border-rose-300 font-semibold',
      REVERTED: 'bg-amber-50 text-amber-800 border-amber-300 font-semibold',
      INVESTIGATING: 'bg-stone-100 text-stone-700 border-stone-200',
      SANDBOX_RUNNING: 'bg-amber-50 text-amber-800 border-amber-300 font-semibold',
      DECISION: 'bg-amber-50 text-amber-800 border-amber-300 font-semibold',
      HUMAN_REVIEW: 'bg-amber-50 text-amber-800 border-amber-300 font-semibold'
    };
    const label = status === 'VERIFIED' || status === 'MERGED' ? 'Repaired' :
                  status === 'SANDBOX_RUNNING' ? 'Analyzing' :
                  status === 'HUMAN_REVIEW' ? 'Manual Review' : status;
    return (
      <span className={`text-[10px] font-mono border px-2.5 py-0.5 rounded-full ${styles[status] || 'bg-amber-50 text-amber-800 border-amber-300'}`}>
        {label}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-28 text-slate-400 space-y-4">
        <RefreshCw className="h-8 w-8 animate-spin text-indigo-400" />
        <p className="text-xs font-mono font-bold tracking-widest text-slate-400">RETRIEVING PRODUCTION INCIDENTS...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      {/* Title */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-extrabold text-[#0F172A] tracking-tight">
            Incident List
          </h2>
          <p className="text-xs text-[#64748B] mt-0.5 font-sans">Active telemetry records, fault locations, and remediation lifecycle</p>
        </div>
        <button 
          onClick={() => { setLoading(true); loadIncidents(); }}
          className="btn-dark px-4 py-2 text-xs font-semibold flex items-center space-x-2"
        >
          <RefreshCw className="h-3.5 w-3.5 text-[#64748B]" />
          <span>Refresh</span>
        </button>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 text-rose-700 font-mono text-xs rounded-2xl flex items-center space-x-3">
          <AlertTriangle className="h-4 w-4 text-rose-500 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* 4 SUMMARY CARDS */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Card 1 */}
        <div className="panel-card p-4 space-y-2">
          <div className="bg-[#4F46E5] text-white px-3 py-1 rounded-lg text-xs font-bold w-fit shadow-xs">
            New Ingested
          </div>
          <div className="flex items-baseline justify-between pt-1">
            <span className="text-3xl font-extrabold text-[#0F172A]">12</span>
            <span className="pill-mint font-bold">+ 2.6%</span>
          </div>
          <p className="text-[10px] text-[#64748B] font-medium">Than last week</p>
        </div>

        {/* Card 2 */}
        <div className="panel-card p-4 space-y-2">
          <div className="bg-[#F59E0B] text-white px-3 py-1 rounded-lg text-xs font-bold w-fit shadow-xs">
            Await Review
          </div>
          <div className="flex items-baseline justify-between pt-1">
            <span className="text-3xl font-extrabold text-[#0F172A]">20</span>
            <span className="pill-mint font-bold">+ 2.0%</span>
          </div>
          <p className="text-[10px] text-[#64748B] font-medium">Than last week</p>
        </div>

        {/* Card 3 */}
        <div className="panel-card p-4 space-y-2">
          <div className="bg-[#EAB308] text-white px-3 py-1 rounded-lg text-xs font-bold w-fit shadow-xs">
            Sandbox CI
          </div>
          <div className="flex items-baseline justify-between pt-1">
            <span className="text-3xl font-extrabold text-[#0F172A]">57</span>
            <span className="pill-coral font-bold">- 0.6%</span>
          </div>
          <p className="text-[10px] text-[#64748B] font-medium">Than last week</p>
        </div>

        {/* Card 4 */}
        <div className="panel-card p-4 space-y-2">
          <div className="bg-[#10B981] text-white px-3 py-1 rounded-lg text-xs font-bold w-fit shadow-xs">
            Verified & Merged
          </div>
          <div className="flex items-baseline justify-between pt-1">
            <span className="text-3xl font-extrabold text-[#0F172A]">98</span>
            <span className="pill-mint font-bold">+ 2.8%</span>
          </div>
          <p className="text-[10px] text-[#64748B] font-medium">Than last week</p>
        </div>
      </div>

      {/* FILTER & TABLE SECTION */}
      <section className="panel-card p-5 space-y-4">
        <div className="flex flex-col md:flex-row items-center justify-between gap-3">
          <div className="relative w-full md:w-80">
            <Search className="absolute left-3.5 top-2.5 h-4 w-4 text-stone-400" />
            <input 
              type="text" 
              placeholder="Search by exception, ID, repository..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-[#F1F5F9] border border-[#CBD5E1] rounded-xl pl-10 pr-3 py-2 text-xs text-[#0F172A] focus:outline-none focus:border-[#4F46E5]"
            />
          </div>

          <div className="flex items-center space-x-3 w-full md:w-auto justify-end">
            <select 
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-[#F1F5F9] border border-[#CBD5E1] rounded-xl px-3 py-2 text-xs text-[#0F172A] focus:outline-none cursor-pointer font-semibold"
            >
              <option value="ALL">All Lifecycle Stages</option>
              <option value="DETECTED">DETECTED</option>
              <option value="LOCALIZED">LOCALIZED</option>
              <option value="HUMAN_REVIEW">HUMAN_REVIEW</option>
              <option value="VERIFIED">VERIFIED (RESOLVED)</option>
            </select>

            <select 
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="bg-[#F1F5F9] border border-[#CBD5E1] rounded-xl px-3 py-2 text-xs text-[#0F172A] focus:outline-none cursor-pointer font-semibold"
            >
              <option value="ALL">All Severities</option>
              <option value="CRITICAL">CRITICAL</option>
              <option value="HIGH">HIGH</option>
              <option value="MEDIUM">MEDIUM</option>
            </select>
          </div>
        </div>

        {/* REGISTRY TABLE */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-[#E2E8F0] text-[11px] font-mono text-[#64748B] uppercase font-bold bg-[#F8FAFC]">
                <th className="py-3 px-4">INCIDENT NUMBER</th>
                <th className="py-3 px-4">EXCEPTION FAULT</th>
                <th className="py-3 px-4">REPOSITORY LOCATION</th>
                <th className="py-3 px-4">SEVERITY</th>
                <th className="py-3 px-4">DATE & TIME</th>
                <th className="py-3 px-4">STATUS</th>
                <th className="py-3 px-4 text-right font-mono">ACTION</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E2E8F0]">
              {filteredIncidents.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-16 text-center text-stone-400 font-mono text-xs">
                    <Archive className="h-8 w-8 text-stone-300 mx-auto mb-2" />
                    NO FAULTS MATCHING ACTIVE FILTERS.
                  </td>
                </tr>
              ) : (
                filteredIncidents.map(inc => (
                  <tr 
                    key={inc.id}
                    onClick={() => onNavigate('IncidentDetail', { incidentId: inc.id })}
                    className="hover:bg-[#F8FAFC] cursor-pointer transition text-xs font-sans group"
                  >
                    <td className="py-3.5 px-4 font-mono font-bold text-[#0F172A]">
                      #{inc.id.slice(0, 8)}
                    </td>
                    <td className="py-3.5 px-4 font-bold text-[#4F46E5]">
                      {inc.exception_type}
                    </td>
                    <td className="py-3.5 px-4 text-[#64748B] font-mono text-xs">
                      {inc.affected_repository || 'seed-org/seed-repo'}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="pill-coral font-bold">{inc.severity}</span>
                    </td>
                    <td className="py-3.5 px-4 text-[#64748B] text-xs font-mono">
                      {new Date(inc.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="pill-mint font-bold">{inc.status}</span>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <span className="text-xs font-bold text-[#6C8EFF] hover:underline flex items-center justify-end space-x-1">
                        <span>Inspect</span>
                        <ChevronRight className="h-3.5 w-3.5" />
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
