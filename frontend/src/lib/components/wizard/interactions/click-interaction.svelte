<script lang="ts">
/**
 * Click Interaction Component
 *
 * Renders a confirmation button with configurable text.
 * Calls onComplete with acknowledgment data when clicked.
 *
 * Requirements: 4.1, 4.2, 4.3, 12.1
 */
import type { ClickConfig } from "$lib/api/client";
import type { InteractionCompletionData, InteractionComponentProps } from "./registry";

const { stepId, interactionId, config: rawConfig, onComplete, disabled = false }: InteractionComponentProps = $props();

// Extract button text from config with default
const config = $derived(rawConfig as unknown as ClickConfig);
const buttonText = $derived(config?.button_text ?? "I Understand");

function handleClick() {
	onComplete({
		interactionId,
		interactionType: "click",
		data: { acknowledged: true },
		completedAt: new Date().toISOString(),
	});
}
</script>

<div class="click-interaction">
	<button type="button" class="confirm-btn" onclick={handleClick} {disabled}>
		{buttonText}
	</button>
</div>

<style>
	.click-interaction {
		display: flex;
		justify-content: center;
		padding: 1rem 0;
	}

	/* Accent button styling per design spec */
	.confirm-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		padding: 0.875rem 2rem;
		font-size: 1rem;
		font-weight: 600;
		color: hsl(220 20% 4%);
		background: hsl(45 90% 55%);
		border: none;
		border-radius: 0.5rem;
		cursor: pointer;
		transition: all 0.2s ease;
		box-shadow:
			0 0 20px hsl(45 90% 55% / 0.25),
			0 4px 12px hsl(0 0% 0% / 0.2);
	}

	.confirm-btn:hover:not(:disabled) {
		transform: scale(1.02);
		box-shadow:
			0 0 28px hsl(45 90% 55% / 0.35),
			0 6px 16px hsl(0 0% 0% / 0.25);
	}

	.confirm-btn:active:not(:disabled) {
		transform: scale(0.98);
	}

	.confirm-btn:disabled {
		cursor: not-allowed;
		opacity: 0.5;
		background: hsl(220 10% 25%);
		color: hsl(220 10% 50%);
		box-shadow: none;
	}
</style>
