<script lang="ts">
/**
 * Terms of Service Interaction Component
 *
 * Renders terms content and acceptance checkbox.
 * Requires checkbox before enabling proceed.
 * Records acceptance timestamp.
 *
 * Requirements: 6.1, 6.2, 6.3, 6.4, 12.3
 */
import { Check } from "@lucide/svelte";
import type { TosConfig, WizardStepResponse } from "$lib/api/client";

export interface StepResponse {
	stepId: string;
	interactionType: string;
	data: { [key: string]: string | number | boolean | null };
	startedAt?: string;
	completedAt: string;
}

interface Props {
	step: WizardStepResponse;
	onComplete: (response: StepResponse) => void;
	disabled?: boolean;
}

const { step, onComplete, disabled = false }: Props = $props();

// Extract checkbox label from config with default
const config = $derived(step.config as unknown as TosConfig);
const checkboxLabel = $derived(
	config?.checkbox_label ?? "I accept the terms of service",
);

// Checkbox state
let accepted = $state(false);

// Derived - can proceed only when accepted
const canProceed = $derived(accepted);

function handleAccept() {
	if (!accepted) return;

	onComplete({
		stepId: step.id,
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
		class="accept-btn"
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
		background: hsl(220 15% 12%);
		border: 2px solid hsl(220 10% 30%);
		border-radius: 0.375rem;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.checkbox:hover:not(:disabled) {
		border-color: hsl(45 90% 55%);
		background: hsl(220 15% 15%);
	}

	.checkbox:focus-visible {
		outline: none;
		box-shadow:
			0 0 0 2px hsl(220 20% 4%),
			0 0 0 4px hsl(45 90% 55% / 0.5);
	}

	.checkbox.checked {
		background: hsl(45 90% 55%);
		border-color: hsl(45 90% 55%);
	}

	.checkbox:disabled {
		cursor: not-allowed;
		opacity: 0.5;
	}

	/* Check icon */
	.checkbox :global(.check-icon) {
		width: 1rem;
		height: 1rem;
		color: hsl(220 20% 4%);
		stroke-width: 3;
	}

	/* Checkbox label */
	.checkbox-label {
		font-size: 0.9375rem;
		line-height: 1.5;
		color: hsl(220 10% 80%);
		user-select: none;
	}

	/* Accept button */
	.accept-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0.75rem 1.5rem;
		font-size: 0.875rem;
		font-weight: 600;
		color: hsl(220 20% 4%);
		background: hsl(45 90% 55%);
		border: none;
		border-radius: 0.375rem;
		cursor: pointer;
		transition: all 0.2s ease;
		box-shadow:
			0 0 16px hsl(45 90% 55% / 0.3),
			0 4px 12px hsl(0 0% 0% / 0.2);
	}

	.accept-btn:hover:not(:disabled) {
		transform: scale(1.02);
		box-shadow:
			0 0 24px hsl(45 90% 55% / 0.4),
			0 6px 16px hsl(0 0% 0% / 0.3);
	}

	.accept-btn:disabled {
		cursor: not-allowed;
		opacity: 0.5;
		background: hsl(220 10% 25%);
		color: hsl(220 10% 50%);
		box-shadow: none;
	}
</style>
