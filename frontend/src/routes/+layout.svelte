<script lang="ts">
import '../app.css';
import { ModeWatcher } from 'mode-watcher';
import type { Snippet } from 'svelte';
import favicon from '$lib/assets/favicon.svg';
import { Toaster } from '$lib/components/ui/sonner';

let { children }: { children: Snippet } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<ModeWatcher />
<Toaster richColors closeButton />

{@render children()}
