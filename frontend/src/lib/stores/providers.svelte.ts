/**
 * Provider metadata store.
 *
 * Holds metadata for registered media server providers (color, label, icon, etc.)
 * Populated from the backend API at app startup via `setProviders()`.
 *
 * @module $lib/stores/providers
 */

// =============================================================================
// Types
// =============================================================================

export interface ProviderMeta {
	server_type: string;
	display_name: string;
	color: string;
	icon_svg: string;
	api_key_help_text: string;
	join_flow_type: string | null;
	capabilities: string[];
	supported_permissions: string[];
}

// =============================================================================
// State
// =============================================================================

// SAFETY: Only mutated from $effect() in +layout.svelte (client-only)
let providers = $state<Map<string, ProviderMeta>>(new Map());

// =============================================================================
// API
// =============================================================================

/** Input shape accepted by setProviders (matches OpenAPI generated type). */
interface ProviderMetaInput {
	server_type: string;
	display_name: string;
	color: string;
	icon_svg: string;
	api_key_help_text?: string;
	join_flow_type?: string | null;
	capabilities?: string[];
	supported_permissions?: string[];
}

/**
 * Replace provider metadata with data from the backend API.
 */
export function setProviders(list: ProviderMetaInput[]): void {
	const map = new Map<string, ProviderMeta>();
	for (const p of list) {
		map.set(p.server_type, {
			server_type: p.server_type,
			display_name: p.display_name,
			color: p.color,
			icon_svg: p.icon_svg,
			api_key_help_text: p.api_key_help_text ?? '',
			join_flow_type: p.join_flow_type ?? null,
			capabilities: p.capabilities ?? [],
			supported_permissions: p.supported_permissions ?? []
		});
	}
	providers = map;
}

/**
 * Get metadata for a specific provider type.
 */
export function getProvider(serverType: string): ProviderMeta | undefined {
	return providers.get(serverType);
}

/**
 * Get display name for a provider type, falling back to the raw type string.
 */
export function getProviderLabel(serverType: string): string {
	return providers.get(serverType)?.display_name ?? serverType;
}

/**
 * Get brand color hex for a provider type.
 */
export function getProviderColor(serverType: string): string {
	return providers.get(serverType)?.color ?? '#6b7280';
}

/**
 * Get SVG path data for a provider's icon.
 */
export function getProviderIconSvg(serverType: string): string {
	return providers.get(serverType)?.icon_svg ?? '';
}

/**
 * Get all registered providers.
 */
export function getAllProviders(): ProviderMeta[] {
	return Array.from(providers.values());
}

// =============================================================================
// Style helpers
// =============================================================================

function hexToRgba(hex: string, alpha: number): string {
	if (!hex || hex.length < 7 || hex[0] !== '#') return `rgba(107, 114, 128, ${alpha})`;
	const r = parseInt(hex.slice(1, 3), 16);
	const g = parseInt(hex.slice(3, 5), 16);
	const b = parseInt(hex.slice(5, 7), 16);
	if (Number.isNaN(r) || Number.isNaN(g) || Number.isNaN(b)) return `rgba(107, 114, 128, ${alpha})`;
	return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/**
 * Get inline CSS style string for a provider badge.
 *
 * Returns background, color, and border-color as inline styles,
 * which avoids UnoCSS build-time limitations with dynamic classes.
 */
export function getProviderBadgeStyle(serverType: string): string {
	const color = getProviderColor(serverType);
	return `background: ${hexToRgba(color, 0.15)}; color: ${color}; border-color: ${hexToRgba(color, 0.3)}`;
}

/**
 * Get inline CSS style for a provider toggle button in active state.
 */
export function getProviderActiveToggleStyle(serverType: string): string {
	const color = getProviderColor(serverType);
	return `background: ${hexToRgba(color, 0.2)}; color: ${color}; border-color: ${hexToRgba(color, 0.3)}`;
}
