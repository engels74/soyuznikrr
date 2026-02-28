/**
 * Property-based tests for markdown XSS sanitization.
 *
 * Tests the following property:
 * - Property 13: Markdown XSS Sanitization
 *
 * @module $lib/components/wizard/__tests__/sanitization.property.test
 */

import DOMPurify from 'dompurify';
import * as fc from 'fast-check';
import { JSDOM } from 'jsdom';
import { marked } from 'marked';
import { describe, expect, it } from 'vitest';

// Initialize DOMPurify with JSDOM for Node.js environment
const window = new JSDOM('').window;
const purify = DOMPurify(window);

/**
 * Sanitize markdown content using the same configuration as wizard-shell.
 */
function sanitizeMarkdown(markdown: string): string {
	const rawHtml = marked.parse(markdown, { async: false }) as string;
	return purify.sanitize(rawHtml, {
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
}

/**
 * Check if HTML contains potentially malicious content.
 */
function containsXSSVectors(html: string): boolean {
	// Check for script tags
	if (/<script[\s>]/i.test(html)) return true;

	// Check for event handlers
	if (/\bon\w+\s*=/i.test(html)) return true;

	// Check for javascript: URLs
	if (/javascript:/i.test(html)) return true;

	// Check for data: URLs (can be used for XSS)
	if (/data:\s*text\/html/i.test(html)) return true;

	// Check for vbscript: URLs
	if (/vbscript:/i.test(html)) return true;

	// Check for iframe, object, embed tags
	if (/<(iframe|object|embed|form|input|button)[\s>]/i.test(html)) return true;

	// Check for style tags (can be used for CSS injection)
	if (/<style[\s>]/i.test(html)) return true;

	// Check for SVG with scripts
	if (/<svg[\s>].*<script/i.test(html)) return true;

	return false;
}

// =============================================================================
// Property 13: Markdown XSS Sanitization
// =============================================================================

describe('Property 13: Markdown XSS Sanitization', () => {
	/**
	 * For any markdown content containing script tags, the sanitized output
	 * SHALL NOT contain any script tags.
	 */
	it('should remove script tags from markdown content', () => {
		fc.assert(
			fc.property(
				fc.oneof(
					// Inline script
					fc.constant('<script>alert("xss")</script>'),
					// Script with attributes
					fc.constant('<script type="text/javascript">alert("xss")</script>'),
					// Script with src
					fc.constant('<script src="https://evil.com/xss.js"></script>'),
					// Script in markdown code block (should be escaped)
					fc.constant('```\n<script>alert("xss")</script>\n```'),
					// Mixed content
					fc
						.tuple(fc.string(), fc.string())
						.map(([before, after]) => `${before}<script>alert("xss")</script>${after}`)
				),
				(maliciousMarkdown) => {
					const sanitized = sanitizeMarkdown(maliciousMarkdown);
					expect(sanitized).not.toMatch(/<script[\s>]/i);
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any markdown content containing event handlers (onclick, onerror, etc.),
	 * the sanitized output SHALL NOT contain any executable event handlers.
	 *
	 * Note: If malicious content is escaped as text (not rendered as HTML),
	 * it is considered safe because it won't execute.
	 */
	it('should remove event handlers from HTML in markdown content', () => {
		fc.assert(
			fc.property(
				fc.oneof(
					// onclick in raw HTML
					fc.constant('<div onclick="alert(\'xss\')">Click me</div>'),
					// onerror in raw HTML
					fc.constant('<img src="x" onerror="alert(\'xss\')">'),
					// onload in raw HTML
					fc.constant('<body onload="alert(\'xss\')">'),
					// onmouseover in raw HTML
					fc.constant('<a href="#" onmouseover="alert(\'xss\')">Hover</a>'),
					// onfocus in raw HTML
					fc.constant('<input onfocus="alert(\'xss\')" autofocus>')
				),
				(maliciousMarkdown) => {
					const sanitized = sanitizeMarkdown(maliciousMarkdown);
					// Parse the output to check for actual HTML attributes
					const dom = new JSDOM(sanitized);
					const elements = dom.window.document.querySelectorAll('*');
					for (const el of elements) {
						// Check that no element has event handler attributes
						for (const attr of el.getAttributeNames()) {
							expect(attr.toLowerCase().startsWith('on')).toBe(false);
						}
					}
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any markdown content containing javascript: URLs, the sanitized output
	 * SHALL NOT contain any javascript: URLs.
	 */
	it('should remove javascript: URLs from markdown content', () => {
		fc.assert(
			fc.property(
				fc.oneof(
					// Direct javascript URL
					fc.constant('<a href="javascript:alert(\'xss\')">Click</a>'),
					// Markdown link with javascript
					fc.constant('[Click me](javascript:alert("xss"))'),
					// Case variations
					fc.constant('<a href="JAVASCRIPT:alert(\'xss\')">Click</a>'),
					fc.constant('<a href="JaVaScRiPt:alert(\'xss\')">Click</a>'),
					// With whitespace
					fc.constant('<a href="  javascript:alert(\'xss\')">Click</a>'),
					// URL encoded
					fc.constant('<a href="&#106;avascript:alert(\'xss\')">Click</a>')
				),
				(maliciousMarkdown) => {
					const sanitized = sanitizeMarkdown(maliciousMarkdown);
					expect(sanitized).not.toMatch(/javascript:/i);
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any markdown content containing iframe, object, or embed tags,
	 * the sanitized output SHALL NOT contain these tags.
	 */
	it('should remove iframe, object, and embed tags from markdown content', () => {
		fc.assert(
			fc.property(
				fc.oneof(
					// iframe
					fc.constant('<iframe src="https://evil.com"></iframe>'),
					// object
					fc.constant('<object data="https://evil.com/flash.swf"></object>'),
					// embed
					fc.constant('<embed src="https://evil.com/flash.swf">'),
					// form (can be used for phishing)
					fc.constant('<form action="https://evil.com"><input></form>')
				),
				(maliciousMarkdown) => {
					const sanitized = sanitizeMarkdown(maliciousMarkdown);
					expect(sanitized).not.toMatch(/<(iframe|object|embed|form)[\s>]/i);
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any markdown content containing style tags or inline styles with
	 * expressions, the sanitized output SHALL NOT contain these.
	 */
	it('should remove style tags from markdown content', () => {
		fc.assert(
			fc.property(
				fc.oneof(
					// Style tag
					fc.constant('<style>body { background: url("javascript:alert(\'xss\')") }</style>'),
					// Style with expression (IE)
					fc.constant('<div style="width: expression(alert(\'xss\'))">'),
					// Style with behavior (IE)
					fc.constant('<div style="behavior: url(xss.htc)">')
				),
				(maliciousMarkdown) => {
					const sanitized = sanitizeMarkdown(maliciousMarkdown);
					expect(sanitized).not.toMatch(/<style[\s>]/i);
					expect(sanitized).not.toMatch(/expression\s*\(/i);
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any valid markdown content (headings, paragraphs, lists, links, code),
	 * the sanitized output SHALL preserve the semantic structure.
	 */
	it('should preserve valid markdown structure', () => {
		fc.assert(
			fc.property(
				fc.oneof(
					// Headings
					fc.constant('# Heading 1'),
					fc.constant('## Heading 2'),
					// Paragraphs
					fc.constant('This is a paragraph.'),
					// Bold and italic
					fc.constant('**bold** and *italic*'),
					// Lists
					fc.constant('- Item 1\n- Item 2'),
					fc.constant('1. First\n2. Second'),
					// Links (safe)
					fc.constant('[Link](https://example.com)'),
					// Code
					fc.constant('`inline code`'),
					fc.constant('```\ncode block\n```'),
					// Blockquote
					fc.constant('> Quote')
				),
				(validMarkdown) => {
					const sanitized = sanitizeMarkdown(validMarkdown);
					// Should not be empty (content preserved)
					expect(sanitized.trim().length).toBeGreaterThan(0);
					// Should not contain XSS vectors
					expect(containsXSSVectors(sanitized)).toBe(false);
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any arbitrary string input, the sanitized output SHALL NOT contain
	 * any XSS vectors.
	 */
	it('should never produce output with XSS vectors for arbitrary input', () => {
		fc.assert(
			fc.property(fc.string({ minLength: 0, maxLength: 1000 }), (arbitraryInput) => {
				const sanitized = sanitizeMarkdown(arbitraryInput);
				expect(containsXSSVectors(sanitized)).toBe(false);
			}),
			{ numRuns: 200 }
		);
	});

	/**
	 * For any combination of valid markdown and XSS payloads, the sanitized
	 * output SHALL preserve valid content while removing malicious content.
	 */
	it('should handle mixed valid and malicious content', () => {
		fc.assert(
			fc.property(
				fc.tuple(
					fc.constantFrom(
						'# Welcome',
						'## Introduction',
						'This is **important**.',
						'- List item',
						'[Safe link](https://example.com)'
					),
					fc.constantFrom(
						'<script>alert("xss")</script>',
						'<img src="x" onerror="alert(\'xss\')">',
						'<a href="javascript:alert(\'xss\')">Click</a>',
						'<iframe src="https://evil.com"></iframe>'
					)
				),
				([validContent, maliciousContent]) => {
					const mixed = `${validContent}\n\n${maliciousContent}`;
					const sanitized = sanitizeMarkdown(mixed);

					// Should not contain XSS vectors
					expect(containsXSSVectors(sanitized)).toBe(false);

					// Should still have some content (valid part preserved)
					expect(sanitized.trim().length).toBeGreaterThan(0);
				}
			),
			{ numRuns: 100 }
		);
	});
});
