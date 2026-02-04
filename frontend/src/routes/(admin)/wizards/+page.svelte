<script lang="ts">
/**
 * Wizard list page.
 *
 * Displays a paginated list of wizards with:
 * - Loading skeleton state during data fetch
 * - Error state with retry functionality
 * - Empty state when no wizards exist
 * - Card view with wizard details
 *
 * Requirements: 13.1
 *
 * @module routes/(admin)/wizards/+page
 */

import { Plus, Wand2 } from '@lucide/svelte';
import { goto, invalidateAll } from '$app/navigation';
import { page } from '$app/state';
import { getErrorMessage, isNetworkError } from '$lib/api/errors';
import EmptyState from '$lib/components/empty-state.svelte';
import ErrorState from '$lib/components/error-state.svelte';
import Pagination from '$lib/components/pagination.svelte';
import { Badge } from '$lib/components/ui/badge';
import { Button } from '$lib/components/ui/button';
import * as Card from '$lib/components/ui/card';
import { Skeleton } from '$lib/components/ui/skeleton';
import type { PageData } from './$types';

let { data }: { data: PageData } = $props();

// Loading state for refresh operations
let isRefreshing = $state(false);

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
 * Navigate to wizard editor.
 */
function handleEditWizard(wizardId: string) {
	goto(`/wizards/${wizardId}`);
}

/**
 * Navigate to create wizard page.
 */
function handleCreateWizard() {
	goto('/wizards/new');
}

/**
 * Handle page change.
 */
function handlePageChange(newPage: number) {
	const url = new URL(page.url);
	url.searchParams.set('page', String(newPage));
	goto(url.toString(), { keepFocus: true, noScroll: true });
}
</script>

<div class="space-y-6">
	<!-- Header with description and create button -->
	<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
		<p class="text-cr-text-muted">Create and manage wizard flows for user onboarding.</p>
		<Button onclick={handleCreateWizard} class="bg-cr-accent text-cr-bg hover:bg-cr-accent-hover">
			<Plus class="size-4" />
			Create Wizard
		</Button>
	</div>

	<!-- Content area with loading/error/empty/data states -->
	{#if isRefreshing}
		<!-- Loading skeleton -->
		<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
			{#each Array(6) as _}
				<Card.Root class="border-cr-border bg-cr-surface">
					<Card.Header>
						<Skeleton class="h-5 w-3/4" />
						<Skeleton class="h-4 w-1/2" />
					</Card.Header>
					<Card.Content>
						<Skeleton class="h-4 w-full" />
					</Card.Content>
				</Card.Root>
			{/each}
		</div>
	{:else if data.error}
		<ErrorState
			message={getErrorMessage(data.error)}
			title={isNetworkError(data.error) ? 'Connection Error' : 'Failed to load wizards'}
			onRetry={handleRetry}
		/>
	{:else if !data.wizards || data.wizards.items.length === 0}
		<EmptyState
			title="No wizards yet"
			description="Create your first wizard to customize the user onboarding experience."
			action={{ label: 'Create Wizard', onClick: handleCreateWizard }}
		/>
	{:else}
		<!-- Wizard cards grid -->
		<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
			{#each data.wizards.items as wizard (wizard.id)}
				<Card.Root
					class="border-cr-border bg-cr-surface cursor-pointer transition-colors hover:border-cr-accent"
					onclick={() => handleEditWizard(wizard.id)}
				>
					<Card.Header>
						<div class="flex items-start justify-between gap-2">
							<div class="flex items-center gap-2">
								<Wand2 class="size-5 text-cr-accent" />
								<Card.Title class="text-cr-text">{wizard.name}</Card.Title>
							</div>
							<Badge
								variant={wizard.enabled ? 'default' : 'secondary'}
								class={wizard.enabled ? 'bg-green-600' : 'bg-cr-text-muted'}
							>
								{wizard.enabled ? 'Enabled' : 'Disabled'}
							</Badge>
						</div>
						{#if wizard.description}
							<Card.Description class="text-cr-text-muted line-clamp-2">
								{wizard.description}
							</Card.Description>
						{/if}
					</Card.Header>
					<Card.Content>
						<p class="text-sm text-cr-text-muted">
							Created {new Date(wizard.created_at).toLocaleDateString()}
						</p>
					</Card.Content>
				</Card.Root>
			{/each}
		</div>

		<!-- Pagination -->
		<Pagination
			page={data.wizards.page}
			pageSize={data.wizards.page_size}
			total={data.wizards.total}
			hasNext={data.wizards.has_next}
			onPageChange={handlePageChange}
		/>
	{/if}
</div>
