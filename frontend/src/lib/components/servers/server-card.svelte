<script lang="ts">
/**
 * Server card component.
 *
 * Displays a media server as a card with:
 * - Server name and type badge
 * - URL
 * - Enabled status
 * - Library count
 *
 * @module $lib/components/servers/server-card
 */

import { Database, ExternalLink, Server } from "@lucide/svelte";
import type { MediaServerWithLibrariesResponse } from "$lib/api/client";
import StatusBadge from "$lib/components/status-badge.svelte";
import { Button } from "$lib/components/ui/button";
import * as Card from "$lib/components/ui/card";

interface Props {
	server: MediaServerWithLibrariesResponse;
	onViewDetails: (id: string) => void;
}

const { server, onViewDetails }: Props = $props();

/**
 * Get server type badge class based on server type.
 */
const serverTypeClass = $derived.by(() => {
	return server.server_type === "plex"
		? "bg-amber-500/15 text-amber-400 border-amber-500/30"
		: "bg-purple-500/15 text-purple-400 border-purple-500/30";
});

/**
 * Get server type display name.
 */
const serverTypeLabel = $derived(
	server.server_type === "plex" ? "Plex" : "Jellyfin",
);

/**
 * Get library count text.
 */
const libraryCountText = $derived.by(() => {
	const count = server.libraries.length;
	return count === 1 ? "1 library" : `${count} libraries`;
});
</script>

<Card.Root
	class="border-cr-border bg-cr-surface transition-colors hover:border-cr-accent/30"
	data-server-card
	data-server-id={server.id}
>
	<Card.Header class="pb-3">
		<div class="flex items-start justify-between gap-3">
			<div class="flex items-center gap-3">
				<div class="rounded-lg bg-cr-accent/10 p-2">
					<Server class="size-5 text-cr-accent" />
				</div>
				<div>
					<Card.Title class="text-cr-text text-lg" data-field="name">{server.name}</Card.Title>
					<div class="flex items-center gap-2 mt-1">
						<span
							class="inline-flex items-center rounded border px-1.5 py-0.5 text-xs font-medium {serverTypeClass}"
							data-field="server_type"
						>
							{serverTypeLabel}
						</span>
					</div>
				</div>
			</div>
			<span data-field="enabled">
				<StatusBadge
					status={server.enabled ? 'active' : 'disabled'}
					label={server.enabled ? 'Enabled' : 'Disabled'}
				/>
			</span>
		</div>
	</Card.Header>
	<Card.Content class="space-y-4">
		<!-- URL -->
		<div class="flex items-center gap-2 text-sm">
			<ExternalLink class="size-4 text-cr-text-muted flex-shrink-0" />
			<span class="font-mono text-cr-text-muted truncate" data-field="url">{server.url}</span>
		</div>

		<!-- Library count -->
		<div class="flex items-center gap-2 text-sm">
			<Database class="size-4 text-cr-text-muted flex-shrink-0" />
			<span class="text-cr-text" data-field="library_count">{libraryCountText}</span>
		</div>
	</Card.Content>
	<Card.Footer class="pt-3 border-t border-cr-border">
		<Button
			variant="outline"
			size="sm"
			onclick={() => onViewDetails(server.id)}
			class="w-full border-cr-border text-cr-text hover:bg-cr-border"
		>
			View Details
		</Button>
	</Card.Footer>
</Card.Root>
