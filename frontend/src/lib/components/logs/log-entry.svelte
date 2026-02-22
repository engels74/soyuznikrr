<script lang="ts">
/**
 * Single log entry row.
 *
 * Fixed height for consistent layout with browser-native virtualization
 * via content-visibility. Color-coded by log level.
 */

import type { LogEntry } from "$lib/stores/log-stream.svelte";

interface Props {
	entry: LogEntry;
}

const { entry }: Props = $props();

const levelColors: Record<string, string> = {
	DEBUG: "text-muted-foreground",
	INFO: "text-blue-500 dark:text-blue-400",
	WARNING: "text-amber-500 dark:text-amber-400",
	ERROR: "text-red-500 dark:text-red-400",
	CRITICAL: "text-red-600 dark:text-red-400 bg-red-500/10",
};

const levelClass = $derived(levelColors[entry.level] ?? "text-muted-foreground");

const formattedTime = $derived.by(() => {
	if (!entry.timestamp) return "";
	try {
		const d = new Date(entry.timestamp);
		return d.toLocaleTimeString("en-GB", { hour12: false, fractionalSecondDigits: 3 });
	} catch {
		return entry.timestamp;
	}
});

const fieldsText = $derived.by(() => {
	const keys = Object.keys(entry.fields);
	if (keys.length === 0) return "";
	return keys.map((k) => `${k}=${entry.fields[k]}`).join(" ");
});
</script>

<div
	class="flex h-7 items-center gap-2 px-2 font-mono text-xs leading-7"
	style="content-visibility: auto; contain-intrinsic-size: 0 28px;"
>
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
	{#if fieldsText}
		<span class="min-w-0 shrink truncate text-muted-foreground" title={fieldsText}>
			{fieldsText}
		</span>
	{/if}
</div>
