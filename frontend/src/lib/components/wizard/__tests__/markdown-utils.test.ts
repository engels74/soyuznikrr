import { JSDOM } from 'jsdom';
import { describe, expect, it } from 'vitest';
import { renderMarkdown } from '../markdown-utils';

/** Parse rendered HTML and return all anchor elements. */
function getAnchors(html: string): Element[] {
	const dom = new JSDOM(html);
	return [...dom.window.document.querySelectorAll('a')];
}

describe('renderMarkdown', () => {
	describe('links open in new tabs', () => {
		it('should add target="_blank" and rel="noopener noreferrer" to markdown links', () => {
			const html = renderMarkdown('[Example](https://example.com)');
			const anchors = getAnchors(html);

			expect(anchors).toHaveLength(1);
			const anchor = anchors[0]!;
			expect(anchor.getAttribute('target')).toBe('_blank');
			expect(anchor.getAttribute('rel')).toBe('noopener noreferrer');
			expect(anchor.getAttribute('href')).toBe('https://example.com');
			expect(anchor.textContent).toBe('Example');
		});

		it('should add target="_blank" to links with titles', () => {
			const html = renderMarkdown('[Example](https://example.com "A title")');
			const anchors = getAnchors(html);

			expect(anchors).toHaveLength(1);
			const anchor = anchors[0]!;
			expect(anchor.getAttribute('target')).toBe('_blank');
			expect(anchor.getAttribute('rel')).toBe('noopener noreferrer');
			expect(anchor.getAttribute('href')).toBe('https://example.com');
		});

		it('should add target="_blank" to multiple links', () => {
			const html = renderMarkdown('[One](https://one.com) and [Two](https://two.com)');
			const anchors = getAnchors(html);

			expect(anchors).toHaveLength(2);
			for (const a of anchors) {
				expect(a.getAttribute('target')).toBe('_blank');
				expect(a.getAttribute('rel')).toBe('noopener noreferrer');
			}
		});

		it('should handle links with inline formatting in text', () => {
			const html = renderMarkdown('[**Bold link**](https://example.com)');
			const anchors = getAnchors(html);

			expect(anchors).toHaveLength(1);
			const anchor = anchors[0]!;
			expect(anchor.getAttribute('target')).toBe('_blank');
			expect(anchor.getAttribute('rel')).toBe('noopener noreferrer');
		});
	});
});
