/**
 * Wizard Components
 *
 * Exports all wizard-related components for the onboarding flow.
 *
 * @module $lib/components/wizard
 */

// Registry and interaction types
export {
	getAllInteractionTypes,
	getInteractionType,
	type InteractionCompletionData,
	type InteractionComponentProps
} from './interactions';

// Admin builder components
export { default as MarkdownEditor } from './markdown-editor.svelte';
export { default as StepEditor } from './step-editor.svelte';
export { default as WizardBuilder } from './wizard-builder.svelte';

// User-facing wizard components
export { default as WizardNavigation } from './wizard-navigation.svelte';
export { default as WizardProgress } from './wizard-progress.svelte';
export { default as WizardShell } from './wizard-shell.svelte';
