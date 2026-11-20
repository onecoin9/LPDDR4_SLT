// Legacy command name; the fixed-unit migration supersedes the unit selector.
require('node:child_process').execFileSync(process.execPath,
  [require('node:path').join(__dirname, 'test-timing-migration.mjs')], { stdio: 'inherit' })
