<script lang="ts">
import "virtual:uno.css";
import "../app.css";
import { ModeWatcher } from "mode-watcher";
import type { Snippet } from "svelte";
import favicon from "$lib/assets/favicon.svg";
import { Toaster } from "$lib/components/ui/sonner";
import { setProviders } from "$lib/stores/providers.svelte";
import type { LayoutData } from "./$types";

const { data, children }: { data: LayoutData; children: Snippet } = $props();

$effect(() => {
	if (data.providers.length > 0) {
		setProviders(data.providers);
	}
});
</script>

<svelte:head>
	<link rel="icon" type="image/svg+xml" href={favicon} />
</svelte:head>

<ModeWatcher />
<Toaster richColors closeButton />

{@render children()}
