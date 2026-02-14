<script lang="ts">
/**
 * Click Interaction Config Editor
 *
 * Provides admin UI for configuring click interaction settings.
 */
import type { ClickConfig } from "$lib/api/client";
import { Input } from "$lib/components/ui/input";
import { Label } from "$lib/components/ui/label";
import type { ConfigEditorProps } from "../registry";

const { config: rawConfig, onConfigChange, errors }: ConfigEditorProps = $props();

const config = $derived(rawConfig as unknown as ClickConfig);

function updateField(value: string) {
	onConfigChange({ ...rawConfig, button_text: value });
}
</script>

<div class="field">
	<Label for="button-text" class="text-cr-text">Button Text</Label>
	<Input
		id="button-text"
		value={config?.button_text ?? ''}
		oninput={(e) => updateField(e.currentTarget.value)}
		placeholder="I Understand"
		class="border-cr-border bg-cr-bg text-cr-text"
	/>
	{#if errors.button_text}
		<p class="error-text">{errors.button_text[0]}</p>
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
