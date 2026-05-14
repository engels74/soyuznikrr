/**
 * Unit tests for wizard interaction components.
 *
 * Tests core functionality for each interaction type:
 * - Click interaction button rendering
 * - Timer countdown and button state
 * - TOS checkbox requirement
 * - Text input validation
 * - Quiz option selection
 *
 * @module $lib/components/wizard/__tests__/interactions.test
 */

import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, type Mock, vi } from 'vitest';
import ClickInteraction from '../interactions/click-interaction.svelte';
import QuizInteraction from '../interactions/quiz-interaction.svelte';
import type { InteractionComponentProps } from '../interactions/registry';
import TextInputInteraction from '../interactions/text-input-interaction.svelte';
import TimerInteraction from '../interactions/timer-interaction.svelte';
import TosInteraction from '../interactions/tos-interaction.svelte';

// =============================================================================
// Test Fixtures
// =============================================================================

function createInteractionProps(
	config: Record<string, unknown> = {},
	overrides: Partial<InteractionComponentProps> = {}
): InteractionComponentProps {
	return {
		interactionId: 'test-interaction-id',
		config,
		onComplete: vi.fn(),
		disabled: false,
		...overrides
	};
}

// =============================================================================
// Click Interaction Tests
// =============================================================================

describe('ClickInteraction', () => {
	it('should render confirmation button with default text', () => {
		const props = createInteractionProps({});

		render(ClickInteraction, { props });

		const button = screen.getByRole('button', { name: 'I Understand' });
		expect(button).toBeInTheDocument();
	});

	it('should render confirmation button with custom text', () => {
		const props = createInteractionProps({ button_text: 'Got it!' });

		render(ClickInteraction, { props });

		const button = screen.getByRole('button', { name: 'Got it!' });
		expect(button).toBeInTheDocument();
	});

	it('should call onComplete with acknowledgment data when clicked', async () => {
		const onComplete = vi.fn();
		const props = createInteractionProps({}, { onComplete });

		render(ClickInteraction, { props });

		const button = screen.getByRole('button', { name: 'I Understand' });
		await fireEvent.click(button);

		expect(onComplete).toHaveBeenCalledTimes(1);
		expect(onComplete).toHaveBeenCalledWith(
			expect.objectContaining({
				interactionId: 'test-interaction-id',
				interactionType: 'click',
				data: { acknowledged: true },
				completedAt: expect.any(String)
			})
		);
	});

	it('should be disabled when disabled prop is true', () => {
		const props = createInteractionProps({}, { disabled: true });

		render(ClickInteraction, { props });

		const button = screen.getByRole('button', { name: 'I Understand' });
		expect(button).toBeDisabled();
	});
});

// =============================================================================
// Timer Interaction Tests
// =============================================================================

describe('TimerInteraction', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		// Real jsdom sessionStorage carries state across tests in the suite —
		// reset it so the per-scope key assertions below see a clean slate.
		try {
			sessionStorage.clear();
		} catch {
			/* ignore */
		}
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('should render countdown timer with initial duration', () => {
		const props = createInteractionProps({ duration_seconds: 10 });

		render(TimerInteraction, { props });

		// Should show initial time (0:10)
		expect(screen.getByText('0:10')).toBeInTheDocument();
	});

	it('should not show completion status while timer is counting down', () => {
		const props = createInteractionProps({ duration_seconds: 10 });

		render(TimerInteraction, { props });

		expect(screen.queryByText('Timer complete')).not.toBeInTheDocument();
	});

	it('should show completion status when timer completes', async () => {
		const props = createInteractionProps({ duration_seconds: 3 });

		render(TimerInteraction, { props });

		// Advance timer to completion (need to advance one tick at a time for Svelte reactivity)
		for (let i = 0; i < 3; i++) {
			await vi.advanceTimersByTimeAsync(1000);
		}

		expect(screen.getByText('Timer complete')).toBeInTheDocument();
	});

	it('should auto-call onComplete when timer reaches zero', async () => {
		const onComplete = vi.fn();
		const props = createInteractionProps({ duration_seconds: 2 }, { onComplete });

		render(TimerInteraction, { props });

		// Advance timer to completion
		for (let i = 0; i < 2; i++) {
			await vi.advanceTimersByTimeAsync(1000);
		}

		// The interval callback auto-completes; the $effect re-emission is deferred
		// via setTimeout so it won't fire synchronously in this test
		expect(onComplete).toHaveBeenCalledTimes(1);
		expect(onComplete).toHaveBeenCalledWith(
			expect.objectContaining({
				interactionId: 'test-interaction-id',
				interactionType: 'timer',
				data: { waited: true },
				startedAt: expect.any(String),
				completedAt: expect.any(String)
			})
		);
	});

	it('should use default duration when not specified', () => {
		const props = createInteractionProps({});

		render(TimerInteraction, { props });

		// Default is 10 seconds
		expect(screen.getByText('0:10')).toBeInTheDocument();
	});

	it('should complete based on wall-clock time, not number of interval ticks', async () => {
		const onComplete = vi.fn();
		const props = createInteractionProps({ duration_seconds: 5 }, { onComplete });

		render(TimerInteraction, { props });

		// Jump the wall clock past the deadline without firing N interval ticks.
		// Simulates Safari pausing setInterval while wall-clock time elapses.
		vi.setSystemTime(Date.now() + 5000);

		// A single subsequent tick is enough — recompute reads Date.now() and
		// sees the deadline has passed, regardless of how many ticks were missed.
		await vi.advanceTimersByTimeAsync(1000);

		expect(onComplete).toHaveBeenCalledTimes(1);
	});

	it('should fire onComplete on visibilitychange when the deadline has passed', async () => {
		const onComplete = vi.fn();
		const props = createInteractionProps({ duration_seconds: 10 }, { onComplete });

		render(TimerInteraction, { props });

		// Simulate the tab being backgrounded for 30s — no interval ticks
		// because Safari/iOS throttles them in background tabs.
		vi.setSystemTime(Date.now() + 30_000);

		// Tab returns to foreground.
		document.dispatchEvent(new Event('visibilitychange'));

		// Flush the deferred setTimeout(0) inside the auto-emit $effect.
		await vi.advanceTimersByTimeAsync(0);

		expect(onComplete).toHaveBeenCalledTimes(1);
	});

	it('should fire onComplete exactly once even after extra ticks past the deadline', async () => {
		const onComplete = vi.fn();
		const props = createInteractionProps({ duration_seconds: 2 }, { onComplete });

		render(TimerInteraction, { props });

		// Advance well past completion. With the legacy tick-decrement
		// implementation, the safeguard $effect could re-emit; with the
		// deadline-based implementation, recompute observing the same `0`
		// repeatedly does not trigger reactivity.
		for (let i = 0; i < 5; i++) {
			await vi.advanceTimersByTimeAsync(1000);
		}

		expect(onComplete).toHaveBeenCalledTimes(1);
	});

	it('should render "Timer complete" immediately when navigating back to a completed step', () => {
		const onComplete = vi.fn();
		const props = createInteractionProps(
			{ duration_seconds: 10 },
			{
				onComplete,
				completionData: {
					interactionId: 'test-interaction-id',
					interactionType: 'timer',
					data: { waited: true },
					startedAt: '2024-01-01T00:00:00Z',
					completedAt: '2024-01-01T00:00:10Z'
				}
			}
		);

		render(TimerInteraction, { props });

		// Renders complete state immediately, without arming a new countdown
		// or re-emitting onComplete.
		expect(screen.getByText('Timer complete')).toBeInTheDocument();
		expect(onComplete).not.toHaveBeenCalled();
	});

	it('should clear the countdown when completionData arrives after mount', async () => {
		// Mid-wizard refresh: child mounts with completionData undefined and
		// arms its interval; wizard-shell's session-restore $effect then flips
		// completionData to a saved {waited:true} record. The synchronisation
		// $effect must zero the display and clear the interval, otherwise the
		// UI reads e.g. "0:09 remaining" while Next is already enabled.
		const onComplete = vi.fn();
		const props = createInteractionProps({ duration_seconds: 10 }, { onComplete });

		const { rerender } = render(TimerInteraction, { props });

		// Mounts armed: countdown is still showing the initial duration.
		expect(screen.getByText('0:10')).toBeInTheDocument();
		expect(screen.queryByText('Timer complete')).not.toBeInTheDocument();

		// Parent's restore effect populates interactionCompletions.
		await rerender({
			...props,
			completionData: {
				interactionId: 'test-interaction-id',
				interactionType: 'timer',
				data: { waited: true },
				startedAt: '2024-01-01T00:00:00Z',
				completedAt: '2024-01-01T00:00:10Z'
			}
		});

		// Display is forced to 0:00 / Timer complete; the synchronisation
		// $effect cleared the armed interval, so further wall-clock advances
		// must not produce ticks that reset the display.
		expect(screen.getByText('0:00')).toBeInTheDocument();
		expect(screen.getByText('Timer complete')).toBeInTheDocument();

		// Advance well past the original deadline. With the interval cleared,
		// no recompute() fires and remainingSeconds stays at 0.
		for (let i = 0; i < 15; i++) {
			await vi.advanceTimersByTimeAsync(1000);
		}
		expect(screen.getByText('Timer complete')).toBeInTheDocument();

		// onComplete must not be re-emitted: the parent already holds the
		// completion record (that's how the prop arrived), and recompute()
		// early-returns on alreadyCompleted before it could call fireComplete.
		expect(onComplete).not.toHaveBeenCalled();
	});

	it('should namespace its sessionStorage key with the provided storageScope', () => {
		// Same wizard + interaction can be reached through multiple invitations
		// (the wizard row is shared). Without a per-invite scope, a startedAt
		// written under invite A would be restored under invite B and let the
		// timer auto-complete with a stale anchor.
		const props = createInteractionProps(
			{ duration_seconds: 30 },
			{ interactionId: 'shared-interaction-uuid', storageScope: 'invite-A' }
		);

		render(TimerInteraction, { props });

		// The scoped key holds the timer's startedAt, while the legacy
		// unscoped key remains untouched. Asserts the namespacing rather than
		// the exact value (an ISO timestamp generated at mount time).
		expect(sessionStorage.getItem('wizard-timer-invite-A-shared-interaction-uuid')).not.toBeNull();
		expect(sessionStorage.getItem('wizard-timer-shared-interaction-uuid')).toBeNull();
	});

	it("should not auto-complete from a sibling scope's stale startedAt", async () => {
		// Reviewer scenario: admin attaches Wizard W (with timer I) to two
		// invites. User opens invite A, the timer arms and writes a startedAt;
		// the tab closes mid-countdown so fireComplete never deletes the key.
		// User then opens invite B in the same browser session. Under the
		// pre-fix key (`wizard-timer-<I>`), the new mount would restore the
		// stale anchor and — if 30s of wall-clock time has passed — fire
		// onComplete immediately with the stale startedAt.

		const sharedInteractionId = 'shared-interaction-uuid';

		// Simulate invite A's leftover entry. The duration is 30s and we
		// advance the wall clock by >30s before mounting invite B, so a leaky
		// key would auto-complete on mount.
		const staleStartedAt = new Date(Date.now()).toISOString();
		sessionStorage.setItem(`wizard-timer-invite-A-${sharedInteractionId}`, staleStartedAt);

		// Skip the wall clock past the duration so a leaky read would trip
		// the immediate-completion path.
		vi.setSystemTime(Date.now() + 60_000);

		const onComplete = vi.fn();
		const propsB = createInteractionProps(
			{ duration_seconds: 30 },
			{
				interactionId: sharedInteractionId,
				storageScope: 'invite-B',
				onComplete
			}
		);

		render(TimerInteraction, { props: propsB });

		// Flush the initial recompute() inside onMount.
		await vi.advanceTimersByTimeAsync(0);

		// Invite B must NOT see invite A's startedAt: it writes its own
		// (fresh-anchored) entry under its scoped key, leaves invite A's
		// key alone, and does not fire onComplete on mount.
		expect(onComplete).not.toHaveBeenCalled();
		expect(sessionStorage.getItem(`wizard-timer-invite-A-${sharedInteractionId}`)).toBe(
			staleStartedAt
		);
		const inviteBKey = sessionStorage.getItem(`wizard-timer-invite-B-${sharedInteractionId}`);
		expect(inviteBKey).not.toBeNull();
		expect(inviteBKey).not.toBe(staleStartedAt);

		// Countdown still shows the full duration: a stale anchor would have
		// driven it to 0:00 immediately.
		expect(screen.getByText('0:30')).toBeInTheDocument();
	});
});

// =============================================================================
// TOS Interaction Tests
// =============================================================================

describe('TosInteraction', () => {
	it('should render checkbox with default label', () => {
		const props = createInteractionProps({});

		render(TosInteraction, { props });

		expect(screen.getByText('I accept the terms of service')).toBeInTheDocument();
	});

	it('should render checkbox with custom label', () => {
		const props = createInteractionProps({
			checkbox_label: 'I agree to the rules'
		});

		render(TosInteraction, { props });

		expect(screen.getByText('I agree to the rules')).toBeInTheDocument();
	});

	it('should have disabled accept button when checkbox is not checked', () => {
		const props = createInteractionProps({});

		render(TosInteraction, { props });

		const acceptButton = screen.getByRole('button', {
			name: 'Accept & Continue'
		});
		expect(acceptButton).toBeDisabled();
	});

	it('should enable accept button when checkbox is checked', async () => {
		const props = createInteractionProps({});

		render(TosInteraction, { props });

		const checkbox = screen.getByRole('checkbox');
		await fireEvent.click(checkbox);

		const acceptButton = screen.getByRole('button', {
			name: 'Accept & Continue'
		});
		expect(acceptButton).not.toBeDisabled();
	});

	it('should call onComplete with acceptance data when accepted', async () => {
		const onComplete = vi.fn();
		const props = createInteractionProps({}, { onComplete });

		render(TosInteraction, { props });

		const checkbox = screen.getByRole('checkbox');
		await fireEvent.click(checkbox);

		const acceptButton = screen.getByRole('button', {
			name: 'Accept & Continue'
		});
		await fireEvent.click(acceptButton);

		expect(onComplete).toHaveBeenCalledTimes(1);
		expect(onComplete).toHaveBeenCalledWith(
			expect.objectContaining({
				interactionId: 'test-interaction-id',
				interactionType: 'tos',
				data: {
					accepted: true,
					accepted_at: expect.any(String)
				}
			})
		);
	});
});

// =============================================================================
// Text Input Interaction Tests
// =============================================================================

describe('TextInputInteraction', () => {
	it('should render labeled input with default label', () => {
		const props = createInteractionProps({});

		render(TextInputInteraction, { props });

		expect(screen.getByLabelText('Your response')).toBeInTheDocument();
	});

	it('should render labeled input with custom label', () => {
		const props = createInteractionProps({ label: 'Enter your name' });

		render(TextInputInteraction, { props });

		expect(screen.getByLabelText('Enter your name')).toBeInTheDocument();
	});

	it('should render input with placeholder', () => {
		const props = createInteractionProps({
			label: 'Name',
			placeholder: 'John Doe'
		});

		render(TextInputInteraction, { props });

		const input = screen.getByPlaceholderText('John Doe');
		expect(input).toBeInTheDocument();
	});

	it('should have disabled submit button when required field is empty', () => {
		const props = createInteractionProps({
			label: 'Name',
			required: true
		});

		render(TextInputInteraction, { props });

		const submitButton = screen.getByRole('button', { name: 'Continue' });
		expect(submitButton).toBeDisabled();
	});

	it('should enable submit button when required field has value', async () => {
		const props = createInteractionProps({
			label: 'Name',
			required: true
		});

		render(TextInputInteraction, { props });

		const input = screen.getByLabelText('Name');
		await fireEvent.input(input, { target: { value: 'Test User' } });

		const submitButton = screen.getByRole('button', { name: 'Continue' });
		expect(submitButton).not.toBeDisabled();
	});

	it('should show validation error for min_length violation', async () => {
		const props = createInteractionProps({
			label: 'Name',
			min_length: 5
		});

		render(TextInputInteraction, { props });

		const input = screen.getByLabelText('Name');
		await fireEvent.input(input, { target: { value: 'abc' } });
		await fireEvent.blur(input);

		expect(screen.getByText('Must be at least 5 characters')).toBeInTheDocument();
	});

	it('should show validation error for max_length violation', async () => {
		const props = createInteractionProps({
			label: 'Name',
			max_length: 5
		});

		render(TextInputInteraction, { props });

		const input = screen.getByLabelText('Name');
		await fireEvent.input(input, { target: { value: 'abcdefgh' } });
		await fireEvent.blur(input);

		expect(screen.getByText('Must be at most 5 characters')).toBeInTheDocument();
	});

	it('should call onComplete with text data when submitted', async () => {
		const onComplete = vi.fn();
		const props = createInteractionProps({ label: 'Name' }, { onComplete });

		render(TextInputInteraction, { props });

		const input = screen.getByLabelText('Name');
		await fireEvent.input(input, { target: { value: 'Test User' } });

		const submitButton = screen.getByRole('button', { name: 'Continue' });
		await fireEvent.click(submitButton);

		expect(onComplete).toHaveBeenCalledTimes(1);
		expect(onComplete).toHaveBeenCalledWith(
			expect.objectContaining({
				interactionId: 'test-interaction-id',
				interactionType: 'text_input',
				data: { text: 'Test User' }
			})
		);
	});
});

// =============================================================================
// Quiz Interaction Tests
// =============================================================================

describe('QuizInteraction', () => {
	it('should render question and options', () => {
		const props = createInteractionProps({
			question: 'What is 2 + 2?',
			options: ['3', '4', '5'],
			correct_answer_index: 1
		});

		render(QuizInteraction, { props });

		expect(screen.getByText('What is 2 + 2?')).toBeInTheDocument();
		expect(screen.getByText('3')).toBeInTheDocument();
		expect(screen.getByText('4')).toBeInTheDocument();
		expect(screen.getByText('5')).toBeInTheDocument();
	});

	it('should have disabled submit button when no option is selected', () => {
		const props = createInteractionProps({
			question: 'What is 2 + 2?',
			options: ['3', '4', '5'],
			correct_answer_index: 1
		});

		render(QuizInteraction, { props });

		const submitButton = screen.getByRole('button', { name: 'Submit Answer' });
		expect(submitButton).toBeDisabled();
	});

	it('should enable submit button when an option is selected', async () => {
		const props = createInteractionProps({
			question: 'What is 2 + 2?',
			options: ['3', '4', '5'],
			correct_answer_index: 1
		});

		render(QuizInteraction, { props });

		const option = screen.getByRole('radio', { name: '4' });
		await fireEvent.click(option);

		const submitButton = screen.getByRole('button', { name: 'Submit Answer' });
		expect(submitButton).not.toBeDisabled();
	});

	it('should call onComplete with selected answer_index when submitted', async () => {
		const onComplete = vi.fn();
		const props = createInteractionProps(
			{
				question: 'What is 2 + 2?',
				options: ['3', '4', '5'],
				correct_answer_index: 1
			},
			{ onComplete }
		);

		render(QuizInteraction, { props });

		const option = screen.getByRole('radio', { name: '4' });
		await fireEvent.click(option);

		const submitButton = screen.getByRole('button', { name: 'Submit Answer' });
		await fireEvent.click(submitButton);

		expect(onComplete).toHaveBeenCalledTimes(1);
		expect(onComplete).toHaveBeenCalledWith(
			expect.objectContaining({
				interactionId: 'test-interaction-id',
				interactionType: 'quiz',
				data: { answer_index: 1 }
			})
		);
	});

	it('should allow changing selection before submitting', async () => {
		const onComplete = vi.fn();
		const props = createInteractionProps(
			{
				question: 'What is 2 + 2?',
				options: ['3', '4', '5'],
				correct_answer_index: 1
			},
			{ onComplete }
		);

		render(QuizInteraction, { props });

		// Select first option
		const option1 = screen.getByRole('radio', { name: '3' });
		await fireEvent.click(option1);
		expect(option1).toHaveAttribute('aria-checked', 'true');

		// Change to second option
		const option2 = screen.getByRole('radio', { name: '4' });
		await fireEvent.click(option2);
		expect(option2).toHaveAttribute('aria-checked', 'true');
		expect(option1).toHaveAttribute('aria-checked', 'false');

		// Submit
		const submitButton = screen.getByRole('button', { name: 'Submit Answer' });
		await fireEvent.click(submitButton);

		expect(onComplete).toHaveBeenCalledWith(
			expect.objectContaining({
				data: { answer_index: 1 }
			})
		);
	});
});

// =============================================================================
// Quiz Interaction Tests — onValidate (backend validation)
// =============================================================================

describe('QuizInteraction with onValidate', () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('should show "Correct!" feedback when onValidate returns valid', async () => {
		const onValidate = vi.fn().mockResolvedValue({ valid: true });
		const onComplete = vi.fn();
		const props = createInteractionProps(
			{
				question: 'What is 2 + 2?',
				options: ['3', '4', '5'],
				correct_answer_index: 1
			},
			{ onComplete, onValidate }
		);

		render(QuizInteraction, { props });

		const option = screen.getByRole('radio', { name: '4' });
		await fireEvent.click(option);

		const submitButton = screen.getByRole('button', { name: 'Submit Answer' });
		await fireEvent.click(submitButton);

		// Wait for async onValidate to resolve
		await vi.waitFor(() => {
			expect(screen.getByText('Correct!')).toBeInTheDocument();
		});

		// Submit button should be hidden after correct answer
		expect(screen.queryByRole('button', { name: 'Submit Answer' })).not.toBeInTheDocument();
	});

	it('should show error feedback when onValidate returns invalid', async () => {
		const onValidate = vi.fn().mockResolvedValue({ valid: false, error: 'Wrong answer!' });
		const onComplete = vi.fn();
		const props = createInteractionProps(
			{
				question: 'What is 2 + 2?',
				options: ['3', '4', '5'],
				correct_answer_index: 1
			},
			{ onComplete, onValidate }
		);

		render(QuizInteraction, { props });

		const option = screen.getByRole('radio', { name: '3' });
		await fireEvent.click(option);

		const submitButton = screen.getByRole('button', { name: 'Submit Answer' });
		await fireEvent.click(submitButton);

		// Wait for async onValidate to resolve
		await vi.waitFor(() => {
			expect(screen.getByText(/Wrong answer!/)).toBeInTheDocument();
		});
	});

	it('should start cooldown after wrong answer and disable options', async () => {
		const onValidate = vi.fn().mockResolvedValue({ valid: false, error: 'Incorrect' });
		const props = createInteractionProps(
			{
				question: 'What is 2 + 2?',
				options: ['3', '4', '5'],
				correct_answer_index: 1
			},
			{ onComplete: vi.fn(), onValidate }
		);

		render(QuizInteraction, { props });

		const option = screen.getByRole('radio', { name: '3' });
		await fireEvent.click(option);

		const submitButton = screen.getByRole('button', { name: 'Submit Answer' });
		await fireEvent.click(submitButton);

		// Wait for validation to complete and cooldown to start
		await vi.waitFor(() => {
			expect(screen.getByRole('button', { name: /Wait 3s/i })).toBeInTheDocument();
		});

		// Options should be disabled during cooldown
		const allOptions = screen.getAllByRole('radio');
		for (const opt of allOptions) {
			expect(opt).toBeDisabled();
		}

		// Advance through cooldown
		for (let i = 0; i < 3; i++) {
			await vi.advanceTimersByTimeAsync(1000);
		}

		// After cooldown, options should be re-enabled
		await vi.waitFor(() => {
			const opts = screen.getAllByRole('radio');
			for (const opt of opts) {
				expect(opt).not.toBeDisabled();
			}
		});
	});

	it('should clear error feedback when selecting a new option after wrong answer', async () => {
		const onValidate = vi.fn().mockResolvedValue({ valid: false, error: 'Incorrect' });
		const props = createInteractionProps(
			{
				question: 'What is 2 + 2?',
				options: ['3', '4', '5'],
				correct_answer_index: 1
			},
			{ onComplete: vi.fn(), onValidate }
		);

		render(QuizInteraction, { props });

		// Select wrong answer and submit
		const option1 = screen.getByRole('radio', { name: '3' });
		await fireEvent.click(option1);

		const submitButton = screen.getByRole('button', { name: 'Submit Answer' });
		await fireEvent.click(submitButton);

		// Wait for error to appear
		await vi.waitFor(() => {
			expect(screen.getByText(/Incorrect/)).toBeInTheDocument();
		});

		// Advance through cooldown so options re-enable
		for (let i = 0; i < 3; i++) {
			await vi.advanceTimersByTimeAsync(1000);
		}

		// Select a different option — error should clear
		const option2 = screen.getByRole('radio', { name: '4' });
		await fireEvent.click(option2);

		expect(screen.queryByText(/Incorrect/)).not.toBeInTheDocument();
	});

	it('should not call onComplete directly when onValidate is provided', async () => {
		const onValidate = vi.fn().mockResolvedValue({ valid: true });
		const onComplete = vi.fn();
		const props = createInteractionProps(
			{
				question: 'What is 2 + 2?',
				options: ['3', '4', '5'],
				correct_answer_index: 1
			},
			{ onComplete, onValidate }
		);

		render(QuizInteraction, { props });

		const option = screen.getByRole('radio', { name: '4' });
		await fireEvent.click(option);

		const submitButton = screen.getByRole('button', { name: 'Submit Answer' });
		await fireEvent.click(submitButton);

		await vi.waitFor(() => {
			expect(screen.getByText('Correct!')).toBeInTheDocument();
		});

		// onComplete should NOT be called directly — the shell's onValidate handler calls it
		expect(onComplete).not.toHaveBeenCalled();
		// But onValidate should have been called
		expect(onValidate).toHaveBeenCalledTimes(1);
	});

	it('should increase cooldown duration with repeated wrong answers', async () => {
		let callCount = 0;
		const onValidate = vi.fn().mockImplementation(async () => {
			callCount++;
			return { valid: false, error: `Wrong #${callCount}` };
		});
		const props = createInteractionProps(
			{
				question: 'What is 2 + 2?',
				options: ['3', '4', '5'],
				correct_answer_index: 1
			},
			{ onComplete: vi.fn(), onValidate }
		);

		render(QuizInteraction, { props });

		// First wrong attempt — 3s cooldown
		const option = screen.getByRole('radio', { name: '3' });
		await fireEvent.click(option);
		await fireEvent.click(screen.getByRole('button', { name: 'Submit Answer' }));

		await vi.waitFor(() => {
			expect(screen.getByRole('button', { name: /Wait 3s/i })).toBeInTheDocument();
		});

		// Advance through first cooldown
		for (let i = 0; i < 3; i++) {
			await vi.advanceTimersByTimeAsync(1000);
		}

		// Second wrong attempt — 5s cooldown
		const option2 = screen.getByRole('radio', { name: '5' });
		await fireEvent.click(option2);
		await fireEvent.click(screen.getByRole('button', { name: 'Submit Answer' }));

		await vi.waitFor(() => {
			expect(screen.getByRole('button', { name: /Wait 5s/i })).toBeInTheDocument();
		});

		expect((onValidate as Mock).mock.calls.length).toBe(2);
	});

	it('should not show "Correct!" when onValidate returns valid with pending', async () => {
		const onValidate = vi.fn().mockResolvedValue({ valid: true, pending: true });
		const onComplete = vi.fn();
		const props = createInteractionProps(
			{
				question: 'What is 2 + 2?',
				options: ['3', '4', '5'],
				correct_answer_index: 1
			},
			{ onComplete, onValidate }
		);

		render(QuizInteraction, { props });

		const option = screen.getByRole('radio', { name: '4' });
		await fireEvent.click(option);

		const submitButton = screen.getByRole('button', { name: 'Submit Answer' });
		await fireEvent.click(submitButton);

		// Wait for async onValidate to resolve
		await vi.waitFor(() => {
			// isSubmitting should be false (finally block ran)
			expect(screen.getByRole('button', { name: 'Submit Answer' })).toBeInTheDocument();
		});

		// "Correct!" should NOT appear — answer is pending backend validation
		expect(screen.queryByText('Correct!')).not.toBeInTheDocument();

		// Submit button should still be visible (feedbackState is not "correct")
		expect(screen.getByRole('button', { name: 'Submit Answer' })).not.toBeDisabled();

		// onComplete should not have been called
		expect(onComplete).not.toHaveBeenCalled();
	});
});
