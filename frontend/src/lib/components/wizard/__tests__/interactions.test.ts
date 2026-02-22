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
 * Requirements: 4.1-4.3, 5.1-5.5, 6.1-6.4, 7.1-7.5, 8.1-8.5
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
// Requirements: 4.1, 4.2, 4.3, 12.1
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
// Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 12.2
// =============================================================================

describe('TimerInteraction', () => {
	beforeEach(() => {
		vi.useFakeTimers();
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

	it('should have disabled button while timer is counting down', () => {
		const props = createInteractionProps({ duration_seconds: 10 });

		render(TimerInteraction, { props });

		const button = screen.getByRole('button', { name: 'Please wait...' });
		expect(button).toBeDisabled();
	});

	it('should enable button when timer completes', async () => {
		const props = createInteractionProps({ duration_seconds: 3 });

		render(TimerInteraction, { props });

		// Advance timer to completion (need to advance one tick at a time for Svelte reactivity)
		for (let i = 0; i < 3; i++) {
			await vi.advanceTimersByTimeAsync(1000);
		}

		const button = screen.getByRole('button', { name: 'Continue' });
		expect(button).not.toBeDisabled();
	});

	it('should call onComplete with waited data when button clicked after timer', async () => {
		const onComplete = vi.fn();
		const props = createInteractionProps({ duration_seconds: 2 }, { onComplete });

		render(TimerInteraction, { props });

		// Advance timer to completion
		for (let i = 0; i < 2; i++) {
			await vi.advanceTimersByTimeAsync(1000);
		}

		const button = screen.getByRole('button', { name: 'Continue' });
		await fireEvent.click(button);

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
});

// =============================================================================
// TOS Interaction Tests
// Requirements: 6.1, 6.2, 6.3, 6.4, 12.3
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
// Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 12.4
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
// Requirements: 8.1, 8.2, 8.3, 12.5
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
// Requirements: 8.4, 8.5
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
});
