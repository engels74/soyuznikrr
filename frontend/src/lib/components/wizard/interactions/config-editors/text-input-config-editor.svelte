<script lang="ts">
/**
 * Text Input Interaction Config Editor
 *
 * Provides admin UI for configuring text input interaction settings.
 */
import type { TextInputConfig } from "$lib/api/client";
import { Input } from "$lib/components/ui/input";
import { Label } from "$lib/components/ui/label";
import type { ConfigEditorProps } from "../registry";

const { config: rawConfig, onConfigChange, errors }: ConfigEditorProps = $props();

const config = $derived(rawConfig as unknown as TextInputConfig);

function updateField(field: string, value: string | number | boolean | null) {
	onConfigChange({ ...rawConfig, [field]: value });
}
</script>

<div class="fields">
	<div class="field">
		<Label for="input-label" class="text-cr-text">Input Label</Label>
		<Input
			id="input-label"
			value={config?.label ?? ''}
			oninput={(e) => updateField('label', e.currentTarget.value)}
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
			value={config?.placeholder ?? ''}
			oninput={(e) => updateField('placeholder', e.currentTarget.value)}
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
				value={config?.min_length ?? ''}
				oninput={(e) =>
					updateField('min_length', e.currentTarget.value ? parseInt(e.currentTarget.value) : null)}
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
				value={config?.max_length ?? ''}
				oninput={(e) =>
					updateField('max_length', e.currentTarget.value ? parseInt(e.currentTarget.value) : null)}
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
				checked={config?.required ?? true}
				onchange={(e) => updateField('required', e.currentTarget.checked)}
				class="checkbox"
			/>
			<span class="text-cr-text">Required field</span>
		</label>
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
	.field-row {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1rem;
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
	.error-text {
		font-size: 0.75rem;
		color: var(--cr-error);
		margin: 0;
	}
</style>
