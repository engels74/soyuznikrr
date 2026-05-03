<script lang="ts">
import StatCard from './stat-card.svelte';

interface Props {
	title: string;
	value: number | string;
	subtitle?: string;
}

const { title, value, subtitle }: Props = $props();
</script>

<StatCard {title} {value} {subtitle}>
	{#snippet icon()}
		<span data-testid="harness-icon" class="size-4">i</span>
	{/snippet}
</StatCard>
