<script lang="ts">
/**
 * Server detail page.
 *
 * Displays server details with:
 * - Server information (name, type, url, enabled)
 * - Library list
 * - Sync button with results dialog
 *
 * @module routes/(admin)/servers/[id]/+page
 */

import {
	ArrowLeft,
	Calendar,
	Database,
	ExternalLink,
	RefreshCw,
	Server
} from '@lucide/svelte';
import { toast } from 'svelte-sonner';
import { goto, invalidateAll } from '$app/navigation';
import { type SyncResult, syncServer } from '$lib/api/client';
import { ApiError, getErrorMessage } from '$lib/api/errors';
import ErrorState from '$lib/components/error-state.svelte';
import SyncResultsDialog from '$lib/components/servers/sync-results-dialog.svelte';
import StatusBadge from '$lib/components/status-badge.svelte';
import { Button } from '$lib/components/ui/button';
import * as Card from '$lib/components/ui/card';
import { Label } from '$lib/components/ui/label';
import type { PageData } from './$types';

let { data }: { data: PageData } = $props();

// Sync state
let syncing = $state(false);
let syncResult = $state<SyncResult | null>(null);
let showSyncDialog = $state(false);

/**
 * Get server type badge class based on server type.
 */
let serverTypeClass = $derived.by(() => {
	if (!data.server) return '';
	return data.server.server_type === 'plex'
		? 'bg-amber-500/15 text-amber-400 border-amber-500/30'
		: 'bg-purple-500/15 text-purple-400 border-purple-500/30';
});

/**
 * Get server type display name.
 */
let serverTypeLabel = $derived.by(() => {
	if (!data.server) return '';
	return data.server.server_type === 'plex' ? 'Plex' : 'Jellyfin';
});

/**
 * Format date for display.
 */
function formatDate(dateString: string | null | undefined): string {
	if (!dateString) return '—';
	try {
		const date = new Date(dateString);
		return date.toLocaleDateString('en-US', {
			month: 'short',
			day: 'numeric',
			year: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	} catch {
		return '—';
	}
}

/**
 * Handle sync button click.
 */
async function handleSync() {
	if (!data.server) return;

	syncing = true;
	try {
		const result = await syncServer(data.server.id, true);

		if (result.error) {
			const status = result.response?.status ?? 500;
			const errorBody = result.error as { error_code?: string; detail?: string };

			// Check for server unreachable error
			if (status === 503) {
				throw new ApiError(
					status,
					errorBody?.error_code ?? 'SERVER_UNREACHABLE',
					errorBody?.detail ?? 'Media server is unreachable'
				);
			}

			throw new ApiError(
				status,
				errorBody?.error_code ?? 'UNKNOWN_ERROR',
				errorBody?.detail ?? 'Failed to sync server'
			);
		}

		if (result.data) {
			syncResult = result.data;
			showSyncDialog = true;
			toast.success('Sync completed successfully');
		}
	} catch (error) {
		toast.error('Sync failed', {
			description: getErrorMessage(error)
		});
	} finally {
		syncing = false;
	}
}

/**
 * Handle retry after error.
 */
async function handleRetry() {
	await invalidateAll();
}

/**
 * Close sync results dialog.
 */
function closeSyncDialog() {
	showSyncDialog = false;
}
</script>

<div class="space-y-6">
	<!-- Back button and header -->
	<div class="flex items-center gap-4">
		<Button
			variant="ghost"
			size="icon"
			onclick={() => goto('/servers')}
			class="text-cr-text-muted hover:text-cr-text"
			aria-label="Back to servers"
		>
			<ArrowLeft class="size-5" />
		</Button>
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
								class="inline-flex items-center rounded border px-2 py-1 text-sm font-medium {serverTypeClass}"
							>
								{serverTypeLabel}
							</span>
						</div>
					</div>

					<!-- URL -->
					<div class="space-y-1" data-field="url">
						<Label class="text-cr-text-muted text-xs uppercase tracking-wide flex items-center gap-1">
							<ExternalLink class="size-3" />
							URL
						</Label>
						<div class="font-mono text-sm text-cr-text bg-cr-bg px-3 py-2 rounded border border-cr-border break-all">
							{data.server.url}
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
						<!-- Sync Button -->
						<Button
							onclick={handleSync}
							disabled={syncing}
							class="bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
							data-action-sync
						>
							{#if syncing}
								<span class="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
								Syncing...
							{:else}
								<RefreshCw class="size-4" />
								Sync Users
							{/if}
						</Button>
						<p class="text-sm text-cr-text-muted">
							Synchronize local user records with the media server to identify discrepancies.
						</p>
					</div>
				</Card.Content>
			</Card.Root>
		</div>
	{/if}
</div>

<!-- Sync Results Dialog -->
<SyncResultsDialog
	bind:open={showSyncDialog}
	result={syncResult}
	onClose={closeSyncDialog}
/>
