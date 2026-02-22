<script lang="ts">
import { ShieldCheck } from '@lucide/svelte';
import { browser } from '$app/environment';
import { setCsrfOrigin, withErrorHandling } from '$lib/api/client';
import { asErrorResponse } from '$lib/api/errors';
import { Button } from '$lib/components/ui/button';
import * as Card from '$lib/components/ui/card';
import { Input } from '$lib/components/ui/input';
import { Label } from '$lib/components/ui/label';
import { csrfOriginSchema } from '$lib/schemas/setup';

interface Props {
	onComplete: () => void;
	onSkip: () => void;
}

const { onComplete, onSkip }: Props = $props();

let origin = $state(browser ? window.location.origin : '');
let errors = $state<Record<string, string>>({});
let serverError = $state('');
let submitting = $state(false);

async function handleSubmit(e: SubmitEvent) {
	e.preventDefault();
	errors = {};
	serverError = '';

	const result = csrfOriginSchema.safeParse({ origin });
	if (!result.success) {
		for (const issue of result.error.issues) {
			const field = issue.path[0];
			if (field && typeof field === 'string') {
				errors[field] = issue.message;
			}
		}
		return;
	}

	submitting = true;
	try {
		const response = await withErrorHandling(
			() => setCsrfOrigin({ csrf_origin: result.data.origin }),
			{ showErrorToast: false }
		);

		if (response.error) {
			const errorBody = asErrorResponse(response.error);
			serverError = errorBody?.detail ?? 'Failed to save CSRF origin';
			return;
		}

		onComplete();
	} finally {
		submitting = false;
	}
}
</script>

<Card.Root class="border-cr-border bg-cr-surface">
	<Card.Header>
		<Card.Title class="text-lg text-cr-text">Security Configuration</Card.Title>
		<Card.Description class="text-cr-text-muted">
			Set your trusted origin for CSRF protection.
		</Card.Description>
	</Card.Header>
	<Card.Content>
		{#if serverError}
			<div
				class="mb-4 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400"
			>
				{serverError}
			</div>
		{/if}

		<!-- Info callout -->
		<div class="mb-4 rounded-lg border border-cr-accent/30 bg-cr-accent/5 p-3">
			<div class="flex items-start gap-2">
				<ShieldCheck class="mt-0.5 size-4 shrink-0 text-cr-accent" />
				<p class="text-sm text-cr-text-muted">
					CSRF protection prevents unauthorized requests from other websites. Set this to
					the URL where you access Zondarr to ensure only your browser can make changes.
				</p>
			</div>
		</div>

		<form onsubmit={handleSubmit} class="flex flex-col gap-4">
			<div class="flex flex-col gap-1.5">
				<Label for="csrf-origin" class="text-cr-text">Trusted Origin</Label>
				<Input
					id="csrf-origin"
					type="url"
					bind:value={origin}
					placeholder="https://zondarr.example.com"
					disabled={submitting}
					class="border-cr-border bg-cr-bg text-cr-text placeholder:text-cr-text-muted/50 focus:border-cr-accent font-mono text-sm"
				/>
				<p class="text-xs text-cr-text-muted">
					The origin URL where Zondarr is accessed (e.g., https://zondarr.example.com)
				</p>
				{#if errors.origin}
					<p class="text-xs text-red-400">{errors.origin}</p>
				{/if}
			</div>

			<div class="flex items-center justify-between gap-3 border-t border-cr-border pt-4">
				<Button
					type="button"
					variant="ghost"
					onclick={onSkip}
					disabled={submitting}
					class="text-cr-text-muted hover:text-cr-text"
				>
					Skip for now
				</Button>
				<Button
					type="submit"
					disabled={submitting}
					class="bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
				>
					{#if submitting}
						<span
							class="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"
						></span>
						Saving...
					{:else}
						Save & Finish
					{/if}
				</Button>
			</div>
		</form>

		<p class="mt-3 text-center text-xs text-cr-text-dim">
			You can change this later in Settings.
		</p>
	</Card.Content>
</Card.Root>
