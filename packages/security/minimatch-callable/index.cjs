'use strict';

// serve-handler and @ts-morph/common call the old CommonJS default export.
// Keep their call shape while executing only the fixed upstream implementation.
module.exports = require('minimatch-fixed').minimatch;
