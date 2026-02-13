<script lang="ts">
/**
 * Create server dialog component.
 *
 * Provides a modal dialog for adding new media servers with:
 * - Form validation via Zod
 * - Server type toggle (dynamically populated from provider registry)
 * - API submission with connection validation
 * - Success/error toast notifications
 * - Auto-close on successful creation
 *
 * @module $lib/components/servers/create-server-dialog
 */

import { Eye, EyeOff, Plug, Plus, Server } from "@lucide/svelte";
import type { ConnectionTestResponse } from "$lib/api/client";
import { createServer, testConnection, withErrorHandling } from "$lib/api/client";
import { Button } from "$lib/components/ui/button";
import * as Dialog from "$lib/components/ui/dialog";
import { Input } from "$lib/components/ui/input";
import { Label } from "$lib/components/ui/label";
import {
	type CreateServerInput,
	createServerSchema,
	transformCreateServerData,
} from "$lib/schemas/server";
import { getAllProviders, getProviderActiveToggleStyle } from "$lib/stores/providers.svelte";
import { showError, showSuccess } from "$lib/utils/toast";

interface Props {
	onSuccess?: () => void;
}

const { onSuccess }: Props = $props();

const providerList = $derived(getAllProviders());

// Dialog open state
let open = $state(false);

// Reset form when dialog closes
$effect(() => {
	if (!open) {
		resetForm();
	}
});

// Submitting state
let submitting = $state(false);

// Show/hide API key
let showApiKey = $state(false);

// Test connection state
let testing = $state(false);
let testResult = $state<ConnectionTestResponse | null>(null);

// Form data state
let formData = $state<CreateServerInput>({
	name: "",
	server_type: "",
	url: "",
	api_key: "",
});

// Validation errors
let errors = $state<Record<string, string[]>>({});

/**
 * Reset form to initial state.
 */
function resetForm() {
	formData = {
		name: "",
		server_type: "",
		url: "",
		api_key: "",
	};
	errors = {};
	showApiKey = false;
	testing = false;
	testResult = null;
}

// Reset test result when url or api_key changes
let prevUrl = $state("");
let prevApiKey = $state("");
$effect(() => {
	if (formData.url !== prevUrl || formData.api_key !== prevApiKey) {
		prevUrl = formData.url;
		prevApiKey = formData.api_key;
		testResult = null;
	}
});

/**
 * Validate form data.
 */
function validateForm(): boolean {
	const result = createServerSchema.safeParse(formData);
	if (!result.success) {
		const fieldErrors: Record<string, string[]> = {};
		for (const issue of result.error.issues) {
			const path = issue.path.join(".");
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
 * Whether the "Test Connection" button should be enabled.
 */
const canTest = $derived(formData.url.trim().length > 0 && formData.api_key.trim().length > 0);

/**
 * Handle test connection button click.
 */
async function handleTestConnection() {
	testing = true;
	testResult = null;

	try {
		const result = await withErrorHandling(
			() => testConnection({ url: formData.url, api_key: formData.api_key }),
			{ showErrorToast: false }
		);

		if (result.error || !result.data) {
			const errorBody = result.error as { detail?: string; message?: string } | undefined;
			testResult = {
				success: false,
				message: errorBody?.detail ?? errorBody?.message ?? "Network error — could not reach the backend.",
			};
			return;
		}

		testResult = result.data;

		// Auto-populate server_type on success
		if (result.data.success && result.data.server_type) {
			formData.server_type = result.data.server_type;
		}
	} finally {
		testing = false;
	}
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
		const result = await withErrorHandling(() => createServer(data), {
			showErrorToast: false,
		});

		if (result.error) {
			const errorBody = result.error as {
				error_code?: string;
				detail?: string;
			};
			showError(
				"Failed to add server",
				errorBody?.detail ?? "An error occurred",
			);
			return;
		}

		// Success
		showSuccess(
			"Server added successfully",
			`${result.data?.name} has been configured`,
		);

		// Close dialog (form resets via $effect watching open)
		open = false;

		// Notify parent to refresh list
		onSuccess?.();
	} finally {
		submitting = false;
	}
}

/**
 * Handle cancel button.
 */
function handleCancel() {
	open = false;
}
</script>

<Dialog.Root bind:open>
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
				Connect a media server to manage user access.
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
					{#each providerList as provider, i (provider.server_type)}
						<button
							type="button"
							disabled={submitting}
							onclick={() => (formData.server_type = provider.server_type)}
							class="flex-1 px-4 py-2.5 text-sm font-medium transition-colors {i < providerList.length - 1 ? 'border-r' : ''} {formData.server_type === provider.server_type
								? ''
								: 'bg-cr-bg text-cr-text-muted hover:bg-cr-border border-cr-border'}"
							style={formData.server_type === provider.server_type ? getProviderActiveToggleStyle(provider.server_type) : ''}
							data-server-type={provider.server_type}
						>
							{provider.display_name}
						</button>
					{/each}
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
					placeholder="https://media.example.com"
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
				{#each providerList as provider (provider.server_type)}
					{#if formData.server_type === provider.server_type && provider.api_key_help_text}
						<p class="text-cr-text-muted text-xs">{provider.api_key_help_text}</p>
					{/if}
				{/each}
				{#if getFieldErrors('api_key').length > 0}
					<div class="text-rose-400 text-sm" data-field-error="api_key">
						{#each getFieldErrors('api_key') as error}
							<p>{error}</p>
						{/each}
					</div>
				{/if}
			</div>

			<!-- Test Connection -->
			<div class="space-y-2">
				<Button
					type="button"
					variant="outline"
					onclick={handleTestConnection}
					disabled={!canTest || testing || submitting}
					class="w-full border-cr-border bg-cr-bg hover:bg-cr-border text-cr-text"
				>
					{#if testing}
						<span class="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
						Testing...
					{:else}
						<Plug class="size-4" />
						Test Connection
					{/if}
				</Button>

				{#if testResult}
					{#if testResult.success}
						{@const providerMeta = providerList.find((p) => p.server_type === testResult?.server_type)}
						<div
							class="rounded-md border px-3 py-2 text-sm"
							style="border-color: {providerMeta?.color ?? '#22c55e'}40; background: {providerMeta?.color ?? '#22c55e'}10; color: {providerMeta?.color ?? '#22c55e'}"
						>
							<p class="font-medium">
								Connected — {providerMeta?.display_name ?? testResult.server_type} server detected
							</p>
							{#if testResult.server_name}
								<p class="text-cr-text-muted text-xs mt-0.5">
									{testResult.server_name}{testResult.version ? ` (v${testResult.version})` : ""}
								</p>
							{/if}
						</div>
					{:else}
						<div class="rounded-md border border-rose-400/30 bg-rose-400/10 px-3 py-2 text-sm text-rose-400">
							<p>{testResult.message}</p>
						</div>
					{/if}
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
