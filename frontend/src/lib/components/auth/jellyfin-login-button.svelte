<script lang="ts">
import { ChevronDown, ChevronUp } from "@lucide/svelte";
import { loginJellyfin } from "$lib/api/auth";
import { Button } from "$lib/components/ui/button";
import { Input } from "$lib/components/ui/input";
import { Label } from "$lib/components/ui/label";
import { jellyfinLoginSchema } from "$lib/schemas/auth";

interface Props {
	onsuccess: () => void;
	onerror: (message: string) => void;
}

const { onsuccess, onerror }: Props = $props();

let expanded = $state(false);
let serverUrl = $state("");
let username = $state("");
let password = $state("");
let errors = $state<Record<string, string>>({});
let loading = $state(false);

async function handleSubmit(e: SubmitEvent) {
	e.preventDefault();
	errors = {};

	const result = jellyfinLoginSchema.safeParse({
		server_url: serverUrl,
		username,
		password,
	});

	if (!result.success) {
		for (const issue of result.error.issues) {
			const field = issue.path[0];
			if (field && typeof field === "string") {
				errors[field] = issue.message;
			}
		}
		return;
	}

	loading = true;
	try {
		const response = await loginJellyfin(result.data);
		if (response.error) {
			const err = response.error as { detail?: string };
			onerror(err.detail ?? "Jellyfin login failed");
		} else {
			onsuccess();
		}
	} finally {
		loading = false;
	}
}
</script>

{#if !expanded}
	<Button
		onclick={() => (expanded = true)}
		variant="outline"
		class="w-full border-cr-border bg-cr-bg text-cr-text hover:bg-[#00A4DC]/10 hover:text-[#00A4DC] hover:border-[#00A4DC]/30"
	>
		<svg class="mr-2 size-4" viewBox="0 0 24 24" fill="currentColor">
			<path
				d="M12 .002C5.375.002 0 5.377 0 12.002c0 6.624 5.375 12 12 12s12-5.376 12-12c0-6.625-5.375-12-12-12zm0 2.5a9.5 9.5 0 0 1 9.5 9.5 9.5 9.5 0 0 1-9.5 9.5 9.5 9.5 0 0 1-9.5-9.5 9.5 9.5 0 0 1 9.5-9.5z"
			/>
		</svg>
		Sign in with Jellyfin
		<ChevronDown class="ml-auto size-4" />
	</Button>
{:else}
	<div class="rounded-md border border-cr-border bg-cr-bg p-3">
		<button
			type="button"
			onclick={() => (expanded = false)}
			class="mb-3 flex w-full items-center gap-2 text-sm font-medium text-cr-text"
		>
			<svg class="size-4" viewBox="0 0 24 24" fill="currentColor">
				<path
					d="M12 .002C5.375.002 0 5.377 0 12.002c0 6.624 5.375 12 12 12s12-5.376 12-12c0-6.625-5.375-12-12-12zm0 2.5a9.5 9.5 0 0 1 9.5 9.5 9.5 9.5 0 0 1-9.5 9.5 9.5 9.5 0 0 1-9.5-9.5 9.5 9.5 0 0 1 9.5-9.5z"
				/>
			</svg>
			Jellyfin login
			<ChevronUp class="ml-auto size-4 text-cr-text-muted" />
		</button>

		<form onsubmit={handleSubmit} class="flex flex-col gap-3">
			<div class="flex flex-col gap-1">
				<Label for="jf-server" class="text-xs text-cr-text">Server URL</Label>
				<Input
					id="jf-server"
					type="url"
					bind:value={serverUrl}
					placeholder="https://jellyfin.example.com"
					class="h-8 border-cr-border bg-cr-surface text-cr-text text-sm placeholder:text-cr-text-dim"
				/>
				{#if errors.server_url}
					<p class="text-xs text-red-400">{errors.server_url}</p>
				{/if}
			</div>

			<div class="flex flex-col gap-1">
				<Label for="jf-username" class="text-xs text-cr-text">Username</Label>
				<Input
					id="jf-username"
					type="text"
					bind:value={username}
					placeholder="Admin username"
					autocomplete="username"
					class="h-8 border-cr-border bg-cr-surface text-cr-text text-sm placeholder:text-cr-text-dim"
				/>
				{#if errors.username}
					<p class="text-xs text-red-400">{errors.username}</p>
				{/if}
			</div>

			<div class="flex flex-col gap-1">
				<Label for="jf-password" class="text-xs text-cr-text">Password</Label>
				<Input
					id="jf-password"
					type="password"
					bind:value={password}
					placeholder="Password"
					autocomplete="current-password"
					class="h-8 border-cr-border bg-cr-surface text-cr-text text-sm placeholder:text-cr-text-dim"
				/>
				{#if errors.password}
					<p class="text-xs text-red-400">{errors.password}</p>
				{/if}
			</div>

			<Button
				type="submit"
				disabled={loading}
				size="sm"
				class="w-full bg-[#00A4DC] text-white hover:bg-[#0088b8]"
			>
				{#if loading}
					Connecting...
				{:else}
					Sign in
				{/if}
			</Button>
		</form>
	</div>
{/if}
