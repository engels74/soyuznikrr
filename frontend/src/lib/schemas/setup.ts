/**
 * Zod validation schemas for onboarding wizard forms.
 */

import { z } from 'zod';

export const csrfOriginSchema = z.object({
	origin: z
		.string()
		.min(1, 'Origin is required')
		.url('Must be a valid URL')
		.regex(/^https?:\/\//, 'Must start with http:// or https://')
		.refine((val) => !val.endsWith('/'), 'Remove trailing slash')
});

export type CsrfOriginInput = z.infer<typeof csrfOriginSchema>;
