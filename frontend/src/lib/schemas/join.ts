/**
 * Zod validation schemas for join/registration forms.
 *
 * Provides client-side validation matching backend constraints for:
 * - User registration (credential-based join flow)
 *
 * @module $lib/schemas/join
 */

import { z } from 'zod';

/**
 * Schema for user registration (credential-based join flow).
 *
 * Validates:
 * - username: 3-32 chars, lowercase, starts with letter, alphanumeric + underscores
 * - password: minimum 8 characters, maximum 128 characters
 * - email: optional valid email address
 */
export const registrationSchema = z.object({
	username: z
		.string()
		.min(3, 'Username must be at least 3 characters')
		.max(32, 'Username must be at most 32 characters')
		.regex(
			/^[a-z][a-z0-9_]*$/,
			'Username must start with a lowercase letter and contain only lowercase letters, numbers, and underscores'
		),
	password: z
		.string()
		.min(8, 'Password must be at least 8 characters')
		.max(128, 'Password must be at most 128 characters'),
	email: z.string().email('Invalid email address').optional().or(z.literal(''))
});

export type RegistrationInput = z.infer<typeof registrationSchema>;

/**
 * Sanitize an email address into a valid username matching `^[a-z][a-z0-9_]*$`.
 *
 * Used during OAuth join flows where the provider returns an email but the
 * backend expects a valid username for the display_name on the Identity record.
 *
 * - Extracts the local part (before `@`)
 * - Lowercases and replaces invalid characters with `_`
 * - Collapses consecutive underscores, strips leading non-letters
 * - Truncates to 32 chars, strips trailing underscores
 * - Pads short results to minimum 3 chars; falls back to `"user"` if empty
 *
 * @example sanitizeEmailToUsername("hans.irwin@tmail.link") // "hans_irwin"
 */
export function sanitizeEmailToUsername(email: string): string {
	// Extract local part before @
	const localPart = email.split('@')[0] ?? '';

	// Lowercase and replace invalid chars with underscore
	let result = localPart.toLowerCase().replace(/[^a-z0-9_]/g, '_');

	// Collapse consecutive underscores
	result = result.replace(/_+/g, '_');

	// Strip leading non-letters (digits, underscores)
	result = result.replace(/^[^a-z]+/, '');

	// Truncate to 32 chars
	result = result.slice(0, 32);

	// Strip trailing underscores
	result = result.replace(/_+$/, '');

	// If nothing valid remains, fallback
	if (result.length === 0) {
		return 'user';
	}

	// Pad to minimum 3 chars
	while (result.length < 3) {
		result += '_';
	}

	return result;
}

/**
 * Transform registration form data to API request format.
 *
 * Converts empty email string to undefined for the API.
 */
export function transformRegistrationFormData(data: RegistrationInput) {
	return {
		username: data.username,
		password: data.password,
		email: data.email && data.email !== '' ? data.email : undefined
	};
}
