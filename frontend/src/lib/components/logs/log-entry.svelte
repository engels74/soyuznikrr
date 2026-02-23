<script lang="ts">
/**
 * Single log entry row.
 *
 * Click-to-expand for entries with fields. Color-coded left border by level.
 * Uses content-visibility for browser-native virtualization.
 */

import { ChevronRight } from "@lucide/svelte";
import type { LogEntry } from "$lib/stores/log-stream.svelte";

interface Props {
	entry: LogEntry;
}

const { entry }: Props = $props();

const hasFields = $derived(Object.keys(entry.fields).length > 0);
let expanded = $state(false);

const levelColors: Record<string, string> = {
	DEBUG: "text-muted-foreground",
	INFO: "text-blue-500 dark:text-blue-400",
	WARNING: "text-amber-500 dark:text-amber-400",
	ERROR: "text-red-500 dark:text-red-400",
	CRITICAL: "text-red-600 dark:text-red-400 bg-red-500/10",
};

const borderColors: Record<string, string> = {
	ERROR: "border-l-red-500",
	CRITICAL: "border-l-red-500",
	WARNING: "border-l-amber-500",
};

const levelClass = $derived(levelColors[entry.level] ?? "text-muted-foreground");
const borderClass = $derived(borderColors[entry.level] ?? "border-l-transparent");

const formattedTime = $derived.by(() => {
	if (!entry.timestamp) return "";
	try {
		const d = new Date(entry.timestamp);
		return d.toLocaleTimeString("en-GB", { hour12: false, fractionalSecondDigits: 3 });
	} catch {
		return entry.timestamp;
	}
});

function toggle() {
	if (hasFields) expanded = !expanded;
}
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="border-l-2 {borderClass} {hasFields ? 'cursor-pointer hover:bg-cr-surface/50' : ''}"
	style="content-visibility: auto; contain-intrinsic-size: auto {expanded ? 'auto' : '28px'};"
	onclick={toggle}
>
	<div class="flex h-7 items-center gap-2 px-2 font-mono text-xs leading-7">
		{#if hasFields}
			<ChevronRight class="size-3 shrink-0 text-muted-foreground transition-transform {expanded ? 'rotate-90' : ''}" />
		{:else}
			<span class="inline-block w-3 shrink-0"></span>
		{/if}
		<span class="shrink-0 text-muted-foreground">{formattedTime}</span>
		<span class="w-14 shrink-0 text-center font-semibold {levelClass}">
			{entry.level}
		</span>
		<span class="max-w-36 shrink-0 truncate text-muted-foreground" title={entry.logger_name}>
			{entry.logger_name}
		</span>
		<span class="min-w-0 truncate" title={entry.message}>
			{entry.message}
		</span>
	</div>

	{#if expanded && hasFields}
		<div class="border-t border-cr-border/50 bg-cr-surface/30 px-4 py-2 pl-7 font-mono text-xs">
			{#each Object.entries(entry.fields) as [key, value] (key)}
				<div class="flex gap-2 py-0.5">
					<span class="shrink-0 font-semibold text-muted-foreground">{key}:</span>
					<span class="min-w-0 break-all">{value}</span>
				</div>
			{/each}
		</div>
	{/if}
</div>
