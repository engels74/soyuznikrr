<script lang="ts">
/**
 * Create invitation dialog component.
 *
 * Provides a modal dialog for creating new invitations with:
 * - Form validation via Zod
 * - API submission with error handling
 * - Success/error toast notifications
 * - Auto-close on successful creation
 *
 * @module $lib/components/invitations/create-invitation-dialog
 */

import { Plus } from '@lucide/svelte';
import { toast } from 'svelte-sonner';
import {
	createInvitation,
	type MediaServerWithLibrariesResponse
} from '$lib/api/client';
import { ApiError, getErrorMessage } from '$lib/api/errors';
import { Button } from '$lib/components/ui/button';
import * as Dialog from '$lib/components/ui/dialog';
import {
	type CreateInvitationInput,
	createInvitationSchema,
	transformCreateFormData
} from '$lib/schemas/invitation';
import InvitationFormSimple from './invitation-form-simple.svelte';

interface Props {
	servers: MediaServerWithLibrariesResponse[];
	onSuccess?: () => void;
}

let { servers, onSuccess }: Props = $props();

// Dialog open state
let open = $state(false);

// Submitting state
let submitting = $state(false);

// Form data state
let formData = $state<CreateInvitationInput>({
	server_ids: [],
	code: '',
	expires_at: '',
	max_uses: undefined,
	duration_days: undefined,
	library_ids: []
});

// Validation errors
let errors = $state<Record<string, string[]>>({});

/**
 * Reset form to initial state.
 */
function resetForm() {
	formData = {
		server_ids: [],
		code: '',
		expires_at: '',
		max_uses: undefined,
		duration_days: undefined,
		library_ids: []
	};
	errors = {};
}

/**
 * Validate form data.
 */
function validateForm(): boolean {
	const result = createInvitationSchema.safeParse(formData);
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
 * Handle form submission.
 */
async function handleSubmit() {
	if (!validateForm()) {
		return;
	}

	submitting = true;
	try {
		const data = transformCreateFormData(formData);
		const result = await createInvitation(data);

		if (result.error) {
			const status = result.response?.status ?? 500;
			const errorBody = result.error as { error_code?: string; detail?: string };
			throw new ApiError(
				status,
				errorBody?.error_code ?? 'UNKNOWN_ERROR',
				errorBody?.detail ?? 'Failed to create invitation'
			);
		}

		// Success
		toast.success('Invitation created successfully', {
			description: `Code: ${result.data?.code}`
		});

		// Close dialog and reset form
		open = false;
		resetForm();

		// Notify parent to refresh list
		onSuccess?.();
	} catch (error) {
		toast.error('Failed to create invitation', {
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
				Create Invitation
			</Button>
		{/snippet}
	</Dialog.Trigger>

	<Dialog.Content
		class="border-cr-border bg-cr-surface sm:max-w-xl max-h-[90vh] overflow-y-auto"
	>
		<Dialog.Header>
			<Dialog.Title class="text-cr-text flex items-center gap-2">
				<Plus class="size-5 text-cr-accent" />
				Create Invitation
			</Dialog.Title>
			<Dialog.Description class="text-cr-text-muted">
				Create a new invitation code for user onboarding. Select target servers and configure optional restrictions.
			</Dialog.Description>
		</Dialog.Header>

		<div class="mt-4">
			<InvitationFormSimple
				bind:formData
				{errors}
				{servers}
				mode="create"
				{submitting}
				onSubmit={handleSubmit}
				onCancel={handleCancel}
			/>
		</div>
	</Dialog.Content>
</Dialog.Root>
