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
	interactionId: string;
	config: Record<string, unknown>;
	onComplete: (data: InteractionCompletionData) => void;
	onValidate?: (
		data: InteractionCompletionData
	) => Promise<{ valid: boolean; pending?: boolean; error?: string | null }>;
	disabled: boolean;
	completionData?: InteractionCompletionData;
	/**
	 * Caller-provided namespace used when an interaction persists transient
	 * state to sessionStorage (e.g. a timer's deadline anchor). Interactions
	 * are reused across invitations — the same wizard + interaction UUID can
	 * appear under two different invite codes — so keying purely by
	 * `interactionId` lets a stale `startedAt` from invite A satisfy the
	 * timer mounted under invite B and auto-complete it. The join page
	 * passes the invite code here; the admin preview path can pass anything
	 * stable (defaults to wizard.id) or leave it undefined.
	 */
	storageScope?: string;
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
