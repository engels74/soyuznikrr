/**
 * Zod validation schemas for authentication forms.
 */

import { z } from 'zod';

export const loginSchema = z.object({
	username: z.string().min(1, 'Username is required'),
	password: z.string().min(1, 'Password is required')
});

export const setupSchema = z
	.object({
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
			.min(15, 'Password must be at least 15 characters')
			.max(128, 'Password must be at most 128 characters'),
		confirmPassword: z.string(),
		email: z.string().email('Invalid email address').optional().or(z.literal(''))
	})
	.refine((data) => data.password === data.confirmPassword, {
		message: 'Passwords do not match',
		path: ['confirmPassword']
	});

export const jellyfinLoginSchema = z.object({
	server_url: z.string().url('Must be a valid URL').min(1, 'Server URL is required'),
	username: z.string().min(1, 'Username is required'),
	password: z.string().min(1, 'Password is required')
});

export type LoginFormData = z.infer<typeof loginSchema>;
export type SetupFormData = z.infer<typeof setupSchema>;
export type JellyfinLoginFormData = z.infer<typeof jellyfinLoginSchema>;
