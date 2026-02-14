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
import type { QuizConfig } from "$lib/api/client";
import type { InteractionComponentProps } from "./registry";

const { stepId, interactionId, config: rawConfig, onComplete, disabled = false }: InteractionComponentProps = $props();

// Extract config
const config = $derived(rawConfig as unknown as QuizConfig);
const question = $derived(config?.question ?? "");
const options = $derived(config?.options ?? []);

// Selection state
let selectedIndex = $state<number | null>(null);

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
		class="submit-btn"
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
		color: hsl(220 10% 92%);
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
		background: hsl(220 15% 10%);
		border: 2px solid hsl(220 10% 22%);
		border-radius: 0.75rem;
		cursor: pointer;
		transition: all 0.2s ease;
		text-align: left;
	}

	.option:hover:not(:disabled):not(.selected) {
		border-color: hsl(45 90% 55% / 0.5);
		box-shadow: 0 0 12px hsl(45 90% 55% / 0.15);
		background: hsl(220 15% 12%);
	}

	.option:focus-visible {
		outline: none;
		border-color: hsl(45 90% 55%);
		box-shadow: 0 0 0 3px hsl(45 90% 55% / 0.2);
	}

	.option.selected {
		border-color: hsl(45 90% 55%);
		background: hsl(45 90% 55% / 0.08);
		box-shadow: 0 0 16px hsl(45 90% 55% / 0.2);
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
		background: hsl(220 15% 15%);
		border: 2px solid hsl(220 10% 30%);
		border-radius: 50%;
		transition: all 0.2s ease;
	}

	.option.selected .option-indicator {
		background: hsl(45 90% 55%);
		border-color: hsl(45 90% 55%);
		animation: check-pop 0.3s ease;
	}

	/* Check icon */
	.option-indicator :global(.check-icon) {
		width: 0.875rem;
		height: 0.875rem;
		color: hsl(220 20% 4%);
		stroke-width: 3;
	}

	/* Option text */
	.option-text {
		font-size: 0.9375rem;
		color: hsl(220 10% 80%);
		line-height: 1.4;
	}

	.option.selected .option-text {
		color: hsl(220 10% 92%);
	}

	/* Submit button */
	.submit-btn {
		align-self: flex-start;
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
		margin-top: 0.5rem;
	}

	.submit-btn:hover:not(:disabled) {
		transform: scale(1.02);
		box-shadow:
			0 0 24px hsl(45 90% 55% / 0.4),
			0 6px 16px hsl(0 0% 0% / 0.3);
	}

	.submit-btn:disabled {
		cursor: not-allowed;
		opacity: 0.5;
		background: hsl(220 10% 25%);
		color: hsl(220 10% 50%);
		box-shadow: none;
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
