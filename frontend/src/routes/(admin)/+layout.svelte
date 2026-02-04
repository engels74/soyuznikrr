<script lang="ts">
import { LayoutDashboard, Menu, Server, Ticket, Users, Wand2, X } from '@lucide/svelte';
import type { Snippet } from 'svelte';
import { page } from '$app/state';
import NavItem from '$lib/components/nav-item.svelte';
import PageTitle from '$lib/components/page-title.svelte';
import ThemeToggle from '$lib/components/theme-toggle.svelte';
import { Button } from '$lib/components/ui/button';
import { Separator } from '$lib/components/ui/separator';

interface Props {
	children: Snippet;
}

let { children }: Props = $props();

// Mobile menu state
let mobileMenuOpen = $state(false);

// Derive current section title from route
let currentTitle = $derived.by(() => {
	const pathname = page.url.pathname;
	if (pathname.startsWith('/dashboard')) return 'Dashboard';
	if (pathname.startsWith('/invitations')) return 'Invitations';
	if (pathname.startsWith('/users')) return 'Users';
	if (pathname.startsWith('/servers')) return 'Servers';
	if (pathname.startsWith('/wizards')) return 'Wizards';
	return 'Admin';
});

// Navigation items configuration
const navItems = [
	{ href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
	{ href: '/invitations', label: 'Invitations', icon: Ticket },
	{ href: '/users', label: 'Users', icon: Users },
	{ href: '/servers', label: 'Servers', icon: Server },
	{ href: '/wizards', label: 'Wizards', icon: Wand2 }
] as const;

// Close mobile menu when route changes
$effect(() => {
	page.url.pathname;
	mobileMenuOpen = false;
});
</script>

<div class="min-h-screen bg-cr-bg">
	<!-- Mobile Header -->
	<header class="sticky top-0 z-50 flex h-14 items-center justify-between border-b border-cr-border bg-cr-bg px-4 md:hidden">
		<Button
			variant="ghost"
			size="icon"
			onclick={() => (mobileMenuOpen = !mobileMenuOpen)}
			aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
			aria-expanded={mobileMenuOpen}
			class="text-cr-text-muted hover:text-cr-accent"
		>
			{#if mobileMenuOpen}
				<X class="size-5" />
			{:else}
				<Menu class="size-5" />
			{/if}
		</Button>
		<PageTitle>{currentTitle}</PageTitle>
		<ThemeToggle />
	</header>

	<!-- Mobile Navigation Overlay -->
	{#if mobileMenuOpen}
		<div
			class="fixed inset-0 z-40 bg-black/50 md:hidden"
			onclick={() => (mobileMenuOpen = false)}
			onkeydown={(e) => e.key === 'Escape' && (mobileMenuOpen = false)}
			role="button"
			tabindex="-1"
			aria-label="Close menu"
		></div>
	{/if}

	<!-- Mobile Sidebar -->
	<aside
		class={[
			'fixed inset-y-0 left-0 z-50 w-64 transform bg-cr-bg border-r border-cr-border transition-transform duration-200 ease-in-out md:hidden',
			mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
		].join(' ')}
	>
		<div class="flex h-14 items-center px-4">
			<span class="font-display text-lg font-bold text-cr-accent">Zondarr</span>
		</div>
		<Separator class="bg-cr-border" />
		<nav class="flex flex-col gap-1 p-4" aria-label="Main navigation">
			{#each navItems as item}
				<NavItem href={item.href}>
					{#snippet icon()}
						<item.icon class="size-5" />
					{/snippet}
					{item.label}
				</NavItem>
			{/each}
		</nav>
	</aside>

	<div class="flex">
		<!-- Desktop Sidebar -->
		<aside class="hidden md:flex md:w-64 md:flex-col md:fixed md:inset-y-0 border-r border-cr-border bg-cr-bg">
			<div class="flex h-14 items-center px-4">
				<span class="font-display text-lg font-bold text-cr-accent">Zondarr</span>
			</div>
			<Separator class="bg-cr-border" />
			<nav class="flex flex-1 flex-col gap-1 p-4" aria-label="Main navigation">
				{#each navItems as item}
					<NavItem href={item.href}>
						{#snippet icon()}
							<item.icon class="size-5" />
						{/snippet}
						{item.label}
					</NavItem>
				{/each}
			</nav>
		</aside>

		<!-- Main Content Area -->
		<div class="flex-1 md:ml-64">
			<!-- Desktop Header -->
			<header class="sticky top-0 z-30 hidden h-14 items-center justify-between border-b border-cr-border bg-cr-bg px-6 md:flex">
				<PageTitle>{currentTitle}</PageTitle>
				<ThemeToggle />
			</header>

			<!-- Page Content -->
			<main class="p-4 md:p-6">
				{@render children()}
			</main>
		</div>
	</div>
</div>
