/**
 * Zod validation schemas for wizard forms.
 *
 * Provides client-side validation matching backend constraints for:
 * - Creating and updating wizards
 * - Configuring wizard steps by interaction type
 * - Validating step responses
 *
 * @module $lib/schemas/wizard
 */

import { z } from 'zod';

// =============================================================================
// Interaction Type Enum
// =============================================================================

/**
 * Valid interaction types for wizard steps.
 * Matches backend InteractionType enum.
 */
export const interactionTypes = ['click', 'timer', 'tos', 'text_input', 'quiz'] as const;
export type InteractionType = (typeof interactionTypes)[number];

// =============================================================================
// Wizard Schemas
// =============================================================================

/**
 * Schema for creating or updating a wizard.
 *
 * Validates:
 * - name: 1-255 characters, required
 * - description: optional, max 2000 characters
 * - enabled: boolean, defaults to true
 *
 * Requirements: 2.1, 2.4
 */
export const wizardSchema = z.object({
	name: z.string().min(1, 'Name is required').max(255, 'Name must be at most 255 characters'),
	description: z.string().max(2000, 'Description must be at most 2000 characters').optional(),
	enabled: z.boolean().default(true)
});

export type WizardInput = z.infer<typeof wizardSchema>;

// =============================================================================
// Step Configuration Schemas
// =============================================================================

/**
 * Schema for click interaction configuration.
 *
 * Validates:
 * - button_text: optional custom button text, max 100 characters
 *
 * Requirements: 4.3
 */
export const clickConfigSchema = z.object({
	button_text: z.string().max(100, 'Button text must be at most 100 characters').optional()
});

export type ClickConfig = z.infer<typeof clickConfigSchema>;

/**
 * Schema for timer interaction configuration.
 *
 * Validates:
 * - duration_seconds: required, 1-300 seconds
 *
 * Requirements: 5.4
 */
export const timerConfigSchema = z.object({
	duration_seconds: z
		.number()
		.int('Duration must be a whole number')
		.min(1, 'Duration must be at least 1 second')
		.max(300, 'Duration must be at most 300 seconds')
});

export type TimerConfig = z.infer<typeof timerConfigSchema>;

/**
 * Schema for terms of service interaction configuration.
 *
 * Validates:
 * - checkbox_label: optional custom label, max 200 characters
 *
 * Requirements: 6.3
 */
export const tosConfigSchema = z.object({
	checkbox_label: z.string().max(200, 'Checkbox label must be at most 200 characters').optional()
});

export type TosConfig = z.infer<typeof tosConfigSchema>;

/**
 * Schema for text input interaction configuration.
 *
 * Validates:
 * - label: required, 1-100 characters
 * - placeholder: optional, max 200 characters
 * - required: boolean, defaults to true
 * - min_length: optional, non-negative integer
 * - max_length: optional, positive integer
 *
 * Requirements: 7.2
 */
export const textInputConfigSchema = z
	.object({
		label: z.string().min(1, 'Label is required').max(100, 'Label must be at most 100 characters'),
		placeholder: z.string().max(200, 'Placeholder must be at most 200 characters').optional(),
		required: z.boolean().default(true),
		min_length: z.number().int().min(0, 'Minimum length must be non-negative').optional(),
		max_length: z.number().int().min(1, 'Maximum length must be at least 1').optional()
	})
	.refine(
		(data) => {
			if (data.min_length !== undefined && data.max_length !== undefined) {
				return data.min_length <= data.max_length;
			}
			return true;
		},
		{ message: 'Minimum length must be less than or equal to maximum length' }
	);

export type TextInputConfig = z.infer<typeof textInputConfigSchema>;

/**
 * Schema for quiz interaction configuration.
 *
 * Validates:
 * - question: required, 1-500 characters
 * - options: required, 2-10 options, each 1-200 characters
 * - correct_answer_index: required, valid index into options array
 *
 * Requirements: 8.2, 8.3
 */
export const quizConfigSchema = z
	.object({
		question: z
			.string()
			.min(1, 'Question is required')
			.max(500, 'Question must be at most 500 characters'),
		options: z
			.array(
				z
					.string()
					.min(1, 'Option cannot be empty')
					.max(200, 'Option must be at most 200 characters')
			)
			.min(2, 'Quiz must have at least 2 options')
			.max(10, 'Quiz must have at most 10 options'),
		correct_answer_index: z.number().int().min(0, 'Answer index must be non-negative')
	})
	.refine((data) => data.correct_answer_index < data.options.length, {
		message: 'Correct answer index must be a valid option index',
		path: ['correct_answer_index']
	});

export type QuizConfig = z.infer<typeof quizConfigSchema>;

// =============================================================================
// Wizard Step Schema
// =============================================================================

/**
 * Schema for creating or updating a wizard step.
 *
 * Steps are bare content containers — interactions are attached separately.
 *
 * Validates:
 * - title: 1-255 characters
 * - content_markdown: required markdown content
 * - step_order: optional, non-negative integer
 *
 * Requirements: 3.1, 3.2
 */
export const wizardStepSchema = z.object({
	title: z.string().min(1, 'Title is required').max(255, 'Title must be at most 255 characters'),
	content_markdown: z.string().min(1, 'Content is required'),
	step_order: z.number().int().min(0, 'Step order must be non-negative').optional()
});

export type WizardStepInput = z.infer<typeof wizardStepSchema>;

// =============================================================================
// Step Response Schemas (for validation)
// =============================================================================

/**
 * Schema for click step response.
 */
export const clickResponseSchema = z.object({
	acknowledged: z.literal(true)
});

/**
 * Schema for timer step response.
 */
export const timerResponseSchema = z.object({
	waited: z.literal(true)
});

/**
 * Schema for TOS step response.
 */
export const tosResponseSchema = z.object({
	accepted: z.literal(true),
	accepted_at: z.string().datetime()
});

/**
 * Schema for text input step response.
 */
export const textInputResponseSchema = z.object({
	text: z.string()
});

/**
 * Schema for quiz step response.
 */
export const quizResponseSchema = z.object({
	answer_index: z.number().int().min(0)
});

// =============================================================================
// Step Validation Request Schema
// =============================================================================

/**
 * Schema for a single interaction response in a validation request.
 */
export const interactionResponseDataSchema = z.object({
	interaction_id: z.uuid('Invalid interaction ID'),
	response: z.record(z.string(), z.unknown()),
	started_at: z.iso.datetime().optional()
});

/**
 * Schema for step validation request.
 *
 * Requirements: 9.1
 */
export const stepValidationRequestSchema = z.object({
	step_id: z.uuid('Invalid step ID'),
	interactions: z.array(interactionResponseDataSchema).default([])
});

export type StepValidationRequest = z.infer<typeof stepValidationRequestSchema>;
