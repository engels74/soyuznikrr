<script lang="ts">
/**
 * Timer Interaction Component
 *
 * Implements countdown with circular progress indicator.
 * Disables button until timer completes.
 * Adds pulse animation on final 5 seconds.
 * Tracks startedAt timestamp for validation.
 *
 * Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 12.2
 */
import { onMount } from "svelte";
import { timerConfigSchema } from "$lib/schemas/wizard";
import type { InteractionComponentProps } from "./registry";

const { interactionId, config: rawConfig, onComplete, disabled = false, completionData }: InteractionComponentProps = $props();

// Validate config with Zod schema, falling back gracefully for partial configs
const config = $derived(timerConfigSchema.safeParse(rawConfig).data);
const durationSeconds = $derived(config?.duration_seconds ?? 10);

// If already completed (navigating back), start at 0
const alreadyCompleted = (() => completionData?.data?.waited === true)();

// Timer state
let remainingSeconds = $state(0);
let startedAt = $state<string | null>((() => completionData?.startedAt ?? null)());
let intervalId: ReturnType<typeof setInterval> | null = null;

// Derived values
const isComplete = $derived(remainingSeconds <= 0);
const isFinalCountdown = $derived(
	remainingSeconds > 0 && remainingSeconds <= 5,
);
const progress = $derived(
	durationSeconds > 0
		? ((durationSeconds - remainingSeconds) / durationSeconds) * 100
		: 100,
);

// Format remaining time as MM:SS
const formattedTime = $derived.by(() => {
	const mins = Math.floor(remainingSeconds / 60);
	const secs = remainingSeconds % 60;
	return `${mins}:${secs.toString().padStart(2, "0")}`;
});

// SVG circle calculations
const radius = 70;
const circumference = 2 * Math.PI * radius;
const strokeDashoffset = $derived(
	circumference - (progress / 100) * circumference,
);

onMount(() => {
	// Skip countdown if already completed (navigating back)
	if (alreadyCompleted) {
		remainingSeconds = 0;
		return;
	}

	// Initialize timer
	remainingSeconds = durationSeconds;
	startedAt = new Date().toISOString();

	intervalId = setInterval(() => {
		if (remainingSeconds > 0) {
			remainingSeconds--;
		} else if (intervalId) {
			clearInterval(intervalId);
			intervalId = null;
		}
	}, 1000);

	return () => {
		if (intervalId) {
			clearInterval(intervalId);
		}
	};
});

function handleComplete() {
	onComplete({
		interactionId,
		interactionType: "timer",
		data: { waited: true },
		startedAt: startedAt ?? undefined,
		completedAt: new Date().toISOString(),
	});
}
</script>

<div class="timer-interaction">
	<!-- Circular progress indicator -->
	<div class="timer-ring" class:pulse={isFinalCountdown} class:complete={isComplete}>
		<svg viewBox="0 0 160 160" class="progress-svg">
			<!-- Background circle -->
			<circle cx="80" cy="80" r={radius} class="track" />
			<!-- Progress circle -->
			<circle
				cx="80"
				cy="80"
				r={radius}
				class="progress"
				style="stroke-dasharray: {circumference}; stroke-dashoffset: {strokeDashoffset};"
			/>
		</svg>
		<!-- Time display -->
		<div class="time-display">
			<span class="time-value">{formattedTime}</span>
			<span class="time-label">{isComplete ? 'Ready!' : 'remaining'}</span>
		</div>
	</div>

	<!-- Continue button -->
	<button
		type="button"
		class="wizard-accent-btn"
		onclick={handleComplete}
		disabled={!isComplete || disabled}
	>
		{isComplete ? 'Continue' : 'Please wait...'}
	</button>
</div>

<style>
	.timer-interaction {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 2rem;
		padding: 1.5rem 0;
	}

	/* Circular timer ring */
	.timer-ring {
		position: relative;
		width: 160px;
		height: 160px;
	}

	.progress-svg {
		width: 100%;
		height: 100%;
		transform: rotate(-90deg);
	}

	/* Track circle */
	.track {
		fill: none;
		stroke: var(--wizard-border);
		stroke-width: 6;
	}

	/* Progress circle with gradient */
	.progress {
		fill: none;
		stroke: url(#timer-gradient);
		stroke-width: 6;
		stroke-linecap: round;
		transition: stroke-dashoffset 0.3s ease;
	}

	/* Gradient definition - using inline style since SVG gradients need to be in the SVG */
	.timer-ring::before {
		content: '';
		position: absolute;
		inset: -4px;
		border-radius: 50%;
		background: transparent;
		transition: box-shadow 0.3s ease;
	}

	/* Pulse animation on final 5 seconds */
	.timer-ring.pulse::before {
		animation: timer-pulse 1s ease-in-out infinite;
	}

	/* Glow on completion */
	.timer-ring.complete::before {
		box-shadow:
			0 0 20px var(--wizard-success-glow-lg),
			0 0 40px var(--wizard-success-glow-sm);
	}

	.timer-ring.complete .progress {
		stroke: var(--wizard-success);
	}

	/* Time display in center */
	.time-display {
		position: absolute;
		inset: 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.25rem;
	}

	.time-value {
		font-family: 'JetBrains Mono', 'Fira Code', monospace;
		font-size: 2.5rem;
		font-weight: 600;
		font-variant-numeric: tabular-nums;
		color: var(--wizard-text);
		letter-spacing: -0.02em;
	}

	.timer-ring.pulse .time-value {
		color: var(--wizard-accent);
		animation: time-pulse 1s ease-in-out infinite;
	}

	.timer-ring.complete .time-value {
		color: var(--wizard-success);
	}

	.time-label {
		font-size: 0.75rem;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		color: var(--wizard-text-dim);
	}

	/* Animations */
	@keyframes timer-pulse {
		0%,
		100% {
			box-shadow:
				0 0 12px var(--wizard-accent-glow-xl),
				0 0 24px var(--wizard-accent-glow-sm);
		}
		50% {
			box-shadow:
				0 0 20px var(--wizard-accent-glow-active),
				0 0 40px var(--wizard-accent-glow-lg);
		}
	}

	@keyframes time-pulse {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.7;
		}
	}
</style>

<!-- SVG gradient definition -->
<svg width="0" height="0" style="position: absolute;">
	<defs>
		<linearGradient id="timer-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
			<stop offset="0%" style="stop-color: var(--wizard-accent-gradient-start)" />
			<stop offset="100%" style="stop-color: var(--wizard-accent-gradient-end)" />
		</linearGradient>
	</defs>
</svg>
