#!/usr/bin/env node
const path = require('path');
const webpack = require('webpack');

const args = process.argv.slice(2);
const isWatch = args.includes('--watch');

const configPath = path.resolve(__dirname, '..', 'webpack.config.js');
let config = require(configPath);
if (typeof config === 'function') {
  config = config({});
}

const compiler = webpack(config);

const logStats = (stats) => {
  const statsString = stats.toString({
    colors: process.stdout.isTTY,
    modules: false,
    children: false,
    chunks: false,
    chunkModules: false,
  });

  if (statsString) {
    console.log(statsString);
  }
};

const handleResult = (err, stats, done) => {
  if (err) {
    console.error('Webpack encountered a fatal error:', err);
    process.exitCode = 1;
    if (done) done();
    return;
  }

  logStats(stats);

  if (stats.hasErrors()) {
    const info = stats.toJson();
    info.errors.forEach((error) => {
      console.error(error.message || error);
      if (error.stack) {
        console.error(error.stack);
      }
    });
    process.exitCode = 1;
  }

  if (stats.hasWarnings()) {
    const info = stats.toJson();
    info.warnings.forEach((warning) => {
      console.warn(warning.message || warning);
    });
  }

  if (done) done();
};

if (isWatch) {
  console.log('Starting webpack in watch mode...');
  compiler.watch({}, (err, stats) => handleResult(err, stats));
} else {
  compiler.run((err, stats) => {
    handleResult(err, stats, () => {
      compiler.close((closeErr) => {
        if (closeErr) {
          console.error('Failed to close webpack compiler cleanly:', closeErr);
          process.exitCode = 1;
        }
        if (process.exitCode && process.exitCode !== 0) {
          process.exit(process.exitCode);
        }
      });
    });
  });
}
