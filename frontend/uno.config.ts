import presetIcons from '@unocss/preset-icons';
import transformerVariantGroup from '@unocss/transformer-variant-group';
import { defineConfig, presetWind4 } from 'unocss';
import presetAnimations from 'unocss-preset-animations';
import { presetShadcn } from 'unocss-preset-shadcn';

export default defineConfig({
	presets: [
		presetWind4({ preflights: { reset: true } }),
		presetAnimations(),
		presetShadcn({ color: 'neutral', darkSelector: '.dark' }),
		presetIcons({ scale: 1.2 })
	],
	transformers: [transformerVariantGroup()],
	content: {
		pipeline: {
			include: [/\.(vue|svelte|[jt]sx|html)($|\?)/, '(components|src)/**/*.{js,ts}']
		}
	},
	theme: {
		fontFamily: {
			sans: ['IBM Plex Sans', 'ui-sans-serif', 'system-ui', 'sans-serif'],
			mono: ['JetBrains Mono', 'IBM Plex Mono', 'ui-monospace', 'monospace'],
			display: ['JetBrains Mono', 'IBM Plex Mono', 'ui-monospace', 'monospace']
		},
		colors: {
			// Control Room palette
			'cr-bg': '#0a0a0b',
			'cr-surface': '#141416',
			'cr-border': '#27272a',
			'cr-accent': '#22d3ee',
			'cr-text': '#fafafa',
			'cr-text-muted': '#a1a1aa',
			// Status colors
			'cr-active': '#10b981',
			'cr-pending': '#f59e0b',
			'cr-disabled': '#f43f5e'
		}
	}
});
