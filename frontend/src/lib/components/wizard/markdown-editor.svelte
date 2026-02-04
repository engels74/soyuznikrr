<script lang="ts">
/**
 * Markdown Editor Component
 *
 * Implements textarea with markdown input and live preview with sanitized HTML.
 *
 * Requirements: 13.4, 15.4
 *
 * @module $lib/components/wizard/markdown-editor
 */

import DOMPurify from 'dompurify';
import { marked } from 'marked';

interface Props {
	value: string;
	placeholder?: string;
	rows?: number;
}

let { value = $bindable(''), placeholder = 'Enter markdown content...', rows = 8 }: Props = $props();

// Tab state for switching between edit and preview
let activeTab = $state<'edit' | 'preview'>('edit');

// Render markdown with sanitization
const renderedHtml = $derived.by(() => {
	if (!value) return '<p class="empty-preview">Preview will appear here...</p>';
	const rawHtml = marked.parse(value, { async: false }) as string;
	return DOMPurify.sanitize(rawHtml, {
		ALLOWED_TAGS: [
			'h1',
			'h2',
			'h3',
			'h4',
			'h5',
			'h6',
			'p',
			'br',
			'strong',
			'em',
			'u',
			'a',
			'ul',
			'ol',
			'li',
			'blockquote',
			'code',
			'pre'
		],
		ALLOWED_ATTR: ['href', 'target', 'rel']
	});
});
</script>

<div class="markdown-editor">
	<!-- Tab buttons -->
	<div class="tabs">
		<button
			type="button"
			class="tab"
			class:active={activeTab === 'edit'}
			onclick={() => (activeTab = 'edit')}
		>
			Edit
		</button>
		<button
			type="button"
			class="tab"
			class:active={activeTab === 'preview'}
			onclick={() => (activeTab = 'preview')}
		>
			Preview
		</button>
	</div>

	<!-- Content area -->
	<div class="content">
		{#if activeTab === 'edit'}
			<textarea
				bind:value
				{placeholder}
				{rows}
				class="editor-textarea"
				spellcheck="true"
			></textarea>
			<div class="help-text">
				Supports Markdown: **bold**, *italic*, [links](url), # headings, - lists
			</div>
		{:else}
			<div class="preview prose prose-invert">
				{@html renderedHtml}
			</div>
		{/if}
	</div>
</div>

<style>
	.markdown-editor {
		display: flex;
		flex-direction: column;
		border: 1px solid var(--cr-border);
		border-radius: 0.5rem;
		overflow: hidden;
		background: var(--cr-bg);
	}

	/* Tabs */
	.tabs {
		display: flex;
		border-bottom: 1px solid var(--cr-border);
		background: var(--cr-surface);
	}

	.tab {
		flex: 1;
		padding: 0.625rem 1rem;
		font-size: 0.875rem;
		font-weight: 500;
		color: var(--cr-text-muted);
		background: transparent;
		border: none;
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.tab:hover {
		color: var(--cr-text);
		background: hsl(220 15% 12%);
	}

	.tab.active {
		color: var(--cr-accent);
		background: var(--cr-bg);
		box-shadow: inset 0 -2px 0 var(--cr-accent);
	}

	/* Content area */
	.content {
		min-height: 200px;
	}

	/* Editor textarea */
	.editor-textarea {
		width: 100%;
		min-height: 200px;
		padding: 1rem;
		font-family: 'JetBrains Mono', 'Fira Code', monospace;
		font-size: 0.875rem;
		line-height: 1.6;
		color: var(--cr-text);
		background: transparent;
		border: none;
		resize: vertical;
		outline: none;
	}

	.editor-textarea::placeholder {
		color: var(--cr-text-muted);
	}

	.help-text {
		padding: 0.5rem 1rem;
		font-size: 0.75rem;
		color: var(--cr-text-muted);
		background: var(--cr-surface);
		border-top: 1px solid var(--cr-border);
	}

	/* Preview area */
	.preview {
		padding: 1rem;
		min-height: 200px;
		font-size: 0.9375rem;
		line-height: 1.7;
		color: var(--cr-text-muted);
	}

	.preview :global(.empty-preview) {
		color: var(--cr-text-muted);
		font-style: italic;
	}

	/* Prose styles for preview */
	.preview :global(h1),
	.preview :global(h2),
	.preview :global(h3),
	.preview :global(h4),
	.preview :global(h5),
	.preview :global(h6) {
		color: var(--cr-text);
		font-weight: 600;
		margin-top: 1.5em;
		margin-bottom: 0.5em;
	}

	.preview :global(h1) {
		font-size: 1.5rem;
	}

	.preview :global(h2) {
		font-size: 1.25rem;
	}

	.preview :global(h3) {
		font-size: 1.125rem;
	}

	.preview :global(p) {
		margin-bottom: 1em;
	}

	.preview :global(a) {
		color: var(--cr-accent);
		text-decoration: underline;
		text-underline-offset: 2px;
	}

	.preview :global(a:hover) {
		opacity: 0.8;
	}

	.preview :global(strong) {
		color: var(--cr-text);
		font-weight: 600;
	}

	.preview :global(em) {
		font-style: italic;
	}

	.preview :global(ul),
	.preview :global(ol) {
		margin-bottom: 1em;
		padding-left: 1.5em;
	}

	.preview :global(li) {
		margin-bottom: 0.25em;
	}

	.preview :global(blockquote) {
		margin: 1em 0;
		padding-left: 1em;
		border-left: 3px solid var(--cr-accent);
		color: var(--cr-text-muted);
		font-style: italic;
	}

	.preview :global(code) {
		font-family: 'JetBrains Mono', 'Fira Code', monospace;
		font-size: 0.875em;
		padding: 0.125rem 0.375rem;
		background: hsl(220 15% 12%);
		border-radius: 0.25rem;
	}

	.preview :global(pre) {
		margin: 1em 0;
		padding: 1rem;
		background: hsl(220 15% 10%);
		border-radius: 0.5rem;
		overflow-x: auto;
	}

	.preview :global(pre code) {
		padding: 0;
		background: transparent;
	}
</style>
