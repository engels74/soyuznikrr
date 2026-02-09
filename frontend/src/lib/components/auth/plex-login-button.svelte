<script lang="ts">
import { loginPlex } from "$lib/api/auth";
import { Button } from "$lib/components/ui/button";

interface Props {
	onsuccess: () => void;
	onerror: (message: string) => void;
}

const { onsuccess, onerror }: Props = $props();

let loading = $state(false);

async function handlePlexLogin() {
	loading = true;
	try {
		// Create a Plex OAuth PIN via the backend
		const API_BASE_URL = import.meta.env.VITE_API_URL ?? "";
		const pinResponse = await fetch(
			`${API_BASE_URL}/api/v1/join/plex/oauth/pin`,
			{
				method: "POST",
				credentials: "include",
			},
		);

		if (!pinResponse.ok) {
			onerror("Failed to start Plex authentication");
			return;
		}

		const pinData = (await pinResponse.json()) as {
			pin_id: number;
			auth_url: string;
		};

		// Open Plex auth in a popup
		const popup = window.open(
			pinData.auth_url,
			"plex-auth",
			"width=800,height=600",
		);

		// Poll for completion
		const pollInterval = setInterval(async () => {
			try {
				const checkResponse = await fetch(
					`${API_BASE_URL}/api/v1/join/plex/oauth/pin/${pinData.pin_id}`,
					{ credentials: "include" },
				);

				if (!checkResponse.ok) return;

				const checkData = (await checkResponse.json()) as {
					authenticated: boolean;
					auth_token?: string;
				};

				if (checkData.authenticated && checkData.auth_token) {
					clearInterval(pollInterval);
					popup?.close();

					// Exchange Plex token for Zondarr session
					const result = await loginPlex(checkData.auth_token);
					if (result.error) {
						const err = result.error as { detail?: string };
						onerror(err.detail ?? "Plex login failed");
					} else {
						onsuccess();
					}
				}
			} catch {
				// Ignore polling errors
			}
		}, 2000);

		// Stop polling after 5 minutes
		setTimeout(() => {
			clearInterval(pollInterval);
			popup?.close();
			loading = false;
		}, 300_000);
	} catch {
		onerror("Failed to connect to Plex");
	} finally {
		loading = false;
	}
}
</script>

<Button
	onclick={handlePlexLogin}
	disabled={loading}
	variant="outline"
	class="w-full border-cr-border bg-cr-bg text-cr-text hover:bg-[#E5A00D]/10 hover:text-[#E5A00D] hover:border-[#E5A00D]/30"
>
	<svg class="mr-2 size-4" viewBox="0 0 24 24" fill="currentColor">
		<path d="M11.643 0H4.68l7.679 12-7.679 12h6.963L19.32 12z" />
	</svg>
	{#if loading}
		Connecting to Plex...
	{:else}
		Sign in with Plex
	{/if}
</Button>
