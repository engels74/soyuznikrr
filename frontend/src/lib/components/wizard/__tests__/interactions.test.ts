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
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { WizardStepResponse } from '$lib/api/client';
import ClickInteraction from '../interactions/click-interaction.svelte';
import QuizInteraction from '../interactions/quiz-interaction.svelte';
import TextInputInteraction from '../interactions/text-input-interaction.svelte';
import TimerInteraction from '../interactions/timer-interaction.svelte';
import TosInteraction from '../interactions/tos-interaction.svelte';

// =============================================================================
// Test Fixtures
// =============================================================================

function createMockStep(
	interactionType: string,
	config: { [key: string]: string | number | boolean | string[] | null } = {}
): WizardStepResponse {
	return {
		id: 'test-step-id',
		wizard_id: 'test-wizard-id',
		step_order: 0,
		interaction_type: interactionType as WizardStepResponse['interaction_type'],
		title: 'Test Step',
		content_markdown: 'Test content',
		config,
		created_at: new Date().toISOString()
	};
}

// =============================================================================
// Click Interaction Tests
// Requirements: 4.1, 4.2, 4.3, 12.1
// =============================================================================

describe('ClickInteraction', () => {
	it('should render confirmation button with default text', () => {
		const step = createMockStep('click', {});
		const onComplete = vi.fn();

		render(ClickInteraction, { props: { step, onComplete } });

		const button = screen.getByRole('button', { name: 'I Understand' });
		expect(button).toBeInTheDocument();
	});

	it('should render confirmation button with custom text', () => {
		const step = createMockStep('click', { button_text: 'Got it!' });
		const onComplete = vi.fn();

		render(ClickInteraction, { props: { step, onComplete } });

		const button = screen.getByRole('button', { name: 'Got it!' });
		expect(button).toBeInTheDocument();
	});

	it('should call onComplete with acknowledgment data when clicked', async () => {
		const step = createMockStep('click', {});
		const onComplete = vi.fn();

		render(ClickInteraction, { props: { step, onComplete } });

		const button = screen.getByRole('button', { name: 'I Understand' });
		await fireEvent.click(button);

		expect(onComplete).toHaveBeenCalledTimes(1);
		expect(onComplete).toHaveBeenCalledWith(
			expect.objectContaining({
				stepId: 'test-step-id',
				interactionType: 'click',
				data: { acknowledged: true },
				completedAt: expect.any(String)
			})
		);
	});

	it('should be disabled when disabled prop is true', () => {
		const step = createMockStep('click', {});
		const onComplete = vi.fn();

		render(ClickInteraction, { props: { step, onComplete, disabled: true } });

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
		const step = createMockStep('timer', { duration_seconds: 10 });
		const onComplete = vi.fn();

		render(TimerInteraction, { props: { step, onComplete } });

		// Should show initial time (0:10)
		expect(screen.getByText('0:10')).toBeInTheDocument();
	});

	it('should have disabled button while timer is counting down', () => {
		const step = createMockStep('timer', { duration_seconds: 10 });
		const onComplete = vi.fn();

		render(TimerInteraction, { props: { step, onComplete } });

		const button = screen.getByRole('button', { name: 'Please wait...' });
		expect(button).toBeDisabled();
	});

	it('should enable button when timer completes', async () => {
		const step = createMockStep('timer', { duration_seconds: 3 });
		const onComplete = vi.fn();

		render(TimerInteraction, { props: { step, onComplete } });

		// Advance timer to completion (need to advance one tick at a time for Svelte reactivity)
		for (let i = 0; i < 3; i++) {
			await vi.advanceTimersByTimeAsync(1000);
		}

		const button = screen.getByRole('button', { name: 'Continue' });
		expect(button).not.toBeDisabled();
	});

	it('should call onComplete with waited data when button clicked after timer', async () => {
		const step = createMockStep('timer', { duration_seconds: 2 });
		const onComplete = vi.fn();

		render(TimerInteraction, { props: { step, onComplete } });

		// Advance timer to completion
		for (let i = 0; i < 2; i++) {
			await vi.advanceTimersByTimeAsync(1000);
		}

		const button = screen.getByRole('button', { name: 'Continue' });
		await fireEvent.click(button);

		expect(onComplete).toHaveBeenCalledTimes(1);
		expect(onComplete).toHaveBeenCalledWith(
			expect.objectContaining({
				stepId: 'test-step-id',
				interactionType: 'timer',
				data: { waited: true },
				startedAt: expect.any(String),
				completedAt: expect.any(String)
			})
		);
	});

	it('should use default duration when not specified', () => {
		const step = createMockStep('timer', {});
		const onComplete = vi.fn();

		render(TimerInteraction, { props: { step, onComplete } });

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
		const step = createMockStep('tos', {});
		const onComplete = vi.fn();

		render(TosInteraction, { props: { step, onComplete } });

		expect(screen.getByText('I accept the terms of service')).toBeInTheDocument();
	});

	it('should render checkbox with custom label', () => {
		const step = createMockStep('tos', {
			checkbox_label: 'I agree to the rules'
		});
		const onComplete = vi.fn();

		render(TosInteraction, { props: { step, onComplete } });

		expect(screen.getByText('I agree to the rules')).toBeInTheDocument();
	});

	it('should have disabled accept button when checkbox is not checked', () => {
		const step = createMockStep('tos', {});
		const onComplete = vi.fn();

		render(TosInteraction, { props: { step, onComplete } });

		const acceptButton = screen.getByRole('button', {
			name: 'Accept & Continue'
		});
		expect(acceptButton).toBeDisabled();
	});

	it('should enable accept button when checkbox is checked', async () => {
		const step = createMockStep('tos', {});
		const onComplete = vi.fn();

		render(TosInteraction, { props: { step, onComplete } });

		const checkbox = screen.getByRole('checkbox');
		await fireEvent.click(checkbox);

		const acceptButton = screen.getByRole('button', {
			name: 'Accept & Continue'
		});
		expect(acceptButton).not.toBeDisabled();
	});

	it('should call onComplete with acceptance data when accepted', async () => {
		const step = createMockStep('tos', {});
		const onComplete = vi.fn();

		render(TosInteraction, { props: { step, onComplete } });

		const checkbox = screen.getByRole('checkbox');
		await fireEvent.click(checkbox);

		const acceptButton = screen.getByRole('button', {
			name: 'Accept & Continue'
		});
		await fireEvent.click(acceptButton);

		expect(onComplete).toHaveBeenCalledTimes(1);
		expect(onComplete).toHaveBeenCalledWith(
			expect.objectContaining({
				stepId: 'test-step-id',
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
		const step = createMockStep('text_input', {});
		const onComplete = vi.fn();

		render(TextInputInteraction, { props: { step, onComplete } });

		expect(screen.getByLabelText('Your response')).toBeInTheDocument();
	});

	it('should render labeled input with custom label', () => {
		const step = createMockStep('text_input', { label: 'Enter your name' });
		const onComplete = vi.fn();

		render(TextInputInteraction, { props: { step, onComplete } });

		expect(screen.getByLabelText('Enter your name')).toBeInTheDocument();
	});

	it('should render input with placeholder', () => {
		const step = createMockStep('text_input', {
			label: 'Name',
			placeholder: 'John Doe'
		});
		const onComplete = vi.fn();

		render(TextInputInteraction, { props: { step, onComplete } });

		const input = screen.getByPlaceholderText('John Doe');
		expect(input).toBeInTheDocument();
	});

	it('should have disabled submit button when required field is empty', () => {
		const step = createMockStep('text_input', {
			label: 'Name',
			required: true
		});
		const onComplete = vi.fn();

		render(TextInputInteraction, { props: { step, onComplete } });

		const submitButton = screen.getByRole('button', { name: 'Continue' });
		expect(submitButton).toBeDisabled();
	});

	it('should enable submit button when required field has value', async () => {
		const step = createMockStep('text_input', {
			label: 'Name',
			required: true
		});
		const onComplete = vi.fn();

		render(TextInputInteraction, { props: { step, onComplete } });

		const input = screen.getByLabelText('Name');
		await fireEvent.input(input, { target: { value: 'Test User' } });

		const submitButton = screen.getByRole('button', { name: 'Continue' });
		expect(submitButton).not.toBeDisabled();
	});

	it('should show validation error for min_length violation', async () => {
		const step = createMockStep('text_input', {
			label: 'Name',
			min_length: 5
		});
		const onComplete = vi.fn();

		render(TextInputInteraction, { props: { step, onComplete } });

		const input = screen.getByLabelText('Name');
		await fireEvent.input(input, { target: { value: 'abc' } });
		await fireEvent.blur(input);

		expect(screen.getByText('Must be at least 5 characters')).toBeInTheDocument();
	});

	it('should show validation error for max_length violation', async () => {
		const step = createMockStep('text_input', {
			label: 'Name',
			max_length: 5
		});
		const onComplete = vi.fn();

		render(TextInputInteraction, { props: { step, onComplete } });

		const input = screen.getByLabelText('Name');
		await fireEvent.input(input, { target: { value: 'abcdefgh' } });
		await fireEvent.blur(input);

		expect(screen.getByText('Must be at most 5 characters')).toBeInTheDocument();
	});

	it('should call onComplete with text data when submitted', async () => {
		const step = createMockStep('text_input', { label: 'Name' });
		const onComplete = vi.fn();

		render(TextInputInteraction, { props: { step, onComplete } });

		const input = screen.getByLabelText('Name');
		await fireEvent.input(input, { target: { value: 'Test User' } });

		const submitButton = screen.getByRole('button', { name: 'Continue' });
		await fireEvent.click(submitButton);

		expect(onComplete).toHaveBeenCalledTimes(1);
		expect(onComplete).toHaveBeenCalledWith(
			expect.objectContaining({
				stepId: 'test-step-id',
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
		const step = createMockStep('quiz', {
			question: 'What is 2 + 2?',
			options: ['3', '4', '5'],
			correct_answer_index: 1
		});
		const onComplete = vi.fn();

		render(QuizInteraction, { props: { step, onComplete } });

		expect(screen.getByText('What is 2 + 2?')).toBeInTheDocument();
		expect(screen.getByText('3')).toBeInTheDocument();
		expect(screen.getByText('4')).toBeInTheDocument();
		expect(screen.getByText('5')).toBeInTheDocument();
	});

	it('should have disabled submit button when no option is selected', () => {
		const step = createMockStep('quiz', {
			question: 'What is 2 + 2?',
			options: ['3', '4', '5'],
			correct_answer_index: 1
		});
		const onComplete = vi.fn();

		render(QuizInteraction, { props: { step, onComplete } });

		const submitButton = screen.getByRole('button', { name: 'Submit Answer' });
		expect(submitButton).toBeDisabled();
	});

	it('should enable submit button when an option is selected', async () => {
		const step = createMockStep('quiz', {
			question: 'What is 2 + 2?',
			options: ['3', '4', '5'],
			correct_answer_index: 1
		});
		const onComplete = vi.fn();

		render(QuizInteraction, { props: { step, onComplete } });

		const option = screen.getByRole('radio', { name: '4' });
		await fireEvent.click(option);

		const submitButton = screen.getByRole('button', { name: 'Submit Answer' });
		expect(submitButton).not.toBeDisabled();
	});

	it('should call onComplete with selected answer_index when submitted', async () => {
		const step = createMockStep('quiz', {
			question: 'What is 2 + 2?',
			options: ['3', '4', '5'],
			correct_answer_index: 1
		});
		const onComplete = vi.fn();

		render(QuizInteraction, { props: { step, onComplete } });

		const option = screen.getByRole('radio', { name: '4' });
		await fireEvent.click(option);

		const submitButton = screen.getByRole('button', { name: 'Submit Answer' });
		await fireEvent.click(submitButton);

		expect(onComplete).toHaveBeenCalledTimes(1);
		expect(onComplete).toHaveBeenCalledWith(
			expect.objectContaining({
				stepId: 'test-step-id',
				interactionType: 'quiz',
				data: { answer_index: 1 }
			})
		);
	});

	it('should allow changing selection before submitting', async () => {
		const step = createMockStep('quiz', {
			question: 'What is 2 + 2?',
			options: ['3', '4', '5'],
			correct_answer_index: 1
		});
		const onComplete = vi.fn();

		render(QuizInteraction, { props: { step, onComplete } });

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
