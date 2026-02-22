<script lang="ts">
import { goto } from '$app/navigation';
import StepAdmin from './step-admin.svelte';
import StepCsrf from './step-csrf.svelte';
import StepIndicator from './step-indicator.svelte';
import StepServer from './step-server.svelte';

let currentStep = $state(1);
let adminCreated = $state(false);

const stepLabels = ['Account', 'Server', 'Security'];

function handleAdminComplete() {
	adminCreated = true;
	currentStep = 2;
}

function handleServerComplete() {
	currentStep = 3;
}

function handleServerSkip() {
	currentStep = 3;
}

function handleCsrfComplete() {
	goto('/dashboard');
}

function handleCsrfSkip() {
	goto('/dashboard');
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
				<StepServer onComplete={handleServerComplete} onSkip={handleServerSkip} />
			{:else}
				<StepCsrf onComplete={handleCsrfComplete} onSkip={handleCsrfSkip} />
			{/if}
		</div>
	{/key}
</div>
