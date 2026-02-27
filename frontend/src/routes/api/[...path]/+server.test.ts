import { afterEach, describe, expect, it, vi } from 'vitest';
import { POST } from './+server';

type PostHandlerEvent = Parameters<typeof POST>[0];

function makeEvent(request: Request, path: string): PostHandlerEvent {
	return {
		request,
		url: new URL(request.url),
		params: { path }
	} as PostHandlerEvent;
}

describe('API proxy route', () => {
	afterEach(() => {
		vi.restoreAllMocks();
	});

	it('forwards Origin and Referer while stripping hop-by-hop headers', async () => {
		const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
			new Response(JSON.stringify({ ok: true }), {
				status: 201,
				headers: { 'content-type': 'application/json' }
			})
		);

		const request = new Request(
			'http://frontend.local/api/v1/settings/csrf-origin/test?from=setup',
			{
				method: 'POST',
				headers: {
					'content-type': 'application/json',
					origin: 'https://app.example.com',
					referer: 'https://app.example.com/setup',
					host: 'frontend.local',
					connection: 'keep-alive',
					'keep-alive': 'timeout=5',
					'transfer-encoding': 'chunked',
					upgrade: 'websocket'
				},
				body: JSON.stringify({ origin: 'https://app.example.com' })
			}
		);

		const response = await POST(
			makeEvent(request, 'v1/settings/csrf-origin/test')
		);

		expect(fetchSpy).toHaveBeenCalledTimes(1);
		const [upstream, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
		expect(upstream).toBe(
			'http://localhost:8000/api/v1/settings/csrf-origin/test?from=setup'
		);
		expect(init.method).toBe('POST');
		expect(init.body).toBeDefined();

		const forwarded = new Headers(init.headers);
		expect(forwarded.get('origin')).toBe('https://app.example.com');
		expect(forwarded.get('referer')).toBe('https://app.example.com/setup');
		expect(forwarded.has('host')).toBe(false);
		expect(forwarded.has('connection')).toBe(false);
		expect(forwarded.has('keep-alive')).toBe(false);
		expect(forwarded.has('transfer-encoding')).toBe(false);
		expect(forwarded.has('upgrade')).toBe(false);

		expect(response.status).toBe(201);
		await expect(response.json()).resolves.toEqual({ ok: true });
	});
});
