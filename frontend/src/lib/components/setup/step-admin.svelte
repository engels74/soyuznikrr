<script lang="ts">
import { getErrorDetail, setupAdmin } from '$lib/api/auth';
import { Button } from '$lib/components/ui/button';
import * as Card from '$lib/components/ui/card';
import { Input } from '$lib/components/ui/input';
import { Label } from '$lib/components/ui/label';
import { type SetupFormData, setupSchema } from '$lib/schemas/auth';

interface Props {
	onComplete: () => void;
}

const { onComplete }: Props = $props();

let username = $state('');
let password = $state('');
let confirmPassword = $state('');
let email = $state('');
let errors = $state<Record<string, string>>({});
let serverError = $state('');
let loading = $state(false);

const passwordLength = $derived(password.length);
const passwordStrength = $derived.by(() => {
	if (passwordLength === 0) return 0;
	if (passwordLength < 8) return 1;
	if (passwordLength < 15) return 2;
	if (passwordLength < 24) return 3;
	return 4;
});
const strengthLabel = $derived(['', 'Weak', 'Fair', 'Good', 'Strong'][passwordStrength]);
const strengthColor = $derived(
	['bg-cr-border', 'bg-red-500', 'bg-amber-500', 'bg-cyan-500', 'bg-emerald-500'][
		passwordStrength
	]
);

async function handleSubmit(e: SubmitEvent) {
	e.preventDefault();
	errors = {};
	serverError = '';

	const formData: SetupFormData = {
		username,
		password,
		confirmPassword,
		email: email || undefined
	};
	const result = setupSchema.safeParse(formData);

	if (!result.success) {
		for (const issue of result.error.issues) {
			const field = issue.path[0];
			if (field && typeof field === 'string') {
				errors[field] = issue.message;
			}
		}
		return;
	}

	loading = true;
	const response = await setupAdmin({
		username: result.data.username,
		password: result.data.password,
		email: result.data.email || undefined
	});

	if (response.error) {
		loading = false;
		serverError = getErrorDetail(response.error, 'Failed to create admin account');
		return;
	}

	loading = false;
	onComplete();
}
</script>

<Card.Root class="border-cr-border bg-cr-surface">
	<Card.Header>
		<Card.Title class="text-lg text-cr-text">Create Admin Account</Card.Title>
		<Card.Description class="text-cr-text-muted">
			Set up your administrator credentials.
		</Card.Description>
	</Card.Header>
	<Card.Content>
		{#if serverError}
			<div
				class="mb-4 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400"
			>
				{serverError}
			</div>
		{/if}

		<form onsubmit={handleSubmit} class="flex flex-col gap-4">
			<div class="flex flex-col gap-1.5">
				<Label for="setup-username" class="text-cr-text">Username</Label>
				<Input
					id="setup-username"
					type="text"
					bind:value={username}
					placeholder="admin"
					autocomplete="username"
					class="border-cr-border bg-cr-bg text-cr-text placeholder:text-cr-text-dim"
				/>
				{#if errors.username}
					<p class="text-xs text-red-400">{errors.username}</p>
				{/if}
			</div>

			<div class="flex flex-col gap-1.5">
				<Label for="setup-password" class="text-cr-text">Password</Label>
				<Input
					id="setup-password"
					type="password"
					bind:value={password}
					placeholder="Min 15 characters"
					autocomplete="new-password"
					class="border-cr-border bg-cr-bg text-cr-text placeholder:text-cr-text-dim"
				/>
				{#if passwordLength > 0}
					<div class="flex items-center gap-2">
						<div class="flex flex-1 gap-1">
							{#each [1, 2, 3, 4] as level}
								<div
									class="h-1 flex-1 rounded-full transition-colors {passwordStrength >= level
										? strengthColor
										: 'bg-cr-border'}"
								></div>
							{/each}
						</div>
						<span class="text-xs text-cr-text-muted">{strengthLabel}</span>
					</div>
				{/if}
				{#if errors.password}
					<p class="text-xs text-red-400">{errors.password}</p>
				{/if}
			</div>

			<div class="flex flex-col gap-1.5">
				<Label for="setup-confirm" class="text-cr-text">Confirm password</Label>
				<Input
					id="setup-confirm"
					type="password"
					bind:value={confirmPassword}
					placeholder="Re-enter password"
					autocomplete="new-password"
					class="border-cr-border bg-cr-bg text-cr-text placeholder:text-cr-text-dim"
				/>
				{#if errors.confirmPassword}
					<p class="text-xs text-red-400">{errors.confirmPassword}</p>
				{/if}
			</div>

			<div class="flex flex-col gap-1.5">
				<Label for="setup-email" class="text-cr-text">
					Email <span class="text-cr-text-dim">(optional)</span>
				</Label>
				<Input
					id="setup-email"
					type="email"
					bind:value={email}
					placeholder="admin@example.com"
					autocomplete="email"
					class="border-cr-border bg-cr-bg text-cr-text placeholder:text-cr-text-dim"
				/>
				{#if errors.email}
					<p class="text-xs text-red-400">{errors.email}</p>
				{/if}
			</div>

			<Button
				type="submit"
				disabled={loading}
				class="mt-2 w-full bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
			>
				{#if loading}
					Creating account...
				{:else}
					Create admin account
				{/if}
			</Button>
		</form>
	</Card.Content>
</Card.Root>
