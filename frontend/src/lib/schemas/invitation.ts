/**
 * Zod validation schemas for invitation forms.
 *
 * Provides client-side validation matching backend constraints for:
 * - Creating new invitations
 * - Updating existing invitations (mutable fields only)
 *
 * @module $lib/schemas/invitation
 */

import { z } from 'zod';

/**
 * Schema for creating a new invitation.
 *
 * Required fields:
 * - server_ids: At least one target server must be selected
 *
 * Optional fields:
 * - code: Custom alphanumeric code (auto-generated if not provided)
 * - expires_at: ISO 8601 datetime string
 * - max_uses: Positive integer limit on uses
 * - duration_days: Positive integer for user access duration
 * - library_ids: Specific libraries to grant access to
 */
export const createInvitationSchema = z.object({
	server_ids: z.array(z.string().uuid('Invalid server ID')).min(1, 'Select at least one server'),
	code: z
		.string()
		.min(1, 'Code must be at least 1 character')
		.max(20, 'Code must be at most 20 characters')
		.regex(/^[a-zA-Z0-9]+$/, 'Code must be alphanumeric')
		.optional()
		.or(z.literal('')),
	expires_at: z.string().datetime({ message: 'Invalid date format' }).optional().or(z.literal('')),
	max_uses: z.coerce
		.number()
		.int('Must be a whole number')
		.positive('Must be a positive number')
		.optional()
		.or(z.literal('')),
	duration_days: z.coerce
		.number()
		.int('Must be a whole number')
		.positive('Must be a positive number')
		.optional()
		.or(z.literal('')),
	library_ids: z.array(z.string().uuid('Invalid library ID')).optional()
});

export type CreateInvitationInput = z.infer<typeof createInvitationSchema>;

/**
 * Schema for updating an existing invitation.
 *
 * Only mutable fields are included:
 * - expires_at: Can be updated or cleared
 * - max_uses: Can be updated or cleared
 * - duration_days: Can be updated or cleared
 * - enabled: Can toggle enabled status
 * - server_ids: Can update target servers
 * - library_ids: Can update allowed libraries
 *
 * Immutable fields (code, use_count, created_at, created_by) are NOT included.
 */
export const updateInvitationSchema = z.object({
	expires_at: z
		.string()
		.datetime({ message: 'Invalid date format' })
		.optional()
		.nullable()
		.or(z.literal('')),
	max_uses: z.coerce
		.number()
		.int('Must be a whole number')
		.positive('Must be a positive number')
		.optional()
		.nullable()
		.or(z.literal('')),
	duration_days: z.coerce
		.number()
		.int('Must be a whole number')
		.positive('Must be a positive number')
		.optional()
		.nullable()
		.or(z.literal('')),
	enabled: z.boolean().optional(),
	server_ids: z
		.array(z.string().uuid('Invalid server ID'))
		.min(1, 'Select at least one server')
		.optional(),
	library_ids: z.array(z.string().uuid('Invalid library ID')).optional()
});

export type UpdateInvitationInput = z.infer<typeof updateInvitationSchema>;

/**
 * Transform form data to API request format.
 *
 * Converts empty strings to null/undefined for optional fields.
 */
export function transformCreateFormData(data: CreateInvitationInput) {
	return {
		server_ids: data.server_ids,
		code: data.code && data.code !== '' ? data.code : undefined,
		expires_at: data.expires_at && data.expires_at !== '' ? data.expires_at : undefined,
		max_uses: typeof data.max_uses === 'number' ? data.max_uses : undefined,
		duration_days: typeof data.duration_days === 'number' ? data.duration_days : undefined,
		library_ids: data.library_ids && data.library_ids.length > 0 ? data.library_ids : undefined
	};
}

/**
 * Transform update form data to API request format.
 *
 * Converts empty strings to null for clearable fields.
 */
export function transformUpdateFormData(data: UpdateInvitationInput) {
	return {
		expires_at: data.expires_at === '' ? null : data.expires_at,
		max_uses:
			data.max_uses === '' ? null : typeof data.max_uses === 'number' ? data.max_uses : undefined,
		duration_days:
			data.duration_days === ''
				? null
				: typeof data.duration_days === 'number'
					? data.duration_days
					: undefined,
		enabled: data.enabled,
		server_ids: data.server_ids,
		library_ids: data.library_ids
	};
}
