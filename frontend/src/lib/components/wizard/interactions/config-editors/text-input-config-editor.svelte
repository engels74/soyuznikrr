<script lang="ts">
/**
 * Text Input Interaction Config Editor
 *
 * Provides admin UI for configuring text input interaction settings.
 */
import { Input } from "$lib/components/ui/input";
import { Label } from "$lib/components/ui/label";
import { Switch } from "$lib/components/ui/switch";
import { textInputConfigSchema } from "$lib/schemas/wizard";
import type { ConfigEditorProps } from "../registry";

const { config: rawConfig, onConfigChange, errors }: ConfigEditorProps = $props();

const config = $derived(textInputConfigSchema.safeParse(rawConfig).data);

function updateField(field: string, value: string | number | boolean | null) {
	onConfigChange({ ...rawConfig, [field]: value });
}
</script>

<div class="flex flex-col gap-4">
	<div class="flex flex-col gap-2">
		<Label for="input-label" class="text-cr-text">Input Label</Label>
		<Input
			id="input-label"
			value={config?.label ?? ''}
			oninput={(e) => updateField('label', e.currentTarget.value)}
			placeholder="Your response"
			class="border-cr-border bg-cr-bg text-cr-text"
		/>
		{#if errors.label}
			<p class="text-xs text-destructive">{errors.label[0]}</p>
		{/if}
	</div>

	<div class="flex flex-col gap-2">
		<Label for="input-placeholder" class="text-cr-text">Placeholder</Label>
		<Input
			id="input-placeholder"
			value={config?.placeholder ?? ''}
			oninput={(e) => updateField('placeholder', e.currentTarget.value)}
			placeholder="Enter placeholder text"
			class="border-cr-border bg-cr-bg text-cr-text"
		/>
	</div>

	<div class="grid grid-cols-2 gap-4">
		<div class="flex flex-col gap-2">
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
				<p class="text-xs text-destructive">{errors.min_length[0]}</p>
			{/if}
		</div>

		<div class="flex flex-col gap-2">
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
				<p class="text-xs text-destructive">{errors.max_length[0]}</p>
			{/if}
		</div>
	</div>

	<div class="flex items-center gap-2">
		<Switch
			checked={config?.required ?? true}
			onCheckedChange={(checked) => updateField('required', checked)}
		/>
		<Label class="text-cr-text cursor-pointer">Required field</Label>
	</div>
</div>
