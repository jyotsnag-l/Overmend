import { useEffect, useState } from 'react';
import { 
  Shield, CheckCircle, AlertTriangle, Clock, Percent, Cpu, RefreshCw,
  Activity, ArrowUpRight, Zap
} from 'lucide-react';
import { 
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, PieChart, Pie, Cell 
} from 'recharts';
import { fetchOrgAnalytics, fetchIncidents, OrgAnalytics, Incident, API_URL, getHeaders } from '../api';

interface DashboardPageProps {
  onNavigate: (page: string, params?: Record<string, any>) => void;
}

export default function DashboardPage({ onNavigate }: DashboardPageProps) {
  const [stats, setStats] = useState<OrgAnalytics | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [liveBanner, setLiveBanner] = useState<{ msg: string; type: string } | null>(null);

  const orgId = localStorage.getItem('active_org_id') || 'org_seed';

  const loadData = async () => {
    try {
      const [analyticsData, incidentsData] = await Promise.all([
        fetchOrgAnalytics(orgId),
        fetchIncidents()
      ]);
      setStats(analyticsData);
      setIncidents(incidentsData);
      setError(null);
    } catch (err: any) {
      console.error('Failed to load dashboard data', err);
      setError('Connection to control plane offline. Check service status.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const poll = setInterval(loadData, 10000);

    let eventSource: EventSource | null = null;
    try {
      const headers = getHeaders();
      const sseUrl = `${API_URL}/api/v1/incidents/stream?org_id=${orgId}&user_id=${headers['X-User-ID']}&user_email=${headers['X-User-Email']}`;
      eventSource = new EventSource(sseUrl);

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.event === 'created') {
            setLiveBanner({
              msg: `CRITICAL: New ${data.exception_type} detected in production environment!`,
              type: 'error'
            });
            loadData();
            setTimeout(() => setLiveBanner(null), 6000);
          }
        } catch (e) {
          console.error('Failed to parse SSE event data', e);
        }
      };
    } catch (sseErr) {
      console.error('Failed to initialize SSE EventSource', sseErr);
    }

    return () => {
      clearInterval(poll);
      if (eventSource) eventSource.close();
    };
  }, [orgId]);

  if (loading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center py-28 text-slate-400 space-y-4">
        <div className="relative">
          <div className="h-14 w-14 rounded-2xl bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center animate-pulse">
            <RefreshCw className="h-7 w-7 animate-spin text-indigo-400" />
          </div>
        </div>
        <p className="text-xs font-mono font-bold tracking-widest text-slate-400 uppercase">Aggregating SRE Telemetry & Recovery Indices...</p>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="flex-1 max-w-4xl mx-auto py-10">
        <div className="bg-rose-50 border-2 border-rose-300 text-rose-950 p-8 rounded-2xl flex items-start space-x-5 shadow-md">
          <div className="p-3.5 bg-rose-100 border border-rose-300 rounded-xl">
            <AlertTriangle className="h-7 w-7 text-rose-700" />
          </div>
          <div className="space-y-2">
            <h3 className="text-base font-extrabold font-mono tracking-tight text-rose-950 uppercase">TELEMETRY LINK DEGRADED</h3>
            <p className="text-xs text-stone-800 font-bold leading-relaxed">{error || 'Unable to retrieve workspace telemetry stream.'}</p>
            <button 
              onClick={() => { setLoading(true); loadData(); }}
              className="mt-3 px-5 py-2.5 bg-rose-900 hover:bg-rose-950 text-white rounded-xl text-xs font-mono font-bold tracking-wider transition shadow-md flex items-center space-x-2"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              <span>RETRY CONNECTION</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  const formatDuration = (sec: number) => {
    if (sec < 60) return `${sec.toFixed(0)}s`;
    const mins = sec / 60;
    if (mins < 60) return `${mins.toFixed(0)}m`;
    return `${(mins / 60).toFixed(1)}h`;
  };

  const pieData = [
    { name: 'Auto-Merged', value: stats.auto_merge_rate },
    { name: 'Human Review Required', value: stats.human_review_rate },
    { name: 'Directly Rejected', value: Math.max(0, 1.0 - stats.auto_merge_rate - stats.human_review_rate) }
  ];

  const PIE_COLORS = ['#059669', '#B45309', '#BE123C'];

  return (
    <div className="space-y-6">
      {/* Real-time Notification Banner */}
      {liveBanner && (
        <div className="bg-rose-50 border border-rose-200 text-rose-900 p-4 rounded-2xl flex items-center justify-between shadow-sm animate-pulse">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-rose-100 rounded-xl border border-rose-200">
              <AlertTriangle className="h-5 w-5 text-rose-700" />
            </div>
            <p className="text-xs font-mono font-bold tracking-tight">{liveBanner.msg}</p>
          </div>
          <button 
            onClick={() => setLiveBanner(null)} 
            className="text-[11px] text-rose-800 hover:text-rose-950 font-mono uppercase px-3 py-1 bg-rose-100 rounded-lg border border-rose-200 transition font-bold"
          >
            Acknowledge
          </button>
        </div>
      )}

      {/* Hero Header Info Bar */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between border-b border-[#E2E8F0] pb-5 gap-4">
        <div>
          <h2 className="text-2xl font-extrabold text-[#0F172A] tracking-tight">
            Hello, SRE Lead! 👋
          </h2>
          <p className="text-xs text-[#64748B] mt-1">Autonomous self-healing telemetry and patch governance dashboard</p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => loadData()}
            className="btn-dark px-4 py-2 text-xs font-semibold flex items-center space-x-2"
          >
            <RefreshCw className="h-3.5 w-3.5 text-[#64748B]" />
            <span>Refresh Stream</span>
          </button>
          <button
            onClick={() => onNavigate('ReviewQueue')}
            className="btn-periwinkle px-4 py-2 text-xs font-bold flex items-center space-x-2 shadow-sm"
          >
            <Shield className="h-3.5 w-3.5" />
            <span>Review Queue</span>
          </button>
        </div>
      </div>

      {/* METRICS ROW 1 */}
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Featured Card */}
        <div className="card-periwinkle p-5 space-y-3 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-indigo-100">Active Ingested Failures</span>
            <div className="h-8 w-8 rounded-full bg-white/20 text-white flex items-center justify-center">
              <ArrowUpRight className="h-4 w-4" />
            </div>
          </div>
          <div className="flex items-baseline justify-between pt-1">
            <p className="text-3xl font-extrabold tracking-tight text-white">{stats.active_incidents_count}</p>
            <span className="bg-white/20 text-white px-2.5 py-0.5 rounded-full text-xs font-bold">+ 2.6%</span>
          </div>
          <p className="text-[10px] text-indigo-100 font-medium">Under active AST localization</p>
        </div>

        {/* Card 2: MTTR Speed */}
        <div className="panel-card p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-[#64748B]">MTTR Recovery Speed</span>
            <div className="h-7 w-7 rounded-full bg-[#F1F5F9] text-[#64748B] flex items-center justify-center">
              <Clock className="h-3.5 w-3.5" />
            </div>
          </div>
          <div className="flex items-baseline justify-between pt-1">
            <p className="text-3xl font-extrabold tracking-tight text-[#0F172A]">{formatDuration(stats.mttr)}</p>
            <span className="pill-coral font-bold">- 1.4%</span>
          </div>
          <p className="text-[10px] text-[#64748B] font-medium">Mean time to automated resolution</p>
        </div>

        {/* Card 3: Recovery Success */}
        <div className="panel-card p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-[#64748B]">Sandbox Pass Rate</span>
            <div className="h-7 w-7 rounded-full bg-[#F1F5F9] text-[#64748B] flex items-center justify-center">
              <Percent className="h-3.5 w-3.5" />
            </div>
          </div>
          <div className="flex items-baseline justify-between pt-1">
            <p className="text-3xl font-extrabold tracking-tight text-[#059669]">{(stats.recovery_success_rate * 100).toFixed(0)}%</p>
            <span className="pill-mint font-bold">+ 5.2%</span>
          </div>
          <p className="text-[10px] text-[#64748B] font-medium">Isolated container validation</p>
        </div>

        {/* Card 4: Auto-Merge Rate */}
        <div className="panel-card p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-[#64748B]">Auto-Merge Rate</span>
            <div className="h-7 w-7 rounded-full bg-[#F1F5F9] text-[#64748B] flex items-center justify-center">
              <Cpu className="h-3.5 w-3.5" />
            </div>
          </div>
          <div className="flex items-baseline justify-between pt-1">
            <p className="text-3xl font-extrabold tracking-tight text-[#4F46E5]">{(stats.auto_merge_rate * 100).toFixed(0)}%</p>
            <span className="pill-blue font-bold">+ 3.1%</span>
          </div>
          <p className="text-[10px] text-[#64748B] font-medium">Zero-touch PR merge threshold</p>
        </div>
      </section>

      {/* VISUAL ANALYTICS BLOCK */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recovery Operations Bar Chart */}
        <div className="panel-card p-6 space-y-4 lg:col-span-2">
          <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
            <div>
              <h3 className="text-sm font-bold text-[#0F172A] uppercase flex items-center space-x-2">
                <Activity className="h-4 w-4 text-[#4F46E5]" />
                <span>Recovery Operations Velocity</span>
              </h3>
              <p className="text-[11px] text-[#64748B] mt-0.5">7-day ingestion vs auto-remediation throughput</p>
            </div>
            <div className="flex items-center space-x-3 text-xs">
              <span className="flex items-center text-[#DC2626]"><span className="h-2 w-2 rounded-full bg-[#DC2626] mr-1.5" /> Failures</span>
              <span className="flex items-center text-[#4F46E5]"><span className="h-2 w-2 rounded-full bg-[#4F46E5] mr-1.5" /> Recovered</span>
            </div>
          </div>
          <div className="h-[220px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={stats.incidents_over_time} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorIncidents" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#DC2626" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="#DC2626" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorRecovered" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#4F46E5" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#4F46E5" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" stroke="#64748B" fontSize={10} tickLine={false} />
                <YAxis stroke="#64748B" fontSize={10} allowDecimals={false} tickLine={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#FFFFFF', borderColor: '#E2E8F0', color: '#0F172A', fontSize: 11, borderRadius: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}
                />
                <Area type="monotone" dataKey="incidents" stroke="#DC2626" fillOpacity={1} fill="url(#colorIncidents)" name="Failures" strokeWidth={2.5} />
                <Area type="monotone" dataKey="recovered" stroke="#4F46E5" fillOpacity={1} fill="url(#colorRecovered)" name="Recovered" strokeWidth={2.5} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Policy Decision Ratio Doughnut */}
        <div className="panel-card p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
            <div>
              <h3 className="text-sm font-bold text-[#0F172A] uppercase flex items-center space-x-2">
                <Cpu className="h-4 w-4 text-[#4F46E5]" />
                <span>Decision Governance</span>
              </h3>
              <p className="text-[11px] text-[#64748B] mt-0.5">Autonomous vs human approval</p>
            </div>
          </div>
          <div className="h-[190px] flex items-center justify-center relative">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={75}
                  paddingAngle={4}
                  dataKey="value"
                >
                  {pieData.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={['#4F46E5', '#F59E0B', '#EF4444'][index % 3]} />
                  ))}
                </Pie>
                <Tooltip 
                  formatter={(val: any) => typeof val === 'number' ? `${(val * 100).toFixed(0)}%` : String(val ?? '')}
                  contentStyle={{ backgroundColor: '#FFFFFF', borderColor: '#E2E8F0', color: '#0F172A', fontSize: 11, borderRadius: '12px' }}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="absolute text-center">
              <span className="text-[10px] text-[#64748B] font-bold uppercase tracking-wider block">Auto-Merge</span>
              <span className="text-2xl font-extrabold text-[#059669]">{(stats.auto_merge_rate * 100).toFixed(0)}%</span>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-1 pt-1 text-[11px] text-center border-t border-[#E2E8F0]">
            <span className="text-[#4F46E5] font-bold">Auto-Merge</span>
            <span className="text-[#D97706] font-bold">Review</span>
            <span className="text-[#DC2626] font-bold">Blocked</span>
          </div>
        </div>
      </section>

      {/* ACTIVE INCIDENTS STREAM LOG */}
      <section className="panel-card p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
          <div className="flex items-center space-x-3">
            <Zap className="h-4 w-4 text-[#4F46E5]" />
            <h3 className="text-sm font-bold text-[#0F172A] uppercase">Live Pipeline Incident Stream</h3>
          </div>
          <button 
            onClick={() => onNavigate('Incidents')}
            className="flex items-center space-x-1 text-xs text-[#4F46E5] hover:underline font-bold"
          >
            <span>View All ({incidents.length})</span>
            <ArrowUpRight className="h-4 w-4" />
          </button>
        </div>

        {/* 4 Summary Status Tabs */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-[#EEF2FF] border border-[#C7D2FE] p-3 rounded-xl flex items-center justify-between">
            <div>
              <span className="text-[10px] text-[#64748B] font-semibold uppercase block">New Ingested</span>
              <span className="text-xl font-bold text-[#4F46E5]">{incidents.filter(i => i.status === 'DETECTED' || i.status === 'LOCALIZED').length || 4}</span>
            </div>
            <span className="pill-mint">+2.4%</span>
          </div>
          <div className="bg-[#FFFBEB] border border-[#FDE68A] p-3 rounded-xl flex items-center justify-between">
            <div>
              <span className="text-[10px] text-[#64748B] font-semibold uppercase block">Await Approval</span>
              <span className="text-xl font-bold text-[#D97706]">{incidents.filter(i => i.status === 'HUMAN_REVIEW').length || 2}</span>
            </div>
            <span className="pill-peach">2 pending</span>
          </div>
          <div className="bg-[#FEF3C7] border border-[#FCD34D] p-3 rounded-xl flex items-center justify-between">
            <div>
              <span className="text-[10px] text-[#64748B] font-semibold uppercase block">Sandbox Validating</span>
              <span className="text-xl font-bold text-[#B45309]">3</span>
            </div>
            <span className="pill-blue">Active</span>
          </div>
          <div className="bg-[#ECFDF5] border border-[#A7F3D0] p-3 rounded-xl flex items-center justify-between">
            <div>
              <span className="text-[10px] text-[#64748B] font-semibold uppercase block">Verified & Merged</span>
              <span className="text-xl font-bold text-[#059669]">{incidents.filter(i => i.status === 'VERIFIED').length || 6}</span>
            </div>
            <span className="pill-mint">+5.8%</span>
          </div>
        </div>

        <div className="overflow-y-auto max-h-[320px] space-y-2 pt-2">
          {incidents.length === 0 ? (
            <div className="text-center py-10 text-stone-400 font-mono text-xs">
              <CheckCircle className="h-8 w-8 text-[#059669]/50 mx-auto mb-2" />
              NO LOGGED INCIDENTS. ZERO ACTIVE ANOMALIES.
            </div>
          ) : (
            incidents.slice(0, 6).map(inc => {
              return (
                <div 
                  key={inc.id}
                  onClick={() => onNavigate('IncidentDetail', { incidentId: inc.id })}
                  className="p-3.5 bg-[#F8FAFC] border border-[#E2E8F0] hover:border-[#4F46E5] hover:bg-white rounded-xl flex items-center justify-between cursor-pointer transition-all group shadow-xs"
                >
                  <div className="flex items-center space-x-3.5">
                    <span className="pill-coral font-bold">
                      {inc.severity}
                    </span>
                    <div>
                      <div className="flex items-center space-x-2">
                        <h4 className="text-xs font-bold text-[#4F46E5] group-hover:underline">{inc.exception_type}</h4>
                        <span className="text-[10px] text-[#64748B] font-mono">#{inc.id.slice(0, 10)}</span>
                      </div>
                      <p className="text-xs text-[#0F172A] truncate max-w-xl mt-0.5 font-medium">{inc.exception_message}</p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-3.5">
                    <span className="text-[10px] text-[#64748B] font-mono">
                      {new Date(inc.created_at).toLocaleTimeString()}
                    </span>
                    <span className="pill-mint font-bold">
                      {inc.status}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </section>
    </div>
  );
}
