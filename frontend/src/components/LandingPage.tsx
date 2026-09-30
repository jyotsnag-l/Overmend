import { useState } from 'react';
import { 
  Shield, Activity, Play, CheckCircle2, GitPullRequest, 
  Terminal, ArrowRight, Layers, Cpu,
  Sparkles, RefreshCw, ShieldCheck
} from 'lucide-react';
import { triggerDemoIncident, HealthStatus } from '../api';

interface LandingPageProps {
  onNavigate: (page: string, params?: Record<string, any>) => void;
  health: HealthStatus | null;
}

export default function LandingPage({ onNavigate, health }: LandingPageProps) {
  const [activeStep, setActiveStep] = useState(0);
  const [simulating, setSimulating] = useState(false);
  const [simFeedback, setSimFeedback] = useState<string | null>(null);

  const pipelineSteps = [
    {
      step: '01',
      title: 'Realtime Ingestion',
      subtitle: 'Instant Error Capture',
      desc: 'SDK and webhooks capture unhandled production exceptions, normalize stack traces, and calculate stable cryptographic fingerprints.',
      icon: Activity,
      badge: 'SDK / Webhook',
      details: 'Deduplicates recurring events via EWMA rolling error rate metrics, evaluates anomaly thresholds, and guarantees zero data loss.'
    },
    {
      step: '02',
      title: 'Fault Localization',
      subtitle: 'AST & Blame Mapping',
      desc: 'Parses traceback frames, traverses code AST to identify enclosing function and class boundaries, and pulls Git blame history.',
      icon: Terminal,
      badge: 'Python AST + Git',
      details: 'Pinpoints the exact faulty line, flags recent commits touching the affected file, and isolates execution blast radius.'
    },
    {
      step: '03',
      title: 'Patch Synthesis',
      subtitle: 'Multi-Candidate Generation',
      desc: 'Generates up to 3 candidate unified-diff patches with explanatory reasoning and change scope estimations.',
      icon: Sparkles,
      badge: 'Zero-Shot AI / Rules',
      details: 'Applies rigorous syntax validation against Python grammar before patches are ever allowed to enter execution testing.'
    },
    {
      step: '04',
      title: 'Sandbox Cloud',
      subtitle: 'Isolated Docker Execution',
      desc: 'Executes candidate patches inside ephemeral, resource-constrained container workspaces with real-time log streaming.',
      icon: Cpu,
      badge: 'Docker Sandboxes',
      details: 'Enforces strict CPU (0.5 cores), memory (512MB), and network isolation while running targeted regression suites.'
    },
    {
      step: '05',
      title: 'Mutation Testing',
      subtitle: 'Synthetic Bug Inversion',
      desc: 'Trust Worker injects intentional syntax mutations (mutants) around the patch to verify test sensitivity and strength.',
      icon: Layers,
      badge: 'Mutmut Engine',
      details: 'Calculates the mutation kill-rate percentage. Ensures patches are genuinely validated rather than passing trivial assertions.'
    },
    {
      step: '06',
      title: 'Trust Scoring',
      subtitle: 'Mathematical Confidence',
      desc: 'Calculates a composite Trust Score (0.0 to 1.0) aggregating test outcomes, mutation kill-rate, and blast radius.',
      icon: Shield,
      badge: 'Trust Score Matrix',
      details: 'High-confidence patches (>= 0.90) qualify for zero-touch deployment; uncertain candidates trigger human approval gates.'
    },
    {
      step: '07',
      title: 'Policy Governance',
      subtitle: 'Decision Engine Gates',
      desc: 'Evaluates enterprise organization rules, compliance checklists, role permissions, and environment constraints.',
      icon: ShieldCheck,
      badge: 'Governance Rules',
      details: 'Automates AUTO_MERGE for safe low-risk bugs, routing critical or high-blast-radius fixes into the Review Queue for sign-off.'
    },
    {
      step: '08',
      title: 'GitHub Automation',
      subtitle: 'Branch & Pull Request',
      desc: 'Creates a clean git branch, commits the verified patch, opens a GitHub PR with complete evidence, and auto-merges when approved.',
      icon: GitPullRequest,
      badge: 'GitHub App API',
      details: 'Generates an immutable audit artifact linking fault analysis, test logs, mutation scores, and reviewer signatures.'
    }
  ];

  const handleSimulate = async (type: string, msg: string, file: string, line: number) => {
    setSimulating(true);
    setSimFeedback(null);
    try {
      const inc = await triggerDemoIncident(type, msg, file, line);
      setSimFeedback(`Realtime Incident #${inc.id.slice(0, 8)} ingested into Overmend! Autonomous pipeline running...`);
      setTimeout(() => {
        onNavigate('IncidentDetail', { incidentId: inc.id });
      }, 1200);
    } catch (e: any) {
      setSimFeedback('Connection error. Ensure API server is running on port 8000.');
    } finally {
      setSimulating(false);
    }
  };

  const isHealthy = health?.status === 'healthy';

  return (
    <div className="space-y-16 pb-16">
      {/* HERO SECTION */}
      <section className="relative overflow-hidden rounded-3xl border border-[#E2E8F0] bg-white p-8 md:p-14 shadow-sm">
        {/* Subtle decorative background gradient */}
        <div className="absolute top-0 right-0 -mt-16 -mr-16 w-96 h-96 rounded-full bg-indigo-50 blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-0 -mb-16 -ml-16 w-96 h-96 rounded-full bg-emerald-50 blur-3xl pointer-events-none" />

        <div className="relative z-10 max-w-4xl space-y-6">
          {/* Top Realtime Status Banner */}
          <div className="inline-flex items-center space-x-2.5 rounded-full border border-indigo-200 bg-indigo-50/80 px-4 py-1.5 text-xs font-semibold text-indigo-700">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-600"></span>
            </span>
            <span>Overmend 2.0 • Autonomous Software Self-Healing & Trust PaaS</span>
            <span className="text-indigo-400">•</span>
            <span className="font-mono text-[11px] text-indigo-600">100% Realtime Telemetry</span>
          </div>

          {/* Main Headline */}
          <h1 className="text-4xl md:text-6xl font-extrabold text-[#0F172A] tracking-tight leading-[1.1]">
            Detect in real-time. Repair with <span className="bg-gradient-to-r from-[#4F46E5] to-[#7C3AED] bg-clip-text text-transparent">proven trust</span>.
          </h1>

          {/* Subtitle */}
          <p className="text-base md:text-lg text-[#64748B] leading-relaxed max-w-3xl">
            Overmend monitors live systems, localizes software exceptions to the exact source line via AST analysis & Git blame, synthesizes verified patches inside isolated Docker sandboxes, and scores patch confidence using mutation testing.
          </p>

          {/* Call to Actions */}
          <div className="flex flex-wrap items-center gap-3 pt-2">
            <button
              id="landing-launch-console-btn"
              onClick={() => onNavigate('Dashboard')}
              className="btn-periwinkle px-6 py-3 text-sm flex items-center space-x-2 shadow-md hover:scale-[1.01] active:scale-[0.99] transition cursor-pointer"
            >
              <Play className="h-4 w-4 fill-white" />
              <span>Launch Live Console</span>
            </button>

            <button
              id="landing-view-incidents-btn"
              onClick={() => onNavigate('Incidents')}
              className="btn-dark px-6 py-3 text-sm flex items-center space-x-2 cursor-pointer"
            >
              <span>View Incidents</span>
              <ArrowRight className="h-4 w-4 text-[#64748B]" />
            </button>

            <button
              id="landing-review-queue-btn"
              onClick={() => onNavigate('ReviewQueue')}
              className="px-5 py-3 text-sm font-semibold rounded-full border border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100 flex items-center space-x-2 cursor-pointer transition"
            >
              <ShieldCheck className="h-4 w-4 text-emerald-600" />
              <span>Review Queue</span>
            </button>
          </div>

          {/* System Telemetry Chips */}
          <div className="pt-6 border-t border-[#F1F5F9] grid grid-cols-2 md:grid-cols-4 gap-4 text-xs font-mono">
            <div>
              <span className="text-[#94A3B8] block text-[10px] uppercase font-bold tracking-wider">Control Plane</span>
              <span className="font-bold flex items-center mt-0.5 text-emerald-700">
                <span className="h-2 w-2 rounded-full bg-emerald-500 mr-1.5" />
                {isHealthy ? 'Live Realtime' : 'Active'}
              </span>
            </div>
            <div>
              <span className="text-[#94A3B8] block text-[10px] uppercase font-bold tracking-wider">Target Org</span>
              <span className="font-bold text-[#0F172A] mt-0.5 block">Overmend AI</span>
            </div>
            <div>
              <span className="text-[#94A3B8] block text-[10px] uppercase font-bold tracking-wider">Avg MTTR</span>
              <span className="font-bold text-indigo-700 mt-0.5 block">&lt; 45 Seconds</span>
            </div>
            <div>
              <span className="text-[#94A3B8] block text-[10px] uppercase font-bold tracking-wider">Trust Engine</span>
              <span className="font-bold text-emerald-700 mt-0.5 block">Mutation-Verified</span>
            </div>
          </div>
        </div>
      </section>

      {/* THREE CORE CLOUD PRODUCTS */}
      <section className="space-y-6">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-2 border-b border-[#E2E8F0] pb-4">
          <div>
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-indigo-600">Product Pillars</span>
            <h2 className="text-2xl font-extrabold text-[#0F172A] tracking-tight mt-0.5">
              Three Specialized Clouds Working in Unison
            </h2>
          </div>
          <p className="text-xs text-[#64748B] max-w-md">
            Decoupled service boundaries allow the Recovery Cloud, Sandbox Cloud, and Trust Engine to operate independently.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Product 1: Recovery Cloud */}
          <div className="panel-card-hover p-6 flex flex-col justify-between space-y-4">
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600">
                <Activity className="h-5 w-5" />
              </div>
              <span className="pill-blue font-mono font-bold">Product 1</span>
              <h3 className="text-lg font-bold text-[#0F172A]">Recovery Cloud</h3>
              <p className="text-xs text-[#64748B] leading-relaxed">
                Autonomous exception capture, stack trace parsing, Python AST inspection, Git blame fault localization, and automated multi-candidate patch synthesis.
              </p>
            </div>
            <ul className="space-y-2 text-xs text-[#334155] border-t border-[#F1F5F9] pt-4 font-mono">
              <li className="flex items-center space-x-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                <span>Zero-touch stack frame localization</span>
              </li>
              <li className="flex items-center space-x-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                <span>3 candidate patches per incident</span>
              </li>
              <li className="flex items-center space-x-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                <span>Automated GitHub PR creation</span>
              </li>
            </ul>
          </div>

          {/* Product 2: Sandbox Cloud */}
          <div className="panel-card-hover p-6 flex flex-col justify-between space-y-4">
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-xl bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-600">
                <Cpu className="h-5 w-5" />
              </div>
              <span className="pill-peach font-mono font-bold">Product 2</span>
              <h3 className="text-lg font-bold text-[#0F172A]">Sandbox Cloud</h3>
              <p className="text-xs text-[#64748B] leading-relaxed">
                Disposable Docker execution containers designed to run unvetted AI-generated patches safely without risk to production hosts or customer data.
              </p>
            </div>
            <ul className="space-y-2 text-xs text-[#334155] border-t border-[#F1F5F9] pt-4 font-mono">
              <li className="flex items-center space-x-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                <span>Resource caps: 0.5 CPU, 512MB RAM</span>
              </li>
              <li className="flex items-center space-x-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                <span>Isolated network bridge mode</span>
              </li>
              <li className="flex items-center space-x-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                <span>Realtime SSE log stream stdout/stderr</span>
              </li>
            </ul>
          </div>

          {/* Product 3: Trust Engine */}
          <div className="panel-card-hover p-6 flex flex-col justify-between space-y-4">
            <div className="space-y-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-600">
                <ShieldCheck className="h-5 w-5" />
              </div>
              <span className="pill-mint font-mono font-bold">Product 3</span>
              <h3 className="text-lg font-bold text-[#0F172A]">Trust Engine</h3>
              <p className="text-xs text-[#64748B] leading-relaxed">
                Mutation-based validation framework that empirically determines whether an AI code fix can be trusted before entering a deployment pipeline.
              </p>
            </div>
            <ul className="space-y-2 text-xs text-[#334155] border-t border-[#F1F5F9] pt-4 font-mono">
              <li className="flex items-center space-x-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                <span>Mutmut test sensitivity verification</span>
              </li>
              <li className="flex items-center space-x-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                <span>Blast radius risk score calculation</span>
              </li>
              <li className="flex items-center space-x-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                <span>Mathematical Trust Score 0.0 - 1.0</span>
              </li>
            </ul>
          </div>
        </div>
      </section>

      {/* INTERACTIVE 8-STEP PIPELINE EXPLORER */}
      <section className="space-y-6">
        <div className="border-b border-[#E2E8F0] pb-4 flex flex-col md:flex-row md:items-end justify-between gap-2">
          <div>
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-indigo-600">Autonomous Architecture</span>
            <h2 className="text-2xl font-extrabold text-[#0F172A] tracking-tight mt-0.5">
              Interactive 8-Step Self-Healing Lifecycle
            </h2>
          </div>
          <span className="text-xs font-mono text-[#64748B]">Click any step to inspect technical details</span>
        </div>

        {/* Step Tabs Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-2">
          {pipelineSteps.map((st, idx) => {
            const Icon = st.icon;
            const isSelected = activeStep === idx;
            return (
              <button
                key={st.step}
                onClick={() => setActiveStep(idx)}
                className={`p-3 text-left rounded-2xl border transition-all cursor-pointer ${
                  isSelected 
                    ? 'border-[#4F46E5] bg-[#EEF2FF] shadow-xs' 
                    : 'border-[#E2E8F0] bg-white hover:border-[#CBD5E1]'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-[10px] font-mono font-bold ${isSelected ? 'text-[#4F46E5]' : 'text-[#94A3B8]'}`}>
                    {st.step}
                  </span>
                  <Icon className={`h-4 w-4 ${isSelected ? 'text-[#4F46E5]' : 'text-[#64748B]'}`} />
                </div>
                <div className="mt-2">
                  <span className="text-xs font-bold block text-[#0F172A] truncate">{st.title}</span>
                  <span className="text-[10px] text-[#64748B] block truncate">{st.subtitle}</span>
                </div>
              </button>
            );
          })}
        </div>

        {/* Selected Step Detail Inspector Panel */}
        <div className="panel-card p-6 md:p-8 bg-gradient-to-r from-white to-[#F8FAFC]">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-[#E2E8F0] pb-5">
            <div className="space-y-1">
              <div className="flex items-center space-x-3">
                <span className="text-sm font-mono font-extrabold text-[#4F46E5]">
                  STEP {pipelineSteps[activeStep].step}
                </span>
                <span className="pill-blue font-mono font-bold">
                  {pipelineSteps[activeStep].badge}
                </span>
              </div>
              <h3 className="text-xl font-extrabold text-[#0F172A]">
                {pipelineSteps[activeStep].title} — {pipelineSteps[activeStep].subtitle}
              </h3>
            </div>

            <div className="flex items-center space-x-2">
              <button
                onClick={() => setActiveStep((prev) => (prev > 0 ? prev - 1 : pipelineSteps.length - 1))}
                className="px-3 py-1.5 rounded-lg border border-[#CBD5E1] bg-white text-xs font-bold text-[#0F172A] hover:bg-[#F1F5F9] cursor-pointer"
              >
                Previous
              </button>
              <button
                onClick={() => setActiveStep((prev) => (prev < pipelineSteps.length - 1 ? prev + 1 : 0))}
                className="px-3 py-1.5 rounded-lg border border-[#CBD5E1] bg-white text-xs font-bold text-[#0F172A] hover:bg-[#F1F5F9] cursor-pointer"
              >
                Next Step
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-6">
            <div className="space-y-3">
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-[#64748B]">Operational Overview</span>
              <p className="text-sm text-[#334155] leading-relaxed">
                {pipelineSteps[activeStep].desc}
              </p>
              <div className="p-4 rounded-xl border border-[#E2E8F0] bg-white space-y-1">
                <span className="text-xs font-bold text-[#0F172A] block">Formal Governance Standard</span>
                <p className="text-xs text-[#64748B]">
                  {pipelineSteps[activeStep].details}
                </p>
              </div>
            </div>

            <div className="rounded-xl border border-[#CBD5E1] bg-[#0F172A] p-4 text-xs font-mono text-emerald-400 overflow-x-auto space-y-2">
              <div className="text-[10px] text-slate-400 border-b border-slate-700 pb-1.5 flex justify-between">
                <span>STAGE_TELEMETRY: {pipelineSteps[activeStep].title.toUpperCase()}</span>
                <span className="text-emerald-400">STATE: VERIFIED</span>
              </div>
              <pre className="text-[11px] leading-relaxed text-slate-300">
                {activeStep === 0 && `POST /api/v1/events HTTP/1.1\nX-Project-ID: proj_feb51039\n{\n  "exception_type": "ZeroDivisionError",\n  "fingerprint": "a9f81bc294a0",\n  "status": "DETECTED",\n  "environment": "production"\n}`}
                {activeStep === 1 && `AST Analyzer: payments/service.py:184\nEnclosing func: calculate_refund_rate\nGit blame hash: 7e9b01c (by @developer)\nBlast radius: 0.12 (LOW)`}
                {activeStep === 2 && `Synthesized 3 patch candidates:\n[1] Safe Zero Check (Confidence 0.96)\n[2] Try/Except Block Fallback (Confidence 0.88)\n[3] Decimal Scaling Guard (Confidence 0.82)`}
                {activeStep === 3 && `Sandbox Container: sbx_c9103e2\nLimits: 0.5 CPU, 512MB RAM, net=none\nTests: 4 passed in 0.08s\nStdout: Exit Code 0 [PASS]`}
                {activeStep === 4 && `Mutmut Engine: 10 mutants synthesized\nMutants killed: 10 / 10\nMutants survived: 0\nMutation Score: 100.0% [ROBUST]`}
                {activeStep === 5 && `Trust Evaluation Formula:\n  S_test: 1.0  * 0.40 = 0.40\n  S_mut:  1.0  * 0.40 = 0.40\n  S_blast:0.88 * 0.20 = 0.176\nFinal Trust Score: 0.976 -> AUTO_MERGE`}
                {activeStep === 6 && `Governance Policy Engine:\nRule 'auto_merge_threshold': >= 0.90 [PASS]\nRule 'sensitive_file_check': None [PASS]\nAction: AUTO_MERGE authorized`}
                {activeStep === 7 && `GitHub Client:\nBranch: recovery/fix-inc_8f192b0\nCommit: "fix: autonomous recovery for incident inc_8f192b0"\nPR #42 opened and automatically merged`}
              </pre>
            </div>
          </div>
        </div>
      </section>

      {/* REALTIME INCIDENT SIMULATION PLAYGROUND */}
      <section className="panel-card p-8 bg-white border border-[#E2E8F0] space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#E2E8F0] pb-5">
          <div>
            <div className="flex items-center space-x-2">
              <span className="pill-coral font-mono font-bold">Interactive Lab</span>
              <h2 className="text-xl font-extrabold text-[#0F172A]">
                Trigger a Realtime Pipeline Execution
              </h2>
            </div>
            <p className="text-xs text-[#64748B] mt-1 font-sans">
              Select any live exception scenario to dispatch a live payload directly through the Overmend ingestion engine.
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <span className="text-xs font-mono text-[#64748B]">Active Repo:</span>
            <span className="pill-blue font-mono font-bold">jyotsnag-l/recovery-test-repo</span>
          </div>
        </div>

        {simFeedback && (
          <div className="p-4 rounded-xl border border-indigo-200 bg-indigo-50 text-indigo-800 text-xs font-mono flex items-center justify-between animate-fadeIn">
            <div className="flex items-center space-x-2">
              <RefreshCw className="h-4 w-4 animate-spin text-indigo-600 shrink-0" />
              <span>{simFeedback}</span>
            </div>
            <button
              onClick={() => onNavigate('Incidents')}
              className="font-bold underline hover:text-indigo-900 cursor-pointer ml-4"
            >
              View in Incidents
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <button
            disabled={simulating}
            onClick={() => handleSimulate('ZeroDivisionError', 'division by zero in calculate_refund_rate()', 'payments/service.py', 184)}
            className="p-5 text-left rounded-2xl border border-[#E2E8F0] bg-[#F8FAFC] hover:border-rose-400 hover:bg-rose-50/50 transition group cursor-pointer"
          >
            <div className="flex justify-between items-center text-xs font-mono mb-2">
              <span className="font-bold text-rose-600">ZeroDivisionError</span>
              <span className="text-[10px] text-[#94A3B8]">service.py:184</span>
            </div>
            <p className="text-xs text-[#64748B] font-sans">Trigger failure when refund calculation encounters zero transactions.</p>
            <span className="text-xs font-bold text-indigo-600 group-hover:translate-x-1 transition-transform inline-flex items-center space-x-1 mt-3">
              <span>Execute Live</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </span>
          </button>

          <button
            disabled={simulating}
            onClick={() => handleSimulate('KeyError', 'stripe_signature header missing in webhook', 'auth/verification.py', 42)}
            className="p-5 text-left rounded-2xl border border-[#E2E8F0] bg-[#F8FAFC] hover:border-amber-400 hover:bg-amber-50/50 transition group cursor-pointer"
          >
            <div className="flex justify-between items-center text-xs font-mono mb-2">
              <span className="font-bold text-amber-600">KeyError</span>
              <span className="text-[10px] text-[#94A3B8]">verification.py:42</span>
            </div>
            <p className="text-xs text-[#64748B] font-sans">Webhook receiver missing authorization signature in request payload.</p>
            <span className="text-xs font-bold text-indigo-600 group-hover:translate-x-1 transition-transform inline-flex items-center space-x-1 mt-3">
              <span>Execute Live</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </span>
          </button>

          <button
            disabled={simulating}
            onClick={() => handleSimulate('AttributeError', "'NoneType' object has no attribute 'get_rate_limit'", 'gateway/rate_limiter.py', 92)}
            className="p-5 text-left rounded-2xl border border-[#E2E8F0] bg-[#F8FAFC] hover:border-purple-400 hover:bg-purple-50/50 transition group cursor-pointer"
          >
            <div className="flex justify-between items-center text-xs font-mono mb-2">
              <span className="font-bold text-purple-600">AttributeError</span>
              <span className="text-[10px] text-[#94A3B8]">rate_limiter.py:92</span>
            </div>
            <p className="text-xs text-[#64748B] font-sans">API gateway attempting lookup on an uninitialized client context.</p>
            <span className="text-xs font-bold text-indigo-600 group-hover:translate-x-1 transition-transform inline-flex items-center space-x-1 mt-3">
              <span>Execute Live</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </span>
          </button>

          <button
            disabled={simulating}
            onClick={() => handleSimulate('TypeError', "unsupported operand type(s) for +: 'NoneType' and 'int'", 'analytics/counter.py', 28)}
            className="p-5 text-left rounded-2xl border border-[#E2E8F0] bg-[#F8FAFC] hover:border-blue-400 hover:bg-blue-50/50 transition group cursor-pointer"
          >
            <div className="flex justify-between items-center text-xs font-mono mb-2">
              <span className="font-bold text-blue-600">TypeError</span>
              <span className="text-[10px] text-[#94A3B8]">counter.py:28</span>
            </div>
            <p className="text-xs text-[#64748B] font-sans">Aggregator attempting arithmetic addition on nullable database field.</p>
            <span className="text-xs font-bold text-indigo-600 group-hover:translate-x-1 transition-transform inline-flex items-center space-x-1 mt-3">
              <span>Execute Live</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </span>
          </button>
        </div>
      </section>

      {/* FOOTER CTA BAR */}
      <div className="card-periwinkle p-8 md:p-10 flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="space-y-1 text-center md:text-left">
          <h3 className="text-2xl font-extrabold text-white">Ready to inspect active recovery pipelines?</h3>
          <p className="text-indigo-100 text-xs md:text-sm">
            Launch the console to monitor live incidents, review sandboxed patches, and configure governance policies.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => onNavigate('Dashboard')}
            className="px-6 py-3 rounded-full bg-white text-[#4F46E5] font-bold text-xs shadow-md hover:bg-indigo-50 transition cursor-pointer"
          >
            Go to Dashboard
          </button>
          <button
            onClick={() => onNavigate('Repository')}
            className="px-6 py-3 rounded-full bg-white/10 hover:bg-white/20 text-white font-bold text-xs border border-white/20 transition cursor-pointer"
          >
            Manage Repositories
          </button>
        </div>
      </div>
    </div>
  );
}
