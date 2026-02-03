<script lang="ts">
/**
 * Join page for invitation code validation and redemption.
 *
 * Displays:
 * - Loading state during validation
 * - Target servers and allowed libraries for valid codes
 * - Duration information if set
 * - Error messages for invalid codes with failure reasons
 *
 * @module routes/(public)/join/[code]/+page
 */

import { AlertTriangle, Calendar, CheckCircle, Clock, Library, Server } from '@lucide/svelte';
import { invalidateAll } from '$app/navigation';
import { getErrorMessage, isNetworkError } from '$lib/api/errors';
import ErrorState from '$lib/components/error-state.svelte';
import { Button } from '$lib/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '$lib/components/ui/card';
import { Skeleton } from '$lib/components/ui/skeleton';
import type { PageData } from './$types';

let { data }: { data: PageData } = $props();

// Loading state for retry operations
let isRetrying = $state(false);

/**
 * Map failure reasons to user-friendly messages.
 */
function getFailureMessage(reason: string | null | undefined): string {
	switch (reason) {
		case 'not_found':
			return 'This invitation code does not exist. Please check the code and try again.';
		case 'disabled':
			return 'This invitation has been disabled by the administrator.';
		case 'expired':
			return 'This invitation has expired and is no longer valid.';
		case 'max_uses_reached':
			return 'This invitation has reached its maximum number of uses.';
		default:
			return 'This invitation code is not valid.';
	}
}

/**
 * Handle retry after error.
 */
async function handleRetry() {
	isRetrying = true;
	try {
		await invalidateAll();
	} finally {
		isRetrying = false;
	}
}

/**
 * Proceed to registration/OAuth flow.
 * TODO: Implement in Tasks 14 and 15
 */
function handleContinue() {
	// Will be implemented in subsequent tasks
	console.log('Continue to registration');
}
</script>

<div class="space-y-6">
	<!-- Page header -->
	<div class="text-center">
		<h1 class="text-2xl font-bold text-cr-text md:text-3xl">Join Media Server</h1>
		<p class="mt-2 text-cr-text-muted">
			Validate your invitation code to get started
		</p>
	</div>

	<!-- Loading state -->
	{#if isRetrying}
		<Card class="border-cr-border bg-cr-surface">
			<CardHeader>
				<Skeleton class="h-6 w-48" />
				<Skeleton class="mt-2 h-4 w-64" />
			</CardHeader>
			<CardContent class="space-y-4">
				<Skeleton class="h-20 w-full" />
				<Skeleton class="h-20 w-full" />
			</CardContent>
		</Card>
	<!-- Error state -->
	{:else if data.error}
		<ErrorState
			message={getErrorMessage(data.error)}
			title={isNetworkError(data.error) ? 'Connection Error' : 'Validation Failed'}
			onRetry={handleRetry}
		/>
	<!-- Invalid code state -->
	{:else if data.validation && !data.validation.valid}
		<Card class="border-rose-500/30 bg-rose-500/5">
			<CardHeader>
				<div class="flex items-center gap-3">
					<div class="rounded-full bg-rose-500/15 p-2 text-rose-400">
						<AlertTriangle class="size-5" />
					</div>
					<div>
						<CardTitle class="text-cr-text">Invalid Invitation</CardTitle>
						<CardDescription class="text-cr-text-muted">
							Code: <span class="font-mono">{data.code}</span>
						</CardDescription>
					</div>
				</div>
			</CardHeader>
			<CardContent>
				<p data-failure-reason={data.validation.failure_reason} class="text-cr-text-muted">
					{getFailureMessage(data.validation.failure_reason)}
				</p>
			</CardContent>
		</Card>
	<!-- Valid code state -->
	{:else if data.validation && data.validation.valid}
		<Card class="border-emerald-500/30 bg-emerald-500/5">
			<CardHeader>
				<div class="flex items-center gap-3">
					<div class="rounded-full bg-emerald-500/15 p-2 text-emerald-400">
						<CheckCircle class="size-5" />
					</div>
					<div>
						<CardTitle class="text-cr-text">Valid Invitation</CardTitle>
						<CardDescription class="text-cr-text-muted">
							Code: <span class="font-mono">{data.code}</span>
						</CardDescription>
					</div>
				</div>
			</CardHeader>
			<CardContent class="space-y-6">
				<!-- Duration info -->
				{#if data.validation.duration_days}
					<div data-duration-display class="flex items-center gap-3 rounded-lg border border-cr-border bg-cr-bg p-4">
						<div class="rounded-full bg-cr-accent/15 p-2 text-cr-accent">
							<Calendar class="size-5" />
						</div>
						<div>
							<p class="font-medium text-cr-text">Access Duration</p>
							<p class="text-sm text-cr-text-muted">
								Your access will be valid for <span class="font-semibold text-cr-accent">{data.validation.duration_days} days</span> after registration.
							</p>
						</div>
					</div>
				{/if}

				<!-- Target servers -->
				{#if data.validation.target_servers && data.validation.target_servers.length > 0}
					<div data-target-servers>
						<div class="mb-3 flex items-center gap-2 text-cr-text">
							<Server class="size-4" />
							<h3 class="font-medium">Target Servers</h3>
						</div>
						<div class="space-y-2">
							{#each data.validation.target_servers as server}
								<div class="flex items-center justify-between rounded-lg border border-cr-border bg-cr-bg p-3">
									<div>
										<p class="font-medium text-cr-text">{server.name}</p>
										<p class="text-sm text-cr-text-muted capitalize">{server.server_type}</p>
									</div>
									<span class="rounded-full bg-emerald-500/15 px-2 py-1 text-xs font-medium text-emerald-400">
										{server.enabled ? 'Online' : 'Offline'}
									</span>
								</div>
							{/each}
						</div>
					</div>
				{/if}

				<!-- Allowed libraries -->
				{#if data.validation.allowed_libraries && data.validation.allowed_libraries.length > 0}
					<div data-allowed-libraries>
						<div class="mb-3 flex items-center gap-2 text-cr-text">
							<Library class="size-4" />
							<h3 class="font-medium">Allowed Libraries</h3>
						</div>
						<div class="flex flex-wrap gap-2">
							{#each data.validation.allowed_libraries as library}
								<span class="rounded-full border border-cr-border bg-cr-bg px-3 py-1 text-sm text-cr-text">
									{library.name}
								</span>
							{/each}
						</div>
					</div>
				{:else if data.validation.target_servers && data.validation.target_servers.length > 0}
					<div class="flex items-center gap-2 text-cr-text-muted">
						<Library class="size-4" />
						<p class="text-sm">Access to all libraries on target servers</p>
					</div>
				{/if}

				<!-- Continue button -->
				<Button
					onclick={handleContinue}
					class="w-full bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
				>
					Continue to Registration
				</Button>
			</CardContent>
		</Card>
	{/if}
</div>
