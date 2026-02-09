<script lang="ts">
/**
 * Invitation list page.
 *
 * Displays a paginated, filterable list of invitations with:
 * - Loading skeleton state during data fetch
 * - Error state with retry functionality
 * - Empty state when no invitations exist
 * - Table view with status badges and actions
 *
 * @module routes/(admin)/invitations/+page
 */

import { Plus } from "@lucide/svelte";
import { toast } from "svelte-sonner";
import { goto, invalidateAll } from "$app/navigation";
import { page } from "$app/state";
import type { ListInvitationsParams } from "$lib/api/client";
import { getErrorMessage, isNetworkError } from "$lib/api/errors";
import EmptyState from "$lib/components/empty-state.svelte";
import ErrorState from "$lib/components/error-state.svelte";
import InvitationFilters from "$lib/components/invitations/invitation-filters.svelte";
import InvitationListSkeleton from "$lib/components/invitations/invitation-list-skeleton.svelte";
import InvitationTable from "$lib/components/invitations/invitation-table.svelte";
import Pagination from "$lib/components/pagination.svelte";
import { Button } from "$lib/components/ui/button";
import type { PageData } from "./$types";

const { data }: { data: PageData } = $props();

// Loading state for refresh operations
let isRefreshing = $state(false);

// Derive current filter state from URL params
const currentParams = $derived(data.params);

/**
 * Handle retry after error.
 */
async function handleRetry() {
	isRefreshing = true;
	try {
		await invalidateAll();
	} finally {
		isRefreshing = false;
	}
}

/**
 * Handle filter changes by updating URL params.
 */
function handleFilterChange(newParams: Partial<ListInvitationsParams>) {
	const url = new URL(page.url);

	// Update or remove each param
	for (const [key, value] of Object.entries(newParams)) {
		if (value === undefined || value === null) {
			url.searchParams.delete(key);
		} else {
			url.searchParams.set(key, String(value));
		}
	}

	// Reset to page 1 when filters change (except for page changes)
	if (!("page" in newParams)) {
		url.searchParams.set("page", "1");
	}

	goto(url.toString(), { keepFocus: true, noScroll: true });
}

/**
 * Handle page change.
 */
function handlePageChange(newPage: number) {
	handleFilterChange({ page: newPage });
}

/**
 * Open create invitation dialog.
 * TODO: Implement in Task 7
 */
function openCreateDialog() {
	toast.info("Create invitation dialog will be implemented in Task 7");
}
</script>

<div class="space-y-6">
	<!-- Header with description and create button -->
	<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
		<p class="text-cr-text-muted">Manage invitation codes for user onboarding.</p>
		<Button
			onclick={openCreateDialog}
			class="bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
		>
			<Plus class="size-4" />
			Create Invitation
		</Button>
	</div>

	<!-- Filters -->
	<InvitationFilters
		enabled={currentParams.enabled}
		expired={currentParams.expired}
		sortBy={currentParams.sort_by ?? 'created_at'}
		sortOrder={currentParams.sort_order ?? 'desc'}
		onFilterChange={handleFilterChange}
	/>

	<!-- Content area with loading/error/empty/data states -->
	{#if isRefreshing}
		<InvitationListSkeleton />
	{:else if data.error}
		<ErrorState
			message={getErrorMessage(data.error)}
			title={isNetworkError(data.error) ? 'Connection Error' : 'Failed to load invitations'}
			onRetry={handleRetry}
		/>
	{:else if !data.invitations || data.invitations.items.length === 0}
		<EmptyState
			title="No invitations yet"
			description="Create your first invitation to start onboarding users to your media servers."
			action={{ label: 'Create Invitation', onClick: openCreateDialog }}
		/>
	{:else}
		<!-- Invitation table -->
		<InvitationTable invitations={data.invitations.items} />

		<!-- Pagination -->
		<Pagination
			page={data.invitations.page}
			pageSize={data.invitations.page_size}
			total={data.invitations.total}
			hasNext={data.invitations.has_next}
			onPageChange={handlePageChange}
		/>
	{/if}
</div>
