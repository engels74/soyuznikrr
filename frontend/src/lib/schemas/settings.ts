/**
 * Zod validation schemas for settings page forms.
 */

import { z } from 'zod';

export const emailUpdateSchema = z.object({
	email: z
		.string()
		.email('Must be a valid email address')
		.max(255, 'Email must be 255 characters or less')
		.or(z.literal(''))
		.transform((val) => (val === '' ? null : val))
});

export type EmailUpdateInput = z.input<typeof emailUpdateSchema>;

export const passwordChangeSchema = z
	.object({
		current_password: z.string().min(1, 'Current password is required'),
		new_password: z
			.string()
			.min(15, 'Password must be at least 15 characters')
			.max(128, 'Password must be 128 characters or less'),
		confirm_password: z.string().min(1, 'Please confirm your new password')
	})
	.refine((data) => data.new_password === data.confirm_password, {
		message: 'Passwords do not match',
		path: ['confirm_password']
	});

export type PasswordChangeInput = z.infer<typeof passwordChangeSchema>;

export const syncIntervalSchema = z.object({
	sync_interval_seconds: z
		.number({ message: 'Must be a number' })
		.int('Must be a whole number')
		.min(60, 'Minimum interval is 60 seconds')
		.max(86400, 'Maximum interval is 86400 seconds (24 hours)')
});

export type SyncIntervalInput = z.infer<typeof syncIntervalSchema>;

export const expirationIntervalSchema = z.object({
	expiration_check_interval_seconds: z
		.number({ message: 'Must be a number' })
		.int('Must be a whole number')
		.min(60, 'Minimum interval is 60 seconds')
		.max(86400, 'Maximum interval is 86400 seconds (24 hours)')
});

export type ExpirationIntervalInput = z.infer<typeof expirationIntervalSchema>;
