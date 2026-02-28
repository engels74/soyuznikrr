<script lang="ts">
/**
 * Wizard editor page.
 *
 * Displays the wizard builder for editing an existing wizard.
 * Includes preview mode for testing the wizard flow.
 *
 * @module routes/(admin)/wizards/[id]/+page
 */

import { goto, invalidateAll } from "$app/navigation";
import type { WizardDetailResponse, WizardStepResponse } from "$lib/api/client";
import { getErrorMessage, isNetworkError } from "$lib/api/errors";
import ErrorState from "$lib/components/error-state.svelte";
import {
	WizardBuilder,
	WizardShell,
} from "$lib/components/wizard";
import type { PageData } from "./$types";

const { data }: { data: PageData } = $props();

// Preview mode state
let isPreviewMode = $state(false);
let previewSteps = $state<WizardStepResponse[]>([]);

/**
 * Handle save - refresh data and stay on page.
 */
async function handleSave(_wizard: WizardDetailResponse) {
	await invalidateAll();
}

/**
 * Handle cancel - go back to wizard list.
 */
function handleCancel() {
	goto("/wizards");
}

/**
 * Toggle preview mode with current steps from the builder.
 */
function handlePreview(currentSteps: WizardStepResponse[]) {
	previewSteps = currentSteps;
	isPreviewMode = true;
}

/**
 * Exit preview mode.
 */
async function handleExitPreview() {
	await invalidateAll();
	isPreviewMode = false;
}

/**
 * Handle wizard completion in preview mode.
 */
async function handlePreviewComplete() {
	await invalidateAll();
	isPreviewMode = false;
}

/**
 * Handle retry after error.
 */
async function handleRetry() {
	await invalidateAll();
}
</script>

{#if data.error}
	<ErrorState
		message={getErrorMessage(data.error)}
		title={isNetworkError(data.error) ? 'Connection Error' : 'Failed to load wizard'}
		onRetry={handleRetry}
	/>
{:else if data.wizard}
	{#if isPreviewMode}
		<!-- Preview mode - render the wizard shell -->
		<div class="preview-container">
			<div class="preview-header">
				<span class="preview-badge">Preview Mode</span>
				<button type="button" class="exit-preview" onclick={handleExitPreview}>
					Exit Preview
				</button>
			</div>
			<WizardShell
				wizard={{ ...data.wizard, steps: previewSteps }}
				onComplete={handlePreviewComplete}
				onCancel={handleExitPreview}
				mode="preview"
			/>
		</div>
	{:else}
		<!-- Edit mode - render the wizard builder -->
		<WizardBuilder
			wizard={data.wizard}
			onSave={handleSave}
			onCancel={handleCancel}
			onPreview={handlePreview}
		/>
	{/if}
{/if}

<style>
	.preview-container {
		position: fixed;
		inset: 0;
		z-index: 100;
		background: hsl(220 20% 4%);
	}

	.preview-header {
		position: absolute;
		top: 1rem;
		right: 1rem;
		z-index: 110;
		display: flex;
		align-items: center;
		gap: 1rem;
	}

	.preview-badge {
		padding: 0.375rem 0.75rem;
		font-size: 0.75rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: hsl(220 20% 4%);
		background: hsl(45 90% 55%);
		border-radius: 0.25rem;
	}

	.exit-preview {
		padding: 0.5rem 1rem;
		font-size: 0.875rem;
		font-weight: 500;
		color: hsl(220 10% 80%);
		background: hsl(220 15% 15%);
		border: 1px solid hsl(220 10% 25%);
		border-radius: 0.375rem;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.exit-preview:hover {
		color: hsl(220 10% 92%);
		background: hsl(220 15% 20%);
		border-color: hsl(220 10% 35%);
	}
</style>
