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
import type { TimerConfig } from "$lib/api/client";
import type { InteractionComponentProps } from "./registry";

const { stepId, interactionId, config: rawConfig, onComplete, disabled = false }: InteractionComponentProps = $props();

// Extract duration from config
const config = $derived(rawConfig as unknown as TimerConfig);
const durationSeconds = $derived(config?.duration_seconds ?? 10);

// Timer state
let remainingSeconds = $state(0);
let startedAt = $state<string | null>(null);
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
		class="continue-btn"
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
		stroke: hsl(220 10% 18%);
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
			0 0 20px hsl(150 60% 45% / 0.4),
			0 0 40px hsl(150 60% 45% / 0.2);
	}

	.timer-ring.complete .progress {
		stroke: hsl(150 60% 45%);
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
		color: hsl(220 10% 92%);
		letter-spacing: -0.02em;
	}

	.timer-ring.pulse .time-value {
		color: hsl(45 90% 55%);
		animation: time-pulse 1s ease-in-out infinite;
	}

	.timer-ring.complete .time-value {
		color: hsl(150 60% 45%);
	}

	.time-label {
		font-size: 0.75rem;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		color: hsl(220 10% 50%);
	}

	/* Continue button */
	.continue-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0.75rem 1.5rem;
		font-size: 0.875rem;
		font-weight: 600;
		color: hsl(220 20% 4%);
		background: hsl(45 90% 55%);
		border: none;
		border-radius: 0.375rem;
		cursor: pointer;
		transition: all 0.2s ease;
		box-shadow:
			0 0 16px hsl(45 90% 55% / 0.3),
			0 4px 12px hsl(0 0% 0% / 0.2);
	}

	.continue-btn:hover:not(:disabled) {
		transform: scale(1.02);
		box-shadow:
			0 0 24px hsl(45 90% 55% / 0.4),
			0 6px 16px hsl(0 0% 0% / 0.3);
	}

	.continue-btn:disabled {
		cursor: not-allowed;
		opacity: 0.5;
		background: hsl(220 10% 25%);
		color: hsl(220 10% 50%);
		box-shadow: none;
	}

	/* Animations */
	@keyframes timer-pulse {
		0%,
		100% {
			box-shadow:
				0 0 12px hsl(45 90% 55% / 0.3),
				0 0 24px hsl(45 90% 55% / 0.15);
		}
		50% {
			box-shadow:
				0 0 20px hsl(45 90% 55% / 0.5),
				0 0 40px hsl(45 90% 55% / 0.25);
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
			<stop offset="0%" style="stop-color: hsl(45 90% 45%)" />
			<stop offset="100%" style="stop-color: hsl(45 90% 60%)" />
		</linearGradient>
	</defs>
</svg>
