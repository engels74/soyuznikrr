<script lang="ts">
/**
 * Timer Interaction Component
 *
 * Implements countdown with circular progress indicator.
 * Auto-completes when timer reaches zero.
 * Adds pulse animation on final 5 seconds.
 * Tracks startedAt timestamp for validation.
 *
 * The remaining time is derived from a wall-clock deadline rather than
 * accumulated interval ticks, so browser throttling (Safari background
 * tabs, iOS lock screen, Chrome inactive tab clamping) cannot stall the
 * countdown. visibilitychange / focus / pageshow listeners trigger an
 * immediate recompute when the tab returns. startedAt is persisted to
 * sessionStorage so a mid-countdown refresh resumes from the correct
 * deadline instead of restarting at full duration.
 */
import { onMount } from "svelte";
import { browser } from "$app/environment";
import { timerConfigSchema } from "$lib/schemas/wizard";
import type { InteractionComponentProps } from "./registry";

const { interactionId, config: rawConfig, onComplete, disabled = false, completionData }: InteractionComponentProps = $props();

// Validate config with Zod schema, falling back gracefully for partial configs
const config = $derived(timerConfigSchema.safeParse(rawConfig).data);
const durationSeconds = $derived(config?.duration_seconds ?? 10);

// If already completed (navigating back), start at 0
const alreadyCompleted = (() => completionData?.data?.waited === true)();

// Compute initial duration from raw config to avoid SSR flash of "complete" state
const initialDuration = (() => {
	const parsed = timerConfigSchema.safeParse(rawConfig);
	return parsed.data?.duration_seconds ?? 10;
})();

// interactionId is a UUID so this key is unique across wizards.
// $derived so Svelte sees the prop read; the value is stable in practice.
const storageKey = $derived(`wizard-timer-${interactionId}`);

// Timer state — initialize to actual duration so SSR renders the countdown, not "Timer complete"
let remainingSeconds = $state(alreadyCompleted ? 0 : initialDuration);
let startedAt = $state<string | null>((() => completionData?.startedAt ?? null)());
let deadline = $state<number | null>(null);
let intervalId: ReturnType<typeof setInterval> | null = null;
// Single-fire guard: prevents the interval, visibility handler, and
// re-emission path from each calling onComplete redundantly for the same
// completion cycle.
let hasFired = $state(alreadyCompleted);
// Set to true the first time the parent surfaces this interaction's
// completion back to us. Re-emission only triggers after a true → false
// transition of completionData (parent-driven clear), not during the
// initial mount phase where completionData is undefined.
let acknowledgedByParent = $state(false);

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

function fireComplete() {
	if (hasFired || disabled) return;
	hasFired = true;
	if (intervalId !== null) {
		clearInterval(intervalId);
		intervalId = null;
	}
	if (browser) {
		try {
			sessionStorage.removeItem(storageKey);
		} catch {
			// ignore storage errors
		}
	}
	onComplete({
		interactionId,
		interactionType: "timer",
		data: { waited: true },
		startedAt: startedAt ?? undefined,
		completedAt: new Date().toISOString(),
	});
}

function recompute() {
	if (deadline === null) return;
	if (alreadyCompleted) return;
	const remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
	remainingSeconds = remaining;
	if (remaining <= 0) {
		fireComplete();
	}
}

onMount(() => {
	// Skip countdown if already completed (navigating back).
	if (alreadyCompleted) {
		remainingSeconds = 0;
		return;
	}

	// Try to restore startedAt from sessionStorage so a refresh mid-timer
	// resumes the countdown from the same deadline. Fall back to
	// completionData (back-navigation), then to "now" for first arming.
	let restored: string | null = null;
	if (browser) {
		try {
			restored = sessionStorage.getItem(storageKey);
		} catch {
			restored = null;
		}
	}
	const initial = restored ?? completionData?.startedAt ?? new Date().toISOString();
	startedAt = initial;

	if (browser && !restored) {
		try {
			sessionStorage.setItem(storageKey, initial);
		} catch {
			// ignore storage errors (quota, private mode)
		}
	}

	const parsedStart = Date.parse(initial);
	const startMs = Number.isFinite(parsedStart) ? parsedStart : Date.now();
	deadline = startMs + durationSeconds * 1000;

	// Initial recompute so SSR -> client transition reflects elapsed time.
	recompute();

	intervalId = setInterval(recompute, 1000);

	return () => {
		if (intervalId !== null) {
			clearInterval(intervalId);
			intervalId = null;
		}
	};
});

// Recompute when the tab becomes visible / regains focus / is restored
// from bfcache. Covers Safari/iOS background throttling and lock screens
// where setInterval is paused but wall-clock time continues to elapse.
$effect(() => {
	if (!browser || alreadyCompleted) return;
	const handler = () => recompute();
	document.addEventListener("visibilitychange", handler);
	window.addEventListener("focus", handler);
	window.addEventListener("pageshow", handler);
	return () => {
		document.removeEventListener("visibilitychange", handler);
		window.removeEventListener("focus", handler);
		window.removeEventListener("pageshow", handler);
	};
});

// Record when the parent acknowledges our fire. We only re-emit on a
// true → false transition of completionData; the initial mount where
// completionData is undefined must NOT trip the re-emission path.
$effect(() => {
	if (completionData) {
		acknowledgedByParent = true;
	}
});

// Re-emit completion if a previously-acknowledged completion was cleared by
// the parent — e.g., a sibling interaction's backend validation failed and
// wizard-shell wiped this step's completion map. Without this, the timer
// would appear complete but its data would not be re-submitted.
// Deferred via setTimeout(0) to avoid suppressing a validation error set in
// the same reactive update cycle.
$effect(() => {
	if (
		acknowledgedByParent &&
		!completionData &&
		!disabled &&
		!alreadyCompleted &&
		remainingSeconds <= 0 &&
		startedAt
	) {
		const timeout = setTimeout(() => {
			// Bypass hasFired here — this is intentional re-emission.
			acknowledgedByParent = false;
			onComplete({
				interactionId,
				interactionType: "timer",
				data: { waited: true },
				startedAt: startedAt ?? undefined,
				completedAt: new Date().toISOString(),
			});
		}, 0);
		return () => clearTimeout(timeout);
	}
});
</script>

<div class="timer-interaction">
	<!-- Circular progress indicator -->
	<div class="timer-ring" class:pulse={isFinalCountdown} class:complete={isComplete}>
		<svg viewBox="0 0 160 160" class="progress-svg" aria-hidden="true">
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

	<!-- Completion status -->
	{#if isComplete}
		<div class="completion-status">
			<svg viewBox="0 0 24 24" class="checkmark-icon" aria-hidden="true">
				<path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" fill="currentColor" />
			</svg>
			<span>Timer complete</span>
		</div>
	{/if}
</div>

<style>
	.timer-interaction {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 2rem;
		padding: 2rem 0;
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

	/* Completion status indicator */
	.completion-status {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		color: var(--wizard-success);
		font-size: 0.9375rem;
		font-weight: 500;
	}

	.checkmark-icon {
		width: 1.25rem;
		height: 1.25rem;
	}
</style>

<!-- SVG gradient definition -->
<svg width="0" height="0" style="position: absolute;" aria-hidden="true">
	<defs>
		<linearGradient id="timer-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
			<stop offset="0%" style="stop-color: var(--wizard-accent-gradient-start)" />
			<stop offset="100%" style="stop-color: var(--wizard-accent-gradient-end)" />
		</linearGradient>
	</defs>
</svg>
