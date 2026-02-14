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
	Server,
	Trash2,
} from "@lucide/svelte";
import { goto, invalidateAll } from "$app/navigation";
import {
	deleteServer,
	type ErrorResponse,
	type SyncResult,
	syncServer,
	withErrorHandling,
} from "$lib/api/client";
import { getErrorMessage } from "$lib/api/errors";
import ConfirmDialog from "$lib/components/confirm-dialog.svelte";
import ErrorState from "$lib/components/error-state.svelte";
import SyncResultsDialog from "$lib/components/servers/sync-results-dialog.svelte";
import StatusBadge from "$lib/components/status-badge.svelte";
import { Button } from "$lib/components/ui/button";
import * as Card from "$lib/components/ui/card";
import { Label } from "$lib/components/ui/label";
import { getProviderBadgeStyle, getProviderLabel } from "$lib/stores/providers.svelte";
import { showError, showSuccess } from "$lib/utils/toast";
import type { PageData } from "./$types";

const { data }: { data: PageData } = $props();

// Sync state
let syncing = $state(false);
let syncResult = $state<SyncResult | null>(null);
let showSyncDialog = $state(false);

// Delete state
let deleting = $state(false);
let showDeleteDialog = $state(false);

const badgeStyle = $derived(data.server ? getProviderBadgeStyle(data.server.server_type) : '');
const serverTypeLabel = $derived(data.server ? getProviderLabel(data.server.server_type) : '');

/**
 * Format date for display.
 */
function formatDate(dateString: string | null | undefined): string {
	if (!dateString) return "—";
	try {
		const date = new Date(dateString);
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
 * Handle sync button click.
 */
async function handleSync() {
	if (!data.server) return;
	const serverId = data.server.id;

	syncing = true;
	try {
		const result = await withErrorHandling(
			() => syncServer(serverId, false),
			{ showErrorToast: false },
		);

		if (result.error) {
			const errorBody = result.error as ErrorResponse | undefined;
			showError("Sync failed", errorBody?.detail ?? "An error occurred");
			return;
		}

		if (result.data) {
			syncResult = result.data as SyncResult;
			showSyncDialog = true;
			showSuccess("Sync completed successfully");
		}
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
			const errorBody = result.error as ErrorResponse | undefined;
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
							disabled={syncing || deleting}
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
						<p class="text-sm text-cr-text-muted flex-1">
							Synchronize local user records with the media server to identify discrepancies.
						</p>

						<!-- Delete Button -->
						<Button
							variant="outline"
							onclick={() => (showDeleteDialog = true)}
							disabled={syncing || deleting}
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
	bind:open={showSyncDialog}
	result={syncResult}
	onClose={closeSyncDialog}
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
