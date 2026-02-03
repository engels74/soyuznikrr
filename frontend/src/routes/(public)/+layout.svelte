<script lang="ts">
/**
 * Public route group layout.
 *
 * Provides a minimal layout for public-facing pages like the join flow.
 * Includes dark mode support via ModeWatcher from the root layout.
 *
 * @module routes/(public)/+layout
 */

import type { Snippet } from 'svelte';
import ThemeToggle from '$lib/components/theme-toggle.svelte';

interface Props {
	children: Snippet;
}

let { children }: Props = $props();
</script>

<div class="min-h-screen bg-cr-bg">
	<!-- Minimal header with branding and theme toggle -->
	<header class="sticky top-0 z-50 flex h-14 items-center justify-between border-b border-cr-border bg-cr-bg px-4 md:px-6">
		<a href="/" class="font-display text-lg font-bold text-cr-accent">
			Zondarr
		</a>
		<ThemeToggle />
	</header>

	<!-- Main content area -->
	<main class="flex flex-col items-center justify-center px-4 py-8 md:py-12">
		<div class="w-full max-w-lg">
			{@render children()}
		</div>
	</main>

	<!-- Minimal footer -->
	<footer class="border-t border-cr-border bg-cr-bg px-4 py-4 text-center text-sm text-cr-text-muted">
		<p>Powered by Zondarr</p>
	</footer>
</div>
