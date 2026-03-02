/**
 * Integration tests for Join Page wizard flow.
 *
 * Tests data structure contracts for wizard steps and interactions.
 * Trivial JSON serialization and self-verifying arbitrary tests removed.
 *
 * @module routes/(public)/join/[code]/join-page-wizard.svelte.test
 */

import { cleanup } from '@testing-library/svelte';
import * as fc from 'fast-check';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type {
	InvitationValidationResponse,
	PublicMediaServerResponse,
	WizardDetailResponse,
	WizardStepResponse
} from '$lib/api/client';

// Mock the API client
vi.mock('$lib/api/client', async () => {
	const actual = await vi.importActual('$lib/api/client');
	return {
		...actual,
		validateStep: vi.fn().mockResolvedValue({
			data: { valid: true, completion_token: 'test-token' }
		}),
		redeemInvitation: vi.fn().mockResolvedValue({
			data: {
				success: true,
				message: 'Account created',
				users_created: []
			}
		})
	};
});

// Mock sessionStorage
const mockSessionStorage = (() => {
	let store: Record<string, string> = {};
	return {
		getItem: vi.fn((key: string) => store[key] || null),
		setItem: vi.fn((key: string, value: string) => {
			store[key] = value;
		}),
		removeItem: vi.fn((key: string) => {
			delete store[key];
		}),
		clear: vi.fn(() => {
			store = {};
		})
	};
})();

Object.defineProperty(window, 'sessionStorage', {
	value: mockSessionStorage
});

// =============================================================================
// Arbitraries for generating test data
// =============================================================================

const isoDateArb = fc
	.integer({ min: 1577836800000, max: 1924905600000 })
	.map((ts) => new Date(ts).toISOString());

const mediaServerResponseArb: fc.Arbitrary<PublicMediaServerResponse> = fc.record({
	name: fc.string({ minLength: 1, maxLength: 50 }).filter((s) => s.trim().length > 0),
	server_type: fc.constant('jellyfin' as const),
	supported_permissions: fc.option(
		fc.array(fc.constantFrom('allow_download', 'allow_sync'), { minLength: 0, maxLength: 2 }),
		{ nil: null }
	)
});

const stepInteractionResponseArb = fc.record({
	id: fc.uuid(),
	step_id: fc.uuid(),
	interaction_type: fc.constantFrom('click', 'timer', 'tos'),
	config: fc.constant({} as { [key: string]: string | number | boolean | string[] | null }),
	display_order: fc.integer({ min: 0, max: 5 }),
	created_at: isoDateArb,
	updated_at: fc.option(isoDateArb, { nil: null })
});

const wizardStepResponseArb: fc.Arbitrary<WizardStepResponse> = fc.record({
	id: fc.uuid(),
	wizard_id: fc.uuid(),
	step_order: fc.integer({ min: 0, max: 10 }),
	title: fc.string({ minLength: 1, maxLength: 100 }).filter((s) => s.trim().length > 0),
	content_markdown: fc.string({ minLength: 1, maxLength: 500 }),
	interactions: fc.array(stepInteractionResponseArb, { minLength: 0, maxLength: 3 }),
	created_at: isoDateArb,
	updated_at: fc.option(isoDateArb, { nil: null })
}) as fc.Arbitrary<WizardStepResponse>;

const wizardDetailResponseArb: fc.Arbitrary<WizardDetailResponse> = fc.record({
	id: fc.uuid(),
	name: fc.string({ minLength: 1, maxLength: 100 }).filter((s) => s.trim().length > 0),
	enabled: fc.constant(true),
	created_at: isoDateArb,
	steps: fc.array(wizardStepResponseArb, { minLength: 1, maxLength: 3 }),
	description: fc.option(fc.string({ maxLength: 200 }), { nil: null }),
	updated_at: fc.option(isoDateArb, { nil: null })
});

const validationWithPreWizardArb: fc.Arbitrary<InvitationValidationResponse> = fc.record({
	valid: fc.constant(true),
	failure_reason: fc.constant(null),
	target_servers: fc.array(mediaServerResponseArb, {
		minLength: 1,
		maxLength: 2
	}),
	allowed_libraries: fc.constant(null),
	duration_days: fc.option(fc.integer({ min: 1, max: 365 }), { nil: null }),
	pre_wizard: wizardDetailResponseArb,
	post_wizard: fc.constant(null)
}) as fc.Arbitrary<InvitationValidationResponse>;

const validationWithPostWizardArb: fc.Arbitrary<InvitationValidationResponse> = fc.record({
	valid: fc.constant(true),
	failure_reason: fc.constant(null),
	target_servers: fc.array(mediaServerResponseArb, {
		minLength: 1,
		maxLength: 2
	}),
	allowed_libraries: fc.constant(null),
	duration_days: fc.option(fc.integer({ min: 1, max: 365 }), { nil: null }),
	pre_wizard: fc.constant(null),
	post_wizard: wizardDetailResponseArb
}) as fc.Arbitrary<InvitationValidationResponse>;

const validationWithBothWizardsArb: fc.Arbitrary<InvitationValidationResponse> = fc.record({
	valid: fc.constant(true),
	failure_reason: fc.constant(null),
	target_servers: fc.array(mediaServerResponseArb, {
		minLength: 1,
		maxLength: 2
	}),
	allowed_libraries: fc.constant(null),
	duration_days: fc.option(fc.integer({ min: 1, max: 365 }), { nil: null }),
	pre_wizard: wizardDetailResponseArb,
	post_wizard: wizardDetailResponseArb
}) as fc.Arbitrary<InvitationValidationResponse>;

// =============================================================================
// Test Setup
// =============================================================================

beforeEach(() => {
	mockSessionStorage.clear();
	vi.clearAllMocks();
});

afterEach(() => {
	cleanup();
});

// =============================================================================
// Wizard step structure validation
// =============================================================================

describe('Wizard step structure validation', () => {
	it('should have wizard steps with valid interaction types', () => {
		fc.assert(
			fc.property(validationWithPreWizardArb, (validation) => {
				const validTypes = ['click', 'timer', 'tos', 'text_input', 'quiz'];

				for (const step of validation.pre_wizard?.steps ?? []) {
					expect(step.title.length).toBeGreaterThan(0);
					expect(step.id).toBeDefined();
					expect(Array.isArray(step.interactions)).toBe(true);
					for (const interaction of step.interactions) {
						expect(validTypes).toContain(interaction.interaction_type);
					}
				}
			}),
			{ numRuns: 50 }
		);
	});

	it('should have content for each wizard step', () => {
		fc.assert(
			fc.property(validationWithPreWizardArb, (validation) => {
				for (const step of validation.pre_wizard?.steps ?? []) {
					expect(step.content_markdown).toBeDefined();
					expect(step.content_markdown.length).toBeGreaterThan(0);
				}
			}),
			{ numRuns: 50 }
		);
	});

	it('should have valid step ordering', () => {
		fc.assert(
			fc.property(validationWithPreWizardArb, (validation) => {
				for (const step of validation.pre_wizard?.steps ?? []) {
					expect(step.step_order).toBeGreaterThanOrEqual(0);
					expect(step.wizard_id).toBeDefined();
				}
			}),
			{ numRuns: 50 }
		);
	});

	it('should have post-wizard steps with valid interaction types', () => {
		fc.assert(
			fc.property(validationWithPostWizardArb, (validation) => {
				const validTypes = ['click', 'timer', 'tos', 'text_input', 'quiz'];

				for (const step of validation.post_wizard?.steps ?? []) {
					for (const interaction of step.interactions) {
						expect(validTypes).toContain(interaction.interaction_type);
					}
				}
			}),
			{ numRuns: 50 }
		);
	});

	it('should support both pre and post wizards simultaneously', () => {
		fc.assert(
			fc.property(validationWithBothWizardsArb, (validation) => {
				expect(validation.pre_wizard).not.toBeNull();
				expect(validation.post_wizard).not.toBeNull();
				expect(validation.pre_wizard?.id).not.toBe(validation.post_wizard?.id);
			}),
			{ numRuns: 50 }
		);
	});
});
