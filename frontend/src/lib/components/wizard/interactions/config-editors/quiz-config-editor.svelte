<script lang="ts">
/**
 * Quiz Interaction Config Editor
 *
 * Provides admin UI for configuring quiz interaction settings.
 */
import type { QuizConfig } from "$lib/api/client";
import { Button } from "$lib/components/ui/button";
import { Input } from "$lib/components/ui/input";
import { Label } from "$lib/components/ui/label";
import type { ConfigEditorProps } from "../registry";

const { config: rawConfig, onConfigChange, errors }: ConfigEditorProps = $props();

const config = $derived(rawConfig as unknown as QuizConfig);

function updateField(field: string, value: unknown) {
	onConfigChange({ ...rawConfig, [field]: value });
}

function addOption() {
	const options = (rawConfig.options as string[]) ?? [];
	onConfigChange({ ...rawConfig, options: [...options, ''] });
}

function removeOption(index: number) {
	const options = (rawConfig.options as string[]) ?? [];
	const newOptions = options.filter((_, i) => i !== index);
	let correctIndex = (rawConfig.correct_answer_index as number) ?? 0;
	if (correctIndex >= newOptions.length) {
		correctIndex = Math.max(0, newOptions.length - 1);
	}
	onConfigChange({ ...rawConfig, options: newOptions, correct_answer_index: correctIndex });
}

function updateOption(index: number, value: string) {
	const options = [...((rawConfig.options as string[]) ?? [])];
	options[index] = value;
	onConfigChange({ ...rawConfig, options });
}
</script>

<div class="fields">
	<div class="field">
		<Label for="question" class="text-cr-text">Question</Label>
		<Input
			id="question"
			value={config?.question ?? ''}
			oninput={(e) => updateField('question', e.currentTarget.value)}
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
				onclick={addOption}
				disabled={(config?.options?.length ?? 0) >= 10}
				class="border-cr-border text-cr-text-muted"
			>
				Add Option
			</Button>
		</div>

		<div class="options-list">
			{#each config?.options ?? [] as option, index}
				<div class="option-row">
					<label class="radio-label">
						<input
							type="radio"
							name="correct-answer"
							checked={(config?.correct_answer_index ?? 0) === index}
							onchange={() => updateField('correct_answer_index', index)}
							class="radio"
						/>
					</label>
					<Input
						value={option}
						oninput={(e) => updateOption(index, e.currentTarget.value)}
						placeholder={`Option ${index + 1}`}
						class="flex-1 border-cr-border bg-cr-bg text-cr-text"
					/>
					<Button
						variant="ghost"
						size="sm"
						onclick={() => removeOption(index)}
						disabled={(config?.options?.length ?? 0) <= 2}
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
</div>

<style>
	.fields {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}
	.field {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
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
	.help-text {
		font-size: 0.75rem;
		color: var(--cr-text-muted);
		margin: 0;
	}
	.error-text {
		font-size: 0.75rem;
		color: var(--cr-error);
		margin: 0;
	}
</style>
