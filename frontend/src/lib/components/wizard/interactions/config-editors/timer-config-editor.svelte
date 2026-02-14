<script lang="ts">
/**
 * Timer Interaction Config Editor
 *
 * Provides admin UI for configuring timer interaction settings.
 */
import type { TimerConfig } from "$lib/api/client";
import { Input } from "$lib/components/ui/input";
import { Label } from "$lib/components/ui/label";
import type { ConfigEditorProps } from "../registry";

const { config: rawConfig, onConfigChange, errors }: ConfigEditorProps = $props();

const config = $derived(rawConfig as unknown as TimerConfig);

function updateDuration(value: string) {
	onConfigChange({ ...rawConfig, duration_seconds: parseInt(value, 10) || 10 });
}
</script>

<div class="field">
	<Label for="duration" class="text-cr-text">Duration (seconds)</Label>
	<Input
		id="duration"
		type="number"
		min="1"
		max="300"
		value={config?.duration_seconds ?? 10}
		oninput={(e) => updateDuration(e.currentTarget.value)}
		class="border-cr-border bg-cr-bg text-cr-text"
	/>
	<p class="help-text">Minimum 1 second, maximum 300 seconds (5 minutes)</p>
	{#if errors.duration_seconds}
		<p class="error-text">{errors.duration_seconds[0]}</p>
	{/if}
</div>

<style>
	.field {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
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
