<script lang="ts">
	import DOMPurify from 'dompurify';
	import { marked } from 'marked';
	import type { Snippet } from 'svelte';
	/**
	 * Wizard Shell Component
	 *
	 * Main orchestrator for wizard flows. Manages step sequencing, progress tracking,
	 * and session persistence. Renders markdown content with XSS sanitization.
	 *
	 * Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 14.6, 15.1, 15.3
	 */
	import { browser } from '$app/environment';
	import type { WizardDetailResponse, WizardStepResponse } from '$lib/api/client';
	import { validateStep } from '$lib/api/client';
	import WizardNavigation from './wizard-navigation.svelte';
	import WizardProgress from './wizard-progress.svelte';

	export interface StepResponse {
		stepId: string;
		interactionType: string;
		data: { [key: string]: string | number | boolean | null };
		startedAt?: string;
		completedAt: string;
	}

	interface Props {
		wizard: WizardDetailResponse;
		onComplete: () => void;
		onCancel?: () => void;
		interaction?: Snippet<
			[
				{
					step: WizardStepResponse;
					onStepComplete: (response: StepResponse) => void;
					disabled: boolean;
				}
			]
		>;
	}

	let { wizard, onComplete, onCancel, interaction }: Props = $props();

	// Reactive state with $state
	let currentStepIndex = $state(0);
	let stepResponses = $state<Map<string, StepResponse>>(new Map());
	let isValidating = $state(false);
	let validationError = $state<string | null>(null);

	// Derived values with $derived
	const currentStep = $derived(wizard.steps[currentStepIndex]);
	const isFirstStep = $derived(currentStepIndex === 0);
	const isLastStep = $derived(currentStepIndex === wizard.steps.length - 1);
	const progress = $derived(((currentStepIndex + 1) / wizard.steps.length) * 100);
	const canProceed = $derived(stepResponses.has(currentStep?.id ?? ''));

	// Render markdown content with sanitization
	const renderedMarkdown = $derived.by(() => {
		if (!currentStep?.content_markdown) return '';
		const rawHtml = marked.parse(currentStep.content_markdown, { async: false }) as string;
		return DOMPurify.sanitize(rawHtml, {
			ALLOWED_TAGS: [
				'h1',
				'h2',
				'h3',
				'h4',
				'h5',
				'h6',
				'p',
				'br',
				'strong',
				'em',
				'u',
				'a',
				'ul',
				'ol',
				'li',
				'blockquote',
				'code',
				'pre'
			],
			ALLOWED_ATTR: ['href', 'target', 'rel']
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
					stepResponses = new Map(parsed.responses ?? []);
				} catch {
					// Invalid saved state, start fresh
				}
			}
		}
	});

	// Persist progress to sessionStorage
	$effect(() => {
		if (browser && wizard.id) {
			sessionStorage.setItem(
				`wizard-${wizard.id}-progress`,
				JSON.stringify({
					stepIndex: currentStepIndex,
					responses: Array.from(stepResponses.entries())
				})
			);
		}
	});

	async function handleNext() {
		const step = currentStep;
		if (!step || !canProceed || isValidating) return;

		const response = stepResponses.get(step.id);
		if (!response) return;

		isValidating = true;
		validationError = null;

		try {
			const result = await validateStep({
				step_id: step.id,
				response: response.data,
				started_at: response.startedAt ?? null
			});

			if (!result.data?.valid) {
				validationError = result.data?.error ?? 'Validation failed';
				return;
			}

			if (isLastStep) {
				// Clear session storage on completion
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

	function handleStepComplete(response: StepResponse) {
		const step = currentStep;
		if (!step) return;
		stepResponses.set(step.id, response);
		// Trigger reactivity by reassigning
		stepResponses = new Map(stepResponses);
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

			<!-- Interaction slot - to be filled by parent -->
			<div class="wizard-interaction">
				{#if interaction && currentStep}
					{@render interaction({
						step: currentStep,
						onStepComplete: handleStepComplete,
						disabled: isValidating
					})}
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
	/* Wizard-specific CSS variables */
	.wizard-shell {
		--wizard-bg: hsl(220 20% 4%);
		--wizard-surface: hsl(220 15% 8%);
		--wizard-border: hsl(220 10% 18%);
		--wizard-text: hsl(220 10% 92%);
		--wizard-text-muted: hsl(220 10% 60%);
		--wizard-accent: hsl(45 90% 55%);
		--wizard-accent-glow: hsl(45 90% 55% / 0.15);
		--wizard-success: hsl(150 60% 45%);
		--wizard-error: hsl(0 70% 55%);

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
		background: radial-gradient(ellipse at center, hsl(220 20% 8%) 0%, var(--wizard-bg) 70%);
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
			0 4px 24px hsl(0 0% 0% / 0.3),
			0 0 0 1px hsl(0 0% 100% / 0.05) inset;
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
		background: hsl(220 15% 12%);
		padding: 0.125rem 0.375rem;
		border-radius: 0.25rem;
		font-size: 0.9em;
	}

	/* Interaction area */
	.wizard-interaction {
		animation: wizard-reveal 0.6s ease-out 0.3s both;
	}

	/* Error message */
	.wizard-error {
		color: var(--wizard-error);
		font-size: 0.875rem;
		margin-top: 1rem;
		padding: 0.75rem 1rem;
		background: hsl(0 70% 55% / 0.1);
		border: 1px solid hsl(0 70% 55% / 0.3);
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
</style>
