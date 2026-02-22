/**
 * Zod validation schemas for onboarding wizard forms.
 */

import { z } from 'zod';

export const csrfOriginSchema = z.object({
	origin: z
		.string()
		.min(1, 'Origin is required')
		.regex(
			/^https?:\/\/[^/?#]+$/,
			'Must be an origin URL (e.g., https://example.com) without a trailing path'
		)
});

export type CsrfOriginInput = z.infer<typeof csrfOriginSchema>;
