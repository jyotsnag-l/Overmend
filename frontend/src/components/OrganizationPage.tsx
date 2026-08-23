import { useEffect, useState } from 'react';
import { 
  Database, RefreshCw, AlertTriangle, Users, Search, 
  Layers, Clock
} from 'lucide-react';
import { 
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend 
} from 'recharts';
import { listAuditLogs, AuditLog, fetchIncidents, Incident, SIMULATED_PROFILES, getSimulatedProfile, setSimulatedProfile } from '../api';
import { ROLE_CONFIGS, UserRole } from '../permissions';

export default function OrganizationPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'analytics' | 'audit' | 'members'>('analytics');

  const activeProfile = getSimulatedProfile();

  const loadData = async () => {
    try {
      const [auditLogs, incList] = await Promise.all([
        listAuditLogs(),
        fetchIncidents()
      ]);
      setLogs(auditLogs);
      setIncidents(incList);
      setError(null);
    } catch (err) {
      console.error('Failed to load organization metrics', err);
      setError('Failed to fetch organization logs.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const filteredLogs = logs.filter(log => {
    const term = searchQuery.toLowerCase();
    return (
      log.action.toLowerCase().includes(term) ||
      log.resource_type.toLowerCase().includes(term) ||
      log.resource_id.toLowerCase().includes(term) ||
      (log.user_id && log.user_id.toLowerCase().includes(term))
    );
  });

  const projectStats: Record<string, { total: number; recovered: number }> = {};
  incidents.forEach(inc => {
    const projName = inc.affected_project || inc.affected_repository || 'seed-microservice';
    if (!projectStats[projName]) {
      projectStats[projName] = { total: 0, recovered: 0 };
    }
    projectStats[projName].total += 1;
    if (inc.status === 'VERIFIED' || (inc.status as string) === 'MERGED') {
      projectStats[projName].recovered += 1;
    }
  });

  const chartData = Object.entries(projectStats).map(([name, data]) => ({
    name,
    'Total Failures': data.total,
    'Auto Recovered': data.recovered
  }));

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-28 text-slate-400 space-y-4">
        <Database className="h-8 w-8 animate-spin text-indigo-400" />
        <p className="text-xs font-mono font-bold tracking-widest text-slate-400">CALCULATING CROSS-PROJECT SRE METRICS...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center border-b border-[#E2E8F0] pb-5 gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <h2 className="text-2xl font-extrabold text-[#0F172A] tracking-tight">
              Organization & Analytics
            </h2>
            <span className="pill-blue font-bold">
              org_seed (Active Org)
            </span>
          </div>
          <p className="text-xs text-[#64748B] mt-1 font-sans">
            Cross-project failure resolution velocity, tamper-evident audit logs, and member directory
          </p>
        </div>

        <div className="flex items-center space-x-2">
          {/* Tab buttons */}
          <div className="flex bg-[#F1F5F9] border border-[#CBD5E1] p-1 rounded-full">
            <button
              onClick={() => setActiveTab('analytics')}
              className={`px-4 py-1.5 rounded-full text-xs font-bold transition ${activeTab === 'analytics' ? 'bg-[#4F46E5] text-white shadow-xs' : 'text-[#64748B] hover:text-[#0F172A]'}`}
            >
              Analytics
            </button>
            <button
              onClick={() => setActiveTab('audit')}
              className={`px-4 py-1.5 rounded-full text-xs font-bold transition ${activeTab === 'audit' ? 'bg-[#4F46E5] text-white shadow-xs' : 'text-[#64748B] hover:text-[#0F172A]'}`}
            >
              Audit Trail
            </button>
            <button
              onClick={() => setActiveTab('members')}
              className={`px-4 py-1.5 rounded-full text-xs font-bold transition ${activeTab === 'members' ? 'bg-[#4F46E5] text-white shadow-xs' : 'text-[#64748B] hover:text-[#0F172A]'}`}
            >
              Members & Roles
            </button>
          </div>

          <button 
            onClick={() => { setLoading(true); loadData(); }}
            className="btn-dark p-2 text-[#64748B]"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 text-rose-700 font-mono text-xs rounded-2xl flex items-center space-x-3">
          <AlertTriangle className="h-4 w-4 text-rose-500 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* TAB 1: ANALYTICS */}
      {activeTab === 'analytics' && (
        <div className="space-y-6">
          <section className="panel-card p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
              <div>
                <h3 className="text-xs font-mono font-bold tracking-wider text-[#0F172A] uppercase flex items-center space-x-2">
                  <Layers className="h-4 w-4 text-[#4F46E5]" />
                  <span>Cross-Project Recovery Effectiveness Matrix</span>
                </h3>
                <p className="text-[10px] text-[#64748B] font-sans mt-0.5">Automated recovery success comparison across deployed microservices</p>
              </div>
            </div>
            
            <div className="h-[260px]">
              {chartData.length === 0 ? (
                <div className="h-full flex items-center justify-center text-[#64748B] font-mono text-xs">
                  NO PROJECT RECOVERY METRICS RECORDED.
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <XAxis dataKey="name" stroke="#64748B" fontSize={10} fontFamily="monospace" tickLine={false} />
                    <YAxis stroke="#64748B" fontSize={10} fontFamily="monospace" allowDecimals={false} tickLine={false} />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#FFFFFF', borderColor: '#CBD5E1', color: '#0F172A', fontFamily: 'monospace', fontSize: 11, borderRadius: '12px' }}
                    />
                    <Legend wrapperStyle={{ fontSize: 10, fontFamily: 'monospace' }} />
                    <Bar dataKey="Total Failures" fill="#DC2626" radius={[6, 6, 0, 0]} />
                    <Bar dataKey="Auto Recovered" fill="#059669" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </section>
        </div>
      )}

      {/* TAB 2: AUDIT TRAIL */}
      {activeTab === 'audit' && (
        <section className="panel-card p-6 space-y-4">
          <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-[#E2E8F0] pb-3 gap-3">
            <div>
              <h3 className="text-xs font-mono font-bold tracking-wider text-[#0F172A] uppercase flex items-center space-x-2">
                <Clock className="h-4 w-4 text-[#4F46E5]" />
                <span>Immutable Workspace Audit Log</span>
              </h3>
              <p className="text-[10px] text-[#64748B] font-sans mt-0.5">Cryptographically logged decision changes, pipeline transitions, and policy commits</p>
            </div>
            
            <div className="relative">
              <Search className="h-3.5 w-3.5 absolute left-3 top-3 text-stone-400" />
              <input
                type="text"
                placeholder="Search audit trail by actor, action..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="bg-[#F1F5F9] border border-[#CBD5E1] rounded-xl pl-9 pr-4 py-2 text-xs font-mono text-[#0F172A] focus:outline-none focus:border-[#4F46E5] w-full md:w-72"
              />
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[#E2E8F0] text-[10px] font-mono text-[#64748B] uppercase font-bold bg-[#F8FAFC]">
                  <th className="py-3 px-4">Audit ID</th>
                  <th className="py-3 px-4">Actor</th>
                  <th className="py-3 px-4">Action Signature</th>
                  <th className="py-3 px-4">Target Resource</th>
                  <th className="py-3 px-4">Details</th>
                  <th className="py-3 px-4 text-right">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2E8F0] font-mono text-xs text-[#0F172A]">
                {filteredLogs.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-[#64748B]">
                      NO AUDIT TRAIL ENTRIES RECORDED.
                    </td>
                  </tr>
                ) : (
                  filteredLogs.map(log => (
                    <tr key={log.id} className="hover:bg-[#F8FAFC] transition">
                      <td className="py-3 px-4 text-[#64748B] font-bold">#{log.id.slice(0, 8)}</td>
                      <td className="py-3 px-4">
                        <span className="pill-blue font-bold">
                          {log.user_id || 'system-orchestrator'}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-[#D97706] font-bold">{log.action}</td>
                      <td className="py-3 px-4 text-[#64748B] text-[11px]">
                        {log.resource_type} ({log.resource_id.slice(0, 10)})
                      </td>
                      <td className="py-3 px-4 max-w-[240px] truncate text-[#64748B] text-[11px]" title={JSON.stringify(log.details)}>
                        {JSON.stringify(log.details)}
                      </td>
                      <td className="py-3 px-4 text-right text-[#64748B] text-[11px]">
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* TAB 3: MEMBERS & RBAC DIRECTORY */}
      {activeTab === 'members' && (
        <section className="panel-card p-6 space-y-5">
          <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
            <div>
              <h3 className="text-xs font-mono font-bold tracking-wider text-[#0F172A] uppercase flex items-center space-x-2">
                <Users className="h-4 w-4 text-[#4F46E5]" />
                <span>Simulated Workspace Members & Role Directory</span>
              </h3>
              <p className="text-[10px] text-[#64748B] font-sans mt-0.5">Click any profile below to instantly switch the simulated authorization context</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {SIMULATED_PROFILES.map(profile => {
              const rConfig = ROLE_CONFIGS[profile.role as UserRole] || ROLE_CONFIGS.VIEWER;
              const RIcon = rConfig.icon;
              const isCurrent = activeProfile.email === profile.email;

              return (
                <div 
                  key={profile.email}
                  onClick={() => {
                    setSimulatedProfile(profile.email);
                    window.location.reload();
                  }}
                  className={`p-5 rounded-2xl border cursor-pointer transition-all flex flex-col justify-between space-y-3 ${
                    isCurrent 
                      ? 'bg-[#EEF2FF] border-[#4F46E5] text-[#0F172A] shadow-xs' 
                      : 'bg-white hover:bg-[#F8FAFC] border-[#E2E8F0] text-[#64748B]'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <div className="p-2 rounded-xl bg-indigo-50 text-[#4F46E5] border border-indigo-200">
                        <RIcon className="h-4 w-4" />
                      </div>
                      <div>
                        <h4 className="text-xs font-mono font-bold text-[#0F172A]">{profile.name}</h4>
                        <span className="text-[10px] font-mono text-[#64748B]">{profile.email}</span>
                      </div>
                    </div>

                    {isCurrent && (
                      <span className="pill-blue font-bold">
                        ACTIVE
                      </span>
                    )}
                  </div>

                  <p className="text-[11px] text-[#64748B] font-sans leading-relaxed">
                    {rConfig.description}
                  </p>

                  <div className="pt-2 border-t border-[#E2E8F0] flex items-center justify-between text-[10px] font-mono">
                    <span className="text-[#64748B]">ID: {profile.id}</span>
                    <span className="pill-blue font-bold">
                      {profile.role}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
