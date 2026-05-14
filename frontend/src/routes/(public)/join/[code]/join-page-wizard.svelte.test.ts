/**
 * Integration tests for Join Page wizard flow.
 *
 * Tests data structure contracts for wizard steps and interactions.
 * Trivial JSON serialization and self-verifying arbitrary tests removed.
 *
 * @module routes/(public)/join/[code]/join-page-wizard.svelte.test
 */

import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import * as fc from 'fast-check';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type {
	InvitationValidationResponse,
	PublicMediaServerResponse,
	WizardDetailResponse,
	WizardStepResponse
} from '$lib/api/client';
import { WizardShell } from '$lib/components/wizard';

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

// Mock the shared language cache used by WizardShell.
vi.mock('$lib/components/wizard/language-cache', () => ({
	getCachedLanguages: () => [],
	loadLanguages: () => Promise.resolve([]),
	getLanguageLabel: (code: string) => code.toUpperCase()
}));

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

// jsdom does not implement matchMedia or scrollIntoView; the wizard-shell
// reaches for them when its scroll-to-top $effect runs.
if (!window.matchMedia) {
	Object.defineProperty(window, 'matchMedia', {
		writable: true,
		value: vi.fn().mockReturnValue({
			matches: false,
			media: '',
			onchange: null,
			addListener: vi.fn(),
			removeListener: vi.fn(),
			addEventListener: vi.fn(),
			removeEventListener: vi.fn(),
			dispatchEvent: vi.fn()
		})
	});
}

if (!Element.prototype.scrollIntoView) {
	Element.prototype.scrollIntoView = vi.fn();
}

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
		expect(validationWithBothWizardsArb).toBeDefined();
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

// =============================================================================
// Pre-wizard rendering and transition tests
//
// The join page renders the pre-wizard via <WizardShell> and only advances to
// the registration step when the wizard fires `onComplete`. These tests cover
// the same handoff but exercise the wizard directly so they don't have to
// stub out the rest of +page.svelte's flow.
// =============================================================================

function makePreWizard(): WizardDetailResponse {
	return {
		id: '00000000-0000-0000-0000-00000000aaaa',
		name: 'Welcome',
		enabled: true,
		created_at: '2024-01-01T00:00:00Z',
		updated_at: null,
		description: null,
		steps: [
			{
				id: '00000000-0000-0000-0000-000000000001',
				wizard_id: '00000000-0000-0000-0000-00000000aaaa',
				step_order: 0,
				title: 'Wait + describe',
				content_markdown: 'multi-interaction step',
				primary_language: 'en',
				translations: [],
				interactions: [
					{
						id: '00000000-0000-0000-0000-0000000000aa',
						step_id: '00000000-0000-0000-0000-000000000001',
						interaction_type: 'timer',
						config: { duration_seconds: 3 },
						display_order: 0,
						created_at: '2024-01-01T00:00:00Z',
						updated_at: null
					},
					{
						id: '00000000-0000-0000-0000-0000000000bb',
						step_id: '00000000-0000-0000-0000-000000000001',
						interaction_type: 'text_input',
						config: { label: 'Your name', required: true },
						display_order: 1,
						created_at: '2024-01-01T00:00:00Z',
						updated_at: null
					}
				] as WizardStepResponse['interactions'],
				created_at: '2024-01-01T00:00:00Z',
				updated_at: null
			}
		]
	};
}

describe('Pre-wizard rendering and flow handoff', () => {
	beforeEach(() => {
		mockSessionStorage.clear();
		vi.useFakeTimers();
	});

	afterEach(() => {
		vi.useRealTimers();
		cleanup();
	});

	it('renders the wizard shell when a pre-wizard is configured', () => {
		const wizard = makePreWizard();
		render(WizardShell, { props: { wizard, onComplete: vi.fn() } });

		// "Wait + describe" renders in both the progress widget and the h2
		// heading — use a heading-specific query to disambiguate.
		expect(screen.getByRole('heading', { level: 2, name: 'Wait + describe' })).toBeInTheDocument();
		// Timer interaction renders a countdown display.
		expect(screen.getByText('0:03')).toBeInTheDocument();
		// Text-input interaction renders a labeled field.
		expect(screen.getByLabelText('Your name')).toBeInTheDocument();
	});

	it('fires onComplete after both interactions on the single step complete', async () => {
		const wizard = makePreWizard();
		const onComplete = vi.fn();
		render(WizardShell, { props: { wizard, onComplete } });

		// Wait out the timer using a wall-clock jump + a single tick.
		vi.setSystemTime(Date.now() + 3000);
		await vi.advanceTimersByTimeAsync(1000);

		// Fill in the required text input.
		const input = screen.getByLabelText('Your name');
		await fireEvent.input(input, { target: { value: 'Tester' } });

		const submit = screen.getByRole('button', { name: 'Continue' });
		await fireEvent.click(submit);

		// Drain microtasks + the validation promise chain.
		await vi.advanceTimersByTimeAsync(0);
		await Promise.resolve();
		await Promise.resolve();

		// Single-step wizard: Next button reads "Complete" because isLastStep.
		const complete = screen.getByRole('button', { name: /Complete/i });
		expect(complete).not.toBeDisabled();
		await fireEvent.click(complete);

		// Resolve the final validateStep promise.
		await vi.advanceTimersByTimeAsync(0);
		await Promise.resolve();
		await Promise.resolve();

		expect(onComplete).toHaveBeenCalledTimes(1);
		// Wizard hands back the completion token so the parent flow can advance
		// to registration / oauth.
		expect(onComplete).toHaveBeenCalledWith('test-token');
	});
});
