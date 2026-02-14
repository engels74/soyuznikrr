<script lang="ts">
/**
 * Timer Interaction Config Editor
 *
 * Provides admin UI for configuring timer interaction settings.
 */
import { Input } from "$lib/components/ui/input";
import { Label } from "$lib/components/ui/label";
import { timerConfigSchema } from "$lib/schemas/wizard";
import type { ConfigEditorProps } from "../registry";

const { config: rawConfig, onConfigChange, errors }: ConfigEditorProps = $props();

const config = $derived(timerConfigSchema.safeParse(rawConfig).data);

function updateDuration(value: string) {
	onConfigChange({ ...rawConfig, duration_seconds: parseInt(value, 10) || 10 });
}
</script>

<div class="flex flex-col gap-2">
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
	<p class="text-xs text-cr-text-muted">Minimum 1 second, maximum 300 seconds (5 minutes)</p>
	{#if errors.duration_seconds}
		<p class="text-xs text-destructive">{errors.duration_seconds[0]}</p>
	{/if}
</div>
