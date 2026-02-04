<script lang="ts">
/**
 * Step Editor Component
 *
 * Renders type-specific configuration forms for wizard steps.
 * Validates config against Zod schemas.
 *
 * Requirements: 13.3
 *
 * @module $lib/components/wizard/step-editor
 */

import type { WizardStepResponse } from '$lib/api/client';
import { Button } from '$lib/components/ui/button';
import { Input } from '$lib/components/ui/input';
import { Label } from '$lib/components/ui/label';
import {
	type ClickConfig,
	clickConfigSchema,
	type InteractionType,
	type QuizConfig,
	quizConfigSchema,
	type TextInputConfig,
	type TimerConfig,
	type TosConfig,
	textInputConfigSchema,
	timerConfigSchema,
	tosConfigSchema,
	validateStepConfig
} from '$lib/schemas/wizard';
import MarkdownEditor from './markdown-editor.svelte';

interface Props {
	step: WizardStepResponse;
	onSave: (updates: Partial<WizardStepResponse>) => void;
	onCancel: () => void;
}

let { step, onSave, onCancel }: Props = $props();

// Form state
let title = $state(step.title);
let contentMarkdown = $state(step.content_markdown);
let config = $state<Record<string, unknown>>({ ...step.config });
let errors = $state<Record<string, string[]>>({});
let isSaving = $state(false);

// Derived interaction type
const interactionType = $derived(step.interaction_type as InteractionType);

// Type-specific config getters/setters
const clickConfig = $derived(config as ClickConfig);
const timerConfig = $derived(config as TimerConfig);
const tosConfig = $derived(config as TosConfig);
const textInputConfig = $derived(config as TextInputConfig);
const quizConfig = $derived(config as QuizConfig);

/**
 * Validate the step configuration.
 */
function validateConfig(): boolean {
	const result = validateStepConfig(interactionType, config);
	if (!result.success) {
		const fieldErrors: Record<string, string[]> = {};
		for (const issue of result.error.issues) {
			const path = issue.path.join('.');
			if (!fieldErrors[path]) {
				fieldErrors[path] = [];
			}
			fieldErrors[path].push(issue.message);
		}
		errors = fieldErrors;
		return false;
	}
	errors = {};
	return true;
}

/**
 * Handle save.
 */
function handleSave() {
	if (!validateConfig()) {
		return;
	}

	isSaving = true;
	onSave({
		title,
		content_markdown: contentMarkdown,
		config
	});
	isSaving = false;
}

/**
 * Update config field.
 */
function updateConfig<T>(field: string, value: T) {
	config = { ...config, [field]: value };
}

/**
 * Add quiz option.
 */
function addQuizOption() {
	const options = (config.options as string[]) ?? [];
	config = { ...config, options: [...options, ''] };
}

/**
 * Remove quiz option.
 */
function removeQuizOption(index: number) {
	const options = (config.options as string[]) ?? [];
	const newOptions = options.filter((_, i) => i !== index);
	// Adjust correct_answer_index if needed
	let correctIndex = (config.correct_answer_index as number) ?? 0;
	if (correctIndex >= newOptions.length) {
		correctIndex = Math.max(0, newOptions.length - 1);
	}
	config = { ...config, options: newOptions, correct_answer_index: correctIndex };
}

/**
 * Update quiz option.
 */
function updateQuizOption(index: number, value: string) {
	const options = [...((config.options as string[]) ?? [])];
	options[index] = value;
	config = { ...config, options };
}
</script>

<div class="step-editor">
	<!-- Title field -->
	<div class="field">
		<Label for="step-title" class="text-cr-text">Step Title</Label>
		<Input
			id="step-title"
			bind:value={title}
			placeholder="Enter step title"
			class="border-cr-border bg-cr-bg text-cr-text"
		/>
	</div>

	<!-- Content markdown editor -->
	<div class="field">
		<Label class="text-cr-text">Content</Label>
		<MarkdownEditor bind:value={contentMarkdown} />
	</div>

	<!-- Type-specific configuration -->
	<div class="config-section">
		<h4 class="config-title">Configuration</h4>

		{#if interactionType === 'click'}
			<!-- Click config -->
			<div class="field">
				<Label for="button-text" class="text-cr-text">Button Text</Label>
				<Input
					id="button-text"
					value={clickConfig.button_text ?? ''}
					oninput={(e) => updateConfig('button_text', e.currentTarget.value)}
					placeholder="I Understand"
					class="border-cr-border bg-cr-bg text-cr-text"
				/>
				{#if errors.button_text}
					<p class="error-text">{errors.button_text[0]}</p>
				{/if}
			</div>
		{:else if interactionType === 'timer'}
			<!-- Timer config -->
			<div class="field">
				<Label for="duration" class="text-cr-text">Duration (seconds)</Label>
				<Input
					id="duration"
					type="number"
					min="1"
					max="300"
					value={timerConfig.duration_seconds ?? 10}
					oninput={(e) => updateConfig('duration_seconds', parseInt(e.currentTarget.value) || 10)}
					class="border-cr-border bg-cr-bg text-cr-text"
				/>
				<p class="help-text">Minimum 1 second, maximum 300 seconds (5 minutes)</p>
				{#if errors.duration_seconds}
					<p class="error-text">{errors.duration_seconds[0]}</p>
				{/if}
			</div>
		{:else if interactionType === 'tos'}
			<!-- TOS config -->
			<div class="field">
				<Label for="checkbox-label" class="text-cr-text">Checkbox Label</Label>
				<Input
					id="checkbox-label"
					value={tosConfig.checkbox_label ?? ''}
					oninput={(e) => updateConfig('checkbox_label', e.currentTarget.value)}
					placeholder="I accept the terms of service"
					class="border-cr-border bg-cr-bg text-cr-text"
				/>
				{#if errors.checkbox_label}
					<p class="error-text">{errors.checkbox_label[0]}</p>
				{/if}
			</div>
		{:else if interactionType === 'text_input'}
			<!-- Text input config -->
			<div class="field">
				<Label for="input-label" class="text-cr-text">Input Label</Label>
				<Input
					id="input-label"
					value={textInputConfig.label ?? ''}
					oninput={(e) => updateConfig('label', e.currentTarget.value)}
					placeholder="Your response"
					class="border-cr-border bg-cr-bg text-cr-text"
				/>
				{#if errors.label}
					<p class="error-text">{errors.label[0]}</p>
				{/if}
			</div>

			<div class="field">
				<Label for="input-placeholder" class="text-cr-text">Placeholder</Label>
				<Input
					id="input-placeholder"
					value={textInputConfig.placeholder ?? ''}
					oninput={(e) => updateConfig('placeholder', e.currentTarget.value)}
					placeholder="Enter placeholder text"
					class="border-cr-border bg-cr-bg text-cr-text"
				/>
			</div>

			<div class="field-row">
				<div class="field">
					<Label for="min-length" class="text-cr-text">Min Length</Label>
					<Input
						id="min-length"
						type="number"
						min="0"
						value={textInputConfig.min_length ?? ''}
						oninput={(e) =>
							updateConfig(
								'min_length',
								e.currentTarget.value ? parseInt(e.currentTarget.value) : undefined
							)}
						placeholder="0"
						class="border-cr-border bg-cr-bg text-cr-text"
					/>
					{#if errors.min_length}
						<p class="error-text">{errors.min_length[0]}</p>
					{/if}
				</div>

				<div class="field">
					<Label for="max-length" class="text-cr-text">Max Length</Label>
					<Input
						id="max-length"
						type="number"
						min="1"
						value={textInputConfig.max_length ?? ''}
						oninput={(e) =>
							updateConfig(
								'max_length',
								e.currentTarget.value ? parseInt(e.currentTarget.value) : undefined
							)}
						placeholder="No limit"
						class="border-cr-border bg-cr-bg text-cr-text"
					/>
					{#if errors.max_length}
						<p class="error-text">{errors.max_length[0]}</p>
					{/if}
				</div>
			</div>

			<div class="field">
				<label class="checkbox-label">
					<input
						type="checkbox"
						checked={textInputConfig.required ?? true}
						onchange={(e) => updateConfig('required', e.currentTarget.checked)}
						class="checkbox"
					/>
					<span class="text-cr-text">Required field</span>
				</label>
			</div>
		{:else if interactionType === 'quiz'}
			<!-- Quiz config -->
			<div class="field">
				<Label for="question" class="text-cr-text">Question</Label>
				<Input
					id="question"
					value={quizConfig.question ?? ''}
					oninput={(e) => updateConfig('question', e.currentTarget.value)}
					placeholder="Enter your question"
					class="border-cr-border bg-cr-bg text-cr-text"
				/>
				{#if errors.question}
					<p class="error-text">{errors.question[0]}</p>
				{/if}
			</div>

			<div class="field">
				<div class="options-header">
					<Label class="text-cr-text">Answer Options</Label>
					<Button
						variant="outline"
						size="sm"
						onclick={addQuizOption}
						disabled={(quizConfig.options?.length ?? 0) >= 10}
						class="border-cr-border text-cr-text-muted"
					>
						Add Option
					</Button>
				</div>

				<div class="options-list">
					{#each quizConfig.options ?? [] as option, index}
						<div class="option-row">
							<label class="radio-label">
								<input
									type="radio"
									name="correct-answer"
									checked={(quizConfig.correct_answer_index ?? 0) === index}
									onchange={() => updateConfig('correct_answer_index', index)}
									class="radio"
								/>
							</label>
							<Input
								value={option}
								oninput={(e) => updateQuizOption(index, e.currentTarget.value)}
								placeholder={`Option ${index + 1}`}
								class="flex-1 border-cr-border bg-cr-bg text-cr-text"
							/>
							<Button
								variant="ghost"
								size="sm"
								onclick={() => removeQuizOption(index)}
								disabled={(quizConfig.options?.length ?? 0) <= 2}
								class="text-cr-text-muted hover:text-destructive"
							>
								×
							</Button>
						</div>
					{/each}
				</div>

				<p class="help-text">Select the radio button next to the correct answer.</p>
				{#if errors.options}
					<p class="error-text">{errors.options[0]}</p>
				{/if}
				{#if errors.correct_answer_index}
					<p class="error-text">{errors.correct_answer_index[0]}</p>
				{/if}
			</div>
		{/if}
	</div>

	<!-- Actions -->
	<div class="actions">
		<Button variant="ghost" onclick={onCancel} class="text-cr-text-muted">
			Cancel
		</Button>
		<Button
			onclick={handleSave}
			disabled={isSaving}
			class="bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
		>
			{isSaving ? 'Saving...' : 'Save Step'}
		</Button>
	</div>
</div>

<style>
	.step-editor {
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.field-row {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1rem;
	}

	.config-section {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		padding-top: 1rem;
		border-top: 1px solid var(--cr-border);
	}

	.config-title {
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--cr-text);
		margin: 0;
	}

	.help-text {
		font-size: 0.75rem;
		color: var(--cr-text-muted);
		margin: 0;
	}

	.error-text {
		font-size: 0.75rem;
		color: hsl(0 70% 55%);
		margin: 0;
	}

	.checkbox-label {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		cursor: pointer;
	}

	.checkbox {
		width: 1rem;
		height: 1rem;
		border-radius: 0.25rem;
		border: 1px solid var(--cr-border);
		background: var(--cr-bg);
		accent-color: var(--cr-accent);
	}

	.options-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.options-list {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.option-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.radio-label {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2rem;
		cursor: pointer;
	}

	.radio {
		width: 1rem;
		height: 1rem;
		accent-color: var(--cr-accent);
	}

	.actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
		padding-top: 1rem;
		border-top: 1px solid var(--cr-border);
	}
</style>
