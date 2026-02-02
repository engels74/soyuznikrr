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
	}
});
