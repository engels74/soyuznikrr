/**
 * Component rendering tests for StepIndicator.
 *
 * Tests step circle rendering, labels, and semantic behavior.
 *
 * @module $lib/components/setup/step-indicator.svelte.test
 */

import { cleanup, render } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';
import StepIndicator from './step-indicator.svelte';

describe('Step Indicator Rendering', () => {
	afterEach(() => {
		cleanup();
	});

	it('should display check icon for completed steps', () => {
		const { container } = render(StepIndicator, {
			props: { currentStep: 3, totalSteps: 3, stepLabels: ['Account', 'Server', 'Security'] }
		});

		// Steps 1 and 2 are completed, should have SVG check icons
		const svgs = container.querySelectorAll('svg');
		expect(svgs.length).toBe(2);
	});

	it('should display step number for current and future steps', () => {
		const { container } = render(StepIndicator, {
			props: { currentStep: 2, totalSteps: 3, stepLabels: ['Account', 'Server', 'Security'] }
		});

		// Step 1 is completed (check icon), steps 2 and 3 show their numbers as text
		const allText = container.textContent ?? '';
		expect(allText).toContain('2');
		expect(allText).toContain('3');
		// Step 1 should not show its number (it has a check icon instead)
		const svgs = container.querySelectorAll('svg');
		expect(svgs.length).toBe(1);
	});

	it('should display all step labels', () => {
		const labels = ['Account', 'Server', 'Security'];
		const { container } = render(StepIndicator, {
			props: { currentStep: 1, totalSteps: 3, stepLabels: labels }
		});

		for (const label of labels) {
			expect(container.textContent).toContain(label);
		}
	});

	it('should render the correct number of steps', () => {
		const { container } = render(StepIndicator, {
			props: { currentStep: 1, totalSteps: 4, stepLabels: ['A', 'B', 'C', 'D'] }
		});

		// All 4 labels should be present
		expect(container.textContent).toContain('A');
		expect(container.textContent).toContain('B');
		expect(container.textContent).toContain('C');
		expect(container.textContent).toContain('D');
	});

	it('should show no check icons when on the first step', () => {
		const { container } = render(StepIndicator, {
			props: { currentStep: 1, totalSteps: 3, stepLabels: ['Account', 'Server', 'Security'] }
		});

		// No steps are completed yet
		const svgs = container.querySelectorAll('svg');
		expect(svgs.length).toBe(0);
	});

	it('should show all check icons when on the last step', () => {
		const { container } = render(StepIndicator, {
			props: { currentStep: 3, totalSteps: 3, stepLabels: ['Account', 'Server', 'Security'] }
		});

		// Steps 1 and 2 are completed
		const svgs = container.querySelectorAll('svg');
		expect(svgs.length).toBe(2);
		// Only step 3 shows its number
		expect(container.textContent).toContain('3');
	});
});
