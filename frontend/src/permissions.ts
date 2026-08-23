import { Crown, Shield, ShieldAlert, Cpu, Eye } from 'lucide-react';
import React from 'react';

export type UserRole = 'OWNER' | 'ADMIN' | 'REVIEWER' | 'ENGINEER' | 'VIEWER';

export interface RoleConfig {
  role: UserRole;
  label: string;
  badgeBg: string;
  badgeText: string;
  badgeBorder: string;
  glowColor: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}

export const ROLE_CONFIGS: Record<UserRole, RoleConfig> = {
  OWNER: {
    role: 'OWNER',
    label: 'Org Owner',
    badgeBg: 'bg-amber-500/10',
    badgeText: 'text-amber-400',
    badgeBorder: 'border-amber-500/30',
    glowColor: 'shadow-amber-500/10',
    description: 'Full administrative control, billing, member role management, security override, and policy commits.',
    icon: Crown
  },
  ADMIN: {
    role: 'ADMIN',
    label: 'Platform Admin',
    badgeBg: 'bg-indigo-500/10',
    badgeText: 'text-indigo-400',
    badgeBorder: 'border-indigo-500/30',
    glowColor: 'shadow-indigo-500/10',
    description: 'Configure recovery thresholds, restricted files, sandbox isolates, and emergency patch approvals.',
    icon: Shield
  },
  REVIEWER: {
    role: 'REVIEWER',
    label: 'Security Reviewer',
    badgeBg: 'bg-cyan-500/10',
    badgeText: 'text-cyan-400',
    badgeBorder: 'border-cyan-500/30',
    glowColor: 'shadow-cyan-500/10',
    description: 'Authorize PR dispatches in review queue, review mutant scores, and inspect AST boundary evidence.',
    icon: ShieldAlert
  },
  ENGINEER: {
    role: 'ENGINEER',
    label: 'Software Engineer',
    badgeBg: 'bg-emerald-500/10',
    badgeText: 'text-emerald-400',
    badgeBorder: 'border-emerald-500/30',
    glowColor: 'shadow-emerald-500/10',
    description: 'Trigger ingestion test telemetry, view sandbox trace streams, inspect unified diff candidates.',
    icon: Cpu
  },
  VIEWER: {
    role: 'VIEWER',
    label: 'Auditor (Read-Only)',
    badgeBg: 'bg-slate-800/60',
    badgeText: 'text-slate-400',
    badgeBorder: 'border-slate-700/50',
    glowColor: 'shadow-slate-500/5',
    description: 'Read-only access to operational MTTR dashboards, historical recovery logs, and safety indices.',
    icon: Eye
  }
};

// Granular RBAC Permissions
export function canApprovePatches(role: UserRole): boolean {
  return ['OWNER', 'ADMIN', 'REVIEWER'].includes(role);
}

export function canEditPolicies(role: UserRole): boolean {
  return ['OWNER', 'ADMIN'].includes(role);
}

export function canTriggerIncidents(role: UserRole): boolean {
  return ['OWNER', 'ADMIN', 'REVIEWER', 'ENGINEER'].includes(role);
}

export function canSyncRepositories(role: UserRole): boolean {
  return ['OWNER', 'ADMIN'].includes(role);
}

export function canManageSettings(role: UserRole): boolean {
  return ['OWNER', 'ADMIN'].includes(role);
}

export function canManageMembers(role: UserRole): boolean {
  return role === 'OWNER';
}

export interface PermissionFeature {
  category: string;
  action: string;
  description: string;
  allowedRoles: UserRole[];
}

export const PERMISSION_MATRIX: PermissionFeature[] = [
  {
    category: 'Recovery Governance',
    action: 'Approve / Reject Review Queue Patches',
    description: 'Approve candidate diffs or reject PR merges in the emergency review queue',
    allowedRoles: ['OWNER', 'ADMIN', 'REVIEWER']
  },
  {
    category: 'Recovery Governance',
    action: 'Commit Policy & Safety Thresholds',
    description: 'Modify auto-merge confidence threshold %, mandatory review %, and restricted file masks',
    allowedRoles: ['OWNER', 'ADMIN']
  },
  {
    category: 'Ingestion & Pipeline',
    action: 'Trigger Ingestion / Simulated Incidents',
    description: 'Send test telemetry events to trigger automated recovery pipelines',
    allowedRoles: ['OWNER', 'ADMIN', 'REVIEWER', 'ENGINEER']
  },
  {
    category: 'Repository & GitHub',
    action: 'Sync GitHub App Repositories',
    description: 'Fetch and register active installation repos from GitHub into the organization registry',
    allowedRoles: ['OWNER', 'ADMIN']
  },
  {
    category: 'Audit & Telemetry',
    action: 'Live Sandbox Terminal & Stream Inspection',
    description: 'Stream containerized sandbox execution logs and inspect resource telemetry',
    allowedRoles: ['OWNER', 'ADMIN', 'REVIEWER', 'ENGINEER', 'VIEWER']
  },
  {
    category: 'Administration',
    action: 'Organization Settings & Team Roles',
    description: 'Manage member roles, security key configurations, and audit logging parameters',
    allowedRoles: ['OWNER']
  }
];
