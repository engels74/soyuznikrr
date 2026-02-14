<script lang="ts">
/**
 * TOS Interaction Config Editor
 *
 * Provides admin UI for configuring Terms of Service interaction settings.
 */
import type { TosConfig } from "$lib/api/client";
import { Input } from "$lib/components/ui/input";
import { Label } from "$lib/components/ui/label";
import type { ConfigEditorProps } from "../registry";

const { config: rawConfig, onConfigChange, errors }: ConfigEditorProps = $props();

const config = $derived(rawConfig as unknown as TosConfig);

function updateField(value: string) {
	onConfigChange({ ...rawConfig, checkbox_label: value });
}
</script>

<div class="field">
	<Label for="checkbox-label" class="text-cr-text">Checkbox Label</Label>
	<Input
		id="checkbox-label"
		value={config?.checkbox_label ?? ''}
		oninput={(e) => updateField(e.currentTarget.value)}
		placeholder="I accept the terms of service"
		class="border-cr-border bg-cr-bg text-cr-text"
	/>
	{#if errors.checkbox_label}
		<p class="error-text">{errors.checkbox_label[0]}</p>
	{/if}
</div>

<style>
	.field {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.error-text {
		font-size: 0.75rem;
		color: var(--cr-error);
		margin: 0;
	}
</style>
