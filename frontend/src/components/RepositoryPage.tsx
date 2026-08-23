import { useEffect, useState } from 'react';
import { 
  GitBranch, ShieldAlert, Heart, CheckCircle2, RefreshCw, Lock, 
  Sliders, FileCode, Check, Plus, X, Globe
} from 'lucide-react';
import { 
  fetchRepositories, syncRepositories, Repository, fetchProjectPolicy, ProjectPolicy, saveProjectPolicy, getSimulatedProfile 
} from '../api';
import { canEditPolicies, canSyncRepositories, UserRole } from '../permissions';

export default function RepositoryPage() {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [selectedRepoId, setSelectedRepoId] = useState<string | null>(null);
  const [policy, setPolicy] = useState<ProjectPolicy | null>(null);
  
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [loadingPolicy, setLoadingPolicy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Form states
  const [autoMergeThreshold, setAutoMergeThreshold] = useState(90);
  const [mandatoryReviewThreshold, setMandatoryReviewThreshold] = useState(70);
  const [restrictedFiles, setRestrictedFiles] = useState<string[]>([]);
  const [newTagInput, setNewTagInput] = useState('');

  // RBAC checks
  const profile = getSimulatedProfile();
  const currentRole = profile.role as UserRole;
  const userCanEdit = canEditPolicies(currentRole);
  const userCanSync = canSyncRepositories(currentRole);
  
  const loadData = async () => {
    try {
      const repos = await fetchRepositories();
      setRepositories(repos);
      if (repos.length > 0 && !selectedRepoId) {
        setSelectedRepoId(repos[0].id);
      }
      setError(null);
    } catch (err) {
      console.error('Failed to load repositories', err);
      setError('Failed to fetch repositories list.');
    } finally {
      setLoading(false);
    }
  };

  const handleSyncRegistry = async () => {
    if (!userCanSync) return;
    setSyncing(true);
    try {
      const synced = await syncRepositories();
      setRepositories(synced);
      if (synced.length > 0) {
        setSelectedRepoId(synced[synced.length - 1].id);
      }
      setSyncMessage(`GITHUB SYNC SUCCESSFUL: ${synced.length} active installation repositories registered.`);
      setTimeout(() => setSyncMessage(null), 5000);
      setError(null);
    } catch (err) {
      console.error('Failed to sync repositories', err);
      setError('GitHub sync failed. Check GitHub App configuration.');
    } finally {
      setSyncing(false);
    }
  };

  const loadPolicy = async (repoId: string) => {
    setLoadingPolicy(true);
    try {
      const repo = repositories.find(r => r.id === repoId);
      if (repo) {
        const pol = await fetchProjectPolicy(repo.project_id);
        setPolicy(pol);
        setAutoMergeThreshold(Math.round(pol.auto_merge_threshold * 100));
        setMandatoryReviewThreshold(Math.round(pol.mandatory_review_threshold * 100));
        setRestrictedFiles(pol.restricted_files || []);
      }
    } catch (err) {
      console.error('Failed to load project policy', err);
    } finally {
      setLoadingPolicy(false);
    }
  };

  const handleAddRestrictedFile = () => {
    if (!newTagInput.trim() || !userCanEdit) return;
    const cleaned = newTagInput.trim().replace(/^[,]+|[,]+$/g, '');
    if (cleaned && !restrictedFiles.includes(cleaned)) {
      setRestrictedFiles([...restrictedFiles, cleaned]);
      setNewTagInput('');
    }
  };

  const handleRemoveRestrictedFile = (fileToRemove: string) => {
    if (!userCanEdit) return;
    setRestrictedFiles(restrictedFiles.filter(f => f !== fileToRemove));
  };

  const handleSavePolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRepoId || !policy) return;
    if (!userCanEdit) {
      alert(`Permission Denied: Your role (${currentRole}) cannot modify policies.`);
      return;
    }

    const repo = repositories.find(r => r.id === selectedRepoId);
    if (!repo) return;

    setLoadingPolicy(true);
    try {
      const updated = await saveProjectPolicy(repo.project_id, {
        auto_merge_threshold: autoMergeThreshold / 100,
        mandatory_review_threshold: mandatoryReviewThreshold / 100,
        restricted_files: restrictedFiles
      });
      
      setPolicy(updated);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 4000);
    } catch (err) {
      console.error('Failed to save policy', err);
      alert('Failed to save project policies. Verify permissions.');
    } finally {
      setLoadingPolicy(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (selectedRepoId && repositories.length > 0) {
      loadPolicy(selectedRepoId);
    }
  }, [selectedRepoId, repositories]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-28 text-slate-400 space-y-4">
        <GitBranch className="h-8 w-8 animate-spin text-indigo-400" />
        <p className="text-xs font-mono font-bold tracking-widest text-slate-400">RETRIEVING REPOSITORY HEALTH INDICES...</p>
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
              Repository Registry
            </h2>
            <span className="pill-blue font-bold">
              {repositories.length} Active Targets
            </span>
          </div>
          <p className="text-xs text-[#64748B] mt-1 font-sans">
            Configure safety thresholds, sensitive file access boundaries, and auto-merge automation
          </p>
        </div>

        {userCanSync ? (
          <button 
            onClick={handleSyncRegistry}
            disabled={syncing}
            className="btn-periwinkle px-5 py-2.5 text-xs font-bold flex items-center space-x-2 shadow-xs disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${syncing ? 'animate-spin' : ''}`} />
            <span>{syncing ? 'Syncing GitHub App...' : 'Sync GitHub App Repos'}</span>
          </button>
        ) : (
          <div 
            title="Syncing repositories requires Platform Admin or Org Owner privileges."
            className="px-4 py-2 bg-[#F1F5F9] border border-[#CBD5E1] text-[#94A3B8] rounded-xl text-xs font-bold flex items-center space-x-2 cursor-not-allowed"
          >
            <Lock className="h-3.5 w-3.5" />
            <span>Sync (Admin Locked)</span>
          </div>
        )}
      </div>

      {syncMessage && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-900 font-mono text-xs rounded-2xl flex items-center space-x-3">
          <CheckCircle2 className="h-5 w-5 text-emerald-700 flex-shrink-0" />
          <span>{syncMessage}</span>
        </div>
      )}

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 text-rose-700 font-mono text-xs rounded-2xl flex items-center space-x-3">
          <ShieldAlert className="h-5 w-5 text-rose-500 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Repositories Selector List */}
        <div className="space-y-4 lg:col-span-1">
          <h3 className="text-xs font-mono font-bold tracking-wider text-[#64748B] uppercase">
            Registered Repositories ({repositories.length})
          </h3>
          <div className="space-y-2.5">
            {repositories.length === 0 ? (
              <div className="text-center py-12 text-[#64748B] font-mono text-xs panel-card">
                NO REPOSITORIES REGISTERED. CLICK SYNC GITHUB APP REPOS.
              </div>
            ) : (
              repositories.map(repo => {
                const isActive = repo.id === selectedRepoId;
                return (
                  <div
                    key={repo.id}
                    onClick={() => setSelectedRepoId(repo.id)}
                    className={`p-4 rounded-2xl border cursor-pointer transition-all flex flex-col space-y-2.5 ${
                      isActive 
                        ? 'bg-[#EEF2FF] border-[#4F46E5] text-[#0F172A] shadow-xs font-bold' 
                        : 'bg-white hover:bg-[#F8FAFC] border-[#E2E8F0] text-[#64748B]'
                    }`}
                  >
                    <div className="flex justify-between items-center">
                      <span className="text-xs font-mono font-bold text-[#0F172A] truncate max-w-[170px]">{repo.name}</span>
                      <span className="pill-mint font-bold flex items-center">
                        <Heart className="h-2.5 w-2.5 text-[#059669] mr-1 animate-pulse" /> 98% Health
                      </span>
                    </div>

                    <div className="flex items-center space-x-1.5 text-[10px] text-[#64748B] font-mono truncate">
                      <Globe className="h-3 w-3 flex-shrink-0" />
                      <span className="truncate">{repo.url}</span>
                    </div>
                    
                    <div className="flex justify-between items-center text-[10px] font-mono text-[#64748B] pt-1.5 border-t border-[#E2E8F0]">
                      <span className="flex items-center">
                        <GitBranch className="h-3 w-3 mr-1 text-stone-400" /> main
                      </span>
                      <span className="text-[#059669] font-semibold">Self-Healing On</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Selected Repository Configuration Details */}
        <div className="lg:col-span-2 space-y-6">
          {loadingPolicy ? (
            <div className="text-center py-28 text-[#64748B] font-mono text-xs panel-card space-y-3">
              <RefreshCw className="h-6 w-6 animate-spin text-[#4F46E5] mx-auto" />
              <p>LOADING PROJECT POLICY CRITERIA...</p>
            </div>
          ) : policy ? (
            <form onSubmit={handleSavePolicy} className="panel-card p-6 space-y-6">
              <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-4">
                <div>
                  <h3 className="text-sm font-mono font-bold tracking-wider text-[#0F172A] uppercase flex items-center space-x-2">
                    <Sliders className="h-4 w-4 text-[#4F46E5]" />
                    <span>Project Policy & Recovery Controls</span>
                  </h3>
                  <p className="text-[10px] text-[#64748B] font-sans mt-0.5">Define automated recovery guardrails and sensitivity masks</p>
                </div>
                {saveSuccess && (
                  <span className="pill-mint font-bold flex items-center">
                    <Check className="h-3 w-3 mr-1" />
                    SAVED TO REPO POLICY
                  </span>
                )}
              </div>

              {/* Status Pills */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl flex items-center justify-between">
                  <div>
                    <span className="text-xs font-mono font-bold text-[#0F172A] block">Autonomous Recovery</span>
                    <span className="text-[10px] text-[#64748B] font-mono">LLM localized patch synthesis</span>
                  </div>
                  <span className="pill-mint font-bold">
                    ACTIVE
                  </span>
                </div>

                <div className="p-4 bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl flex items-center justify-between">
                  <div>
                    <span className="text-xs font-mono font-bold text-[#0F172A] block">Auto-Merge Engine</span>
                    <span className="text-[10px] text-[#64748B] font-mono">Direct PR sign-off upon passing CI</span>
                  </div>
                  <span className="pill-mint font-bold">
                    ACTIVE
                  </span>
                </div>
              </div>

              {/* Slider Threshold Fields */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-3 p-4 bg-stone-50 border border-stone-200 rounded-xl">
                  <div className="flex justify-between items-center">
                    <label className="text-[10px] font-mono text-stone-500 uppercase font-bold tracking-wider">
                      Auto-Merge Confidence (%)
                    </label>
                    <span className="text-sm font-mono font-bold text-emerald-800">
                      {autoMergeThreshold}%
                    </span>
                  </div>
                  <input 
                    type="range"
                    min="50"
                    max="100"
                    value={autoMergeThreshold}
                    disabled={!userCanEdit}
                    onChange={(e) => setAutoMergeThreshold(Number(e.target.value))}
                    className="w-full accent-emerald-600 cursor-pointer disabled:opacity-40"
                  />
                  <span className="text-[10px] text-stone-500 font-sans block">
                    Patches with trust scores &ge; {autoMergeThreshold}% will auto-merge to main without manual review.
                  </span>
                </div>

                <div className="space-y-3 p-4 bg-stone-50 border border-stone-200 rounded-xl">
                  <div className="flex justify-between items-center">
                    <label className="text-[10px] font-mono text-stone-500 uppercase font-bold tracking-wider">
                      Mandatory Review Threshold (%)
                    </label>
                    <span className="text-sm font-mono font-bold text-amber-800">
                      {mandatoryReviewThreshold}%
                    </span>
                  </div>
                  <input 
                    type="range"
                    min="30"
                    max="90"
                    value={mandatoryReviewThreshold}
                    disabled={!userCanEdit}
                    onChange={(e) => setMandatoryReviewThreshold(Number(e.target.value))}
                    className="w-full accent-amber-600 cursor-pointer disabled:opacity-40"
                  />
                  <span className="text-[10px] text-stone-500 font-sans block">
                    Trust scores between {mandatoryReviewThreshold}% and {autoMergeThreshold}% halt for human sign-off.
                  </span>
                </div>
              </div>

              {/* Restricted Files Tag Manager */}
              <div className="space-y-3 p-4 bg-stone-50 border border-stone-200 rounded-xl">
                <div className="flex items-center justify-between">
                  <label className="text-[10px] font-mono text-stone-500 uppercase font-bold tracking-wider flex items-center">
                    <FileCode className="h-3.5 w-3.5 mr-1.5 text-rose-700" />
                    Restricted Sensitive File Boundaries
                  </label>
                  <span className="text-[10px] font-mono text-rose-800 font-bold">
                    {restrictedFiles.length} Blocked File Masks
                  </span>
                </div>

                {userCanEdit && (
                  <div className="flex items-center space-x-2">
                    <input 
                      type="text"
                      placeholder="e.g. auth.py, payment.py, .env, secrets.json"
                      value={newTagInput}
                      onChange={(e) => setNewTagInput(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAddRestrictedFile(); } }}
                      className="flex-1 bg-white border border-stone-200 rounded-xl px-4 py-2 text-xs font-mono text-stone-900 focus:outline-none focus:border-amber-400"
                    />
                    <button
                      type="button"
                      onClick={handleAddRestrictedFile}
                      className="px-3.5 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-xl text-xs font-mono font-bold flex items-center space-x-1 transition"
                    >
                      <Plus className="h-3.5 w-3.5" />
                      <span>Add Mask</span>
                    </button>
                  </div>
                )}

                <div className="flex flex-wrap gap-2 pt-1">
                  {restrictedFiles.map((file, idx) => (
                    <span key={idx} className="px-3 py-1 bg-rose-50 border border-rose-200 text-rose-900 text-xs font-mono font-semibold rounded-xl flex items-center space-x-1.5">
                      <span>{file}</span>
                      {userCanEdit && (
                        <button
                          type="button"
                          onClick={() => handleRemoveRestrictedFile(file)}
                          className="text-rose-700 hover:text-rose-950 transition"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      )}
                    </span>
                  ))}
                </div>
                <span className="text-[10px] text-stone-500 font-sans block">
                  Any synthesized candidate that touches these files is strictly blocked from zero-touch merge and diverted to the Emergency Review Queue.
                </span>
              </div>

              {/* Submission */}
              <div className="flex items-center justify-between pt-3 border-t border-stone-200">
                <div className="text-[11px] font-mono text-stone-500">
                  {!userCanEdit && (
                    <span className="flex items-center text-amber-800">
                      <Lock className="h-3 w-3 mr-1" /> Read-Only: Role {currentRole} cannot modify policy parameters.
                    </span>
                  )}
                </div>
                
                {userCanEdit ? (
                  <button
                    type="submit"
                    className="px-6 py-2.5 bg-amber-600 hover:bg-amber-700 text-white rounded-xl text-xs font-mono font-bold tracking-wider transition shadow-sm"
                  >
                    COMMIT POLICY CHANGES
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled
                    className="px-6 py-2.5 bg-stone-100 border border-stone-200 text-stone-400 rounded-xl text-xs font-mono font-bold cursor-not-allowed"
                  >
                    POLICY LOCKED
                  </button>
                )}
              </div>
            </form>
          ) : (
            <div className="text-center py-28 text-stone-500 font-mono text-xs bg-white border border-stone-200 rounded-2xl">
              SELECT A REPOSITORY TO VIEW POLICY CONFIGURATION
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
