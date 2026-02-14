/**
 * Register Default Interaction Types
 *
 * Registers all 5 built-in interaction types with the registry.
 * Import this module at app startup to ensure all types are available.
 *
 * @module $lib/components/wizard/interactions/register-defaults
 */

import { CircleHelp, MousePointerClick, ScrollText, TextCursorInput, Timer } from '@lucide/svelte';

import {
	clickConfigSchema,
	quizConfigSchema,
	textInputConfigSchema,
	timerConfigSchema,
	tosConfigSchema
} from '$lib/schemas/wizard';

import ClickInteraction from './click-interaction.svelte';
import ClickConfigEditor from './config-editors/click-config-editor.svelte';
import QuizConfigEditor from './config-editors/quiz-config-editor.svelte';
import TextInputConfigEditor from './config-editors/text-input-config-editor.svelte';
import TimerConfigEditor from './config-editors/timer-config-editor.svelte';
import TosConfigEditor from './config-editors/tos-config-editor.svelte';
import QuizInteraction from './quiz-interaction.svelte';
import { registerInteractionType } from './registry';
import TextInputInteraction from './text-input-interaction.svelte';
import TimerInteraction from './timer-interaction.svelte';
import TosInteraction from './tos-interaction.svelte';

registerInteractionType({
	type: 'click',
	label: 'Click Confirmation',
	description: 'Simple button that users click to confirm',
	icon: MousePointerClick,
	configSchema: clickConfigSchema,
	defaultConfig: () => ({ button_text: 'I Understand' }),
	configEditor: ClickConfigEditor,
	interactionComponent: ClickInteraction
});

registerInteractionType({
	type: 'timer',
	label: 'Timed Wait',
	description: 'Countdown timer that users must wait through',
	icon: Timer,
	configSchema: timerConfigSchema,
	defaultConfig: () => ({ duration_seconds: 10 }),
	configEditor: TimerConfigEditor,
	interactionComponent: TimerInteraction
});

registerInteractionType({
	type: 'tos',
	label: 'Terms of Service',
	description: 'Checkbox that users must accept to proceed',
	icon: ScrollText,
	configSchema: tosConfigSchema,
	defaultConfig: () => ({ checkbox_label: 'I accept the terms of service' }),
	configEditor: TosConfigEditor,
	interactionComponent: TosInteraction
});

registerInteractionType({
	type: 'text_input',
	label: 'Text Input',
	description: 'Free-form text field with validation',
	icon: TextCursorInput,
	configSchema: textInputConfigSchema,
	defaultConfig: () => ({ label: 'Your response', required: true }),
	configEditor: TextInputConfigEditor,
	interactionComponent: TextInputInteraction
});

registerInteractionType({
	type: 'quiz',
	label: 'Quiz Question',
	description: 'Multiple choice question with a correct answer',
	icon: CircleHelp,
	configSchema: quizConfigSchema,
	defaultConfig: () => ({
		question: 'Enter your question here',
		options: ['Option A', 'Option B'],
		correct_answer_index: 0
	}),
	configEditor: QuizConfigEditor,
	interactionComponent: QuizInteraction
});
