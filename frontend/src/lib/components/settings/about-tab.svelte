<script lang="ts">
import { Info } from '@lucide/svelte';
import type { AboutResponse } from '$lib/api/client';
import * as Card from '$lib/components/ui/card';

interface Props {
	about: AboutResponse;
}

let { about }: Props = $props();
</script>

<div class="space-y-6">
	<Card.Root>
		<Card.Header>
			<div class="flex items-center gap-2">
				<Info class="size-5 text-cr-accent" />
				<Card.Title>System Information</Card.Title>
			</div>
			<Card.Description>Read-only information about your Zondarr instance.</Card.Description>
		</Card.Header>
		<Card.Content>
			<dl class="grid grid-cols-[auto_1fr] gap-x-6 gap-y-3 text-sm">
				<dt class="text-muted-foreground font-medium">App Version</dt>
				<dd class="font-mono">{about.app_version}</dd>

				<dt class="text-muted-foreground font-medium">Python Version</dt>
				<dd class="font-mono">{about.python_version}</dd>

				<dt class="text-muted-foreground font-medium">Database Engine</dt>
				<dd class="font-mono">{about.db_engine}</dd>

				<dt class="text-muted-foreground font-medium">Operating System</dt>
				<dd class="font-mono">{about.os_info}</dd>
			</dl>
		</Card.Content>
	</Card.Root>
</div>
