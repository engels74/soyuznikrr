<script lang="ts">
/**
 * Click Interaction Component
 *
 * Renders a confirmation button with configurable text.
 * Calls onComplete with acknowledgment data when clicked.
 *
 * Requirements: 4.1, 4.2, 4.3, 12.1
 */
import { clickConfigSchema } from "$lib/schemas/wizard";
import type { InteractionCompletionData, InteractionComponentProps } from "./registry";

const { interactionId, config: rawConfig, onComplete, disabled = false }: InteractionComponentProps = $props();

// Validate config with Zod schema, falling back gracefully for partial configs
const config = $derived(clickConfigSchema.safeParse(rawConfig).data);
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
	<button type="button" class="wizard-accent-btn confirm-btn" onclick={handleClick} {disabled}>
		{buttonText}
	</button>
</div>

<style>
	.click-interaction {
		display: flex;
		justify-content: center;
		padding: 1rem 0;
	}

	/* Override accent button sizing for primary CTA */
	.confirm-btn {
		gap: 0.5rem;
		padding: 0.875rem 2rem;
		font-size: 1rem;
		border-radius: 0.5rem;
		box-shadow:
			0 0 20px hsl(45 90% 55% / 0.25),
			0 4px 12px hsl(0 0% 0% / 0.2);
	}

	.confirm-btn:hover:not(:disabled) {
		box-shadow:
			0 0 28px hsl(45 90% 55% / 0.35),
			0 6px 16px hsl(0 0% 0% / 0.25);
	}
</style>
