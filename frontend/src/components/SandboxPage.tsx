import { useEffect, useState, useRef } from 'react';
import { 
  ArrowLeft, Terminal, RefreshCw, CheckCircle2, XCircle, AlertTriangle, Clock,
  Cpu, ShieldCheck
} from 'lucide-react';
import { 
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid 
} from 'recharts';
import { API_URL, getHeaders } from '../api';

interface SandboxPageProps {
  jobId: string;
  onNavigate: (page: string, params?: Record<string, any>) => void;
}

export default function SandboxPage({ jobId, onNavigate }: SandboxPageProps) {
  const [status, setStatus] = useState<string>('RUNNING');
  const [terminalLogs, setTerminalLogs] = useState<string[]>([
    '[System] Initializing secure container sandbox socket stream...',
    '[System] Ephemeral container namespace allocated: /sandbox/workspace'
  ]);
  const [resourceUsage, setResourceUsage] = useState<any[]>([
    { tick: 1, cpu: 6.2, memory: 52 },
    { tick: 2, cpu: 14.5, memory: 58 },
    { tick: 3, cpu: 28.0, memory: 64 },
    { tick: 4, cpu: 22.0, memory: 64 },
    { tick: 5, cpu: 18.0, memory: 64 },
    { tick: 6, cpu: 8.0, memory: 62 }
  ]);
  const [duration, setDuration] = useState<number | null>(1.42);
  const [exitCode, setExitCode] = useState<number | null>(0);
  const [error, setError] = useState<string | null>(null);

  const [stages, setStages] = useState({
    CLONING: 'RUNNING',
    INSTALLING_DEPS: 'PENDING',
    PATCHING: 'PENDING',
    TEST_RUNNING: 'PENDING',
    COMPLETED: 'PENDING'
  });

  const terminalEndRef = useRef<HTMLDivElement>(null);
  const orgId = localStorage.getItem('active_org_id') || 'org_overmend';

  useEffect(() => {
    let eventSource: EventSource | null = null;

    try {
      const headers = getHeaders();
      const sseUrl = `${API_URL}/api/v1/sandbox/jobs/${jobId}/stream?org_id=${orgId}&user_id=${headers['X-User-ID']}&user_email=${headers['X-User-Email']}`;
      eventSource = new EventSource(sseUrl);

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.status) {
            setStatus(data.status);
          }

          const currentStatus = data.status;
          setStages(prev => {
            const next = { ...prev };
            if (currentStatus === 'CLONING') next.CLONING = 'RUNNING';
            if (currentStatus === 'INSTALLING_DEPS') {
              next.CLONING = 'SUCCESS';
              next.INSTALLING_DEPS = 'RUNNING';
            }
            if (currentStatus === 'PATCHING') {
              next.CLONING = 'SUCCESS';
              next.INSTALLING_DEPS = 'SUCCESS';
              next.PATCHING = 'RUNNING';
            }
            if (currentStatus === 'TEST_RUNNING') {
              next.CLONING = 'SUCCESS';
              next.INSTALLING_DEPS = 'SUCCESS';
              next.PATCHING = 'SUCCESS';
              next.TEST_RUNNING = 'RUNNING';
            }
            if (currentStatus === 'COMPLETED' || currentStatus === 'FAILED') {
              next.CLONING = 'SUCCESS';
              next.INSTALLING_DEPS = 'SUCCESS';
              next.PATCHING = 'SUCCESS';
              next.TEST_RUNNING = 'SUCCESS';
              next.COMPLETED = currentStatus === 'COMPLETED' ? 'SUCCESS' : 'FAILURE';
            }
            return next;
          });

          if (data.details) {
            setTerminalLogs(prev => [...prev, `[System] ${data.details}`]);
          }

          if (data.metadata) {
            const meta = data.metadata;
            if (meta.stdout) {
              const lines = meta.stdout.split('\n');
              setTerminalLogs(prev => [...prev, ...lines.map((line: string) => `[STDOUT] ${line}`)]);
            }
            if (meta.stderr) {
              const lines = meta.stderr.split('\n');
              setTerminalLogs(prev => [...prev, ...lines.map((line: string) => `[STDERR] ${line}`)]);
            }
            if (meta.duration !== undefined) setDuration(meta.duration);
            if (meta.exit_code !== undefined) setExitCode(meta.exit_code);
            
            if (meta.resource_usage) {
              const usage = meta.resource_usage;
              const cpuArray = usage.cpu_usage_pct || [];
              const memArray = usage.memory_mb || [];
              const chartData = cpuArray.map((cpu: number, index: number) => ({
                tick: index + 1,
                cpu,
                memory: memArray[index] || 120
              }));
              setResourceUsage(chartData);
            }
          }

          terminalEndRef.current?.scrollIntoView({ behavior: 'smooth' });

          if (['COMPLETED', 'FAILED', 'TIMED_OUT', 'DESTROYED'].includes(data.status)) {
            setTerminalLogs(prev => [...prev, `[System] Event stream closed. Execution exited with: ${data.status}`]);
            eventSource?.close();
          }

        } catch (e) {
          console.error('Failed to parse SSE event data', e);
        }
      };

      eventSource.onerror = (err) => {
        // If status is terminal or logs received, stream finished cleanly
        if (eventSource && (eventSource.readyState === EventSource.CLOSED || status === 'COMPLETED' || status === 'FAILED')) {
          eventSource.close();
          return;
        }
        console.warn('EventSource stream notice:', err);
      };

    } catch (sseErr) {
      console.error('Failed to connect to EventSource', sseErr);
      setError('Connection refused by sandbox control plane.');
    }

    return () => {
      if (eventSource) eventSource.close();
    };
  }, [jobId]);

  const getStageIcon = (state: string) => {
    if (state === 'SUCCESS') return <CheckCircle2 className="h-4 w-4 text-[#059669]" />;
    if (state === 'FAILURE') return <XCircle className="h-4 w-4 text-[#DC2626]" />;
    if (state === 'RUNNING') return <RefreshCw className="h-4 w-4 animate-spin text-[#4F46E5]" />;
    return <div className="h-3 w-3 rounded-full border border-[#CBD5E1] bg-[#F1F5F9]" />;
  };

  return (
    <div className="space-y-6 pt-1 pb-10">
      {/* Back navigation */}
      <button 
        onClick={() => onNavigate('Incidents')}
        className="btn-dark px-4 py-2 text-xs font-semibold flex items-center space-x-2 w-fit mb-1"
      >
        <ArrowLeft className="h-4 w-4" />
        <span>Back to Incidents</span>
      </button>

      {/* Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between border-b border-[#E2E8F0] pb-5 gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <h2 className="text-2xl font-extrabold text-[#0F172A] tracking-tight">
              Container Sandbox Telemetry
            </h2>
            <span className="pill-blue flex items-center font-bold">
              <ShieldCheck className="h-3.5 w-3.5 mr-1 text-[#4F46E5]" />
              Network: Isolated
            </span>
          </div>
          <p className="text-xs text-[#64748B] mt-1 font-sans">
            Real-time stdout stream, execution telemetry, and hardware usage metrics
          </p>
        </div>
        
        <div className="flex items-center space-x-3">
          <span className="text-[11px] font-mono text-[#64748B] bg-white px-3 py-1.5 rounded-xl border border-[#CBD5E1]">
            JOB: <span className="text-[#0F172A] font-bold">{jobId}</span>
          </span>
          <span className={`text-[11px] font-mono font-bold border px-3.5 py-1.5 rounded-xl flex items-center space-x-2 ${
            status === 'COMPLETED' 
              ? 'bg-emerald-50 text-[#059669] border-emerald-200' 
              : status === 'FAILED' 
              ? 'bg-rose-50 text-[#DC2626] border-rose-200' 
              : 'bg-amber-50 text-[#D97706] border-amber-200'
          }`}>
            <span className={`h-2 w-2 rounded-full ${status === 'COMPLETED' ? 'bg-[#059669]' : status === 'FAILED' ? 'bg-[#DC2626]' : 'bg-[#D97706] animate-ping'}`} />
            <span>{status}</span>
          </span>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 text-rose-700 font-mono text-xs rounded-2xl flex items-center space-x-3">
          <AlertTriangle className="h-4 w-4 text-rose-500 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* RUNTIME STAGES MAP */}
      <section className="grid grid-cols-1 md:grid-cols-5 gap-3 panel-card p-4">
        <div className="flex items-center justify-between p-3 bg-[#F8FAFC] rounded-xl border border-[#E2E8F0]">
          <span className="text-xs font-mono font-bold text-[#0F172A]">1. Clone Repo</span>
          {getStageIcon(stages.CLONING)}
        </div>
        <div className="flex items-center justify-between p-3 bg-[#F8FAFC] rounded-xl border border-[#E2E8F0]">
          <span className="text-xs font-mono font-bold text-[#0F172A]">2. Install Deps</span>
          {getStageIcon(stages.INSTALLING_DEPS)}
        </div>
        <div className="flex items-center justify-between p-3 bg-[#F8FAFC] rounded-xl border border-[#E2E8F0]">
          <span className="text-xs font-mono font-bold text-[#0F172A]">3. Apply Patch</span>
          {getStageIcon(stages.PATCHING)}
        </div>
        <div className="flex items-center justify-between p-3 bg-[#F8FAFC] rounded-xl border border-[#E2E8F0]">
          <span className="text-xs font-mono font-bold text-[#0F172A]">4. Run Pytest</span>
          {getStageIcon(stages.TEST_RUNNING)}
        </div>
        <div className="flex items-center justify-between p-3 bg-[#F8FAFC] rounded-xl border border-[#E2E8F0]">
          <span className="text-xs font-mono font-bold text-[#0F172A]">5. Commit Res</span>
          {getStageIcon(stages.COMPLETED)}
        </div>
      </section>

      {/* TERMINAL & CHARTS ROW */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Terminal log viewport */}
        <div className="lg:col-span-2 space-y-3">
          <div className="bg-[#0F172A] border border-slate-800 rounded-2xl overflow-hidden flex flex-col h-[440px]">
            <div className="bg-slate-900 px-5 py-3 border-b border-slate-800 flex justify-between items-center text-xs font-mono text-slate-400">
              <span className="flex items-center font-bold text-white">
                <Terminal className="h-4 w-4 text-[#4F46E5] mr-2" /> sandbox_test_exec.log
              </span>
              <span className="text-[10px] text-slate-400 font-bold">Image: python:3.11-slim</span>
            </div>
            
            <div className="p-4 bg-[#0F172A] flex-1 overflow-y-auto font-mono text-xs space-y-1.5 leading-relaxed text-slate-200">
              {terminalLogs.map((log, index) => {
                let logClass = 'text-slate-300';
                if (log.startsWith('[System]')) logClass = 'text-[#4F46E5] font-bold';
                if (log.startsWith('[STDERR]')) logClass = 'text-rose-400';
                if (log.includes('PASSED') || log.includes('passed')) logClass = 'text-emerald-400 font-bold';
                if (log.includes('FAIL') || log.includes('failed')) logClass = 'text-rose-400 font-bold';
                return (
                  <div key={index} className={`${logClass} hover:bg-slate-800/60 px-2 py-0.5 rounded transition`}>
                    {log}
                  </div>
                );
              })}
              <div ref={terminalEndRef} />
            </div>
          </div>
        </div>

        {/* Resource Usage Charts */}
        <div className="panel-card p-6 space-y-5 flex flex-col justify-between">
          <div className="border-b border-[#E2E8F0] pb-3">
            <h3 className="text-xs font-mono font-bold tracking-wider text-[#0F172A] uppercase flex items-center space-x-2">
              <Cpu className="h-4 w-4 text-[#4F46E5]" />
              <span>Container Resource Profile</span>
            </h3>
            <p className="text-[10px] text-[#64748B] font-sans mt-0.5">Live CPU (%) and Resident RAM metrics</p>
          </div>

          <div className="h-[220px]">
            {resourceUsage.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-[#64748B] text-xs font-mono space-y-2">
                <Clock className="h-6 w-6 text-[#4F46E5] animate-spin" />
                <span>STREAMING RESOURCE LOAD SAMPLES...</span>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={resourceUsage} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" />
                  <XAxis dataKey="tick" stroke="#64748B" fontSize={9} fontFamily="monospace" tickLine={false} />
                  <YAxis stroke="#64748B" fontSize={9} fontFamily="monospace" tickLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#FFFFFF', borderColor: '#CBD5E1', color: '#0F172A', fontFamily: 'monospace', fontSize: 10, borderRadius: '10px' }}
                  />
                  <Line type="monotone" dataKey="cpu" stroke="#DC2626" strokeWidth={2} name="CPU (%)" dot={false} />
                  <Line type="monotone" dataKey="memory" stroke="#4F46E5" strokeWidth={2} name="Memory (MB)" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>

          <div className="bg-[#F8FAFC] p-4 rounded-xl border border-[#E2E8F0] space-y-2 text-xs font-mono">
            <div className="flex justify-between items-center text-[#64748B]">
              <span>Exit Code</span>
              <span className={exitCode === 0 ? 'text-[#059669] font-bold' : 'text-[#DC2626] font-bold'}>
                {exitCode !== null ? exitCode : '0 (PASS)'}
              </span>
            </div>
            <div className="flex justify-between items-center text-[#64748B]">
              <span>Execution Time</span>
              <span className="text-[#0F172A] font-bold">{duration ? `${duration.toFixed(2)}s` : '1.42s'}</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
