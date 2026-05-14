/**
 * Tests for wizard-shell.svelte session restore hardening and handleNext fallback.
 *
 * Targets two regressions that produce a "dead Next button":
 *  - Stored stepIndex outside [0, wizard.steps.length) makes currentStep
 *    undefined; canProceed is vacuously true but handleNext early-returns.
 *  - Stored completions / progressTokens that don't match the current wizard
 *    shape (interaction removed, missing prior-step token) produce the same
 *    inconsistent state on restore.
 *
 * @module $lib/components/wizard/__tests__/wizard-shell.svelte.test
 */

import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { WizardDetailResponse } from '$lib/api/client';
import WizardShell from '../wizard-shell.svelte';

// =============================================================================
// API mocks — language cache + validateStep
// =============================================================================

vi.mock('$lib/api/client', async () => {
	const actual = await vi.importActual<Record<string, unknown>>('$lib/api/client');
	return {
		...actual,
		validateStep: vi.fn().mockResolvedValue({
			data: { valid: true, completion_token: 'mock-token' }
		})
	};
});

vi.mock('../language-cache', () => ({
	getCachedLanguages: () => [],
	loadLanguages: () => Promise.resolve([]),
	getLanguageLabel: (code: string) => code.toUpperCase()
}));

// =============================================================================
// sessionStorage shim
// =============================================================================

const mockSessionStorage = (() => {
	let store: Record<string, string> = {};
	return {
		getItem: vi.fn((key: string) => store[key] ?? null),
		setItem: vi.fn((key: string, value: string) => {
			store[key] = value;
		}),
		removeItem: vi.fn((key: string) => {
			delete store[key];
		}),
		clear: vi.fn(() => {
			store = {};
		}),
		_set(key: string, value: string) {
			store[key] = value;
		},
		_get(key: string) {
			return store[key];
		},
		_reset() {
			store = {};
		}
	};
})();

Object.defineProperty(window, 'sessionStorage', { value: mockSessionStorage });

// jsdom does not implement matchMedia or scrollIntoView; the wizard-shell
// reaches for them in its scroll-to-top $effect.
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
// Fixtures
// =============================================================================

const WIZARD_ID = '00000000-0000-0000-0000-00000000aaaa';
const STEP_0_ID = '00000000-0000-0000-0000-000000000001';
const STEP_1_ID = '00000000-0000-0000-0000-000000000002';
const INTERACTION_A = '00000000-0000-0000-0000-0000000000aa';

function makeWizard(): WizardDetailResponse {
	return {
		id: WIZARD_ID,
		name: 'Test wizard',
		enabled: true,
		created_at: '2024-01-01T00:00:00Z',
		updated_at: null,
		description: null,
		steps: [
			{
				id: STEP_0_ID,
				wizard_id: WIZARD_ID,
				step_order: 0,
				title: 'Step one',
				content_markdown: 'first step',
				primary_language: 'en',
				translations: [],
				interactions: [
					{
						id: INTERACTION_A,
						step_id: STEP_0_ID,
						interaction_type: 'click',
						config: {},
						display_order: 0,
						created_at: '2024-01-01T00:00:00Z',
						updated_at: null
					}
				],
				created_at: '2024-01-01T00:00:00Z',
				updated_at: null
			},
			{
				id: STEP_1_ID,
				wizard_id: WIZARD_ID,
				step_order: 1,
				title: 'Step two',
				content_markdown: 'second step',
				primary_language: 'en',
				translations: [],
				interactions: [],
				created_at: '2024-01-01T00:00:00Z',
				updated_at: null
			}
		]
	};
}

const PROGRESS_KEY = `wizard-${WIZARD_ID}-progress`;
const LANGUAGE_KEY = `wizard-${WIZARD_ID}-language`;

function seedProgress(payload: unknown) {
	mockSessionStorage._set(PROGRESS_KEY, JSON.stringify(payload));
}

/** Asserts the wizard is currently rendering step `current` of `total`. */
function expectOnStep(current: number, total: number) {
	// WizardProgress renders an aria-live "Step N of M" label.
	expect(screen.getByText(`Step ${current} of ${total}`)).toBeInTheDocument();
}

/**
 * Returns the persisted progress payload after the wizard's persist $effect
 * has written it. We can't assert that storage is "undefined" after a
 * discard because the persist effect immediately rewrites the current
 * (reset) state.
 */
function persistedProgress(): {
	stepIndex: number;
	completions: unknown[];
	progressToken: string | null;
	progressTokens: [number, string | null][];
} | null {
	const raw = mockSessionStorage._get(PROGRESS_KEY);
	return raw ? JSON.parse(raw) : null;
}

// =============================================================================
// Tests
// =============================================================================

beforeEach(() => {
	mockSessionStorage._reset();
	vi.clearAllMocks();
});

afterEach(() => {
	cleanup();
});

describe('wizard-shell sessionStorage restore hardening', () => {
	it('discards saved state when stepIndex is out of range', () => {
		const wizard = makeWizard();
		seedProgress({
			stepIndex: 999,
			progressToken: 'tok',
			completions: [],
			progressTokens: [[0, 'tok']]
		});

		render(WizardShell, { props: { wizard, onComplete: vi.fn() } });

		expectOnStep(1, 2);
		expect(mockSessionStorage.removeItem).toHaveBeenCalledWith(PROGRESS_KEY);
		// Persist effect will have rewritten storage with the safe (reset) state.
		expect(persistedProgress()?.stepIndex).toBe(0);
	});

	it('discards saved state when stepIndex is negative', () => {
		const wizard = makeWizard();
		seedProgress({
			stepIndex: -1,
			progressToken: null,
			completions: [],
			progressTokens: []
		});

		render(WizardShell, { props: { wizard, onComplete: vi.fn() } });

		expectOnStep(1, 2);
		expect(mockSessionStorage.removeItem).toHaveBeenCalledWith(PROGRESS_KEY);
	});

	it('discards saved state when stepIndex is not an integer', () => {
		const wizard = makeWizard();
		seedProgress({
			stepIndex: 'not-a-number',
			progressToken: null,
			completions: [],
			progressTokens: []
		});

		render(WizardShell, { props: { wizard, onComplete: vi.fn() } });

		expectOnStep(1, 2);
		expect(mockSessionStorage.removeItem).toHaveBeenCalledWith(PROGRESS_KEY);
	});

	it('discards completions referencing removed interactions', () => {
		const wizard = makeWizard();
		seedProgress({
			stepIndex: 0,
			progressToken: null,
			completions: [
				[
					STEP_0_ID,
					[
						[
							'00000000-0000-0000-0000-deadbeefdead',
							{
								interactionId: '00000000-0000-0000-0000-deadbeefdead',
								interactionType: 'click',
								data: { acknowledged: true },
								completedAt: '2024-01-01T00:00:00Z'
							}
						]
					]
				]
			],
			progressTokens: []
		});

		render(WizardShell, { props: { wizard, onComplete: vi.fn() } });

		expect(mockSessionStorage.removeItem).toHaveBeenCalledWith(PROGRESS_KEY);
		// Storage was rewritten with empty completions for step 0 because
		// the saved interactionId no longer matches.
		const persisted = persistedProgress();
		expect(persisted?.stepIndex).toBe(0);
		expect(persisted?.completions).toEqual([]);

		// Next is still disabled — the missing-id completion was not honored.
		const nextBtn = screen.getByRole('button', { name: /Next/i });
		expect(nextBtn).toBeDisabled();
	});

	it('discards completions referencing removed steps', () => {
		const wizard = makeWizard();
		seedProgress({
			stepIndex: 0,
			progressToken: null,
			completions: [
				[
					'00000000-0000-0000-0000-deadbeefffff',
					[
						[
							INTERACTION_A,
							{
								interactionId: INTERACTION_A,
								interactionType: 'click',
								data: { acknowledged: true },
								completedAt: '2024-01-01T00:00:00Z'
							}
						]
					]
				]
			],
			progressTokens: []
		});

		render(WizardShell, { props: { wizard, onComplete: vi.fn() } });

		expect(mockSessionStorage.removeItem).toHaveBeenCalledWith(PROGRESS_KEY);
		expect(persistedProgress()?.completions).toEqual([]);
	});

	it('discards non-zero stepIndex when prior progress token is missing', () => {
		const wizard = makeWizard();
		seedProgress({
			stepIndex: 1,
			progressToken: 'tok',
			completions: [],
			// No token recorded for step 0 — restore would proceed with an
			// unvalidatable backend handoff.
			progressTokens: []
		});

		render(WizardShell, { props: { wizard, onComplete: vi.fn() } });

		expectOnStep(1, 2);
		expect(mockSessionStorage.removeItem).toHaveBeenCalledWith(PROGRESS_KEY);
	});

	it('accepts a valid saved state', () => {
		const wizard = makeWizard();
		// progressToken (singular, current-step) must match progressTokens.get(savedIndex - 1).
		// Both are written from the same source in the persist $effect, so a
		// divergence indicates corruption and is rejected by the restore guard.
		seedProgress({
			stepIndex: 1,
			progressToken: 'tok-0',
			completions: [
				[
					STEP_0_ID,
					[
						[
							INTERACTION_A,
							{
								interactionId: INTERACTION_A,
								interactionType: 'click',
								data: { acknowledged: true },
								completedAt: '2024-01-01T00:00:00Z'
							}
						]
					]
				]
			],
			progressTokens: [[0, 'tok-0']]
		});

		render(WizardShell, { props: { wizard, onComplete: vi.fn() } });

		// We restored to step 2 (index 1).
		expectOnStep(2, 2);
		// removeItem was NOT called for the progress key because state was valid.
		expect(mockSessionStorage.removeItem).not.toHaveBeenCalledWith(PROGRESS_KEY);
	});

	it('discards non-zero stepIndex when current progressToken is missing', () => {
		const wizard = makeWizard();
		// progressTokens has a valid entry for step 0, but progressToken (singular)
		// is null — the wizard would otherwise try to validate step 1 with a null
		// token and surface a confusing backend rejection.
		seedProgress({
			stepIndex: 1,
			progressToken: null,
			completions: [],
			progressTokens: [[0, 'tok-0']]
		});

		render(WizardShell, { props: { wizard, onComplete: vi.fn() } });

		expectOnStep(1, 2);
		expect(mockSessionStorage.removeItem).toHaveBeenCalledWith(PROGRESS_KEY);
	});

	it('discards non-zero stepIndex when current progressToken disagrees with archive', () => {
		const wizard = makeWizard();
		// progressToken (the token to present at step 1) must equal
		// progressTokens.get(0) (the token archived after validating step 0).
		// A mismatch indicates tampered/corrupted storage.
		seedProgress({
			stepIndex: 1,
			progressToken: 'stale-tok',
			completions: [],
			progressTokens: [[0, 'tok-0']]
		});

		render(WizardShell, { props: { wizard, onComplete: vi.fn() } });

		expectOnStep(1, 2);
		expect(mockSessionStorage.removeItem).toHaveBeenCalledWith(PROGRESS_KEY);
	});

	it('discards step-0 saved state when progressToken is non-null', () => {
		const wizard = makeWizard();
		// A legitimate step-0 record always has progressToken: null — the
		// persist $effect only writes a non-null token after handleNext
		// increments currentStepIndex. A non-null token co-existing with
		// stepIndex: 0 therefore indicates tampering or corruption.
		seedProgress({
			stepIndex: 0,
			progressToken: 'tampered-token',
			completions: [],
			progressTokens: []
		});

		render(WizardShell, { props: { wizard, onComplete: vi.fn() } });

		expectOnStep(1, 2);
		expect(mockSessionStorage.removeItem).toHaveBeenCalledWith(PROGRESS_KEY);
		// Persist effect rewrites storage with the safe (reset) state:
		// progressToken back to null.
		expect(persistedProgress()?.progressToken).toBeNull();
	});

	it('discards step-0 saved state when progressTokens map is non-empty', () => {
		const wizard = makeWizard();
		// Same invariant from the opposite angle: progressTokens entries are
		// only written alongside a currentStepIndex increment, so a non-empty
		// map at stepIndex: 0 is a tampering signal. A stale entry at index
		// > 0 would otherwise survive the restore and be picked up by
		// handleBack at a later step.
		seedProgress({
			stepIndex: 0,
			progressToken: null,
			completions: [],
			progressTokens: [[1, 'stale-token']]
		});

		render(WizardShell, { props: { wizard, onComplete: vi.fn() } });

		expectOnStep(1, 2);
		expect(mockSessionStorage.removeItem).toHaveBeenCalledWith(PROGRESS_KEY);
		// Persist effect rewrites storage with the safe (reset) state:
		// empty progressTokens.
		expect(persistedProgress()?.progressTokens).toEqual([]);
	});

	it('discards saved state with completion for a step beyond savedIndex', () => {
		const wizard = makeWizard();
		// savedIndex: 0 means the user has only reached step 0. A completion
		// entry for STEP_1_ID (index 1) is therefore tampered or corrupted —
		// the persist $effect only writes completion data for steps the user
		// has actually reached. Accepting it would pre-arm the
		// alreadyCompleted path at step 1 and let the user bypass that
		// step's interaction UX (e.g. timer countdown, TOS acknowledgement).
		seedProgress({
			stepIndex: 0,
			progressToken: null,
			completions: [
				[
					STEP_1_ID,
					[
						[
							INTERACTION_A,
							{
								interactionId: INTERACTION_A,
								interactionType: 'click',
								data: { acknowledged: true },
								completedAt: '2024-01-01T00:00:00Z'
							}
						]
					]
				]
			],
			progressTokens: []
		});

		render(WizardShell, { props: { wizard, onComplete: vi.fn() } });

		expectOnStep(1, 2);
		expect(mockSessionStorage.removeItem).toHaveBeenCalledWith(PROGRESS_KEY);
		// Persist effect rewrites storage with the safe (reset) state:
		// empty completions, untouched by the future-step entry.
		expect(persistedProgress()?.completions).toEqual([]);
	});

	it('discards malformed JSON', () => {
		mockSessionStorage._set(PROGRESS_KEY, 'not-json');

		render(WizardShell, { props: { wizard: makeWizard(), onComplete: vi.fn() } });

		expectOnStep(1, 2);
		expect(mockSessionStorage.removeItem).toHaveBeenCalledWith(PROGRESS_KEY);
	});

	it('clears the language key alongside discarded progress', () => {
		const wizard = makeWizard();
		mockSessionStorage._set(LANGUAGE_KEY, 'de');
		seedProgress({ stepIndex: 999 });

		render(WizardShell, { props: { wizard, onComplete: vi.fn() } });

		expect(mockSessionStorage.removeItem).toHaveBeenCalledWith(LANGUAGE_KEY);
	});

	it('resets in-memory selectedLanguage alongside discarded progress', () => {
		// Symmetry with handleNext's fallback: discard() must clear both the
		// `-language` storage key AND the in-memory `selectedLanguage` state.
		// Without this, the language restore $effect (declared first) seeds
		// `selectedLanguage = "fr"`, the progress restore $effect's discard
		// removes the storage key but leaves `selectedLanguage` populated, and
		// the wizard renders in French until the next page reload.
		const wizard: WizardDetailResponse = {
			...makeWizard(),
			steps: [
				{
					id: STEP_0_ID,
					wizard_id: WIZARD_ID,
					step_order: 0,
					title: 'Primary title',
					content_markdown: 'primary body',
					primary_language: 'en',
					translations: [
						{
							language_code: 'fr',
							title: 'Titre traduit',
							content_markdown: 'corps traduit'
						}
					],
					interactions: [],
					created_at: '2024-01-01T00:00:00Z',
					updated_at: null
				}
			]
		} as WizardDetailResponse;

		mockSessionStorage._set(LANGUAGE_KEY, 'fr');
		// Trigger discard() via an out-of-range stepIndex.
		seedProgress({ stepIndex: 999 });

		render(WizardShell, { props: { wizard, onComplete: vi.fn() } });

		// After discard, selectedLanguage is null and effectiveLanguage falls
		// back to the step's primary language ("en"). The rendered title and
		// content are the primary-language strings, not the seeded "fr".
		// (WizardProgress also surfaces the step title, so getAllByText is
		// the right query for the title; the markdown body appears once.)
		expect(screen.getAllByText('Primary title').length).toBeGreaterThan(0);
		expect(screen.queryByText('Titre traduit')).not.toBeInTheDocument();
		expect(screen.getByText('primary body')).toBeInTheDocument();
		expect(screen.queryByText('corps traduit')).not.toBeInTheDocument();
	});
});

describe('wizard-shell handleNext dead-button fallback', () => {
	it('round-trips: completing the required interaction enables and advances Next', async () => {
		const wizard = makeWizard();
		const onComplete = vi.fn();

		render(WizardShell, { props: { wizard, onComplete } });

		const next = screen.getByRole('button', { name: /Next/i });
		expect(next).toBeDisabled();

		// Complete the click interaction.
		const ack = screen.getByRole('button', { name: /I Understand/i });
		await fireEvent.click(ack);

		const nextEnabled = screen.getByRole('button', { name: /Next/i });
		expect(nextEnabled).not.toBeDisabled();

		await fireEvent.click(nextEnabled);

		// Wait for validateStep promise + state update.
		await new Promise((resolve) => setTimeout(resolve, 0));
		await Promise.resolve();

		expectOnStep(2, 2);
	});

	it('surfaces an error and resets storage when handleNext sees no current step', async () => {
		// Empty-steps wizard: currentStep is always undefined, canProceed is
		// vacuously true, Next renders enabled, and clicking it would otherwise
		// be a silent no-op. The defensive fallback should clear progress and
		// surface a validation message.
		const wizard: WizardDetailResponse = {
			id: WIZARD_ID,
			name: 'Empty wizard',
			enabled: true,
			created_at: '2024-01-01T00:00:00Z',
			updated_at: null,
			description: null,
			steps: []
		};
		mockSessionStorage._set(PROGRESS_KEY, '{"stepIndex": 0}');

		render(WizardShell, { props: { wizard, onComplete: vi.fn() } });

		const next = screen.getByRole('button', { name: /Next/i });
		await fireEvent.click(next);

		await new Promise((resolve) => setTimeout(resolve, 0));

		expect(screen.getByText(/Your progress was reset/i)).toBeInTheDocument();
		expect(mockSessionStorage.removeItem).toHaveBeenCalledWith(PROGRESS_KEY);
	});
});
