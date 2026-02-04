<script lang="ts">
	/**
	 * Text Input Interaction Component
	 *
	 * Renders labeled input with placeholder.
	 * Implements client-side validation for required, min_length, max_length.
	 * Displays validation errors inline.
	 *
	 * Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 12.4
	 */
	import type { TextInputConfig, WizardStepResponse } from '$lib/api/client';

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

	let { step, onComplete, disabled = false }: Props = $props();

	// Extract config with defaults
	const config = $derived(step.config as unknown as TextInputConfig);
	const label = $derived(config?.label ?? 'Your response');
	const placeholder = $derived(config?.placeholder ?? '');
	const isRequired = $derived(config?.required ?? true);
	const minLength = $derived(config?.min_length);
	const maxLength = $derived(config?.max_length);

	// Input state
	let inputValue = $state('');
	let touched = $state(false);

	// Validation
	const validationError = $derived.by(() => {
		if (!touched) return null;

		const value = inputValue.trim();

		if (isRequired && value.length === 0) {
			return 'This field is required';
		}

		if (minLength !== undefined && value.length < minLength) {
			return `Must be at least ${minLength} characters`;
		}

		if (maxLength !== undefined && value.length > maxLength) {
			return `Must be at most ${maxLength} characters`;
		}

		return null;
	});

	const isValid = $derived.by(() => {
		const value = inputValue.trim();

		if (isRequired && value.length === 0) return false;
		if (minLength !== undefined && value.length < minLength) return false;
		if (maxLength !== undefined && value.length > maxLength) return false;

		return true;
	});

	// Character count display
	const charCount = $derived(inputValue.length);
	const showCharCount = $derived(minLength !== undefined || maxLength !== undefined);

	function handleBlur() {
		touched = true;
	}

	function handleSubmit() {
		touched = true;
		if (!isValid) return;

		onComplete({
			stepId: step.id,
			interactionType: 'text_input',
			data: { text: inputValue.trim() },
			completedAt: new Date().toISOString()
		});
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter' && !event.shiftKey) {
			event.preventDefault();
			handleSubmit();
		}
	}
</script>

<div class="text-input-interaction">
	<!-- Label -->
	<label for="wizard-text-input" class="input-label">{label}</label>

	<!-- Input container -->
	<div class="input-container">
		<input
			id="wizard-text-input"
			type="text"
			class="text-input"
			class:error={validationError}
			bind:value={inputValue}
			onblur={handleBlur}
			onkeydown={handleKeydown}
			{placeholder}
			{disabled}
			aria-invalid={!!validationError}
			aria-describedby={validationError ? 'input-error' : undefined}
		/>

		<!-- Character count -->
		{#if showCharCount}
			<div class="char-count" class:warning={maxLength !== undefined && charCount > maxLength}>
				{charCount}{#if maxLength !== undefined}/{maxLength}{/if}
			</div>
		{/if}
	</div>

	<!-- Validation error -->
	{#if validationError}
		<p id="input-error" class="error-message">{validationError}</p>
	{/if}

	<!-- Submit button -->
	<button type="button" class="submit-btn" onclick={handleSubmit} disabled={!isValid || disabled}>
		Continue
	</button>
</div>

<style>
	.text-input-interaction {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		padding: 1rem 0;
		width: 100%;
	}

	/* Label */
	.input-label {
		font-size: 0.875rem;
		font-weight: 500;
		color: hsl(220 10% 80%);
	}

	/* Input container */
	.input-container {
		position: relative;
		width: 100%;
	}

	/* Text input */
	.text-input {
		width: 100%;
		padding: 0.75rem 1rem;
		font-size: 1rem;
		color: hsl(220 10% 92%);
		background: hsl(220 15% 10%);
		border: 1px solid hsl(220 10% 25%);
		border-radius: 0.5rem;
		outline: none;
		transition: all 0.2s ease;
	}

	.text-input::placeholder {
		color: hsl(220 10% 45%);
	}

	.text-input:focus {
		border-color: hsl(45 90% 55%);
		box-shadow: 0 0 0 3px hsl(45 90% 55% / 0.15);
	}

	.text-input.error {
		border-color: hsl(0 70% 55%);
	}

	.text-input.error:focus {
		box-shadow: 0 0 0 3px hsl(0 70% 55% / 0.15);
	}

	.text-input:disabled {
		cursor: not-allowed;
		opacity: 0.5;
	}

	/* Character count */
	.char-count {
		position: absolute;
		right: 0.75rem;
		top: 50%;
		transform: translateY(-50%);
		font-size: 0.75rem;
		font-family: 'JetBrains Mono', 'Fira Code', monospace;
		font-variant-numeric: tabular-nums;
		color: hsl(220 10% 45%);
	}

	.char-count.warning {
		color: hsl(0 70% 55%);
	}

	/* Error message */
	.error-message {
		font-size: 0.8125rem;
		color: hsl(0 70% 55%);
		margin: 0;
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
</style>
