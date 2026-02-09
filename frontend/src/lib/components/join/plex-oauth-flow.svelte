<script lang="ts">
/**
 * Plex OAuth flow component.
 *
 * Provides OAuth authentication flow for Plex servers:
 * - "Sign in with Plex" button
 * - PIN creation via API
 * - PIN code display
 * - Opens Plex auth URL in new window/tab
 * - Polls PIN status until authenticated or expired
 * - Displays user's Plex email when authenticated
 * - Error handling with retry option
 *
 * Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6
 *
 * @module $lib/components/join/plex-oauth-flow
 */

import {
	AlertTriangle,
	CheckCircle,
	ExternalLink,
	Loader2,
	RefreshCw,
} from "@lucide/svelte";
import { onDestroy } from "svelte";
import { toast } from "svelte-sonner";
import {
	checkPlexPin,
	createPlexPin,
	type PlexOAuthCheckResponse,
	type PlexOAuthPinResponse,
} from "$lib/api/client";
import { getErrorMessage } from "$lib/api/errors";
import { Button } from "$lib/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "$lib/components/ui/card";

interface Props {
	/** Callback when authentication is successful */
	onAuthenticated: (email: string) => void;
	/** Callback when user cancels the flow */
	onCancel?: () => void;
}

const { onAuthenticated, onCancel }: Props = $props();

// Flow state
type FlowStep =
	| "idle"
	| "creating_pin"
	| "waiting"
	| "authenticated"
	| "expired"
	| "error";
let currentStep = $state<FlowStep>("idle");

// PIN data
let pinData = $state<PlexOAuthPinResponse | null>(null);
let authenticatedEmail = $state<string | null>(null);
let errorMessage = $state<string | null>(null);

// Polling
let pollingInterval = $state<ReturnType<typeof setInterval> | null>(null);
const POLL_INTERVAL_MS = 2000;

/**
 * Clean up polling interval.
 */
function stopPolling() {
	if (pollingInterval) {
		clearInterval(pollingInterval);
		pollingInterval = null;
	}
}

// Clean up on component destroy
onDestroy(() => {
	stopPolling();
});

/**
 * Check if PIN has expired based on expires_at timestamp.
 */
function isPinExpired(expiresAt: string): boolean {
	return new Date(expiresAt) <= new Date();
}

/**
 * Start the Plex OAuth flow.
 */
async function startOAuthFlow() {
	currentStep = "creating_pin";
	errorMessage = null;

	try {
		const { data, error } = await createPlexPin();

		if (error) {
			throw new Error(getErrorMessage(error));
		}

		if (!data) {
			throw new Error("Failed to create PIN");
		}

		pinData = data;
		currentStep = "waiting";

		// Open Plex auth URL in new window/tab
		window.open(pinData.auth_url, "_blank", "noopener,noreferrer");

		// Start polling for PIN status
		startPolling();
	} catch (err) {
		errorMessage = getErrorMessage(err);
		currentStep = "error";
		toast.error("Failed to start Plex authentication");
	}
}

/**
 * Start polling for PIN status.
 */
function startPolling() {
	if (!pinData) return;

	pollingInterval = setInterval(async () => {
		if (!pinData) {
			stopPolling();
			return;
		}

		// Check if PIN has expired
		if (isPinExpired(pinData.expires_at)) {
			stopPolling();
			currentStep = "expired";
			return;
		}

		try {
			const { data, error } = await checkPlexPin(pinData.pin_id);

			if (error) {
				// Don't stop polling on transient errors
				console.error("PIN check error:", error);
				return;
			}

			if (!data) return;

			const checkResponse = data as PlexOAuthCheckResponse;

			if (checkResponse.authenticated && checkResponse.email) {
				stopPolling();
				authenticatedEmail = checkResponse.email;
				currentStep = "authenticated";
				onAuthenticated(checkResponse.email);
			} else if (checkResponse.error) {
				stopPolling();
				errorMessage = checkResponse.error;
				currentStep = "error";
			}
		} catch (err) {
			// Don't stop polling on network errors, just log
			console.error("PIN polling error:", err);
		}
	}, POLL_INTERVAL_MS);
}

/**
 * Retry the OAuth flow after error or expiration.
 */
function handleRetry() {
	stopPolling();
	pinData = null;
	authenticatedEmail = null;
	errorMessage = null;
	startOAuthFlow();
}

/**
 * Cancel the OAuth flow.
 */
function handleCancel() {
	stopPolling();
	pinData = null;
	currentStep = "idle";
	onCancel?.();
}

/**
 * Open the Plex auth URL again.
 */
function openAuthUrl() {
	if (pinData?.auth_url) {
		window.open(pinData.auth_url, "_blank", "noopener,noreferrer");
	}
}
</script>

<div class="space-y-6" data-plex-oauth-flow data-step={currentStep}>
	<!-- Idle state: Sign in button -->
	{#if currentStep === 'idle'}
		<div class="text-center space-y-4">
			<p class="text-cr-text-muted">
				Sign in with your Plex account to get access to the media server.
			</p>
			<Button
				onclick={startOAuthFlow}
				class="w-full bg-[#e5a00d] text-black hover:bg-[#cc8f0c] font-semibold"
				data-plex-signin-button
			>
				<svg class="size-5 mr-2" viewBox="0 0 24 24" fill="currentColor">
					<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
				</svg>
				Sign in with Plex
			</Button>
		</div>

	<!-- Creating PIN state -->
	{:else if currentStep === 'creating_pin'}
		<div class="text-center space-y-4">
			<div class="flex justify-center">
				<Loader2 class="size-8 animate-spin text-cr-accent" />
			</div>
			<p class="text-cr-text-muted">Preparing Plex authentication...</p>
		</div>

	<!-- Waiting for authentication -->
	{:else if currentStep === 'waiting' && pinData}
		<Card class="border-cr-border bg-cr-surface">
			<CardHeader>
				<CardTitle class="text-cr-text">Complete Authentication</CardTitle>
				<CardDescription class="text-cr-text-muted">
					A new window has opened for Plex sign-in. Complete the authentication there.
				</CardDescription>
			</CardHeader>
			<CardContent class="space-y-4">
				<!-- PIN Code Display -->
				<div class="rounded-lg border border-cr-border bg-cr-bg p-4 text-center" data-pin-display>
					<p class="text-sm text-cr-text-muted mb-2">Your PIN Code</p>
					<p class="text-3xl font-mono font-bold text-cr-accent tracking-widest" data-pin-code>
						{pinData.code}
					</p>
				</div>

				<!-- Waiting indicator -->
				<div class="flex items-center justify-center gap-2 text-cr-text-muted">
					<Loader2 class="size-4 animate-spin" />
					<span class="text-sm">Waiting for authentication...</span>
				</div>

				<!-- Action buttons -->
				<div class="flex gap-2">
					<Button
						variant="outline"
						onclick={openAuthUrl}
						class="flex-1 border-cr-border bg-cr-surface hover:bg-cr-border text-cr-text"
					>
						<ExternalLink class="size-4 mr-2" />
						Open Plex Again
					</Button>
					<Button
						variant="ghost"
						onclick={handleCancel}
						class="text-cr-text-muted hover:text-cr-text"
					>
						Cancel
					</Button>
				</div>
			</CardContent>
		</Card>

	<!-- Authenticated state -->
	{:else if currentStep === 'authenticated' && authenticatedEmail}
		<Card class="border-emerald-500/30 bg-emerald-500/5">
			<CardHeader>
				<div class="flex items-center gap-3">
					<div class="rounded-full bg-emerald-500/15 p-2 text-emerald-400">
						<CheckCircle class="size-5" />
					</div>
					<div>
						<CardTitle class="text-cr-text">Plex Authentication Successful</CardTitle>
						<CardDescription class="text-cr-text-muted">
							Signed in as <span class="font-medium text-cr-text" data-plex-email>{authenticatedEmail}</span>
						</CardDescription>
					</div>
				</div>
			</CardHeader>
		</Card>

	<!-- Expired state -->
	{:else if currentStep === 'expired'}
		<Card class="border-amber-500/30 bg-amber-500/5">
			<CardHeader>
				<div class="flex items-center gap-3">
					<div class="rounded-full bg-amber-500/15 p-2 text-amber-400">
						<AlertTriangle class="size-5" />
					</div>
					<div>
						<CardTitle class="text-cr-text">Authentication Expired</CardTitle>
						<CardDescription class="text-cr-text-muted">
							The PIN has expired. Please try again.
						</CardDescription>
					</div>
				</div>
			</CardHeader>
			<CardContent>
				<Button
					onclick={handleRetry}
					class="w-full bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
				>
					<RefreshCw class="size-4 mr-2" />
					Try Again
				</Button>
			</CardContent>
		</Card>

	<!-- Error state -->
	{:else if currentStep === 'error'}
		<Card class="border-rose-500/30 bg-rose-500/5">
			<CardHeader>
				<div class="flex items-center gap-3">
					<div class="rounded-full bg-rose-500/15 p-2 text-rose-400">
						<AlertTriangle class="size-5" />
					</div>
					<div>
						<CardTitle class="text-cr-text">Authentication Failed</CardTitle>
						<CardDescription class="text-cr-text-muted">
							{errorMessage ?? 'An error occurred during authentication.'}
						</CardDescription>
					</div>
				</div>
			</CardHeader>
			<CardContent>
				<Button
					onclick={handleRetry}
					class="w-full bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
				>
					<RefreshCw class="size-4 mr-2" />
					Try Again
				</Button>
			</CardContent>
		</Card>
	{/if}
</div>
