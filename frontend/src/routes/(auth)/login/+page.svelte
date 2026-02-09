<script lang="ts">
import { goto } from "$app/navigation";
import { loginLocal } from "$lib/api/auth";
import JellyfinLoginButton from "$lib/components/auth/jellyfin-login-button.svelte";
import LocalLoginForm from "$lib/components/auth/local-login-form.svelte";
import PlexLoginButton from "$lib/components/auth/plex-login-button.svelte";
import * as Card from "$lib/components/ui/card";
import { Separator } from "$lib/components/ui/separator";

const { data } = $props();

let error = $state("");

const hasPlex = $derived(data.methods.includes("plex"));
const hasJellyfin = $derived(data.methods.includes("jellyfin"));
const hasExternal = $derived(hasPlex || hasJellyfin);

async function handleLocalLogin(username: string, password: string) {
	error = "";
	const result = await loginLocal({ username, password });
	if (result.error) {
		const err = result.error as { detail?: string };
		error = err.detail ?? "Invalid credentials";
		return;
	}
	await goto("/dashboard");
}

function handleExternalSuccess() {
	goto("/dashboard");
}

function handleExternalError(message: string) {
	error = message;
}
</script>

<Card.Root class="border-cr-border bg-cr-surface">
	<Card.Header>
		<Card.Title class="text-center text-lg text-cr-text">Sign in to Zondarr</Card.Title>
		<Card.Description class="text-center text-cr-text-muted">
			Enter your credentials to continue
		</Card.Description>
	</Card.Header>
	<Card.Content class="flex flex-col gap-4">
		{#if error}
			<div class="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
				{error}
			</div>
		{/if}

		<LocalLoginForm onsubmit={handleLocalLogin} />

		{#if hasExternal}
			<div class="relative my-2">
				<Separator class="bg-cr-border" />
				<span
					class="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-cr-surface px-3 text-xs text-cr-text-dim"
				>
					or
				</span>
			</div>

			<div class="flex flex-col gap-2">
				{#if hasPlex}
					<PlexLoginButton
						onsuccess={handleExternalSuccess}
						onerror={handleExternalError}
					/>
				{/if}
				{#if hasJellyfin}
					<JellyfinLoginButton
						onsuccess={handleExternalSuccess}
						onerror={handleExternalError}
					/>
				{/if}
			</div>
		{/if}
	</Card.Content>
</Card.Root>
