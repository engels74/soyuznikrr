/**
 * Wizard Interaction Components
 *
 * Exports interaction components, registry, and types.
 *
 * @module $lib/components/wizard/interactions
 */

// Ensure all built-in interaction types are registered
import './register-defaults';

// Interaction components (consumed via registry, but exported for direct use)
export { default as ClickInteraction } from './click-interaction.svelte';
export { default as QuizInteraction } from './quiz-interaction.svelte';
// Registry exports
export {
	type ConfigEditorProps,
	getAllInteractionTypes,
	getInteractionType,
	type InteractionCompletionData,
	type InteractionComponentProps,
	type InteractionTypeRegistration,
	isRegisteredType,
	registerInteractionType
} from './registry';
export { default as TextInputInteraction } from './text-input-interaction.svelte';
export { default as TimerInteraction } from './timer-interaction.svelte';
export { default as TosInteraction } from './tos-interaction.svelte';
