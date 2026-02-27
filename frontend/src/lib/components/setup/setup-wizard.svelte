<script lang="ts">
import { goto } from '$app/navigation';
import {
	advanceOnboarding,
	getErrorDetail,
	type OnboardingStep
} from '$lib/api/auth';
import StepAdmin from './step-admin.svelte';
import StepCsrf from './step-csrf.svelte';
import StepIndicator from './step-indicator.svelte';
import StepServer from './step-server.svelte';

interface Props {
	initialStep?: OnboardingStep;
}

const { initialStep = 'account' }: Props = $props();

function onboardingStepToUiStep(step: OnboardingStep): number {
	if (step === 'account') return 1;
	if (step === 'security') return 2;
	return 3;
}

let currentStep = $state(1);
let stepInitialized = $state(false);
let advancing = $state(false);

$effect(() => {
	if (stepInitialized) return;
	currentStep = onboardingStepToUiStep(initialStep);
	stepInitialized = true;
});

const stepLabels = ['Account', 'Security', 'Server'];

function handleAdminComplete() {
	currentStep = 2;
}

async function advanceStep(): Promise<boolean> {
	if (advancing) return false;
	advancing = true;
	try {
		const response = await advanceOnboarding();
		if (response.error) {
			console.warn('[setup wizard] failed to advance onboarding:', getErrorDetail(response.error));
			return false;
		}
		return true;
	} finally {
		advancing = false;
	}
}

async function handleServerComplete() {
	const ok = await advanceStep();
	if (!ok) return;
	await goto('/dashboard');
}

async function handleServerSkip() {
	const ok = await advanceStep();
	if (!ok) return;
	await goto('/dashboard');
}

function handleCsrfComplete() {
	currentStep = 3;
}

async function handleCsrfSkip() {
	const ok = await advanceStep();
	if (!ok) return;
	currentStep = 3;
}
</script>

<style>
	@keyframes step-enter {
		from {
			opacity: 0;
			transform: translateY(16px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	.step-content {
		animation: step-enter 0.4s ease-out;
	}
</style>

<div class="flex flex-col gap-4">
	<StepIndicator {currentStep} totalSteps={3} {stepLabels} />

	{#key currentStep}
		<div class="step-content">
			{#if currentStep === 1}
				<StepAdmin onComplete={handleAdminComplete} />
			{:else if currentStep === 2}
				<StepCsrf onComplete={handleCsrfComplete} onSkip={handleCsrfSkip} />
			{:else}
				<StepServer onComplete={handleServerComplete} onSkip={handleServerSkip} />
			{/if}
		</div>
	{/key}
</div>
