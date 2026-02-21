<script lang="ts">
/**
 * Quiz Interaction Component
 *
 * Renders question and selectable options.
 * Applies border glow on hover, checkmark animation on selection.
 * Calls onComplete with selected answer_index.
 *
 * Requirements: 8.1, 8.2, 8.3, 12.5
 */
import { Check } from "@lucide/svelte";
import { quizConfigSchema } from "$lib/schemas/wizard";
import type { InteractionComponentProps } from "./registry";

const { interactionId, config: rawConfig, onComplete, disabled = false, completionData }: InteractionComponentProps = $props();

// Validate config with Zod schema, falling back gracefully for partial configs
const config = $derived(quizConfigSchema.safeParse(rawConfig).data);
const question = $derived(config?.question ?? "");
const options = $derived(config?.options ?? []);

// Selection state — restore from completion data if navigating back
let selectedIndex = $state<number | null>(
	(() => (typeof completionData?.data?.answer_index === "number" ? completionData.data.answer_index : null))(),
);

// Derived - has selection
const hasSelection = $derived(selectedIndex !== null);

function selectOption(index: number) {
	if (disabled) return;
	selectedIndex = index;
}

function handleSubmit() {
	if (selectedIndex === null) return;

	onComplete({
		interactionId,
		interactionType: "quiz",
		data: { answer_index: selectedIndex },
		completedAt: new Date().toISOString(),
	});
}

function handleKeydown(event: KeyboardEvent, index: number) {
	if (event.key === "Enter" || event.key === " ") {
		event.preventDefault();
		selectOption(index);
	}
}
</script>

<div class="quiz-interaction">
	<!-- Question -->
	<h3 class="question">{question}</h3>

	<!-- Options -->
	<div class="options" role="radiogroup" aria-label="Quiz options">
		{#each options as option, index}
			<button
				type="button"
				role="radio"
				aria-checked={selectedIndex === index}
				class="option"
				class:selected={selectedIndex === index}
				onclick={() => selectOption(index)}
				onkeydown={(e) => handleKeydown(e, index)}
				{disabled}
			>
				<span class="option-indicator">
					{#if selectedIndex === index}
						<Check class="check-icon" />
					{/if}
				</span>
				<span class="option-text">{option}</span>
			</button>
		{/each}
	</div>

	<!-- Submit button -->
	<button
		type="button"
		class="wizard-accent-btn submit-btn"
		onclick={handleSubmit}
		disabled={!hasSelection || disabled}
	>
		Submit Answer
	</button>
</div>

<style>
	.quiz-interaction {
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
		padding: 1rem 0;
	}

	/* Question */
	.question {
		font-family: 'Instrument Serif', 'Playfair Display', Georgia, serif;
		font-size: 1.375rem;
		font-weight: 500;
		color: var(--wizard-text);
		margin: 0;
		line-height: 1.4;
	}

	/* Options container */
	.options {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	/* Individual option */
	.option {
		display: flex;
		align-items: center;
		gap: 0.875rem;
		padding: 1rem 1.25rem;
		background: var(--wizard-input-bg);
		border: 2px solid var(--wizard-input-border);
		border-radius: 0.75rem;
		cursor: pointer;
		transition: all 0.2s ease;
		text-align: left;
	}

	.option:hover:not(:disabled):not(.selected) {
		border-color: var(--wizard-accent-border-hover);
		box-shadow: 0 0 12px var(--wizard-accent-glow-sm);
		background: var(--wizard-input-hover-bg);
	}

	.option:focus-visible {
		outline: none;
		border-color: var(--wizard-accent);
		box-shadow: 0 0 0 3px var(--wizard-accent-glow-md);
	}

	.option.selected {
		border-color: var(--wizard-accent);
		background: var(--wizard-accent-bg-subtle);
		box-shadow: 0 0 16px var(--wizard-accent-glow-md);
	}

	.option:disabled {
		cursor: not-allowed;
		opacity: 0.5;
	}

	/* Option indicator (circle/check) */
	.option-indicator {
		flex-shrink: 0;
		width: 1.5rem;
		height: 1.5rem;
		display: flex;
		align-items: center;
		justify-content: center;
		background: var(--wizard-indicator-bg);
		border: 2px solid var(--wizard-ring-border);
		border-radius: 50%;
		transition: all 0.2s ease;
	}

	.option.selected .option-indicator {
		background: var(--wizard-accent);
		border-color: var(--wizard-accent);
		animation: check-pop 0.3s ease;
	}

	/* Check icon */
	.option-indicator :global(.check-icon) {
		width: 0.875rem;
		height: 0.875rem;
		color: var(--wizard-bg);
		stroke-width: 3;
	}

	/* Option text */
	.option-text {
		font-size: 0.9375rem;
		color: var(--wizard-text-secondary);
		line-height: 1.4;
	}

	.option.selected .option-text {
		color: var(--wizard-text);
	}

	/* Submit button layout */
	.submit-btn {
		align-self: flex-start;
		margin-top: 0.5rem;
	}

	/* Checkmark pop animation */
	@keyframes check-pop {
		0% {
			transform: scale(0.8);
		}
		50% {
			transform: scale(1.1);
		}
		100% {
			transform: scale(1);
		}
	}
</style>
