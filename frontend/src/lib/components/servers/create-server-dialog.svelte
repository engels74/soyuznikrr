<script lang="ts">
/**
 * Create server dialog component.
 *
 * Provides a modal dialog for adding new media servers with:
 * - Form validation via Zod
 * - Server type toggle (Jellyfin/Plex)
 * - API submission with connection validation
 * - Success/error toast notifications
 * - Auto-close on successful creation
 *
 * @module $lib/components/servers/create-server-dialog
 */

import { Eye, EyeOff, Plus, Server } from '@lucide/svelte';
import { toast } from 'svelte-sonner';
import { createServer } from '$lib/api/client';
import { ApiError, getErrorMessage } from '$lib/api/errors';
import { Button } from '$lib/components/ui/button';
import * as Dialog from '$lib/components/ui/dialog';
import { Input } from '$lib/components/ui/input';
import { Label } from '$lib/components/ui/label';
import {
	type CreateServerInput,
	createServerSchema,
	transformCreateServerData
} from '$lib/schemas/server';

interface Props {
	onSuccess?: () => void;
}

let { onSuccess }: Props = $props();

// Dialog open state
let open = $state(false);

// Submitting state
let submitting = $state(false);

// Show/hide API key
let showApiKey = $state(false);

// Form data state
let formData = $state<CreateServerInput>({
	name: '',
	server_type: 'jellyfin',
	url: '',
	api_key: ''
});

// Validation errors
let errors = $state<Record<string, string[]>>({});

/**
 * Reset form to initial state.
 */
function resetForm() {
	formData = {
		name: '',
		server_type: 'jellyfin',
		url: '',
		api_key: ''
	};
	errors = {};
	showApiKey = false;
}

/**
 * Validate form data.
 */
function validateForm(): boolean {
	const result = createServerSchema.safeParse(formData);
	if (!result.success) {
		const fieldErrors: Record<string, string[]> = {};
		for (const issue of result.error.issues) {
			const path = issue.path.join('.');
			if (!fieldErrors[path]) {
				fieldErrors[path] = [];
			}
			fieldErrors[path].push(issue.message);
		}
		errors = fieldErrors;
		return false;
	}
	errors = {};
	return true;
}

/**
 * Get field errors for a specific field.
 */
function getFieldErrors(field: string): string[] {
	return errors[field] || [];
}

/**
 * Handle form submission.
 */
async function handleSubmit(event: Event) {
	event.preventDefault();

	if (!validateForm()) {
		return;
	}

	submitting = true;
	try {
		const data = transformCreateServerData(formData);
		const result = await createServer(data);

		if (result.error) {
			const status = result.response?.status ?? 500;
			const errorBody = result.error as { error_code?: string; detail?: string };
			throw new ApiError(
				status,
				errorBody?.error_code ?? 'UNKNOWN_ERROR',
				errorBody?.detail ?? 'Failed to create server'
			);
		}

		// Success
		toast.success('Server added successfully', {
			description: `${result.data?.name} has been configured`
		});

		// Close dialog and reset form
		open = false;
		resetForm();

		// Notify parent to refresh list
		onSuccess?.();
	} catch (error) {
		toast.error('Failed to add server', {
			description: getErrorMessage(error)
		});
	} finally {
		submitting = false;
	}
}

/**
 * Handle dialog close.
 */
function handleOpenChange(isOpen: boolean) {
	open = isOpen;
	if (!isOpen) {
		resetForm();
	}
}

/**
 * Handle cancel button.
 */
function handleCancel() {
	open = false;
	resetForm();
}
</script>

<Dialog.Root bind:open onOpenChange={handleOpenChange}>
	<Dialog.Trigger>
		{#snippet child({ props })}
			<Button
				{...props}
				class="bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
			>
				<Plus class="size-4" />
				Add Server
			</Button>
		{/snippet}
	</Dialog.Trigger>

	<Dialog.Content
		class="border-cr-border bg-cr-surface sm:max-w-md"
	>
		<Dialog.Header>
			<Dialog.Title class="text-cr-text flex items-center gap-2">
				<Server class="size-5 text-cr-accent" />
				Add Media Server
			</Dialog.Title>
			<Dialog.Description class="text-cr-text-muted">
				Connect a Jellyfin or Plex media server to manage user access.
			</Dialog.Description>
		</Dialog.Header>

		<form onsubmit={handleSubmit} class="mt-4 space-y-4">
			<!-- Server Name -->
			<div class="space-y-2">
				<Label for="name" class="text-cr-text">Server Name</Label>
				<Input
					id="name"
					bind:value={formData.name}
					placeholder="My Media Server"
					disabled={submitting}
					class="border-cr-border bg-cr-bg text-cr-text placeholder:text-cr-text-muted/50 focus:border-cr-accent"
					data-field="name"
				/>
				{#if getFieldErrors('name').length > 0}
					<div class="text-rose-400 text-sm" data-field-error="name">
						{#each getFieldErrors('name') as error}
							<p>{error}</p>
						{/each}
					</div>
				{/if}
			</div>

			<!-- Server Type Toggle -->
			<div class="space-y-2">
				<Label class="text-cr-text">Server Type</Label>
				<div class="flex rounded-lg border border-cr-border overflow-hidden" role="group">
					<button
						type="button"
						disabled={submitting}
						onclick={() => (formData.server_type = 'jellyfin')}
						class="flex-1 px-4 py-2.5 text-sm font-medium transition-colors {formData.server_type === 'jellyfin'
							? 'bg-purple-500/20 text-purple-400 border-r border-purple-500/30'
							: 'bg-cr-bg text-cr-text-muted hover:bg-cr-border border-r border-cr-border'}"
						data-server-type="jellyfin"
					>
						Jellyfin
					</button>
					<button
						type="button"
						disabled={submitting}
						onclick={() => (formData.server_type = 'plex')}
						class="flex-1 px-4 py-2.5 text-sm font-medium transition-colors {formData.server_type === 'plex'
							? 'bg-amber-500/20 text-amber-400'
							: 'bg-cr-bg text-cr-text-muted hover:bg-cr-border'}"
						data-server-type="plex"
					>
						Plex
					</button>
				</div>
				{#if getFieldErrors('server_type').length > 0}
					<div class="text-rose-400 text-sm" data-field-error="server_type">
						{#each getFieldErrors('server_type') as error}
							<p>{error}</p>
						{/each}
					</div>
				{/if}
			</div>

			<!-- Server URL -->
			<div class="space-y-2">
				<Label for="url" class="text-cr-text">Server URL</Label>
				<Input
					id="url"
					type="url"
					bind:value={formData.url}
					placeholder="https://jellyfin.example.com"
					disabled={submitting}
					class="border-cr-border bg-cr-bg text-cr-text placeholder:text-cr-text-muted/50 focus:border-cr-accent font-mono text-sm"
					data-field="url"
				/>
				<p class="text-cr-text-muted text-xs">Full URL including protocol (http:// or https://)</p>
				{#if getFieldErrors('url').length > 0}
					<div class="text-rose-400 text-sm" data-field-error="url">
						{#each getFieldErrors('url') as error}
							<p>{error}</p>
						{/each}
					</div>
				{/if}
			</div>

			<!-- API Key -->
			<div class="space-y-2">
				<Label for="api_key" class="text-cr-text">API Key</Label>
				<div class="relative">
					<Input
						id="api_key"
						type={showApiKey ? 'text' : 'password'}
						bind:value={formData.api_key}
						placeholder="Enter API key"
						disabled={submitting}
						class="border-cr-border bg-cr-bg text-cr-text placeholder:text-cr-text-muted/50 focus:border-cr-accent font-mono text-sm pr-10"
						data-field="api_key"
					/>
					<button
						type="button"
						onclick={() => (showApiKey = !showApiKey)}
						class="absolute right-2 top-1/2 -translate-y-1/2 text-cr-text-muted hover:text-cr-text p-1"
						aria-label={showApiKey ? 'Hide API key' : 'Show API key'}
					>
						{#if showApiKey}
							<EyeOff class="size-4" />
						{:else}
							<Eye class="size-4" />
						{/if}
					</button>
				</div>
				<p class="text-cr-text-muted text-xs">
					{#if formData.server_type === 'jellyfin'}
						Create an API key in Jellyfin: Dashboard > API Keys
					{:else}
						Find your Plex token in account settings or use a Plex Pass API token
					{/if}
				</p>
				{#if getFieldErrors('api_key').length > 0}
					<div class="text-rose-400 text-sm" data-field-error="api_key">
						{#each getFieldErrors('api_key') as error}
							<p>{error}</p>
						{/each}
					</div>
				{/if}
			</div>

			<!-- Form Actions -->
			<div class="flex items-center justify-end gap-3 pt-4 border-t border-cr-border">
				<Button
					type="button"
					variant="outline"
					onclick={handleCancel}
					disabled={submitting}
					class="border-cr-border bg-cr-surface hover:bg-cr-border text-cr-text"
				>
					Cancel
				</Button>
				<Button
					type="submit"
					disabled={submitting}
					class="bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
				>
					{#if submitting}
						<span class="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
						Testing Connection...
					{:else}
						Add Server
					{/if}
				</Button>
			</div>
		</form>
	</Dialog.Content>
</Dialog.Root>
