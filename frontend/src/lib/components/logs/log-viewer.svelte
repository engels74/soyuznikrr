<script lang="ts">
/**
 * Main log viewer container.
 *
 * Manages SSE lifecycle, filtering, and auto-scroll behavior.
 * Connects on mount, disconnects on cleanup.
 */

import { ArrowDown } from "@lucide/svelte";
import { Button } from "$lib/components/ui/button";
import {
	clearEntries,
	connect,
	disconnect,
	getConnected,
	getEntries,
	getError,
	LEVEL_ORDER,
	type LogLevel,
} from "$lib/stores/log-stream.svelte";
import LogEntryRow from "./log-entry.svelte";
import LogToolbar from "./log-toolbar.svelte";

// Filter state
let levelFilter = $state("ALL");
let sourceFilter = $state("");
let searchQuery = $state("");

// Auto-scroll state
let autoScroll = $state(true);
let scrollContainer: HTMLDivElement | undefined = $state();

// Reactive getters
const entries = $derived(getEntries());
const connected = $derived(getConnected());
const error = $derived(getError());

// Filtered entries
const filteredEntries = $derived.by(() => {
	let result = entries;

	if (levelFilter !== "ALL") {
		const minLevel = LEVEL_ORDER[levelFilter as LogLevel] ?? 0;
		result = result.filter((e) => (LEVEL_ORDER[e.level] ?? 0) >= minLevel);
	}

	if (sourceFilter) {
		const src = sourceFilter.toLowerCase();
		result = result.filter((e) => e.logger_name.toLowerCase().includes(src));
	}

	if (searchQuery) {
		const q = searchQuery.toLowerCase();
		result = result.filter(
			(e) =>
				e.message.toLowerCase().includes(q) ||
				e.logger_name.toLowerCase().includes(q) ||
				Object.values(e.fields).some((v) => v.toLowerCase().includes(q)),
		);
	}

	return result;
});

// Auto-scroll when new entries arrive
$effect(() => {
	// Track dependency on filtered entries length
	filteredEntries.length;

	if (autoScroll && scrollContainer) {
		// Use requestAnimationFrame to scroll after DOM updates
		requestAnimationFrame(() => {
			if (scrollContainer) {
				scrollContainer.scrollTop = scrollContainer.scrollHeight;
			}
		});
	}
});

// Connect on mount, disconnect on cleanup
$effect(() => {
	connect();
	return () => disconnect();
});

function handleScroll() {
	if (!scrollContainer) return;
	const { scrollTop, scrollHeight, clientHeight } = scrollContainer;
	// Consider "at bottom" if within 50px of the end
	autoScroll = scrollHeight - scrollTop - clientHeight < 50;
}

function jumpToLatest() {
	if (scrollContainer) {
		scrollContainer.scrollTop = scrollContainer.scrollHeight;
		autoScroll = true;
	}
}
</script>

<div class="flex flex-col gap-3">
	<LogToolbar
		{levelFilter}
		{sourceFilter}
		{searchQuery}
		entryCount={filteredEntries.length}
		{connected}
		{error}
		onLevelChange={(v) => (levelFilter = v)}
		onSourceChange={(v) => (sourceFilter = v)}
		onSearchChange={(v) => (searchQuery = v)}
		onClear={clearEntries}
	/>

	<!-- Scroll container -->
	<div class="relative">
		<div
			bind:this={scrollContainer}
			onscroll={handleScroll}
			class="h-[calc(100vh-13rem)] overflow-y-auto rounded-md border border-cr-border bg-cr-bg-card"
		>
			{#if filteredEntries.length === 0}
				<div class="flex h-full items-center justify-center text-sm text-muted-foreground">
					{#if entries.length === 0}
						Waiting for log entries...
					{:else}
						No entries match the current filters.
					{/if}
				</div>
			{:else}
				{#each filteredEntries as entry (entry.seq)}
					<LogEntryRow {entry} />
				{/each}
			{/if}
		</div>

		<!-- Jump to latest button -->
		{#if !autoScroll}
			<div class="absolute bottom-3 left-1/2 -translate-x-1/2">
				<Button
					variant="secondary"
					size="sm"
					onclick={jumpToLatest}
					class="gap-1.5 shadow-md"
				>
					<ArrowDown class="size-3.5" />
					Jump to latest
				</Button>
			</div>
		{/if}
	</div>
</div>
