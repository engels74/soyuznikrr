/**
 * Component rendering tests for StepIndicator.
 *
 * Tests step circle rendering, connector tracks, and styling.
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

	it('should render the correct number of step circles', () => {
		const { container } = render(StepIndicator, {
			props: { currentStep: 1, totalSteps: 3, stepLabels: ['Account', 'Server', 'Security'] }
		});

		// Each step has a circle div with rounded-full class
		const circles = container.querySelectorAll('.rounded-full.border-2');
		expect(circles.length).toBe(3);
	});

	it('should render connector tracks between steps', () => {
		const { container } = render(StepIndicator, {
			props: { currentStep: 1, totalSteps: 3, stepLabels: ['Account', 'Server', 'Security'] }
		});

		// 3 steps = 2 connectors (divs with mx-2 class)
		const connectors = container.querySelectorAll('.mx-2');
		expect(connectors.length).toBe(2);
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

		// Step 1 is completed (check icon), steps 2 and 3 show numbers
		const stepNumbers = container.querySelectorAll('.font-mono.text-xs.font-semibold');
		expect(stepNumbers.length).toBe(2);
		expect(stepNumbers[0]?.textContent).toBe('2');
		expect(stepNumbers[1]?.textContent).toBe('3');
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

	it('should apply active styling to completed and current labels', () => {
		const { container } = render(StepIndicator, {
			props: { currentStep: 2, totalSteps: 3, stepLabels: ['Account', 'Server', 'Security'] }
		});

		const labelSpans = container.querySelectorAll('.text-xs.font-medium.uppercase');
		expect(labelSpans.length).toBe(3);

		// Step 1 (completed) and step 2 (current) should have text-cr-text
		expect(labelSpans[0]?.className).toContain('text-cr-text');
		expect(labelSpans[1]?.className).toContain('text-cr-text');
		// Step 3 (future) should have text-cr-text-dim
		expect(labelSpans[2]?.className).toContain('text-cr-text-dim');
	});

	it('should fill connector tracks for completed segments', () => {
		const { container } = render(StepIndicator, {
			props: { currentStep: 2, totalSteps: 3, stepLabels: ['Account', 'Server', 'Security'] }
		});

		// First connector should be filled (step 1 completed)
		const connectorInners = container.querySelectorAll('.h-full.rounded-full');
		expect(connectorInners.length).toBe(2);
		expect(connectorInners[0]?.className).toContain('bg-cr-accent');
		// Second connector should be unfilled (step 2 is current, not completed)
		expect(connectorInners[1]?.className).toContain('bg-cr-border');
	});

	it('should show ping animation on current step only', () => {
		const { container } = render(StepIndicator, {
			props: { currentStep: 2, totalSteps: 3, stepLabels: ['Account', 'Server', 'Security'] }
		});

		const pingElements = container.querySelectorAll('.animate-ping');
		expect(pingElements.length).toBe(1);
	});
});
