<script lang="ts">
/**
 * Join page for invitation code validation and redemption.
 *
 * Displays:
 * - Loading state during validation
 * - Target servers and allowed libraries for valid codes
 * - Duration information if set
 * - Error messages for invalid codes with failure reasons
 * - Jellyfin registration form for Jellyfin servers
 * - Plex OAuth flow for Plex servers
 * - Success page after successful registration
 *
 * @module routes/(public)/join/[code]/+page
 */

import { AlertTriangle, ArrowLeft, Calendar, CheckCircle, Library, Server } from '@lucide/svelte';
import { toast } from 'svelte-sonner';
import { invalidateAll } from '$app/navigation';
import {
	type RedemptionErrorResponse,
	type RedemptionResponse,
	redeemInvitation
} from '$lib/api/client';
import { getErrorMessage, isNetworkError } from '$lib/api/errors';
import ErrorState from '$lib/components/error-state.svelte';
import { JellyfinRegistrationForm, PlexOAuthFlow, RegistrationError, SuccessPage } from '$lib/components/join';
import { Button } from '$lib/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '$lib/components/ui/card';
import { Skeleton } from '$lib/components/ui/skeleton';
import {
	type JellyfinRegistrationInput,
	jellyfinRegistrationSchema,
	transformRegistrationFormData
} from '$lib/schemas/join';
import type { PageData } from './$types';

let { data }: { data: PageData } = $props();

// Flow state
type FlowStep = 'validation' | 'registration' | 'plex_oauth' | 'plex_redeeming' | 'success' | 'error';
let currentStep = $state<FlowStep>('validation');

// Loading states
let isRetrying = $state(false);
let isSubmitting = $state(false);

// Form data
let formData = $state<JellyfinRegistrationInput>({
	username: '',
	password: '',
	email: ''
});
let formErrors = $state<Record<string, string[]>>({});

// Plex OAuth state
let plexEmail = $state<string | null>(null);

// Response data
let redemptionResponse = $state<RedemptionResponse | null>(null);
let redemptionError = $state<RedemptionErrorResponse | null>(null);

// Derive server URLs for success page
let serverUrls = $derived.by(() => {
	const urls: Record<string, string> = {};
	if (data.validation?.target_servers) {
		for (const server of data.validation.target_servers) {
			urls[server.id] = server.url;
		}
	}
	return urls;
});

// Check if any target server is Jellyfin
let hasJellyfinServer = $derived(
	data.validation?.target_servers?.some((s) => s.server_type === 'jellyfin') ?? false
);

// Check if any target server is Plex
let hasPlexServer = $derived(
	data.validation?.target_servers?.some((s) => s.server_type === 'plex') ?? false
);

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
 * Proceed to registration flow.
 */
function handleContinue() {
	// Determine which registration flow to use based on server types
	if (hasPlexServer && !hasJellyfinServer) {
		currentStep = 'plex_oauth';
	} else {
		currentStep = 'registration';
	}
}

/**
 * Go back to validation step.
 */
function handleBack() {
	currentStep = 'validation';
	formErrors = {};
	plexEmail = null;
}

/**
 * Handle registration form submission.
 */
async function handleRegistrationSubmit() {
	// Validate form data
	const result = jellyfinRegistrationSchema.safeParse(formData);
	if (!result.success) {
		// Transform Zod errors to our format
		const errors: Record<string, string[]> = {};
		for (const issue of result.error.issues) {
			const field = issue.path[0] as string;
			if (!errors[field]) {
				errors[field] = [];
			}
			errors[field].push(issue.message);
		}
		formErrors = errors;
		return;
	}

	// Clear errors and submit
	formErrors = {};
	isSubmitting = true;

	try {
		const apiData = transformRegistrationFormData(result.data);
		const response = await redeemInvitation(data.code, apiData);

		if (response.error) {
			// Handle API error response - cast through unknown for type safety
			const errorBody = response.error as unknown as RedemptionErrorResponse;
			if (errorBody.error_code) {
				redemptionError = errorBody;
				currentStep = 'error';
				toast.error(errorBody.message || 'Registration failed');
			} else {
				toast.error('An unexpected error occurred');
			}
			return;
		}

		if (response.data) {
			// Check if it's an error response (has error_code)
			const responseData = response.data as RedemptionResponse | RedemptionErrorResponse;
			if ('error_code' in responseData) {
				redemptionError = responseData as RedemptionErrorResponse;
				currentStep = 'error';
				toast.error(redemptionError.message || 'Registration failed');
			} else if (responseData.success) {
				redemptionResponse = responseData as RedemptionResponse;
				currentStep = 'success';
				toast.success('Account created successfully!');
			} else {
				toast.error('Registration failed');
			}
		}
	} catch (err) {
		toast.error(getErrorMessage(err));
	} finally {
		isSubmitting = false;
	}
}

/**
 * Handle Plex OAuth authentication success.
 */
async function handlePlexAuthenticated(email: string) {
	plexEmail = email;
	currentStep = 'plex_redeeming';

	// Proceed to redeem the invitation with Plex credentials
	// For Plex, we use the email as username and a placeholder password
	// The backend will handle the actual Plex user creation
	try {
		const response = await redeemInvitation(data.code, {
			username: email,
			password: 'plex_oauth', // Placeholder - backend handles Plex auth differently
			email: email
		});

		if (response.error) {
			// Cast through unknown for type safety
			const errorBody = response.error as unknown as RedemptionErrorResponse;
			if (errorBody.error_code) {
				redemptionError = errorBody;
				currentStep = 'error';
				toast.error(errorBody.message || 'Registration failed');
			} else {
				toast.error('An unexpected error occurred');
			}
			return;
		}

		if (response.data) {
			const responseData = response.data as RedemptionResponse | RedemptionErrorResponse;
			if ('error_code' in responseData) {
				redemptionError = responseData as RedemptionErrorResponse;
				currentStep = 'error';
				toast.error(redemptionError.message || 'Registration failed');
			} else if (responseData.success) {
				redemptionResponse = responseData as RedemptionResponse;
				currentStep = 'success';
				toast.success('Successfully added to Plex server!');
			} else {
				toast.error('Registration failed');
			}
		}
	} catch (err) {
		redemptionError = {
			success: false,
			error_code: 'NETWORK_ERROR',
			message: getErrorMessage(err)
		};
		currentStep = 'error';
		toast.error(getErrorMessage(err));
	}
}

/**
 * Handle Plex OAuth cancellation.
 */
function handlePlexCancel() {
	currentStep = 'validation';
	plexEmail = null;
}

/**
 * Handle retry after registration error.
 */
function handleRegistrationRetry() {
	redemptionError = null;
	plexEmail = null;
	// Go back to appropriate registration step
	if (hasPlexServer && !hasJellyfinServer) {
		currentStep = 'plex_oauth';
	} else {
		currentStep = 'registration';
	}
}
</script>

<div class="space-y-6">
	<!-- Page header -->
	<div class="text-center">
		<h1 class="text-2xl font-bold text-cr-text md:text-3xl">Join Media Server</h1>
		<p class="mt-2 text-cr-text-muted">
			{#if currentStep === 'validation'}
				Validate your invitation code to get started
			{:else if currentStep === 'registration'}
				Create your account
			{:else if currentStep === 'plex_oauth'}
				Sign in with Plex
			{:else if currentStep === 'plex_redeeming'}
				Adding you to the server...
			{:else if currentStep === 'success'}
				Welcome aboard!
			{:else}
				Something went wrong
			{/if}
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

	<!-- Error state (network/validation error) -->
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

	<!-- Success state -->
	{:else if currentStep === 'success' && redemptionResponse}
		<SuccessPage response={redemptionResponse} {serverUrls} />

	<!-- Registration error state -->
	{:else if currentStep === 'error' && redemptionError}
		<RegistrationError error={redemptionError} onRetry={handleRegistrationRetry} />

	<!-- Registration form state -->
	{:else if currentStep === 'registration' && data.validation?.valid}
		<Card class="border-cr-border bg-cr-surface">
			<CardHeader>
				<div class="flex items-center gap-3">
					<Button
						variant="ghost"
						size="icon"
						onclick={handleBack}
						class="text-cr-text-muted hover:text-cr-text"
						aria-label="Go back"
					>
						<ArrowLeft class="size-5" />
					</Button>
					<div>
						<CardTitle class="text-cr-text">Create Your Account</CardTitle>
						<CardDescription class="text-cr-text-muted">
							{#if hasJellyfinServer && !hasPlexServer}
								Enter your details to create a Jellyfin account
							{:else if hasPlexServer && !hasJellyfinServer}
								Sign in with your Plex account
							{:else}
								Complete registration for your media server access
							{/if}
						</CardDescription>
					</div>
				</div>
			</CardHeader>
			<CardContent>
				{#if hasJellyfinServer}
					<JellyfinRegistrationForm
						bind:formData
						errors={formErrors}
						submitting={isSubmitting}
						onSubmit={handleRegistrationSubmit}
					/>
				{:else}
					<p class="text-cr-text-muted">No supported server types found.</p>
				{/if}
			</CardContent>
		</Card>

	<!-- Plex OAuth flow state -->
	{:else if currentStep === 'plex_oauth' && data.validation?.valid}
		<Card class="border-cr-border bg-cr-surface">
			<CardHeader>
				<div class="flex items-center gap-3">
					<Button
						variant="ghost"
						size="icon"
						onclick={handleBack}
						class="text-cr-text-muted hover:text-cr-text"
						aria-label="Go back"
					>
						<ArrowLeft class="size-5" />
					</Button>
					<div>
						<CardTitle class="text-cr-text">Sign in with Plex</CardTitle>
						<CardDescription class="text-cr-text-muted">
							Authenticate with your Plex account to get access
						</CardDescription>
					</div>
				</div>
			</CardHeader>
			<CardContent>
				<PlexOAuthFlow
					onAuthenticated={handlePlexAuthenticated}
					onCancel={handlePlexCancel}
				/>
			</CardContent>
		</Card>

	<!-- Plex redeeming state -->
	{:else if currentStep === 'plex_redeeming'}
		<Card class="border-cr-border bg-cr-surface">
			<CardHeader>
				<CardTitle class="text-cr-text">Adding You to the Server</CardTitle>
				<CardDescription class="text-cr-text-muted">
					Please wait while we set up your access...
				</CardDescription>
			</CardHeader>
			<CardContent class="flex flex-col items-center gap-4 py-8">
				<div class="size-8 animate-spin rounded-full border-2 border-cr-accent border-t-transparent"></div>
				{#if plexEmail}
					<p class="text-sm text-cr-text-muted">
						Signed in as <span class="font-medium text-cr-text">{plexEmail}</span>
					</p>
				{/if}
			</CardContent>
		</Card>

	<!-- Valid code state (validation step) -->
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
