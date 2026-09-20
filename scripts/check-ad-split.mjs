import assert from 'node:assert/strict';
import { splitAddonContent } from '../src/lib/addon-ad.js';

const paragraph = 'Readable text with useful details. '.repeat(55);
const long = `${paragraph}\n\n## Compatibility\n\n${paragraph}`;
assert.equal(splitAddonContent('Short description.').length, 1);
const parts = splitAddonContent(long);
assert.equal(parts.length, 2);
assert.equal(parts.join(''), long);
assert.equal(splitAddonContent(long.replace('## Compatibility', '## Installation Steps')).length, 1);
assert.equal(splitAddonContent(long.replace('## Compatibility', '### Compatibility')).length, 1);
assert.equal(splitAddonContent(`${paragraph}\n\n~~~\n## Compatibility\n~~~\n\n${paragraph}`).length, 1);
const withList = `${paragraph}\n\n- Complete feature one\n- Complete feature two\n\n## Compatibility\n\n${paragraph}`;
assert.equal(splitAddonContent(withList).length, 2);
assert.equal(splitAddonContent(withList).join(''), withList);
console.log('Ad split checks passed: short content, section boundaries, steps, code, and content preservation.');
