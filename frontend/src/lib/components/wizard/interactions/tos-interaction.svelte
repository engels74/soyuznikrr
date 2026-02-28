<script lang="ts">
/**
 * Terms of Service Interaction Component
 *
 * Renders terms content and acceptance checkbox.
 * Requires checkbox before enabling proceed.
 * Records acceptance timestamp.
 */
import { Check } from "@lucide/svelte";
import { tosConfigSchema } from "$lib/schemas/wizard";
import type { InteractionComponentProps } from "./registry";

const { interactionId, config: rawConfig, onComplete, disabled = false, completionData }: InteractionComponentProps = $props();

// Validate config with Zod schema, falling back gracefully for partial configs
const config = $derived(tosConfigSchema.safeParse(rawConfig).data);
const checkboxLabel = $derived(
	config?.checkbox_label ?? "I accept the terms of service",
);

// Checkbox state — restore from completion data if navigating back
let accepted = $state((() => completionData?.data?.accepted === true)());

// Derived - can proceed only when accepted
const canProceed = $derived(accepted);

function handleAccept() {
	if (!accepted) return;

	onComplete({
		interactionId,
		interactionType: "tos",
		data: {
			accepted: true,
			accepted_at: new Date().toISOString(),
		},
		completedAt: new Date().toISOString(),
	});
}

function toggleAccepted() {
	accepted = !accepted;
}
</script>

<div class="tos-interaction">
	<!-- Custom checkbox -->
	<label class="checkbox-container">
		<button
			type="button"
			role="checkbox"
			aria-checked={accepted}
			class="checkbox"
			class:checked={accepted}
			onclick={toggleAccepted}
			{disabled}
		>
			{#if accepted}
				<Check class="check-icon" />
			{/if}
		</button>
		<span class="checkbox-label">{checkboxLabel}</span>
	</label>

	<!-- Accept button -->
	<button
		type="button"
		class="wizard-accent-btn"
		onclick={handleAccept}
		disabled={!canProceed || disabled}
	>
		Accept & Continue
	</button>
</div>

<style>
	.tos-interaction {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1.5rem;
		padding: 1rem 0;
	}

	/* Checkbox container */
	.checkbox-container {
		display: flex;
		align-items: flex-start;
		gap: 0.75rem;
		cursor: pointer;
		max-width: 100%;
	}

	/* Custom checkbox button */
	.checkbox {
		flex-shrink: 0;
		width: 1.5rem;
		height: 1.5rem;
		display: flex;
		align-items: center;
		justify-content: center;
		background: var(--wizard-input-hover-bg);
		border: 2px solid var(--wizard-ring-border);
		border-radius: 0.375rem;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.checkbox:hover:not(:disabled) {
		border-color: var(--wizard-accent);
		background: var(--wizard-indicator-bg);
	}

	.checkbox:focus-visible {
		outline: none;
		box-shadow:
			0 0 0 2px var(--wizard-bg),
			0 0 0 4px var(--wizard-focus-ring);
	}

	.checkbox.checked {
		background: var(--wizard-accent);
		border-color: var(--wizard-accent);
	}

	.checkbox:disabled {
		cursor: not-allowed;
		opacity: 0.5;
	}

	/* Check icon */
	.checkbox :global(.check-icon) {
		width: 1rem;
		height: 1rem;
		color: var(--wizard-bg);
		stroke-width: 3;
	}

	/* Checkbox label */
	.checkbox-label {
		font-size: 0.9375rem;
		line-height: 1.5;
		color: var(--wizard-text-secondary);
		user-select: none;
	}
</style>
