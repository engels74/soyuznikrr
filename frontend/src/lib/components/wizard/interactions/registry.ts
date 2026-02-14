/**
 * Interaction Type Registry
 *
 * Provides a registry pattern for mapping interaction types to their
 * components, config editors, and metadata. This enables composable
 * interaction types — steps can have zero or multiple interactions.
 *
 * @module $lib/components/wizard/interactions/registry
 */

import type { Component } from 'svelte';
import type { z } from 'zod';

/** Props for config editor components (admin side) */
export interface ConfigEditorProps {
	config: Record<string, unknown>;
	onConfigChange: (config: Record<string, unknown>) => void;
	errors: Record<string, string[]>;
}

/** Data emitted when a user completes an interaction */
export interface InteractionCompletionData {
	interactionId: string;
	interactionType: string;
	data: Record<string, string | number | boolean | null>;
	startedAt?: string;
	completedAt: string;
}

/** Props for interaction components (user-facing side) */
export interface InteractionComponentProps {
	stepId: string;
	interactionId: string;
	config: Record<string, unknown>;
	onComplete: (data: InteractionCompletionData) => void;
	disabled: boolean;
}

/** Registration for a single interaction type */
export interface InteractionTypeRegistration {
	type: string;
	label: string;
	description: string;
	icon: Component;
	configSchema: z.ZodType;
	defaultConfig: () => Record<string, unknown>;
	configEditor: Component<ConfigEditorProps>;
	interactionComponent: Component<InteractionComponentProps>;
}

/** Internal store of registered types */
const registry = new Map<string, InteractionTypeRegistration>();

/**
 * Register an interaction type with its components and metadata.
 */
export function registerInteractionType(registration: InteractionTypeRegistration): void {
	registry.set(registration.type, registration);
}

/**
 * Get a registered interaction type by its key.
 */
export function getInteractionType(type: string): InteractionTypeRegistration | undefined {
	return registry.get(type);
}

/**
 * Get all registered interaction types.
 */
export function getAllInteractionTypes(): InteractionTypeRegistration[] {
	return Array.from(registry.values());
}

/**
 * Check if an interaction type is registered.
 */
export function isRegisteredType(type: string): boolean {
	return registry.has(type);
}
