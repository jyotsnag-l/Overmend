import { useEffect, useState } from 'react';
import { 
  Shield, Activity, AlertTriangle, AlertCircle, LayoutDashboard, 
  ShieldCheck, Settings2, BarChart2, GitFork, PlaySquare,
  Lock, Check, X, Info
} from 'lucide-react';

// API & Components Imports
import { 
  fetchHealth, HealthStatus, SIMULATED_PROFILES, getSimulatedProfile, setSimulatedProfile, triggerDemoIncident 
} from './api';
import { 
  ROLE_CONFIGS, canTriggerIncidents, UserRole, PERMISSION_MATRIX 
} from './permissions';
import DashboardPage from './components/DashboardPage';
import IncidentsPage from './components/IncidentsPage';
import IncidentDetailPage from './components/IncidentDetailPage';
import PatchComparisonPage from './components/PatchComparisonPage';
import SandboxPage from './components/SandboxPage';
import TrustPage from './components/TrustPage';
import RepositoryPage from './components/RepositoryPage';
import SettingsPage from './components/SettingsPage';
import ReviewQueuePage from './components/ReviewQueuePage';
import OrganizationPage from './components/OrganizationPage';

export default function App() {
  // Routing & navigation state
  const [currentPage, setCurrentPage] = useState<string>('Dashboard');
  const [pageParams, setPageParams] = useState<Record<string, any>>({});

  // Telemetry Health state
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Profile switcher state
  const [activeProfile, setActiveProfile] = useState(getSimulatedProfile());
  const [showRbacModal, setShowRbacModal] = useState(false);
  const [showTosModal, setShowTosModal] = useState(false);
  const [showPrivacyModal, setShowPrivacyModal] = useState(false);

  // Demo trigger modal / button state
  const [triggering, setTriggering] = useState(false);
  const [triggerSuccess, setTriggerSuccess] = useState<string | null>(null);

  const currentRole = activeProfile.role as UserRole;
  const roleConfig = ROLE_CONFIGS[currentRole] || ROLE_CONFIGS.VIEWER;
  const RoleIcon = roleConfig.icon;
  const userCanTrigger = canTriggerIncidents(currentRole);

  const fetchSystemHealth = async () => {
    try {
      const data = await fetchHealth();
      setHealth(data);
      setErrorMsg(null);
    } catch (e: any) {
      console.error("Failed to fetch system health link", e);
      setHealth({
        status: "unhealthy",
        database: "unhealthy",
        redis: "unhealthy",
        celery: "unhealthy"
      });
      setErrorMsg("Telemetry connection degraded. Control plane offline.");
    }
  };

  const handleProfileChange = (email: string) => {
    setSimulatedProfile(email);
    const newProfile = getSimulatedProfile();
    setActiveProfile(newProfile);
    window.location.reload();
  };

  const handleNavigate = (page: string, params: Record<string, any> = {}) => {
    setCurrentPage(page);
    setPageParams(params);
  };

  const handleTriggerDemo = async () => {
    if (!userCanTrigger) return;
    setTriggering(true);
    try {
      await triggerDemoIncident(
        'KeyError',
        'stripe_signature header missing in webhook',
        'auth/verification.py',
        42
      );
      setTriggerSuccess('Simulated KeyError incident ingested! Self-healing pipeline enqueued.');
      fetchSystemHealth();
      setCurrentPage('Incidents');
      setTimeout(() => setTriggerSuccess(null), 5000);
    } catch (e) {
      console.error('Failed to trigger demo incident', e);
      alert('Ingestion error: Ensure FastAPI server is running on port 8000.');
    } finally {
      setTriggering(false);
    }
  };

  useEffect(() => {
    fetchSystemHealth();
    const timer = setInterval(fetchSystemHealth, 6000);
    return () => clearInterval(timer);
  }, []);

  const renderPage = () => {
    switch (currentPage) {
      case 'Dashboard':
        return <DashboardPage onNavigate={handleNavigate} />;
      case 'Incidents':
        return <IncidentsPage onNavigate={handleNavigate} />;
      case 'IncidentDetail':
        return <IncidentDetailPage incidentId={pageParams.incidentId} onNavigate={handleNavigate} />;
      case 'PatchComparison':
        return (
          <PatchComparisonPage 
            incidentId={pageParams.incidentId} 
            activePatchId={pageParams.activePatchId} 
            onNavigate={handleNavigate} 
          />
        );
      case 'Sandbox':
        return <SandboxPage jobId={pageParams.jobId} onNavigate={handleNavigate} />;
      case 'Trust':
        return <TrustPage patchCandidateId={pageParams.patchCandidateId} onNavigate={handleNavigate} />;
      case 'Repository':
        return <RepositoryPage />;
      case 'Organization':
        return <OrganizationPage />;
      case 'Settings':
        return <SettingsPage />;
      case 'ReviewQueue':
        return <ReviewQueuePage />;
      default:
        return <DashboardPage onNavigate={handleNavigate} />;
    }
  };

  const menuItems = [
    { name: 'Dashboard', icon: LayoutDashboard, badge: null },
    { name: 'Incidents', icon: AlertCircle, badge: null },
    { name: 'Review Queue', icon: ShieldCheck, badge: 'Live' },
    { name: 'Repository', icon: GitFork, badge: null },
    { name: 'Organization', icon: BarChart2, badge: null },
    { name: 'Settings', icon: Settings2, badge: null }
  ];

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-[#0F172A] flex flex-col antialiased selection:bg-[#4F46E5] selection:text-white">
      {/* TOP HEADER CONTROL BAR */}
      <header className="bg-white border-b border-[#E2E8F0] sticky top-0 z-40 px-8 py-4 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-sm">
        {/* Brand & Search Bar */}
        <div className="flex items-center space-x-8">
          <div className="flex items-center space-x-3.5 cursor-pointer" onClick={() => handleNavigate('Dashboard')}>
            <div className="flex items-center justify-center h-11 w-11 rounded-2xl bg-[#EEF2FF] border border-[#C7D2FE] shadow-xs">
              <img src="/overmend_logo.svg" alt="Overmend Logo" className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-lg font-black tracking-wider text-[#0F172A] uppercase font-mono leading-none">
                Overmend AI
              </h1>
              <span className="text-[10px] font-mono font-bold text-[#4F46E5] tracking-widest uppercase">Self-Healing Infrastructure</span>
            </div>
          </div>

          <div className="relative hidden md:block w-80 lg:w-96">
            <input 
              type="text"
              placeholder="Search incidents, repos, stack traces..."
              className="w-full bg-[#F1F5F9] border border-[#CBD5E1] rounded-full px-5 py-2.5 text-sm text-[#0F172A] placeholder-stone-400 focus:outline-none focus:border-[#4F46E5] shadow-xs transition"
            />
          </div>
        </div>

        {/* User Profile & Ingest Action */}
        <div className="flex items-center space-x-4">
          {/* RBAC Role Switcher */}
          <div className="flex items-center space-x-2.5 bg-[#F1F5F9] border border-[#CBD5E1] px-4 py-2.5 rounded-full shadow-xs hover:border-[#4F46E5] transition">
            <RoleIcon className="h-4 w-4 text-[#4F46E5] flex-shrink-0" />
            <select
              value={activeProfile.email}
              onChange={(e) => handleProfileChange(e.target.value)}
              className="bg-transparent text-sm font-bold text-[#0F172A] focus:outline-none border-none cursor-pointer pr-2"
            >
              {SIMULATED_PROFILES.map((p) => (
                <option key={p.email} value={p.email} className="bg-white text-[#0F172A] font-semibold">
                  {p.name} ({p.role})
                </option>
              ))}
            </select>
          </div>

          {/* Trigger Demo Ingestion */}
          {userCanTrigger ? (
            <button
              onClick={handleTriggerDemo}
              disabled={triggering}
              className="btn-periwinkle px-6 py-2.5 text-sm font-extrabold transition flex items-center space-x-2.5 shadow-md rounded-full active:scale-95 disabled:opacity-50"
            >
              <PlaySquare className="h-4 w-4" />
              <span>{triggering ? 'Ingesting...' : '+ Ingest Fail Event'}</span>
            </button>
          ) : (
            <div 
              title="Action Restricted: Viewer role is Read-Only."
              className="flex items-center space-x-2 px-5 py-2.5 bg-[#F1F5F9] border border-[#CBD5E1] text-stone-400 rounded-full text-xs font-bold cursor-not-allowed"
            >
              <Lock className="h-3.5 w-3.5 text-stone-400" />
              <span>Ingest (Locked)</span>
            </div>
          )}
        </div>
      </header>

      {/* Connection Degradation Warning */}
      {errorMsg && (
        <div className="bg-rose-50 border-b border-rose-200 text-rose-700 px-8 py-2.5 flex items-center space-x-3 text-xs font-bold">
          <AlertTriangle className="h-4 w-4 text-rose-500 flex-shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Trigger Success Notification */}
      {triggerSuccess && (
        <div className="bg-emerald-50 border-b border-emerald-200 text-emerald-700 px-8 py-2.5 flex items-center space-x-3 text-xs font-bold">
          <Activity className="h-4 w-4 text-emerald-500 flex-shrink-0" />
          <span>{triggerSuccess}</span>
        </div>
      )}

      {/* WORKSPACE SIDEBAR & RENDER PAGE */}
      <div className="flex-1 flex flex-col md:flex-row">
        {/* SIDEBAR NAVIGATION */}
        <aside className="w-full md:w-72 border-r border-[#E2E8F0] bg-white px-5 py-7 flex flex-col justify-between shadow-xs">
          <div className="space-y-6">
            <div>
              <span className="text-xs font-mono text-stone-400 uppercase tracking-widest font-bold block px-3 mb-3">
                Workspace Navigation
              </span>
              <nav className="space-y-1.5">
                {menuItems.map((item) => {
                  const Icon = item.icon;
                  const isActive = currentPage === item.name || 
                    (item.name === 'Incidents' && (currentPage === 'IncidentDetail' || currentPage === 'PatchComparison' || currentPage === 'Sandbox' || currentPage === 'Trust'));
                  return (
                    <button
                      key={item.name}
                      onClick={() => handleNavigate(item.name)}
                      className={`w-full flex items-center justify-between px-4 py-3 rounded-2xl text-sm font-bold transition-all ${
                        isActive 
                          ? 'bg-[#4F46E5] text-white shadow-sm' 
                          : 'text-[#64748B] hover:bg-[#F1F5F9] hover:text-[#0F172A]'
                      }`}
                    >
                      <div className="flex items-center space-x-3.5">
                        <Icon className={`h-5 w-5 ${isActive ? 'text-white' : 'text-[#64748B]'}`} />
                        <span>{item.name}</span>
                      </div>
                      {item.badge && (
                        <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0] font-bold">
                          {item.badge}
                        </span>
                      )}
                    </button>
                  );
                })}
              </nav>
            </div>

            {/* Active Role Card */}
            <div className="p-5 rounded-2xl border border-[#E2E8F0] bg-[#F8FAFC] space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-stone-500">Current Role</span>
                <span className="pill-mint font-bold">
                  {roleConfig.label}
                </span>
              </div>
              <p className="text-xs text-[#64748B] font-sans leading-relaxed">
                {roleConfig.description}
              </p>
            </div>
          </div>

          <div className="pt-4 border-t border-[#E2E8F0] text-xs font-mono text-[#64748B] space-y-1.5 px-2">
            <div className="flex justify-between">
              <span>Organization:</span>
              <span className="text-[#0F172A] font-bold">org_seed</span>
            </div>
            <div className="flex justify-between">
              <span>Recovery Engine:</span>
              <span className="text-[#059669] font-bold flex items-center">
                <span className="h-2 w-2 rounded-full bg-[#059669] mr-1.5" />
                Active
              </span>
            </div>
          </div>
        </aside>

        {/* MAIN PANEL CONTENT */}
        <main className="flex-1 p-6 overflow-y-auto max-w-7xl mx-auto w-full">
          {renderPage()}
        </main>
      </div>

      {/* RBAC PERMISSIONS INSPECTOR MODAL */}
      {showRbacModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="panel-card max-w-2xl w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
              <div>
                <h3 className="text-sm font-bold font-mono text-[#0F172A] flex items-center space-x-2">
                  <ShieldCheck className="h-4 w-4 text-[#4F46E5]" />
                  <span>Role-Based Access Control (RBAC) Matrix</span>
                </h3>
                <p className="text-xs text-[#64748B] mt-0.5 font-sans">Multi-tenant role boundaries and authorization governance</p>
              </div>
              <button 
                onClick={() => setShowRbacModal(false)}
                className="p-1 text-[#64748B] hover:text-[#0F172A] rounded hover:bg-[#F1F5F9]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="border-b border-[#E2E8F0] text-[#64748B] text-[10px] uppercase bg-[#F8FAFC]">
                    <th className="text-left py-2 font-semibold">Action / Feature</th>
                    <th className="text-center py-2">Owner</th>
                    <th className="text-center py-2">Admin</th>
                    <th className="text-center py-2">Reviewer</th>
                    <th className="text-center py-2">Engineer</th>
                    <th className="text-center py-2">Viewer</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E2E8F0]">
                  {PERMISSION_MATRIX.map((perm, idx) => (
                    <tr key={idx} className="hover:bg-[#F8FAFC] transition">
                      <td className="py-2 pr-4">
                        <span className="font-semibold text-[#0F172A] block">{perm.action}</span>
                        <span className="text-[10px] text-[#64748B] block font-sans">{perm.description}</span>
                      </td>
                      {(['OWNER', 'ADMIN', 'REVIEWER', 'ENGINEER', 'VIEWER'] as UserRole[]).map(r => {
                        const allowed = perm.allowedRoles.includes(r);
                        const isCurrent = currentRole === r;
                        return (
                          <td key={r} className={`text-center py-2 px-2 ${isCurrent ? 'bg-[#EEF2FF]' : ''}`}>
                            {allowed ? (
                              <span className="inline-flex items-center justify-center h-4 w-4 rounded bg-emerald-100 text-emerald-700 border border-emerald-300">
                                <Check className="h-3 w-3" />
                              </span>
                            ) : (
                              <span className="inline-flex items-center justify-center h-4 w-4 rounded bg-[#F1F5F9] text-[#94A3B8]">
                                <X className="h-3 w-3" />
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

            <div className="flex items-center justify-between pt-3 border-t border-[#E2E8F0]">
              <div className="text-[11px] text-[#64748B] flex items-center space-x-2">
                <span>Authenticated as:</span>
                <span className="font-mono font-semibold text-[#0F172A]">
                  {roleConfig.label} ({currentRole})
                </span>
              </div>
              <button
                onClick={() => setShowRbacModal(false)}
                className="btn-dark px-3 py-1 text-xs font-mono"
              >
                Close Matrix
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TERMS OF SERVICE MODAL */}
      {showTosModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="panel-card max-w-xl w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
              <h3 className="text-sm font-bold font-mono text-[#0F172A]">Terms of Service</h3>
              <button onClick={() => setShowTosModal(false)} className="p-1 text-[#64748B] hover:text-[#0F172A]"><X className="h-4 w-4" /></button>
            </div>
            <div className="text-xs text-[#64748B] font-sans space-y-3 max-h-[300px] overflow-y-auto leading-relaxed">
              <p><strong>1. Acceptable Usage Policy</strong>: Overmend AI provides automated software fault localization and AST patch synthesis for authorized repository owners. Users are responsible for configuring appropriate decision thresholds and reviewing patches for security-sensitive modules.</p>
              <p><strong>2. Telemetry Data Protection</strong>: Stack traces, exception telemetry, and AST mutations are processed securely within your designated cloud or on-premise control plane instance. No proprietary source code is shared externally.</p>
              <p><strong>3. Warranty & Liability</strong>: The self-healing pipeline executes sandbox verification suites prior to pull request generation. Overmend AI provides automated remediation assistance without replacing human engineering review for safety-critical systems.</p>
            </div>
            <div className="flex justify-end pt-2 border-t border-[#E2E8F0]">
              <button onClick={() => setShowTosModal(false)} className="btn-dark px-4 py-1.5 text-xs font-mono">I Understand</button>
            </div>
          </div>
        </div>
      )}

      {/* PRIVACY POLICY MODAL */}
      {showPrivacyModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="panel-card max-w-xl w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
              <h3 className="text-sm font-bold font-mono text-[#0F172A]">Privacy Policy</h3>
              <button onClick={() => setShowPrivacyModal(false)} className="p-1 text-[#64748B] hover:text-[#0F172A]"><X className="h-4 w-4" /></button>
            </div>
            <div className="text-xs text-[#64748B] font-sans space-y-3 max-h-[300px] overflow-y-auto leading-relaxed">
              <p><strong>1. Telemetry Data Collection</strong>: We collect error exception traces, function line identifiers, and mutation execution scores strictly for fault localization and patch candidate generation.</p>
              <p><strong>2. Encryption & Storage</strong>: All audit logs, pull request records, and trust metrics are encrypted at rest using AES-256 and transmitted exclusively over TLS 1.3 encrypted channels.</p>
              <p><strong>3. Data Retention & Access</strong>: Historical incident logs and sandbox execution streams are retained according to your organization policy configurations. You may purge incident telemetry at any time via Settings.</p>
            </div>
            <div className="flex justify-end pt-2 border-t border-[#E2E8F0]">
              <button onClick={() => setShowPrivacyModal(false)} className="btn-dark px-4 py-1.5 text-xs font-mono">Close Policy</button>
            </div>
          </div>
        </div>
      )}

      {/* FOOTER */}
      <footer className="border-t border-[#E2E8F0] bg-white px-6 py-3 flex flex-col md:flex-row items-center justify-between gap-2 text-[11px] font-mono text-[#64748B]">
        <p>© 2026 Overmend AI Systems Inc. Enterprise Control Plane.</p>
        <div className="flex items-center space-x-4">
          <button onClick={() => setShowTosModal(true)} className="hover:text-[#0F172A] underline font-semibold transition">Terms of Service</button>
          <span>•</span>
          <button onClick={() => setShowPrivacyModal(true)} className="hover:text-[#0F172A] underline font-semibold transition">Privacy Policy</button>
          <span>•</span>
          <span className="text-emerald-600 font-semibold">v1.0-stable</span>
        </div>
      </footer>
    </div>
  );
}
