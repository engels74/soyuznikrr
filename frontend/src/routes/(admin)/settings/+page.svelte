<script lang="ts">
import AboutTab from '$lib/components/settings/about-tab.svelte';
import AccountTab from '$lib/components/settings/account-tab.svelte';
import GeneralTab from '$lib/components/settings/general-tab.svelte';
import SyncTab from '$lib/components/settings/sync-tab.svelte';
import * as Tabs from '$lib/components/ui/tabs';

interface Props {
	data: {
		settings: import('$lib/api/client').AllSettingsResponse | null;
		about: import('$lib/api/client').AboutResponse | null;
		me: import('$lib/api/auth').AdminMeResponse | null;
	};
}

let { data }: Props = $props();
</script>

<div class="mx-auto max-w-3xl space-y-6">
	<Tabs.Root value="general">
		<Tabs.List>
			<Tabs.Trigger value="general">General</Tabs.Trigger>
			<Tabs.Trigger value="account">Account</Tabs.Trigger>
			<Tabs.Trigger value="sync">Sync & Tasks</Tabs.Trigger>
			<Tabs.Trigger value="about">About</Tabs.Trigger>
		</Tabs.List>

		<Tabs.Content value="general">
			{#if data.settings}
				<GeneralTab
					csrfOrigin={data.settings.csrf_origin.value}
					isLocked={data.settings.csrf_origin.is_locked}
				/>
			{:else}
				<p class="text-sm text-muted-foreground py-4">Failed to load settings.</p>
			{/if}
		</Tabs.Content>

		<Tabs.Content value="account">
			{#if data.me}
				<AccountTab me={data.me} />
			{:else}
				<p class="text-sm text-muted-foreground py-4">Failed to load profile.</p>
			{/if}
		</Tabs.Content>

		<Tabs.Content value="sync">
			{#if data.settings}
				<SyncTab
					syncInterval={data.settings.sync_interval_seconds}
					expirationInterval={data.settings.expiration_check_interval_seconds}
				/>
			{:else}
				<p class="text-sm text-muted-foreground py-4">Failed to load settings.</p>
			{/if}
		</Tabs.Content>

		<Tabs.Content value="about">
			{#if data.about}
				<AboutTab about={data.about} />
			{:else}
				<p class="text-sm text-muted-foreground py-4">Failed to load system info.</p>
			{/if}
		</Tabs.Content>
	</Tabs.Root>
</div>
