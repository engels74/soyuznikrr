<script lang="ts">
/**
 * Wizard Shell Component
 *
 * Main orchestrator for wizard flows. Manages step sequencing, progress tracking,
 * and session persistence. Renders markdown content with XSS sanitization.
 * Interactions are rendered internally via the interaction type registry.
 *
 * Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 14.6, 15.1, 15.3
 */
import DOMPurify from "dompurify";
import { marked } from "marked";
import { browser } from "$app/environment";
import type { WizardDetailResponse } from "$lib/api/client";
import { validateStep } from "$lib/api/client";
import { getInteractionType, type InteractionCompletionData } from "./interactions";
import WizardNavigation from "./wizard-navigation.svelte";
import WizardProgress from "./wizard-progress.svelte";

interface Props {
	wizard: WizardDetailResponse;
	onComplete: () => void;
	onCancel?: () => void;
}

const { wizard, onComplete, onCancel }: Props = $props();

// Reactive state
let currentStepIndex = $state(0);
let interactionCompletions = $state<
	Map<string, Map<string, InteractionCompletionData>>
>(new Map());
let isValidating = $state(false);
let validationError = $state<string | null>(null);

// Derived values
const currentStep = $derived(wizard.steps[currentStepIndex]);
const isFirstStep = $derived(currentStepIndex === 0);
const isLastStep = $derived(currentStepIndex === wizard.steps.length - 1);
const progress = $derived(
	((currentStepIndex + 1) / wizard.steps.length) * 100,
);

// Current step's interactions
const currentInteractions = $derived(currentStep?.interactions ?? []);
const hasInteractions = $derived(currentInteractions.length > 0);
const isMultiInteraction = $derived(currentInteractions.length > 1);

// Current step's completions
const currentCompletions = $derived(
	interactionCompletions.get(currentStep?.id ?? "") ?? new Map(),
);

// Can proceed: zero interactions = true; otherwise all must be completed
const canProceed = $derived(
	!hasInteractions ||
		currentInteractions.every((i) => currentCompletions.has(i.id)),
);

// Count completions for progress display
const completedCount = $derived(currentCompletions.size);
const totalCount = $derived(currentInteractions.length);

// Render markdown content with sanitization
const renderedMarkdown = $derived.by(() => {
	if (!currentStep?.content_markdown) return "";
	const rawHtml = marked.parse(currentStep.content_markdown, {
		async: false,
	}) as string;
	return DOMPurify.sanitize(rawHtml, {
		ALLOWED_TAGS: [
			"h1",
			"h2",
			"h3",
			"h4",
			"h5",
			"h6",
			"p",
			"br",
			"strong",
			"em",
			"u",
			"a",
			"ul",
			"ol",
			"li",
			"blockquote",
			"code",
			"pre",
		],
		ALLOWED_ATTR: ["href", "target", "rel"],
	});
});

// Restore progress from sessionStorage on mount
$effect(() => {
	if (browser) {
		const saved = sessionStorage.getItem(`wizard-${wizard.id}-progress`);
		if (saved) {
			try {
				const parsed = JSON.parse(saved);
				currentStepIndex = parsed.stepIndex ?? 0;
				// Restore nested map structure
				if (parsed.completions) {
					interactionCompletions = new Map(
						(
							parsed.completions as [
								string,
								[string, InteractionCompletionData][],
							][]
						).map(([stepId, entries]) => [stepId, new Map(entries)]),
					);
				}
			} catch {
				// Invalid saved state, start fresh
			}
		}
	}
});

// Persist progress to sessionStorage
$effect(() => {
	if (browser && wizard.id) {
		// Serialize nested map
		const completions = Array.from(interactionCompletions.entries()).map(
			([stepId, completionMap]) => [
				stepId,
				Array.from(completionMap.entries()),
			],
		);
		sessionStorage.setItem(
			`wizard-${wizard.id}-progress`,
			JSON.stringify({
				stepIndex: currentStepIndex,
				completions,
			}),
		);
	}
});

async function handleNext() {
	const step = currentStep;
	if (!step || !canProceed || isValidating) return;

	isValidating = true;
	validationError = null;

	try {
		// Build interaction responses array
		const interactions = currentInteractions.map((interaction) => {
			const completion = currentCompletions.get(interaction.id);
			return {
				interaction_id: interaction.id,
				response: completion?.data ?? {},
				started_at: completion?.startedAt ?? null,
			};
		});

		const result = await validateStep({
			step_id: step.id,
			interactions: interactions.length > 0 ? interactions : [],
		});

		if (!result.data?.valid) {
			validationError = result.data?.error ?? "Validation failed";
			return;
		}

		if (isLastStep) {
			if (browser) {
				sessionStorage.removeItem(`wizard-${wizard.id}-progress`);
			}
			onComplete();
		} else {
			currentStepIndex++;
		}
	} finally {
		isValidating = false;
	}
}

function handleBack() {
	if (!isFirstStep) {
		currentStepIndex--;
		validationError = null;
	}
}

function handleInteractionComplete(data: InteractionCompletionData) {
	const stepId = currentStep?.id;
	if (!stepId) return;

	const stepCompletions = new Map(
		interactionCompletions.get(stepId) ?? new Map(),
	);
	stepCompletions.set(data.interactionId, data);

	const newMap = new Map(interactionCompletions);
	newMap.set(stepId, stepCompletions);
	interactionCompletions = newMap;
}
</script>

<div class="wizard-shell">
	<!-- Background gradient -->
	<div class="wizard-bg"></div>

	<div class="wizard-container">
		<!-- Progress indicator -->
		<WizardProgress current={currentStepIndex + 1} total={wizard.steps.length} {progress} />

		<!-- Step content card -->
		<div class="wizard-card">
			<!-- Step title -->
			{#if currentStep?.title}
				<h2 class="wizard-title">{currentStep.title}</h2>
			{/if}

			<!-- Markdown content -->
			<div class="wizard-content prose prose-invert">
				{@html renderedMarkdown}
			</div>

			<!-- Interactions area -->
			<div class="wizard-interaction">
				{#if hasInteractions}
					{#if isMultiInteraction}
						<div class="interaction-progress">
							<span class="progress-text">{completedCount}/{totalCount} completed</span>
							<div class="progress-track">
								<div
									class="progress-fill"
									style="width: {totalCount > 0 ? (completedCount / totalCount) * 100 : 0}%"
								></div>
							</div>
						</div>
					{/if}

					{#each currentInteractions as interaction, idx (interaction.id)}
						{@const registration = getInteractionType(interaction.interaction_type)}
						{@const isCompleted = currentCompletions.has(interaction.id)}

						{#if isMultiInteraction && idx > 0}
							<div class="interaction-divider"></div>
						{/if}

						{#if registration}
							{@const InteractionComponent = registration.interactionComponent}
							<div
								class="interaction-block"
								class:completed={isCompleted && isMultiInteraction}
								style="animation-delay: {0.3 + idx * 0.1}s"
							>
								{#if isMultiInteraction}
									<div class="interaction-header">
										<div class="completion-ring" class:done={isCompleted}>
											{#if isCompleted}
												<svg viewBox="0 0 20 20" class="check-icon">
													<path d="M6 10l3 3 5-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
												</svg>
											{/if}
										</div>
										<span class="interaction-label">{registration.label}</span>
									</div>
								{/if}

								<InteractionComponent
									interactionId={interaction.id}
									config={interaction.config}
									onComplete={handleInteractionComplete}
									disabled={isValidating || isCompleted}
								/>
							</div>
						{/if}
					{/each}
				{/if}
			</div>

			<!-- Validation error -->
			{#if validationError}
				<p class="wizard-error">{validationError}</p>
			{/if}
		</div>

		<!-- Navigation -->
		<WizardNavigation
			{isFirstStep}
			{isLastStep}
			{canProceed}
			loading={isValidating}
			onBack={handleBack}
			onNext={handleNext}
			{onCancel}
		/>
	</div>
</div>

<style>
	/*
	 * Wizard shell CSS variables — intentionally a fixed dark-mode-only design.
	 * The wizard is a standalone cinematic experience that doesn't follow the
	 * admin theme. Colors are hardcoded here rather than in app.css :root.
	 */
	.wizard-shell {
		--wizard-bg: hsl(220 20% 4%);
		--wizard-surface: hsl(220 15% 8%);
		--wizard-surface-elevated: hsl(220 20% 8%);
		--wizard-border: hsl(220 10% 18%);
		--wizard-text: hsl(220 10% 92%);
		--wizard-text-muted: hsl(220 10% 60%);
		--wizard-accent: var(--cr-module-active-accent);
		--wizard-accent-dim: var(--cr-module-active-accent-dim);
		--wizard-accent-glow: hsl(45 90% 55% / 0.15);
		--wizard-success: var(--cr-success);
		--wizard-error: var(--cr-error);
		--wizard-error-bg: hsl(0 70% 55% / 0.1);
		--wizard-error-border: hsl(0 70% 55% / 0.3);
		--wizard-code-bg: hsl(220 15% 12%);
		--wizard-track-bg: hsl(220 10% 16%);
		--wizard-divider: hsl(220 10% 20%);
		--wizard-ring-border: hsl(220 10% 30%);

		/* Glow/shadow colors (used by interaction components for box-shadow) */
		--wizard-accent-glow-sm: hsl(45 90% 55% / 0.15);
		--wizard-accent-glow-md: hsl(45 90% 55% / 0.2);
		--wizard-accent-glow-lg: hsl(45 90% 55% / 0.25);
		--wizard-accent-glow-xl: hsl(45 90% 55% / 0.3);
		--wizard-accent-glow-2xl: hsl(45 90% 55% / 0.35);
		--wizard-accent-glow-hover: hsl(45 90% 55% / 0.4);
		--wizard-accent-glow-active: hsl(45 90% 55% / 0.5);
		--wizard-accent-border-hover: hsl(45 90% 55% / 0.5);
		--wizard-accent-bg-subtle: hsl(45 90% 55% / 0.08);
		--wizard-shadow-sm: hsl(0 0% 0% / 0.2);
		--wizard-shadow-md: hsl(0 0% 0% / 0.25);
		--wizard-shadow-lg: hsl(0 0% 0% / 0.3);
		--wizard-success-glow-lg: hsl(150 60% 45% / 0.4);
		--wizard-success-glow-sm: hsl(150 60% 45% / 0.2);
		--wizard-error-glow-sm: hsl(0 70% 55% / 0.15);
		--wizard-card-inset: hsl(0 0% 100% / 0.05);
		--wizard-focus-ring: hsl(45 90% 55% / 0.5);

		/* SVG gradient stop colors */
		--wizard-accent-gradient-start: hsl(45 90% 45%);
		--wizard-accent-gradient-end: hsl(45 90% 60%);

		/* Form element colors (used by interaction components) */
		--wizard-text-secondary: hsl(220 10% 80%);
		--wizard-text-dim: hsl(220 10% 50%);
		--wizard-input-bg: hsl(220 15% 10%);
		--wizard-input-border: hsl(220 10% 22%);
		--wizard-input-hover-bg: hsl(220 15% 12%);
		--wizard-indicator-bg: hsl(220 15% 15%);
		--wizard-placeholder: hsl(220 10% 45%);
		--wizard-btn-disabled-bg: hsl(220 10% 25%);

		position: relative;
		min-height: 100vh;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 2rem;
		background: var(--wizard-bg);
		color: var(--wizard-text);
		font-family: 'Satoshi', 'DM Sans', system-ui, sans-serif;
	}

	/* Atmospheric background gradient */
	.wizard-bg {
		position: absolute;
		inset: 0;
		background: radial-gradient(ellipse at center, var(--wizard-surface-elevated) 0%, var(--wizard-bg) 70%);
		pointer-events: none;
	}

	.wizard-container {
		position: relative;
		width: 100%;
		max-width: 640px;
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}

	/* Step card with glass effect */
	.wizard-card {
		background: var(--wizard-surface);
		border: 1px solid var(--wizard-border);
		border-radius: 1rem;
		padding: 2rem;
		backdrop-filter: blur(8px);
		box-shadow:
			0 4px 24px var(--wizard-shadow-lg),
			0 0 0 1px var(--wizard-card-inset) inset;
		animation: wizard-reveal 0.6s ease-out 0.1s both;
	}

	/* Cinematic title */
	.wizard-title {
		font-family: 'Instrument Serif', 'Playfair Display', Georgia, serif;
		font-size: 2rem;
		font-weight: 500;
		letter-spacing: -0.02em;
		margin-bottom: 1.5rem;
		color: var(--wizard-text);
		animation: wizard-reveal 0.6s ease-out 0.15s both;
	}

	/* Content area */
	.wizard-content {
		font-size: 1.125rem;
		line-height: 1.7;
		color: var(--wizard-text-muted);
		margin-bottom: 1.5rem;
		animation: wizard-reveal 0.6s ease-out 0.2s both;
	}

	.wizard-content :global(a) {
		color: var(--wizard-accent);
		text-decoration: underline;
		text-underline-offset: 2px;
	}

	.wizard-content :global(a:hover) {
		opacity: 0.8;
	}

	.wizard-content :global(strong) {
		color: var(--wizard-text);
		font-weight: 600;
	}

	.wizard-content :global(code) {
		font-family: 'JetBrains Mono', 'Fira Code', monospace;
		background: var(--wizard-code-bg);
		padding: 0.125rem 0.375rem;
		border-radius: 0.25rem;
		font-size: 0.9em;
	}

	/* Interaction area */
	.wizard-interaction {
		animation: wizard-reveal 0.6s ease-out 0.3s both;
	}

	/* Multi-interaction progress bar */
	.interaction-progress {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin-bottom: 1.25rem;
	}

	.progress-text {
		font-size: 0.6875rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--wizard-text-muted);
	}

	.progress-track {
		height: 2px;
		background: var(--wizard-track-bg);
		border-radius: 1px;
		overflow: hidden;
	}

	.progress-fill {
		height: 100%;
		background: linear-gradient(to right, var(--wizard-accent), var(--wizard-accent-dim));
		border-radius: 1px;
		transition: width 0.4s ease;
	}

	/* Gradient divider between interactions */
	.interaction-divider {
		height: 1px;
		margin: 1.25rem 0;
		background: linear-gradient(to right, transparent, var(--wizard-divider), transparent);
	}

	/* Interaction block */
	.interaction-block {
		animation: wizard-reveal 0.5s ease-out both;
	}

	.interaction-block.completed {
		opacity: 0.7;
		transition: opacity 0.3s ease;
	}

	/* Interaction header (multi-interaction only) */
	.interaction-header {
		display: flex;
		align-items: center;
		gap: 0.625rem;
		margin-bottom: 0.75rem;
	}

	.completion-ring {
		width: 1.25rem;
		height: 1.25rem;
		border-radius: 50%;
		border: 1.5px solid var(--wizard-ring-border);
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.3s ease;
		flex-shrink: 0;
	}

	.completion-ring.done {
		border-color: var(--wizard-accent);
		background: var(--wizard-accent);
		animation: check-pop 0.3s ease;
	}

	.check-icon {
		width: 0.75rem;
		height: 0.75rem;
		color: var(--wizard-bg);
	}

	.interaction-label {
		font-size: 0.6875rem;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--wizard-text-muted);
	}

	/* Error message */
	.wizard-error {
		color: var(--wizard-error);
		font-size: 0.875rem;
		margin-top: 1rem;
		padding: 0.75rem 1rem;
		background: var(--wizard-error-bg);
		border: 1px solid var(--wizard-error-border);
		border-radius: 0.5rem;
	}

	/* Reveal animation */
	@keyframes wizard-reveal {
		from {
			opacity: 0;
			transform: translateY(20px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	@keyframes check-pop {
		0% {
			transform: scale(0.8);
		}
		50% {
			transform: scale(1.15);
		}
		100% {
			transform: scale(1);
		}
	}
</style>
