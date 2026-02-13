/**
 * Zod validation schemas for server forms.
 *
 * Provides client-side validation matching backend constraints for:
 * - Creating new media servers
 *
 * @module $lib/schemas/server
 */

import { z } from 'zod';

/**
 * Schema for creating a new media server.
 *
 * Required fields:
 * - name: Human-readable name for the server
 * - server_type: Type of media server (as registered by a provider)
 * - url: Base URL for the media server API
 * - api_key: Authentication token for the server
 */
export const createServerSchema = z.object({
	name: z.string().min(1, 'Name is required').max(255, 'Name must be at most 255 characters'),
	server_type: z.string().min(1, 'Server type is required'),
	url: z
		.string()
		.min(1, 'URL is required')
		.url('Must be a valid URL')
		.max(2048, 'URL must be at most 2048 characters'),
	api_key: z
		.string()
		.min(1, 'API key is required')
		.max(512, 'API key must be at most 512 characters')
});

export type CreateServerInput = z.infer<typeof createServerSchema>;

/**
 * Transform form data to API request format.
 */
export function transformCreateServerData(data: CreateServerInput) {
	return {
		name: data.name.trim(),
		server_type: data.server_type,
		url: data.url.trim(),
		api_key: data.api_key.trim()
	};
}
