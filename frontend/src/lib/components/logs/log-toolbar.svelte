<script lang="ts">
/**
 * Log viewer toolbar with filter controls.
 *
 * Provides level dropdown, source filter, search input, clear button,
 * pause/resume button, and entry count badge.
 */

import { Eraser, Pause, Play, Search } from "@lucide/svelte";
import { Badge } from "$lib/components/ui/badge";
import { Button } from "$lib/components/ui/button";
import { Input } from "$lib/components/ui/input";
import * as Select from "$lib/components/ui/select";

interface Props {
	levelFilter: string;
	sourceFilter: string;
	searchQuery: string;
	entryCount: number;
	totalCount: number;
	connected: boolean;
	loading: boolean;
	paused: boolean;
	error: string | null;
	onLevelChange: (value: string) => void;
	onSourceChange: (value: string) => void;
	onSearchChange: (value: string) => void;
	onClear: () => void;
	onTogglePause: () => void;
}

const {
	levelFilter,
	sourceFilter,
	searchQuery,
	entryCount,
	totalCount,
	connected,
	loading,
	paused,
	error,
	onLevelChange,
	onSourceChange,
	onSearchChange,
	onClear,
	onTogglePause,
}: Props = $props();

const levelOptions = [
	{ value: "ALL", label: "All Levels" },
	{ value: "DEBUG", label: "Debug" },
	{ value: "INFO", label: "Info" },
	{ value: "WARNING", label: "Warning" },
	{ value: "ERROR", label: "Error" },
	{ value: "CRITICAL", label: "Critical" },
];

const selectedLabel = $derived(
	levelOptions.find((o) => o.value === levelFilter)?.label ?? "All Levels"
);

const hasActiveFilters = $derived(
	levelFilter !== "ALL" || sourceFilter !== "" || searchQuery !== ""
);
</script>

<div class="flex flex-wrap items-center gap-2">
	<!-- Connection status -->
	<div class="flex items-center gap-1.5" title={error ?? (connected ? "Connected" : loading ? "Connecting..." : "Disconnected")}>
		{#if loading}
			<span class="inline-block size-2 animate-pulse rounded-full bg-amber-500"></span>
			<span class="text-xs text-muted-foreground">Connecting</span>
		{:else}
			<span
				class="inline-block size-2 rounded-full {connected
					? 'bg-green-500'
					: 'bg-red-500'}"
			></span>
			<span class="text-xs text-muted-foreground">
				{connected ? "Live" : "Disconnected"}
			</span>
		{/if}
	</div>

	<!-- Pause/Resume -->
	<Button
		variant={paused ? "default" : "outline"}
		size="icon-sm"
		onclick={onTogglePause}
		title={paused ? "Resume" : "Pause"}
	>
		{#if paused}
			<Play class="size-3.5" />
		{:else}
			<Pause class="size-3.5" />
		{/if}
	</Button>

	<!-- Level filter -->
	<Select.Root
		type="single"
		value={levelFilter}
		onValueChange={(v) => { if (v) onLevelChange(v); }}
	>
		<Select.Trigger size="sm" class="w-32">
			{selectedLabel}
		</Select.Trigger>
		<Select.Content>
			{#each levelOptions as opt (opt.value)}
				<Select.Item value={opt.value}>{opt.label}</Select.Item>
			{/each}
		</Select.Content>
	</Select.Root>

	<!-- Source filter -->
	<Input
		placeholder="Filter source..."
		value={sourceFilter}
		oninput={(e) => onSourceChange(e.currentTarget.value)}
		class="h-8 w-40 text-xs"
	/>

	<!-- Search -->
	<div class="relative">
		<Search class="absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
		<Input
			placeholder="Search messages..."
			value={searchQuery}
			oninput={(e) => onSearchChange(e.currentTarget.value)}
			class="h-8 w-48 pl-7 text-xs"
		/>
	</div>

	<!-- Clear button -->
	<Button variant="outline" size="sm" onclick={onClear} class="h-8 gap-1 text-xs">
		<Eraser class="size-3.5" />
		Clear
	</Button>

	<!-- Entry count -->
	<Badge variant="secondary" class="ml-auto text-xs">
		{#if hasActiveFilters}
			{entryCount.toLocaleString()} / {totalCount.toLocaleString()}
		{:else}
			{entryCount.toLocaleString()} entries
		{/if}
	</Badge>
</div>
