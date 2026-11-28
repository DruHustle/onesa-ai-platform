const path = require('node:path');
const { getDefaultConfig } = require('expo/metro-config');
const config = getDefaultConfig(__dirname);
// The streaming parser is this repository's reviewed, versioned source.
// No sibling repository or network contract participates in native bundles.
config.watchFolders = [path.resolve(__dirname, '../../packages/api-client')];
module.exports = config;
