<script lang="ts">
/**
 * Step Editor Component
 *
 * Renders step metadata form (title, content) and registry-driven
 * interaction toggles. Interactions are managed via direct API calls.
 *
 * Requirements: 13.3
 *
 * @module $lib/components/wizard/step-editor
 */

import { onDestroy } from "svelte";
import { slide } from "svelte/transition";
import { toast } from "svelte-sonner";
import type { StepInteractionResponse, WizardStepResponse } from "$lib/api/client";
import {
	addStepInteraction,
	removeStepInteraction,
	updateStepInteraction,
} from "$lib/api/client";
import { Button } from "$lib/components/ui/button";
import { Input } from "$lib/components/ui/input";
import { Label } from "$lib/components/ui/label";
import { Switch } from "$lib/components/ui/switch";
import { getAllInteractionTypes, type InteractionTypeRegistration } from "./interactions";
import MarkdownEditor from "./markdown-editor.svelte";

interface Props {
	step: WizardStepResponse;
	wizardId: string;
	onSave: (updates: Partial<WizardStepResponse>) => void | Promise<void>;
	onCancel: () => void;
	onInteractionsChange: (interactions: StepInteractionResponse[]) => void;
}

const { step, wizardId, onSave, onCancel, onInteractionsChange }: Props = $props();

// Form state (local copies — intentionally captures initial prop values)
// svelte-ignore state_referenced_locally
let title = $state(step.title);
// svelte-ignore state_referenced_locally
let contentMarkdown = $state(step.content_markdown);
let isSaving = $state(false);

// Track active interactions locally
// svelte-ignore state_referenced_locally
let activeInteractions = $state<StepInteractionResponse[]>([...step.interactions]);

// Loading states per interaction type
let loadingTypes = $state<Set<string>>(new Set());

// Config errors per interaction type
let configErrors = $state<Record<string, Record<string, string[]>>>({});

// Debounce timers for config persist (keyed by interaction type)
const persistTimers = new Map<string, ReturnType<typeof setTimeout>>();
onDestroy(() => {
	for (const timer of persistTimers.values()) clearTimeout(timer);
});

// All registered interaction types
const registeredTypes = $derived(getAllInteractionTypes());

// Check if a type is active
function isActive(type: string): boolean {
	return activeInteractions.some((i) => i.interaction_type === type);
}

// Get the active interaction for a type
function getActiveInteraction(type: string): StepInteractionResponse | undefined {
	return activeInteractions.find((i) => i.interaction_type === type);
}

/**
 * Toggle an interaction type on/off.
 */
async function handleToggle(registration: InteractionTypeRegistration, checked: boolean) {
	const type = registration.type;

	loadingTypes = new Set([...loadingTypes, type]);

	try {
		if (checked) {
			// Add interaction
			const result = await addStepInteraction(wizardId, step.id, {
				interaction_type: type,
				config: registration.defaultConfig() as Record<string, string | number | boolean | string[] | null>,
			});

			if (result.error) {
				throw new Error(result.error.detail ?? "Failed to add interaction");
			}

			if (result.data) {
				activeInteractions = [...activeInteractions, result.data];
				onInteractionsChange(activeInteractions);
			}
		} else {
			// Remove interaction
			const existing = getActiveInteraction(type);
			if (existing) {
				const result = await removeStepInteraction(wizardId, step.id, existing.id);

				if (result.error) {
					throw new Error(result.error.detail ?? "Failed to remove interaction");
				}

				activeInteractions = activeInteractions.filter((i) => i.id !== existing.id);
				// Clear errors for this type
				const newErrors = { ...configErrors };
				delete newErrors[type];
				configErrors = newErrors;
				onInteractionsChange(activeInteractions);
			}
		}
	} catch (error) {
		toast.error(error instanceof Error ? error.message : "Failed to toggle interaction");
	} finally {
		loadingTypes = new Set([...loadingTypes].filter((t) => t !== type));
	}
}

/**
 * Persist config to backend (called after debounce).
 */
async function persistConfig(interactionId: string, newConfig: Record<string, unknown>) {
	try {
		const result = await updateStepInteraction(wizardId, step.id, interactionId, {
			config: newConfig as Record<string, string | number | boolean | string[] | null>,
		});

		if (result.error) {
			throw new Error(result.error.detail ?? "Failed to update interaction config");
		}

		if (result.data) {
			const updated = result.data;
			activeInteractions = activeInteractions.map((i) =>
				i.id === interactionId ? updated : i,
			);
			onInteractionsChange(activeInteractions);
		}
	} catch (error) {
		toast.error(error instanceof Error ? error.message : "Failed to save config");
	}
}

/**
 * Handle config change for an interaction type.
 * Updates local state immediately, debounces the backend persist.
 */
function handleConfigChange(type: string, newConfig: Record<string, unknown>) {
	const existing = getActiveInteraction(type);
	if (!existing) return;

	// Validate with schema
	const registration = registeredTypes.find((r) => r.type === type);
	if (registration) {
		const result = registration.configSchema.safeParse(newConfig);
		if (!result.success) {
			const fieldErrors: Record<string, string[]> = {};
			for (const issue of result.error.issues) {
				const path = issue.path.join(".");
				if (!fieldErrors[path]) {
					fieldErrors[path] = [];
				}
				fieldErrors[path].push(issue.message);
			}
			configErrors = { ...configErrors, [type]: fieldErrors };
			// Still update locally for UI responsiveness
			activeInteractions = activeInteractions.map((i) =>
				i.id === existing.id ? { ...i, config: newConfig as typeof i.config } : i,
			);
			return;
		}
		// Clear errors on valid config
		const newErrors = { ...configErrors };
		delete newErrors[type];
		configErrors = newErrors;
	}

	// Optimistically update local state
	activeInteractions = activeInteractions.map((i) =>
		i.id === existing.id ? { ...i, config: newConfig as typeof i.config } : i,
	);

	// Debounce backend persist (300ms)
	const existingTimer = persistTimers.get(type);
	if (existingTimer) clearTimeout(existingTimer);

	const interactionId = existing.id;
	persistTimers.set(
		type,
		setTimeout(() => {
			persistTimers.delete(type);
			persistConfig(interactionId, newConfig);
		}, 300),
	);
}

/**
 * Handle save (title + content only).
 */
async function handleSave() {
	isSaving = true;
	try {
		await onSave({
			title,
			content_markdown: contentMarkdown,
		});
	} finally {
		isSaving = false;
	}
}
</script>

<div class="step-editor">
	<!-- Title field -->
	<div class="field">
		<Label for="step-title" class="text-cr-text">Step Title</Label>
		<Input
			id="step-title"
			bind:value={title}
			placeholder="Enter step title"
			class="border-cr-border bg-cr-bg text-cr-text"
		/>
	</div>

	<!-- Content markdown editor -->
	<div class="field">
		<Label class="text-cr-text">Content</Label>
		<MarkdownEditor bind:value={contentMarkdown} />
	</div>

	<!-- Interaction toggles -->
	<div class="interactions-section">
		<div class="section-header">
			<h4 class="section-title">Interactions</h4>
			<p class="section-description">
				Add interactions to this step. Users must complete all active interactions to proceed.
			</p>
		</div>

		<div class="module-stack">
			{#each registeredTypes as registration (registration.type)}
				{@const active = isActive(registration.type)}
				{@const interaction = getActiveInteraction(registration.type)}
				{@const loading = loadingTypes.has(registration.type)}
				{@const IconComponent = registration.icon}
				{@const errors = configErrors[registration.type] ?? {}}

				<div class="module-card" class:active>
					{#if active}
						<div class="active-bar"></div>
					{/if}

					<div class="module-header">
						<div class="module-icon" class:active>
							{#if IconComponent}
								<IconComponent size={16} />
							{/if}
						</div>
						<div class="module-info">
							<span class="module-label" class:active>{registration.label}</span>
							<span class="module-description">{registration.description}</span>
						</div>
						<Switch
							checked={active}
							onCheckedChange={(checked: boolean) => handleToggle(registration, checked)}
							disabled={loading}
						/>
					</div>

					{#if active && interaction}
						{@const ConfigEditor = registration.configEditor}
						<div class="module-config" transition:slide={{ duration: 200 }}>
							<ConfigEditor
								config={interaction.config}
								onConfigChange={(config) => handleConfigChange(registration.type, config)}
								{errors}
							/>
						</div>
					{/if}
				</div>
			{/each}
		</div>
	</div>

	<!-- Actions -->
	<div class="actions">
		<Button variant="ghost" onclick={onCancel} class="text-cr-text-muted">
			Cancel
		</Button>
		<Button
			onclick={handleSave}
			disabled={isSaving}
			class="bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
		>
			{isSaving ? 'Saving...' : 'Save Step'}
		</Button>
	</div>
</div>

<style>
	.step-editor {
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
	}

	.field {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	/* Interactions section */
	.interactions-section {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		padding-top: 1rem;
		border-top: 1px solid var(--cr-border);
	}

	.section-header {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.section-title {
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--cr-text);
		margin: 0;
	}

	.section-description {
		font-size: 0.75rem;
		color: var(--cr-text-muted);
		margin: 0;
	}

	/* Module stack */
	.module-stack {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	/* Module card */
	.module-card {
		position: relative;
		border: 1px solid var(--cr-module-border);
		border-radius: 0.625rem;
		background: var(--cr-module-bg);
		overflow: hidden;
		transition: border-color 0.2s ease;
	}

	.module-card.active {
		border-color: var(--cr-module-active-border);
	}

	/* Gold left accent bar */
	.active-bar {
		position: absolute;
		left: 0;
		top: 0;
		bottom: 0;
		width: 3px;
		background: linear-gradient(to bottom, var(--cr-module-active-accent), var(--cr-module-active-accent-dim));
		border-radius: 3px 0 0 3px;
	}

	/* Module header */
	.module-header {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.75rem 1rem;
	}

	.module-card.active .module-header {
		padding-left: calc(1rem + 3px);
	}

	.module-icon {
		width: 2rem;
		height: 2rem;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 0.5rem;
		background: var(--cr-module-icon-bg);
		color: var(--cr-module-icon-color);
		flex-shrink: 0;
		transition: all 0.2s ease;
	}

	.module-icon.active {
		background: var(--cr-module-active-icon-bg);
		color: var(--cr-module-active-icon-color);
	}

	.module-info {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
		min-width: 0;
	}

	.module-label {
		font-size: 0.8125rem;
		font-weight: 500;
		color: var(--cr-text);
		transition: color 0.2s ease;
	}

	.module-label.active {
		color: var(--cr-module-active-label);
	}

	.module-description {
		font-size: 0.6875rem;
		color: var(--cr-text-muted);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	/* Module config section */
	.module-config {
		padding: 0.75rem 1rem 1rem;
		padding-left: calc(1rem + 3px);
		border-top: 1px solid var(--cr-module-config-border);
	}

	/* Actions */
	.actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
		padding-top: 1rem;
		border-top: 1px solid var(--cr-border);
	}
</style>
