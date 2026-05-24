import * as esbuild from 'esbuild';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const srcDir = join(__dirname, 'src');
const outDir = join(__dirname, '..', 'js');

const entries = [
  { in: 'store.ts',        out: 'main.js' },
  { in: 'monitor.ts',      out: 'monitor.js' },
  { in: 'mosaic.ts',       out: 'mosaic.js' },
  { in: 'trial-viewer.ts', out: 'trial-viewer.js' },
];

const vendorDir = join(__dirname, '..', 'vendored');

const isWatch = process.argv.includes('--watch');

const cmBundleOptions = {
  entryPoints: [join(srcDir, 'cm-bundle.ts')],
  outfile: join(vendorDir, 'codemirror.bundle.js'),
  bundle: true,
  minify: true,
  target: 'es2020',
  format: /** @type {'iife'} */ ('iife'),
  globalName: 'CM',
  platform: 'browser',
};

if (isWatch) {
  const contexts = await Promise.all([
    ...entries.map(({ in: inFile, out: outFile }) =>
      esbuild.context({
        entryPoints: [join(srcDir, inFile)],
        outfile: join(outDir, outFile),
        bundle: true,
        sourcemap: true,
        target: 'es2020',
        format: 'iife',
        platform: 'browser',
      }),
    ),
    esbuild.context(cmBundleOptions),
  ]);
  await Promise.all(contexts.map((ctx) => ctx.watch()));
  console.log('Watching for changes...');
} else {
  await Promise.all([
    ...entries.map(async ({ in: inFile, out: outFile }) => {
      await esbuild.build({
        entryPoints: [join(srcDir, inFile)],
        outfile: join(outDir, outFile),
        bundle: true,
        sourcemap: true,
        target: 'es2020',
        format: 'iife',
        platform: 'browser',
      });
      console.log(`✓ src/${inFile} → js/${outFile}`);
    }),
    esbuild.build(cmBundleOptions).then(() => {
      console.log('✓ src/cm-bundle.ts → vendored/codemirror.bundle.js');
    }),
  ]);
}
