<script lang="ts">

/**
 * Server detail page.
 *
 * Displays server details with:
 * - Server information (name, type, url, enabled)
 * - Library list
 * - Sync status indicators
 * - Sync actions with results dialogs
 *
 * @module routes/(admin)/servers/[id]/+page
 */

import {
	AlertTriangle,
	ArrowLeft,
	Calendar,
	CheckCircle2,
	Clock3,
	Database,
	ExternalLink,
	History,
	KeyRound,
	Lock,
	RefreshCw,
	Server,
	Trash2,
	XCircle,
} from "@lucide/svelte";
import { onMount } from "svelte";
import { goto, invalidateAll } from "$app/navigation";
import {
	deleteServer,
	type LibrarySyncResult,
	type SyncChannelStatus,
	type SyncResult,
	type SyncRunEntry,
	syncServer,
	syncServerLibraries,
	withErrorHandling,
} from "$lib/api/client";
import { asErrorResponse, getErrorMessage } from "$lib/api/errors";
import ConfirmDialog from "$lib/components/confirm-dialog.svelte";
import ErrorState from "$lib/components/error-state.svelte";
import LibrarySyncResultsDialog from "$lib/components/servers/library-sync-results-dialog.svelte";
import SyncResultsDialog from "$lib/components/servers/sync-results-dialog.svelte";
import StatusBadge from "$lib/components/status-badge.svelte";
import { Badge } from "$lib/components/ui/badge";
import { Button } from "$lib/components/ui/button";
import * as Card from "$lib/components/ui/card";
import { Label } from "$lib/components/ui/label";
import { getProviderBadgeStyle, getProviderLabel } from "$lib/stores/providers.svelte";
import { showError, showSuccess } from "$lib/utils/toast";
import type { PageData } from "./$types";

const { data }: { data: PageData } = $props();

// Sync state
let syncingUsers = $state(false);
let syncingLibraries = $state(false);
let userSyncResult = $state<SyncResult | null>(null);
let librarySyncResult = $state<LibrarySyncResult | null>(null);
let showUserSyncDialog = $state(false);
let showLibrarySyncDialog = $state(false);

// Status refresh state
let nowMs = $state(Date.now());

// Delete state
let deleting = $state(false);
let showDeleteDialog = $state(false);

const badgeStyle = $derived(data.server ? getProviderBadgeStyle(data.server.server_type) : '');
const serverTypeLabel = $derived(data.server ? getProviderLabel(data.server.server_type) : '');
const librariesStatus = $derived<SyncChannelStatus | null>(
	data.server?.sync_status?.libraries ?? null,
);
const usersStatus = $derived<SyncChannelStatus | null>(
	data.server?.sync_status?.users ?? null,
);
const actionBusy = $derived(syncingUsers || syncingLibraries || deleting);
const urlLocked = $derived(data.credentialLocks?.url_locked ?? false);
const apiKeyLocked = $derived(data.credentialLocks?.api_key_locked ?? false);

onMount(() => {
	const countdownTimer = setInterval(() => {
		nowMs = Date.now();
	}, 1000);
	const pollTimer = setInterval(() => {
		void invalidateAll();
	}, 15000);

	return () => {
		clearInterval(countdownTimer);
		clearInterval(pollTimer);
	};
});

/**
 * Format date for display.
 */
function formatDate(dateInput: string | Date | null | undefined): string {
	if (!dateInput) return "—";
	try {
		const date = dateInput instanceof Date ? dateInput : new Date(dateInput);
		if (Number.isNaN(date.getTime())) return "—";
		return date.toLocaleDateString("en-US", {
			month: "short",
			day: "numeric",
			year: "numeric",
			hour: "2-digit",
			minute: "2-digit",
		});
	} catch {
		return "—";
	}
}

/**
 * Parse ISO date string safely.
 */
function parseDate(dateString: string | null | undefined): Date | null {
	if (!dateString) return null;
	const parsed = new Date(dateString);
	return Number.isNaN(parsed.getTime()) ? null : parsed;
}

/**
 * Format time-until countdown label.
 */
function formatCountdown(
	nextScheduledAt: string | null | undefined,
	inProgress: boolean,
): string {
	if (inProgress) return "Syncing now...";
	const target = parseDate(nextScheduledAt);
	if (!target) return "Not scheduled";

	const diffMs = target.getTime() - nowMs;
	if (diffMs <= 0) return "Due now";

	const totalSeconds = Math.floor(diffMs / 1000);
	const days = Math.floor(totalSeconds / 86400);
	const hours = Math.floor((totalSeconds % 86400) / 3600);
	const minutes = Math.floor((totalSeconds % 3600) / 60);
	const seconds = totalSeconds % 60;

	if (days > 0) return `in ${days}d ${hours}h`;
	if (hours > 0) return `in ${hours}h ${minutes}m`;
	if (minutes > 0) return `in ${minutes}m ${seconds}s`;
	return `in ${seconds}s`;
}

/**
 * Format a relative time ago label.
 */
function formatTimeAgo(dateInput: string | null | undefined): string {
	if (!dateInput) return "—";
	const date = parseDate(dateInput);
	if (!date) return "—";

	const diffMs = nowMs - date.getTime();
	if (diffMs < 0) return "just now";

	const totalSeconds = Math.floor(diffMs / 1000);
	if (totalSeconds < 60) return "just now";

	const minutes = Math.floor(totalSeconds / 60);
	if (minutes < 60) return `${minutes}m ago`;

	const hours = Math.floor(minutes / 60);
	if (hours < 24) return `${hours}h ago`;

	const days = Math.floor(hours / 24);
	return `${days}d ago`;
}

/**
 * Merge and sort recent runs from both channels for a unified history view.
 */
const allRecentRuns = $derived.by(() => {
	const libRuns: Array<SyncRunEntry & { channel: string }> = (librariesStatus?.recent_runs ?? []).map(
		(r) => ({ ...r, channel: "libraries" }),
	);
	const usrRuns: Array<SyncRunEntry & { channel: string }> = (usersStatus?.recent_runs ?? []).map(
		(r) => ({ ...r, channel: "users" }),
	);
	return [...libRuns, ...usrRuns]
		.sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())
		.slice(0, 10);
});

/**
 * Whether the last sync for either channel failed.
 */
const hasRecentFailure = $derived(
	!!(librariesStatus?.last_error_message || usersStatus?.last_error_message),
);

/**
 * Handle user sync button click.
 */
async function handleUserSync() {
	if (!data.server) return;
	const serverId = data.server.id;

	syncingUsers = true;
	try {
		const result = await withErrorHandling(
			() => syncServer(serverId, false),
			{ showErrorToast: false },
		);

		if (result.error) {
			const errorBody = asErrorResponse(result.error);
			showError("Sync failed", errorBody?.detail ?? "An error occurred");
			return;
		}

		if (result.data) {
			userSyncResult = result.data as SyncResult;
			showUserSyncDialog = true;
			showSuccess("User sync completed successfully");
			await invalidateAll();
		}
	} finally {
		syncingUsers = false;
	}
}

/**
 * Handle library sync button click.
 */
async function handleLibrarySync() {
	if (!data.server) return;
	const serverId = data.server.id;

	syncingLibraries = true;
	try {
		const result = await withErrorHandling(
			() => syncServerLibraries(serverId),
			{ showErrorToast: false },
		);

		if (result.error) {
			const errorBody = asErrorResponse(result.error);
			showError("Library sync failed", errorBody?.detail ?? "An error occurred");
			return;
		}

		if (result.data) {
			librarySyncResult = result.data as LibrarySyncResult;
			showLibrarySyncDialog = true;
			showSuccess("Library sync completed successfully");
			await invalidateAll();
		}
	} finally {
		syncingLibraries = false;
	}
}

/**
 * Handle retry after error.
 */
async function handleRetry() {
	await invalidateAll();
}

/**
 * Close user sync results dialog.
 */
function closeUserSyncDialog() {
	showUserSyncDialog = false;
}

/**
 * Close library sync results dialog.
 */
function closeLibrarySyncDialog() {
	showLibrarySyncDialog = false;
}

/**
 * Handle delete server action.
 */
async function handleDelete() {
	if (!data.server) return;
	const serverId = data.server.id;

	deleting = true;
	try {
		const result = await withErrorHandling(
			() => deleteServer(serverId),
			{ showErrorToast: false },
		);

		if (result.error) {
			const errorBody = asErrorResponse(result.error);
			showError(
				"Failed to delete server",
				errorBody?.detail ?? "An error occurred",
			);
			return;
		}

		showSuccess("Server deleted successfully");
		goto("/servers");
	} finally {
		deleting = false;
		showDeleteDialog = false;
	}
}
</script>

<div class="space-y-6">
	<!-- Back button and header -->
	<div class="flex items-center gap-4">
		<a
			href="/servers"
			class="inline-flex items-center justify-center size-9 rounded-md text-cr-text-muted hover:text-cr-text hover:bg-accent"
			aria-label="Back to servers"
		>
			<ArrowLeft class="size-5" />
		</a>
		<div class="flex-1">
			<h1 class="text-xl font-semibold text-cr-text">Server Details</h1>
			{#if data.server}
				<p class="text-cr-text-muted">
					<span class="font-medium text-cr-text">{data.server.name}</span>
				</p>
			{/if}
		</div>
		{#if data.server}
			<StatusBadge
				status={data.server.enabled ? 'active' : 'disabled'}
				label={data.server.enabled ? 'Enabled' : 'Disabled'}
			/>
		{/if}
	</div>

	{#if data.error}
		<ErrorState
			message={getErrorMessage(data.error)}
			title="Failed to load server"
			onRetry={handleRetry}
		/>
	{:else if data.server}
		<div class="grid gap-6 lg:grid-cols-2">
			<!-- Server Information Card -->
			<Card.Root class="border-cr-border bg-cr-surface" data-server-info>
				<Card.Header>
					<Card.Title class="text-cr-text flex items-center gap-2">
						<Server class="size-5 text-cr-accent" />
						Server Information
					</Card.Title>
					<Card.Description class="text-cr-text-muted">
						Details about this media server.
					</Card.Description>
				</Card.Header>
				<Card.Content class="space-y-4">
					<!-- Name -->
					<div class="space-y-1" data-field="name">
						<Label class="text-cr-text-muted text-xs uppercase tracking-wide">Name</Label>
						<div class="font-medium text-lg text-cr-text">{data.server.name}</div>
					</div>

					<!-- Server Type -->
					<div class="space-y-1" data-field="server_type">
						<Label class="text-cr-text-muted text-xs uppercase tracking-wide">Type</Label>
						<div>
							<span
								class="inline-flex items-center rounded border px-2 py-1 text-sm font-medium"
								style={badgeStyle}
							>
								{serverTypeLabel}
							</span>
						</div>
					</div>

					<!-- URL -->
					<div class="space-y-1" data-field="url">
						<div class="flex items-center gap-2">
							<Label class="text-cr-text-muted text-xs uppercase tracking-wide flex items-center gap-1">
								<ExternalLink class="size-3" />
								URL
							</Label>
							{#if urlLocked}
								<Badge variant="secondary" class="gap-1">
									<Lock class="size-3" />
									Environment Variable
								</Badge>
							{/if}
						</div>
						<div class="font-mono text-sm text-cr-text bg-cr-bg px-3 py-2 rounded border border-cr-border break-all">
							{data.server.url}
						</div>
					</div>

					<!-- API Key -->
					<div class="space-y-1" data-field="api_key">
						<div class="flex items-center gap-2">
							<Label class="text-cr-text-muted text-xs uppercase tracking-wide flex items-center gap-1">
								<KeyRound class="size-3" />
								API Key
							</Label>
							{#if apiKeyLocked}
								<Badge variant="secondary" class="gap-1">
									<Lock class="size-3" />
									Environment Variable
								</Badge>
							{/if}
						</div>
						<div class="font-mono text-sm text-cr-text bg-cr-bg px-3 py-2 rounded border border-cr-border break-all">
							{#if apiKeyLocked}
								<span class="text-cr-text-muted">Set via environment variable</span>
							{:else}
								<span class="text-cr-text-muted">••••••••</span>
							{/if}
						</div>
					</div>

					<!-- Enabled Status -->
					<div class="space-y-1" data-field="enabled">
						<Label class="text-cr-text-muted text-xs uppercase tracking-wide">Status</Label>
						<div class="flex items-center gap-2">
							<StatusBadge
								status={data.server.enabled ? 'active' : 'disabled'}
								label={data.server.enabled ? 'Enabled' : 'Disabled'}
							/>
						</div>
					</div>

					<!-- Created At -->
					<div class="space-y-1">
						<Label class="text-cr-text-muted text-xs uppercase tracking-wide flex items-center gap-1">
							<Calendar class="size-3" />
							Created
						</Label>
						<div class="text-cr-text font-data">{formatDate(data.server.created_at)}</div>
					</div>

					<!-- Updated At -->
					{#if data.server.updated_at}
						<div class="space-y-1">
							<Label class="text-cr-text-muted text-xs uppercase tracking-wide">Last Updated</Label>
							<div class="text-cr-text font-data">{formatDate(data.server.updated_at)}</div>
						</div>
					{/if}
				</Card.Content>
			</Card.Root>

			<!-- Libraries Card -->
			<Card.Root class="border-cr-border bg-cr-surface" data-libraries>
				<Card.Header>
					<Card.Title class="text-cr-text flex items-center gap-2">
						<Database class="size-5 text-cr-accent" />
						Libraries
						<span class="text-sm font-normal text-cr-text-muted">
							({data.server.libraries.length})
						</span>
					</Card.Title>
					<Card.Description class="text-cr-text-muted">
						Content libraries available on this server.
					</Card.Description>
				</Card.Header>
				<Card.Content>
					{#if data.server.libraries.length === 0}
						<div class="text-center py-6 text-cr-text-muted">
							No libraries found on this server.
						</div>
					{:else}
						<div class="space-y-2">
							{#each data.server.libraries as library (library.id)}
								<div
									class="flex items-center justify-between rounded-lg border border-cr-border bg-cr-bg p-3"
									data-library={library.id}
								>
									<div class="flex-1 min-w-0">
										<div class="font-medium text-cr-text truncate">{library.name}</div>
										<div class="flex items-center gap-2 mt-1">
											<span class="text-xs text-cr-text-muted capitalize">
												{library.library_type}
											</span>
											<span class="text-xs text-cr-text-muted">•</span>
											<span class="text-xs font-mono text-cr-text-muted truncate">
												{library.external_id}
											</span>
										</div>
									</div>
								</div>
							{/each}
						</div>
					{/if}
				</Card.Content>
			</Card.Root>

			<!-- Sync Failure Alert -->
			{#if hasRecentFailure}
				<div
					class="lg:col-span-2 rounded-lg border border-rose-500/30 bg-rose-500/5 p-4"
					role="alert"
					data-sync-failure-alert
				>
					<div class="flex items-start gap-3">
						<AlertTriangle class="size-5 text-rose-400 mt-0.5 shrink-0" />
						<div class="space-y-1 min-w-0">
							<div class="font-medium text-rose-400 text-sm">Last sync failed</div>
							{#if librariesStatus?.last_error_message}
								<div class="text-xs text-cr-text-muted">
									<span class="font-medium text-cr-text">Libraries:</span>
									{librariesStatus.last_error_message}
									{#if librariesStatus.last_failed_at}
										<span class="text-cr-text-muted/60">
											&mdash; {formatTimeAgo(librariesStatus.last_failed_at)}
										</span>
									{/if}
								</div>
							{/if}
							{#if usersStatus?.last_error_message}
								<div class="text-xs text-cr-text-muted">
									<span class="font-medium text-cr-text">Users:</span>
									{usersStatus.last_error_message}
									{#if usersStatus.last_failed_at}
										<span class="text-cr-text-muted/60">
											&mdash; {formatTimeAgo(usersStatus.last_failed_at)}
										</span>
									{/if}
								</div>
							{/if}
							{#if librariesStatus?.next_scheduled_at || usersStatus?.next_scheduled_at}
								<div class="text-xs text-amber-400 mt-1">
									Will retry automatically at next scheduled sync.
								</div>
							{/if}
						</div>
					</div>
				</div>
			{/if}

			<!-- Sync Status Card -->
			<Card.Root class="border-cr-border bg-cr-surface lg:col-span-2" data-sync-status>
				<Card.Header>
					<Card.Title class="text-cr-text flex items-center gap-2">
						<Clock3 class="size-5 text-cr-accent" />
						Sync Status
					</Card.Title>
					<Card.Description class="text-cr-text-muted">
						Automatic synchronization schedule and current activity.
					</Card.Description>
				</Card.Header>
				<Card.Content>
					<div class="grid gap-3 md:grid-cols-2">
						<div
							class="rounded-lg border p-4 space-y-2 {librariesStatus?.last_error_message ? 'border-rose-500/20 bg-rose-500/5' : 'border-cr-border bg-cr-bg'}"
							data-sync-channel="libraries"
						>
							<div class="flex items-center justify-between gap-3">
								<div>
									<div class="font-medium text-cr-text flex items-center gap-1.5">
										Libraries
										{#if librariesStatus?.last_error_message}
											<XCircle class="size-3.5 text-rose-400" />
										{:else if librariesStatus?.last_completed_at}
											<CheckCircle2 class="size-3.5 text-emerald-400" />
										{/if}
									</div>
									<div class="text-xs text-cr-text-muted">Media library sync</div>
								</div>
								<div class="text-right">
									{#if syncingLibraries || librariesStatus?.in_progress}
										<div class="inline-flex items-center gap-2 text-amber-300 text-sm">
											<span class="size-3 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
											Syncing now...
										</div>
									{:else}
										<div class="text-sm text-cr-text">
											Next: {formatCountdown(librariesStatus?.next_scheduled_at, false)}
										</div>
										<div class="text-xs text-cr-text-muted">
											{formatDate(librariesStatus?.next_scheduled_at)}
										</div>
									{/if}
								</div>
							</div>
							<div class="text-xs text-cr-text-muted">
								Last success: {formatDate(librariesStatus?.last_completed_at)}
							</div>
						</div>

						<div
							class="rounded-lg border p-4 space-y-2 {usersStatus?.last_error_message ? 'border-rose-500/20 bg-rose-500/5' : 'border-cr-border bg-cr-bg'}"
							data-sync-channel="users"
						>
							<div class="flex items-center justify-between gap-3">
								<div>
									<div class="font-medium text-cr-text flex items-center gap-1.5">
										Users
										{#if usersStatus?.last_error_message}
											<XCircle class="size-3.5 text-rose-400" />
										{:else if usersStatus?.last_completed_at}
											<CheckCircle2 class="size-3.5 text-emerald-400" />
										{/if}
									</div>
									<div class="text-xs text-cr-text-muted">Account state sync</div>
								</div>
								<div class="text-right">
									{#if syncingUsers || usersStatus?.in_progress}
										<div class="inline-flex items-center gap-2 text-amber-300 text-sm">
											<span class="size-3 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
											Syncing now...
										</div>
									{:else}
										<div class="text-sm text-cr-text">
											Next: {formatCountdown(usersStatus?.next_scheduled_at, false)}
										</div>
										<div class="text-xs text-cr-text-muted">
											{formatDate(usersStatus?.next_scheduled_at)}
										</div>
									{/if}
								</div>
							</div>
							<div class="text-xs text-cr-text-muted">
								Last success: {formatDate(usersStatus?.last_completed_at)}
							</div>
						</div>
					</div>
				</Card.Content>
			</Card.Root>

			<!-- Sync History Card -->
			{#if allRecentRuns.length > 0}
				<Card.Root class="border-cr-border bg-cr-surface lg:col-span-2" data-sync-history>
					<Card.Header>
						<Card.Title class="text-cr-text flex items-center gap-2">
							<History class="size-5 text-cr-accent" />
							Sync History
						</Card.Title>
						<Card.Description class="text-cr-text-muted">
							Recent synchronization runs.
						</Card.Description>
					</Card.Header>
					<Card.Content>
						<div class="space-y-2">
							{#each allRecentRuns as run (run.started_at + run.channel)}
								<div
									class="flex items-center gap-3 rounded-lg border border-cr-border bg-cr-bg px-3 py-2"
									data-sync-run
								>
									<!-- Status icon -->
									{#if run.status === "success"}
										<CheckCircle2 class="size-4 text-emerald-400 shrink-0" />
									{:else}
										<XCircle class="size-4 text-rose-400 shrink-0" />
									{/if}

									<!-- Channel badge -->
									<span class="text-xs font-medium px-1.5 py-0.5 rounded border border-cr-border text-cr-text-muted capitalize shrink-0">
										{run.channel}
									</span>

									<!-- Trigger -->
									<span class="text-xs text-cr-text-muted capitalize shrink-0">
										{run.trigger}
									</span>

									<!-- Error message (if failed) -->
									{#if run.status === "failed" && run.error_message}
										<span class="text-xs text-rose-400 truncate min-w-0 flex-1" title={run.error_message}>
											{run.error_message}
										</span>
									{:else}
										<span class="flex-1"></span>
									{/if}

									<!-- Time -->
									<span class="text-xs text-cr-text-muted shrink-0 tabular-nums">
										{formatTimeAgo(run.started_at)}
									</span>
								</div>
							{/each}
						</div>
					</Card.Content>
				</Card.Root>
			{/if}

			<!-- Actions Card -->
			<Card.Root class="border-cr-border bg-cr-surface lg:col-span-2" data-actions>
				<Card.Header>
					<Card.Title class="text-cr-text">Actions</Card.Title>
					<Card.Description class="text-cr-text-muted">
						Manage this media server.
					</Card.Description>
				</Card.Header>
				<Card.Content>
					<div class="flex flex-wrap items-center gap-3">
						<!-- Sync Users Button -->
						<Button
							onclick={handleUserSync}
							disabled={actionBusy}
							class="bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
							data-action-sync
							data-action-sync-users
						>
							{#if syncingUsers}
								<span class="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
								Syncing Users...
							{:else}
								<RefreshCw class="size-4" />
								Sync Users
							{/if}
						</Button>

						<!-- Sync Libraries Button -->
						<Button
							variant="outline"
							onclick={handleLibrarySync}
							disabled={actionBusy}
							class="border-cr-accent/60 text-cr-accent hover:bg-cr-accent/10 hover:border-cr-accent"
							data-action-sync-libraries
						>
							{#if syncingLibraries}
								<span class="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
								Syncing Libraries...
							{:else}
								<Database class="size-4" />
								Sync Libraries
							{/if}
						</Button>

						<!-- Delete Button -->
						<Button
							variant="outline"
							onclick={() => (showDeleteDialog = true)}
							disabled={actionBusy}
							class="border-rose-500/50 text-rose-400 hover:bg-rose-500/10 hover:border-rose-500"
							data-action-delete
						>
							<Trash2 class="size-4" />
							Delete Server
						</Button>
					</div>
				</Card.Content>
			</Card.Root>
		</div>
	{/if}
</div>

<!-- Sync Results Dialog -->
<SyncResultsDialog
	bind:open={showUserSyncDialog}
	result={userSyncResult}
	onClose={closeUserSyncDialog}
/>

<!-- Library Sync Results Dialog -->
<LibrarySyncResultsDialog
	bind:open={showLibrarySyncDialog}
	result={librarySyncResult}
	onClose={closeLibrarySyncDialog}
/>

<!-- Delete Confirmation Dialog -->
<ConfirmDialog
	bind:open={showDeleteDialog}
	title="Delete Server"
	description="Are you sure you want to delete this server? This will remove all associated libraries and user records. Users will NOT be deleted from the media server itself, but their local tracking records will be lost. This action cannot be undone."
	confirmLabel="Delete"
	variant="destructive"
	loading={deleting}
	onConfirm={handleDelete}
	onCancel={() => (showDeleteDialog = false)}
/>
