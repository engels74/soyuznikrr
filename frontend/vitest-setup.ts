import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

// Mock SvelteKit's $env/dynamic/public for test environment
vi.mock('$env/dynamic/public', () => ({
	env: {}
}));
